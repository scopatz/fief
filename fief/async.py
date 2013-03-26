import threading
import multiprocessing
import types
from collections import deque
import sys
import weakref

default_pool_size = multiprocessing.cpu_count()

class Pool(object):
  __slots__ = ('name','size')
  def __init__(me, name, size=default_pool_size):
    me.name = name
    me.size = size

def pool_name(pool):
  return None if pool is None else pool.name

def pool_size(pool):
  return default_pool_size if pool is None else pool.size

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
  return None if type(lam) is not Pinned else lam._pool

class _Return(object):
  pass

class Result(_Return):
  __slots__ = ('_val',)
  def __init__(me, val):
    me._val = val
  def __call__(me):
    return me._val

class Raise(_Return):
  __slots__ = ('_ex','_tb')
  def __init__(me, ex, tb):
    me._ex = ex
    me._tb = tb
  def __call__(me):
    raise type(me._ex), me._ex, me._tb

class _Yield(object):
  pass

class Begin(_Yield):
  __slots__ = ('_task',)
  def __init__(me, task):
    me._task = task

class WaitAny(_Yield):
  __slots__ = ('_futs',)
  def __init__(me, futs):
    assert len(futs) > 0
    me._futs = futs

class Sync(_Yield):
  __slots__ = ('_task',)
  def __init__(me, task):
    me._task = task

class _Future(object):
  def __init__(me):
    me._wait_sts = set() # set of waiting ItStat's
    me._ret = None # _Return
  
  def done(me):
    return me._ret is not None
  
  def result(me):
    assert me._ret is not None
    return me._ret()

  def _finish(me, ret):
    assert isinstance(ret, _Return)
    assert me._ret is None
    me._ret = ret
    for st in me._wait_sts:
      for fut in st.wait_futs:
        if fut is not me:
          fut._wait_sts.discard(st)
      st.wake(me)

class Future(_Future):
  def __init__(me):
    super(Future, me).__init__()
  
  def finish(me, value=None):
    me._finish(Result(value))

class Lock(object):
  def __init__(me):
    me._futs = None # if not-none then lock is taken
  
  def acquire(me):
    fut = Future()
    if me._futs is None:
      me._futs = deque()
      fut.finish()
    else:
      me._futs.append(fut)
    return fut
  
  def release(me):
    if len(me._futs) > 0:
      me._futs.popleft().finish()
    else:
      me._futs = None

class Barrier(object):
  def __init__(me):
    me._futs = deque()
  
  def enlist(me):
    fut = Future()
    me._futs.append(fut)
    return fut
  
  def fireone(me):
    if len(me._futs) > 0:
      me._futs.popleft().finish()
  
  def fireall(me):
    for fut in me._futs:
      fut.finish()
    me._futs.clear()

class _Frame(object):
  def __init__(me, seed):
    me._acc = seed
  def aggregate(me):
    return me._acc

class Signal(object):
  def __init__(me, seed=None, fold=lambda a,b: b):
    me._seed = seed
    me._fold = fold
    me._frames = weakref.WeakKeyDictionary()
    me._frame_reuse = None
  
  def begin_frame(me):
    if me._frame_reuse is None:
      frame = _Frame(me._seed)
      me._frame_reuse = frame
      me._frames[frame] = None
    return me._frame_reuse
  
  def pulse(me, x):
    me._frame_reuse = None
    for frame in me._frames:
      frame._acc = me._fold(frame._acc, x)

def run(a):
  lock = threading.Lock()
  cv_done = threading.Condition(lock)
  pool_num = {} # {pool.name: int} -- number of spawned threads in pool
  pool_idle = {} # {pool.name: int} -- number of idle threads in pool
  pool_cv = {} # {pool.name: Condition}
  pool_jobs = {} # {pool.name: deque(callable)}
  wake_list = deque() # deque(ItStat) -- queue of iters to wake, no duplicates
  wake_set = set() # set(ItStat) -- set of iters to wake, matches wake_list
  class closure:
    jobs_notdone = 0
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
    
    closure.jobs_notdone += 1
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
        closure.jobs_notdone -= 1
        fut._finish(ret)
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
  
  class ItStat(object):
    __slots__ = (
      'par_fut', # _Future -- parent future
      'it', # iterator routine
      'wait_futs', # tuple(_Future) -- futures this suspended iterator is waiting on
      'wake_meth', # lambda ItStat: _Yield -- how to awaken suspended iterator
      'wake_fut', # future with which to wake iterator
    )
    
    def __init__(me, par_fut, it):
      assert isinstance(par_fut, _Future)
      me.par_fut = par_fut
      me.it = it
      me.wait_futs = None
      me.wake_meth = None
      me.wake_fut = None
    
    def wake(me, fut):
      me.wait_futs = None
      if me not in wake_set:
        wake_list.append(me)
        wake_set.add(me)
        me.wake_fut = fut
  
  send_none = lambda st: st.it.send(None)
  send_fut = lambda st: st.it.send(st.wake_fut)
  def send_sync(st):
    ret = st.wake_fut._ret
    if type(ret) is Result:
      return st.it.send(ret._val)
    elif type(ret) is Raise:
      return st.it.throw(type(ret._ex), ret._ex, ret._tb)
    else:
      assert False
  
  def begin(task):
    fut = _Future()
    if isinstance(task, types.GeneratorType):
      st = ItStat(fut, task.__iter__())
      wake_list.appendleft(st)
      wake_set.add(st)
      st.wake_meth = send_none
    elif callable(task):
      pool = pinned_pool(task)
      post_job(pool, fut, task)
    else:
      assert False
    return fut
  
  def awaken():
    while len(wake_list) > 0:
      st = wake_list.popleft()
      wake_set.discard(st)
      try:
        got = st.wake_meth(st)
      except StopIteration:
        got = Result(None)
      except Exception, ex:
        ex.async_future = st.par_fut
        got = Raise(ex, sys.exc_traceback)
      
      if isinstance(got, _Return):
        st.par_fut._finish(got)
      elif isinstance(got, Begin):
        fut = begin(got._task)
        assert st not in wake_set
        wake_list.append(st)
        wake_set.add(st)
        st.wake_fut = fut
        st.wake_meth = send_fut
      elif isinstance(got, WaitAny):
        assert st.wait_futs is None
        for fut in got._futs: # test if any futures are already done, no need to sleep
          if fut._ret is not None: # done
            assert st not in wake_set
            wake_list.appendleft(st)
            wake_set.add(st)
            st.wake_fut = fut
            st.wake_meth = send_fut
            break
        if st not in wake_set: # none were already done, suspend st
          st.wait_futs = tuple(got._futs)
          for fut in st.wait_futs:
            fut._wait_sts.add(st)
      elif isinstance(got, Sync):
        fut = begin(got._task)
        assert fut._ret is None
        assert st.wait_futs is None
        st.wait_futs = (fut,)
        fut._wait_sts.add(st)
        st.wake_meth = send_sync
      else:
        assert False
    
    if closure.jobs_notdone == 0:
      closure.quitting = True
      for cv in pool_cv.itervalues():
        cv.notify_all()
  
  lock.acquire()
  top = begin(a)
  awaken()
  if not closure.quitting:
    cv_done.wait()
  lock.release()
  return top.result()

if False: # test code
  import urllib2
  import time
  def main_a():
    def get(url):
      print '> ' + url
      f = urllib2.urlopen(url)
      s = f.read(100)
      time.sleep(1)
      print '< ' + url
      return s
    urls = ['http://www.google.com','http://www.yahoo.com','http://www.microsoft.com']
    fut = {}
    for u in urls:
      fut[u] = yield Begin((lambda u: lambda: get(u))(u))
    for u in urls:
      f = yield WaitAny([fut[u]])
      print 'url: ' + u
    print 'done'
  def b():
    for i in range(2):
      try:
        yield Sync(main_a())
      except Exception, e:
        print 'caught ', e
  run(b())
