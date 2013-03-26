import threading
import multiprocessing
import types
from collections import deque
import sys

default_pool_size = multiprocessing.cpu_count()

class Pool(object):
  def __init__(me, name, size=default_pool_size):
    me.name = name
    me.size = size

def pool_name(pool):
  if pool is None:
    return None
  else:
    return pool.name

def pool_size(pool):
  if pool is None:
    return default_pool_size
  else:
    return pool.size

class Pinned(object):
  """a callable that is pinned to run on a named thread"""
  def __init__(me, lam, pool):
    me._lam = lam
    me._pool = pool
  def __call__(me, *a, **kw):
    return me._lam(*a, **kw)

def pinned(pool):
  return lambda lam: Pinned(lam, pool)

def pinned_pool(lam):
  if type(lam) is Pinned:
    return lam._pool
  else:
    return None

class _Return(object):
  pass

class Result(_Return):
  def __init__(me, val):
    me._val = val
  def __call__(me):
    return me._val

class Raise(_Return):
  def __init__(me, ex, tb):
    me._ex = ex
    me._tb = tb
  def __call__(me):
    raise type(me._ex), me._ex, me._tb

class _Yield(object):
  pass

class Begin(_Yield):
  def __init__(me, task):
    me._task = task

class WaitAny(_Yield):
  def __init__(me, futs):
    assert len(futs) > 0
    me._futs = futs

class _Future(object):
  def __init__(me):
    me._wait_sts = set() # set of ItStat waiting on this future
    me._ret = None # _Return
  def done(me):
    return me._ret is not None
  def result(me):
    assert me._ret is not None
    return me._ret()

class _ItStat(object):
  def __init__(me, parfut, it):
    assert isinstance(parfut, Future)
    me.parfut = parfut
    me.it = it
    me.wait_futs = set() # set of futures

def run(a):
  lock = threading.Lock()
  cv_done = threading.Condition(lock)
  pool_num = {} # {pool.name: int} - number of spawned threads in pool
  pool_idle = {} # {pool.name: int} - number of idle threads in pool
  pool_cv = {} # {pool.name: Condition}
  pool_jobs = {} # {pool.name: deque(callable)}
  wake_sts = deque() # deque(_ItStat): queue of iters to wake, no duplicates
  wake_meth = {} # {_ItStat: it->()}: set of iters to wake
  class closure:
    quitting = False
  
  def post_job(pool, fut, job):
    poo, size = pool_name(pool), pool_size(pool)
    
    if poo not in pool_jobs or (pool_idle[poo] == 0 and pool_num[poo] < size):
      if poo not in pool_jobs:
        pool_jobs[poo] = deque()
        pool_cv[poo] = threading.Condition(lock)
        pool_num[poo] = 0
        pool_idle[poo] = 0
      pool_num[poo] += 1
      threading.Thread(target=worker_proc, kwargs={'poo':poo}).start()
    
    if pool_idle[poo] > 0:
      pool_idle[poo] -= 1
    
    pool_jobs[poo].append((fut, job))
    pool_cv[poo].notify()
  
  def worker_proc(*args, **kwargs):
    poo = kwargs['poo']
    jobs = pool_jobs[poo]
    cv = pool_cv[poo]
    
    lock.acquire()
    while True:
      if len(jobs) > 0:
        fut, job = jobs.popleft()
        lock.release()
        try:
          ret = Result(job())
        except Exception, ex:
          ret = Raise(ex, sys.exc_traceback)
        lock.acquire()
        pool_idle[poo] += 1
        finish(fut, ret)
        awaken()
      elif closure.quitting:
        break
      else:
        cv.wait()
    
    pool_num[poo] -= 1
    if pool_num[poo] == 0:
      del pool_num[poo]
    if len(pool_num) == 0:
      cv_done.notify()
    lock.release()
  
  def finish(fut, ret):
    assert isinstance(fut, _Future)
    assert isinstance(ret, _Return)
    assert fut._ret is None
    fut._ret = ret
    if isinstance(ret, Result):
      meth = lambda it: it.send((fut, ret._val))
    else:
      meth = lambda it: it.throw(type(ret._ex), ret._ex, ret._tb)
    for st in fut.wait_sts:
      for fut1 in st.wait_futs:
        if fut1 is not fut:
          fut1.wait_sts.discard(st)
      st.wait_futs.clear()
      if st not in wake_meth:
        wake_sts.append(st)
        wake_meth[st] = meth
    fut.wait_sts.clear()
  
  def begin(task):
    fut = _Future()
    if isinstance(task, types.GeneratorType):
      st1 = _ItStat(fut, task)
      wake_sts.appendleft(st1)
      wake_meth[st1] = lambda it: it.send(None)
    elif callable(task):
      pool = pinned_pool(task)
      post_job(pool, fut, job)
    else:
      assert False
    return fut
  
  def awaken():
    while len(wake_sts) > 0:
      st = wake_sts.popleft()
      meth = wake_meth.pop(st)
      try:
        got = meth(st.it)
      except StopIteration:
        got = Result(None)
      except Exception, ex:
        ex.async_future = st.parfut
        got = Raise(ex, sys.exc_traceback)
      
      if isinstance(got, _Return):
        finish(st.parfut, got)
      elif isinstance(got, Begin):
        fut = begin(got._task)
        assert st not in wake_meth
        wake_sts.append(st)
        wake_meth[st] = (lambda fut: lambda it: it.send(fut1))(fut)
      elif isinstance(got, WaitAny):
        assert len(st.wait_futs) == 0
        for fut in got._futs: # test if any futures are already done, no need to sleep
          if fut._ret is not None: # done
            assert st not in wake_fut
            wake_sts.appendleft(st)
            wake_fut[st] = fut
            break
        if st not in wake_fut: # none were already done, put to sleep
          for fut in got._futs:
            st.wait_futs.add(fut)
            fut.wait_sts.add(st)
      else:
        assert False
    
    if all(len(jobs) == 0 for jobs in pool_jobs.itervalues()):
      closure.quitting = True
      for poo in pool_cv:
        pool_cv[poo].notify_all()
  
  lock.acquire()
  top = begin(a)
  awaken()
  if not closure.quitting:
    cv_done.wait()
  lock.release()
  
  return top._ret()

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
  __slots__ = ('it','par','key','rcvr','taskn','waitp','hold','par_actn')
  def __init__(me, it, par, rcvr, key):
    me.it = it
    me.par = par
    me.rcvr = rcvr
    me.key = key
    me.taskn = 0
    me.waitp = None
    me.hold = []
    me.par_actn = None
    
  def async_traceback(me):
    lines = []
    p = me
    while p is not None:
      if p.it is not None:
        file = p.it.gi_code.co_filename
        lineno = '?' if p.it.gi_frame is None else str(p.it.gi_frame.f_lineno)
        name = p.it.gi_code.co_name
        key = 'WaitFor' if p.key is WaitFor else p.key
        lines.append('  File "%s", line %s, in %s, task key %r' % (file, lineno, name, key))
      else:
        lines.append('  <abandoner>, task key %r' % p.key)
      p = p.par
    lines.append('Asynchronous traceback (most recent call last):')
    lines.reverse()
    return '\n'.join(lines)

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
      st.taskn -= 1
      if st.taskn == 0 and st.par_actn is not None:
        actns.append(st.par_actn)
        st.par_actn = None
      rcvr(None)
      return None # no action on iterator
    else:
      assert st.waitp is not None
      if st.waitp(key):
        st.waitp = None
        st.taskn -= 1
        if st.taskn == 0 and st.par_actn is not None:
          actns.append(st.par_actn)
          st.par_actn = None
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
    ex.async_key = key
    return it_advance(st, rcvr, key, (lambda it: it.throw(type(ex), ex, tb)))
  
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
      except Exception, ex:
        if not hasattr(ex, 'async_traceback'):
          ex.async_traceback = st.async_traceback()
        if hasattr(ex, 'async_key'):
          del ex.async_key
        item = ex
        item_tb = sys.exc_traceback
      
      if item is None:
        pass # no action on iterator
      elif isinstance(item, Result) or isinstance(item, Exception):
        closure.its_live -= 1
        st.it = None
        st.taskn -= len(st.hold)
        for rcvr,key,meth in st.hold:
          rcvr(None)
        if isinstance(item, Result):
          if st.par is None:
            closure.result = item.val
          else:
            st.par_actn = (actn_send, st.par, st.rcvr, st.key, item.val)
        else:
          if st.par is None:
            closure.result_ex = item
            closure.result_tb = item_tb
          else:
            st.par_actn = (actn_throw, st.par, st.rcvr, st.key, item, item_tb) 
        if st.taskn == 0 and st.par_actn is not None:
          actns.append(st.par_actn)
          st.par_actn = None
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
