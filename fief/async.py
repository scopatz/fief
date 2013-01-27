import threading
import multiprocessing
import types
from collections import deque
import sys
import bake

max_threads = multiprocessing.cpu_count()

class Yield(object):
  def __init__(me, tasks, waitp):
    # tasks: [(rcvr,key,work,aff)]
    object.__init__(me)
    me.tasks = tasks
    me.waitp = waitp

def Task(key, work, aff=None):
  return Yield((((lambda it:it), key, work, aff),), None)

WaitAny = Yield((), lambda key:True)

def WaitSome(key_pred):
  return Yield((), key_pred)

class _KeyStripper(object):
  def __init__(me, it):
    me.it = it
  def send(me, msg):
    key, val = msg
    return me.it.send(val)
  def throw(me, c, ex, tb):
    return me.it.throw(type(ex.ex), ex.ex, tb)

def WaitFor(work, aff=None):
  task = (_KeyStripper, WaitFor, work, aff)
  waitp = lambda key: key is WaitFor
  return Yield((task,), waitp)

class Barrier(object):
  class _Box(object):
    __slots__ = ('acc','refs')
  
  def __init__(me, seed=None, fold=lambda a,b: b):
    object.__init__(me)
    me._seed = seed
    me._fold = fold
    me._sleeps = []
    me._box = None
    me._boxs = set()
    me._send = None
  
  def _enlist(me, send, st, rcvr, key):
    assert me._send is None or me._send is send
    me._send = send
    box = me._box
    if box is None:
      box = Barrier._Box()
      box.acc = me._seed
      box.refs = 0
      me._box = box
      me._boxs.add(box)
    box.refs += 1
    me._sleeps.append((st,rcvr,key,box))
  
  def _wraprcvr(me, rcvr, box):
    class R(object):
      def __init__(me1, it):
        me1.it = it
        box.refs -= 1
        if box.refs == 0:
          me._boxs.discard(box)
      def send(me1, data):
        k = data[0]
        v = box.acc
        return rcvr(me1.it).send((k,v))
    return R
  
  def fireone(me, val=None):
    me._box = None
    for box in me._boxs:
      box.acc = me._fold(box.acc, val)
    if len(me._sleeps) > 0:
      st,rcvr,key,box = me._sleeps.pop()
      me._send(st, me._wraprcvr(rcvr, box), key, None)
  
  def fireall(me, val=None):
    me._box = None
    for box in me._boxs:
      box.acc = me._fold(box.acc, val)
    for st,rcvr,key,box in me._sleeps:
      me._send(st, me._wraprcvr(rcvr, box), key, None)
    del me._sleeps[:]

class Result(object):
  __slots__ = ("val",)
  def __init__(me, val):
    object.__init__(me)
    me.val = val

class TaskError(Exception):
  def __init__(me, key, ex, tb):
    Exception.__init__(me)
    me.key = key
    me.ex = ex
    me.traceback = tb
  def reraise(me):
    raise type(me.ex), me.ex, me.traceback

class Lock(object):
  def __init__(me):
    object.__init__(me)
    me._bar = Barrier(False, lambda a,b: a or b)
    me._taken = False
  
  def acquire_a(me):
    if me._taken:
      return me._acquire_a()
    else:
      me._taken = True
      return Result(False)
  
  def _acquire_a(me):
    signal = False
    while me._taken:
      s = yield WaitFor(me._bar)
      signal = signal or s
    me._taken = True
    yield Result(signal)
  
  def release(me, signal=False):
    me._taken = False
    me._bar.fireone(signal)

class _ItStat(object):
  __slots__ = ('it','par','key','rcvr','taskn','waitp','hold','done')
  def __init__(me, it, par, rcvr, key):
    me.it = it
    me.par = par
    me.rcvr = rcvr
    me.key = key
    me.taskn = 0
    me.waitp = None
    me.hold = []

def run(it):
  lock = threading.Lock()
  cv_done = threading.Condition(lock)
  aff_cv_jobs = {} # {aff:threading.Condition}
  aff_jobs = {} # {aff:deque()}
  
  class closure:
    its_live = 0
    noaff_idle = 0
    noaff_thds = 0
    thds = 0
    quitting = False
  
  actns = deque()
  
  def it_advance(st, rcvr, key, meth):
    if st.it is None:
      rcvr(None)
      return None # no action on iterator
    else:
      assert st.waitp is not None
      if st.waitp(key):
        st.taskn -= 1
        st.waitp = None
        return meth(rcvr(st.it))
      else:
        st.hold.append((rcvr, key, meth))
        return None
  
  def actn_next(st):
    assert st.it is not None
    assert st.waitp is None
    return st.it.next()
  
  def actn_send(st, rcvr, key, val):
    return it_advance(st, rcvr, key, (lambda it: it.send((key, val))))
  
  def actn_throw(st, rcvr, key, ex, tb):
    ex = TaskError(key, ex, tb)
    return it_advance(st, rcvr, key, (lambda it: it.throw(TaskError, ex, tb)))
  
  def bar_send(st, rcvr, key, val): # given to barriers
    actns.append((actn_send, st, rcvr, key, val))
  
  def progress():
    while len(actns) > 0:
      actn = actns.popleft()
      st = actn[1]
      try:
        item = actn[0](*actn[1:])
      except StopIteration:
        item = Result(None)
      except AssertionError:
        raise
      except Exception, ex:
        item = ex
        item_tb = sys.exc_traceback
      
      if item is None:
        pass # no action on iterator
      elif isinstance(item, Result) or isinstance(item, Exception):
        st.it = None
        closure.its_live -= 1
        for rcvr,key,meth in st.hold:
          rcvr(None)
        if isinstance(item, Result):
          if st.par is None:
            closure.result = item.val
          else:
            actns.append((actn_send, st.par, st.rcvr, st.key, item.val))
        else:
          if st.par is None:
            closure.result_ex = item
            closure.result_tb = item_tb
          else:
            actns.append((actn_throw, st.par, st.rcvr, st.key, item, item_tb))
      else:
        assert isinstance(item, Yield)
        assert st.it is not None
        assert st.waitp is None
        tasks, waitp = item.tasks, item.waitp
        
        st.taskn += len(tasks)
        for rcvr,key,work,aff in tasks:
          if isinstance(work, Result):
            assert aff is None
            actns.append((actn_send, st, rcvr, key, work.val))
          elif isinstance(work, types.GeneratorType):
            assert aff is None
            st1 = _ItStat(work.__iter__(), st, rcvr, key)
            closure.its_live += 1
            actns.append((actn_next, st1))
          elif isinstance(work, Barrier):
            assert aff is None
            work._enlist(bar_send, st, rcvr, key)
          else:
            if aff not in aff_jobs or (aff is None and closure.noaff_idle == 0 and closure.noaff_thds < max_threads):
              if aff not in aff_jobs:
                aff_jobs[aff] = deque()
                aff_cv_jobs[aff] = threading.Condition(lock)
              closure.thds += 1
              closure.noaff_thds += 1 if aff is None else 0
              thd = threading.Thread(target=worker_proc, kwargs={'aff':aff})
              thd.start()
            if aff is None and closure.noaff_idle > 0:
              closure.noaff_idle -= 1
            aff_jobs[aff].append((st, rcvr, key, work))
            aff_cv_jobs[aff].notify()
        
        if waitp is None:
          actns.appendleft((actn_next, st))
        elif st.taskn == 0:
          actns.appendleft((actn_next, st))
        else:
          st.waitp = waitp
          for i in xrange(len(st.hold)):
            rcvr,key,meth = st.hold[i]
            if waitp(key):
              del st.hold[i]
              st.waitp = None
              st.taskn -= 1
              actns.appendleft((lambda st,rcvr,meth: meth(rcvr(st.it))), st, rcvr, meth)
              break
    
    if closure.its_live == 0:
      closure.quitting = True
      for aff in aff_cv_jobs:
        aff_cv_jobs[aff].notifyAll()
  
  def worker_proc(*args,**kwargs):
    aff = kwargs['aff']
    jobs = aff_jobs[aff]
    cv_jobs = aff_cv_jobs[aff]
    n = 0
    lock.acquire()
    while True:
      if len(jobs) > 0:
        st,rcvr,key,work = jobs.popleft()
        lock.release()
        try:
          val = work()
          actn = (actn_send, st, rcvr, key, val)
        except Exception, ex:
          actn = (actn_throw, st, rcvr, key, ex, sys.exc_traceback)
        lock.acquire()
        closure.noaff_idle += 1 if aff is None else 0
        actns.append(actn)
        progress()
      elif closure.quitting:
        break
      else:
        n += 1
        cv_jobs.wait()
    closure.noaff_thds -= 1 if aff is None else 0
    closure.thds -= 1
    if closure.thds == 0:
      cv_done.notify()
    lock.release()
  
  st = _ItStat(it.__iter__(), None, (lambda it:it), None)
  closure.its_live += 1
  
  lock.acquire()
  actns.append((actn_next, st))
  progress()
  if not closure.quitting:
    cv_done.wait()
  lock.release()
  
  if hasattr(closure, 'result_ex'):
    raise type(closure.result_ex), closure.result_ex, closure.result_tb 
  else:
    return closure.result
