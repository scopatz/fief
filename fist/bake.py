import async
import array
import binascii
import hashlib
import os
import sqlite3
import struct
import subprocess
import sys
import types
import valtool

_bin2hex = binascii.hexlify
_hex2bin = binascii.unhexlify

def _assert_insts(*pairs):
  for x,y in pairs:
    if not isinstance(x, y):
      print 'x:', x, ', y:', y
      assert False
    
def _ensure_dirs(path):
  d = os.path.split(path)[0]
  if not os.path.exists(d):
    os.makedirs(d)

def _sql_ensure_table(cxn, name, cols, ixs=()):
  cur = cxn.cursor()
  cur.execute("select name from sqlite_master where type='table' and name=?", (name,))
  if cur.fetchone() is None:
    cur.execute("create table " + name + "(" + ",".join(cols) + ")")
    i = 0
    for ix in ixs:
      cur.execute("create index " + ("%s__index_%d"%(name,i)) + " on " + name + "(" + ",".join(ix) + ")")
      i += 1

def _flatten(x):
  if getattr(x, "__iter__", False):
    for it in x:
      for y in _flatten(it):
        yield y
  else:
    yield x

class Cmd(object):
  def __init__(me, ctx):
    object.__init__(me)
    me._ctx = ctx
    me._toks = []
    me._oxs = {}
    me.cwd = None
    me.showout = False
    me.showerr = True
  
  def lit(me, *toks):
    me._toks += _flatten(toks)
    return me
  
  def inf(me, path, fmt="%s"):
    path = os.path.normpath(path)
    me._ctx.input(path)
    me._toks.append(fmt % path)
    return me
  
  def infs(me, paths, fmt="%s"):
    for p in paths:
      me.inf(p, fmt)
    return me
  
  def outf(me, path, fmt="%s"):
    me._oxs[path] = (len(me._toks), fmt)
    me._toks.append(None)
    return me
  
  def prepare_a(me):
    for o in me._oxs:
      ix, fmt = me._oxs[o]
      me._oxs[o] = fmt % (yield async.WaitFor(me._ctx.outfile_a(o)))
      me._toks[ix] = me._oxs[o]
    me.shline = subprocess.list2cmdline(me._toks)
    me.outs = me._oxs
  
  def exec_a(me):
    if not hasattr(me, 'shline'):
      yield async.WaitFor(me.prepare_a())
    
    def go():
      pipe = subprocess.PIPE
      p = subprocess.Popen(me._toks, cwd=me.cwd, stdin=pipe, stdout=pipe, stderr=pipe)
      me.stdout, me.stderr = p.communicate()
      me.returncode = p.returncode
    
    if me.showerr:
      print >> sys.stderr, '[RUN] ' + me.shline
    yield async.WaitFor(go)
    
    if me.showerr and me.stderr != '':
      print >> sys.stderr, '-'*72 + '\n[ERR] ' + me.shline + '\n' + me.stderr + ('' if me.stderr[-1] == '\n' else '\n') + '-'*72
    if me.showout and me.stdout != '':
      print >> sys.stderr, '-'*72 + '\n[OUT] ' + me.shline + '\n' + me.stdout + ('' if me.stdout[-1] == '\n' else '\n') + '-'*72
    
    if me.returncode != 0:
      raise subprocess.CalledProcessError(me.returncode, me.shline)

def MemoHost(host_a):
  """Given a host, memoize it so that redundant key lookups are cached.  This
  makes sense when we expect the state of the world to remain frozen for the
  lifetime of this host object.
  """
  cache = {}
  def query_a(keys, stash):
    keys = keys if type(keys) is set else set(keys)
    vals = {}
    for k in keys:
      if k in cache:
        vals[k] = cache[k]
    if len(vals) != len(keys):
      keys1 = tuple(k for k in keys if k not in vals)
      vals1 = yield async.WaitFor(host_a(keys1, stash))
      vals.update(vals1)
      cache.update(vals1)
      assert len(vals) == len(keys)
    yield async.Result(vals)
  return query_a

def FileHost_a(paths, stash):
  """A host whose keys are interpreted as filesystem paths, the returned hashes values are content hashes.
  """
  def action(path, old):
    t0, h0 = old if old is not None else (0, '')
    if os.path.exists(path):
      t1 = int(os.path.getmtime(path)*10000)
      if t0 != t1:
        md5 = hashlib.md5()
        with open(path, 'rb') as f:
          for b in iter(lambda: f.read(8192), ''):
            md5.update(b)
        h1 = md5.digest()
      else:
        h1 = h0
    else:
      t1, h1 = 0, ''
    return (t1, h1) if (t1, h1) != (t0, h0) else old
  reals = dict((p, os.path.realpath(p)) for p in paths)
  ans = yield async.WaitFor(stash.updates_a(reals.keys(), action))
  ans = dict((k,th[1]) for k,th in ans.iteritems())
  yield async.Result(ans)

class Oven(object):
  def __init__(me, host_a, path):
    object.__init__(me)
    me._host_a = host_a
    me._path = path
    me._dbcxn = None
    me._dbpath = os.path.join(path, "db")
    me._dbaff = ("sqlite3", me._dbpath)
    me._logdb = _LogDb(me)
  
  def _dbjob(me, job):
    def wrap():
      if me._dbcxn is None:
        _ensure_dirs(me._dbpath)
        me._dbcxn = sqlite3.connect(me._dbpath)
      return job(me._dbcxn)
    return wrap
  
  def _Task_db(me, key, job):
    return async.Task(key, me._dbjob(job), me._dbaff)
  
  def _WaitFor_db(me, job):
    return async.WaitFor(me._dbjob(job), me._dbaff)
  
  def close_a(me):
    def close_it():
      if me._dbcxn is not None:
        me._dbcxn.close()
        me._dbcxn = None
    yield async.Task(None, close_it, me._dbaff)
    yield async.WaitAny
  
  def query_a(me, keys):
    return me._host_a(keys, _Stash(me))
  
  def _call_a(me, par, fun_a, argmap):
    def calc_a(log):
      ctx = _Context(me, par, argmap, log)
      try:
        result = yield async.WaitFor(fun_a(ctx))
      except Exception, e:
        tb = sys.exc_traceback
        yield async.WaitFor(ctx._flush_a())
        raise type(e), e, tb
      yield async.WaitFor(ctx._flush_a())
      yield async.Result(result)
    
    funval = valtool.Hasher().eat(fun_a).digest()
    view = _View(me, par, argmap)
    log = yield async.WaitFor(me._logdb.memo_a(funval, view, calc_a))
    yield async.Result(log)
  
  def memo_a(me, fun_a, argroot):
    assert argroot is not None
    if isinstance(argroot, dict):
      argmap = lambda x,up: argroot.get(x, None)
    else:
      argmap = lambda x,up: argroot(x)
    
    log = yield async.WaitFor(me._call_a(None, fun_a, argmap))
    result = log.result() # might throw, let it go
    yield async.Result(result)

class _Stash(object):
  def __init__(me, oven):
    me._oven = oven
  
  def updates_a(me, keys, action):
    size_i = struct.calcsize('<i')
    def go(cxn):
      _sql_ensure_table(cxn, 'stash', ('hk0','hk1','val'), [['hk0']])
      try:
        cur = cxn.cursor()
        ans = {}
        for k in keys:
          hk = valtool.Hasher().eat(k).digest()
          hk0 = struct.unpack_from('<i', hk)[0]
          hk1 = buffer(hk, size_i)
          row = cur.execute("select val from stash where hk0=? and hk1=?", (hk0,hk1)).fetchone()
          old = None if row is None else valtool.unpack(row[0])
          new = action(k, old)
          ans[k] = new
          if row is not None and new is None:
            cur.execute('delete from stash where hk0=? and hk1=?', (hk0,hk1))
          elif row is None and new is not None:
            val = valtool.pack(new)
            cur.execute('insert into stash(hk0,hk1,val) values(?,?,?)', (hk0,hk1,buffer(val)))
          elif old is not new:
            val = valtool.pack(new)
            cur.execute('update stash set val=? where hk0=? and hk1=?', (buffer(val),hk0,hk1))
        cur.close()
        cxn.commit()
        return ans
      except:
        cxn.rollback()
        raise
    ans = yield me._oven._WaitFor_db(go)
    yield async.Result(ans)
  
  def gets_a(me, keys):
    return me.updates_a(keys, lambda key,old: old)
  
  def puts_a(me, keyvals):
    return me.updates_a(keyvals.keys(), lambda key,old: keyvals[key])

class _View(object):
  def __init__(me, oven, par, argmap):
    object.__init__(me)
    me._oven = oven
    me._par = par
    me._argmap = argmap
    me._argmemo = {}
  
  def _hash_tagkey_a(me, tag, key):
    assert tag in (_tag_inp, _tag_arg)
    if tag == _tag_inp:
      a = yield async.WaitFor(me._hash_input_a(key))
      yield async.Result(a)
    else:
      yield async.Result(me._hash_arg(key)[1])
  
  def _hash_input_a(me, inp):
    ans = yield async.WaitFor(me._oven.query_a([inp]))
    yield async.Result(ans[inp])
  
  def _hash_inputs_a(me, inps):
    return me._oven.query_a(inps)
  
  def _hash_arg(me, x):
    if x not in me._argmemo:
      y = me._argmap(x, lambda x: me._par._hash_arg(x)[0])
      me._argmemo[x] = (y, valtool.Hasher().eat(y).digest())
    return me._argmemo[x]

class _Context(_View):
  def __init__(me, oven, par, argmap, log):
    _View.__init__(me, oven, par, argmap)
    me._log = log
    me._inpset = set()
    me._inphold = []
    me._argset = set()
    
  def input(me, key):
    if key not in me._inpset and not me._is_outfile(key):
      me._inpset.add(key)
      me._inphold.append(key)
    return key
  
  def digest_a(me):
    yield async.WaitFor(me._flush_a())
    yield async.Result(me._log.digest())
  
  def _is_outfile(me, path):
    o = os.path.join(os.path.realpath(me._oven._path), 'o')
    p = os.path.realpath(path)
    return p.startswith(o + os.path.sep) # ugly, should use os.path.samefile
  
  def tmpfile(me, name):
    assert False # implement me!
    
  def outfile_a(me, path):
    yield async.WaitFor(me._flush_a())
    dig = _bin2hex(me._log.digest())
    o = os.path.join(me._oven._path, 'o', path, dig)
    _ensure_dirs(o)
    yield async.Result(o)
  
  def __getitem__(me, x):
    y, yh = me._hash_arg(x)
    if x not in me._argset:
      me._argset.add(x)
      me._log.add(_tag_arg, x, yh)
    return y
  
  def __call__(me, fun_a, argmap=(lambda x,up: up(x))):
    assert argmap is not None
    if isinstance(argmap, dict):
      d = argmap
      argmap = lambda x,up: d[x] if x in d else up(x)
    
    log = yield async.WaitFor(me._oven._call_a(me, fun_a, argmap))
    
    for tag,key,val in log.records():
      if tag == _tag_inp:
        if key not in me._inpset:
          me._inpset.add(key)
          me._log.add(tag, key, val)
      elif tag == _tag_arg:
        argmap(key, lambda x: me[x])
    
    yield async.Result(log.result())
    
  def _flush_a(me):
    if len(me._inphold) > 0:
      them = yield async.WaitFor(me._hash_inputs_a(me._inphold))
      del me._inphold[:]
      for inf in them:
        me._log.add(_tag_inp, inf, them[inf])

_tag_done = 0
_tag_inp = 1
_tag_arg = 2

class _Log(object):
  def __init__(me, funval):
    object.__init__(me)
    me._h = valtool.Hasher().raw(funval)
    me._vals = [funval]
    me._tags = []
    me._keys = []
    me._bar = async.Barrier()
    me._err = None
  
  def add(me, tag, key, val):
    assert len(me._tags) == 0 or me._tags[-1] != _tag_done
    assert tag != _tag_done
    me._tags.append(tag)
    me._keys.append(key)
    me._vals.append(val)
    me._h.raw(str(tag)).eat(key).raw(val)
    me._bar.fireall()
  
  def digest(me):
    return me._h.digest()

  def finish(me, result):
    assert len(me._tags) == 0 or me._tags[-1] != _tag_done
    me._tags.append(_tag_done)
    me._keys.append(result)
    me._bar.fireall()
  
  def explode(me, ex, tb):
    assert len(me._tags) == 0 or me._tags[-1] != _tag_done
    me._err = (ex, tb)
    me._bar.fireall()
  
  def funval(me):
    return me._vals[0]
  
  def records(me):
    assert me._err is not None or me._tags[-1] == _tag_done
    num = len(me._tags) - (0 if me._err is not None else 1)
    return ((me._tags[i], me._keys[i], me._vals[i+1]) for i in xrange(num))
  
  def result(me):
    if me._err is not None:
      raise type(me._err[0]), me._err[0], me._err[1]
    else:
      assert me._tags[-1] == _tag_done
      return me._keys[-1]
  
  def error(me):
    return me._err

class _LogDb(object):
  def __init__(me, oven):
    object.__init__(me)
    me._oven = oven
    me._lock = async.Lock()
    me._wips = set() # set(_Log) -- work-in-progress
    me._sqlinit = False
    me._keyenc = {}
    me._keydec = {}
  
  def _ensure_schema(me, cxn):
    if not me._sqlinit:
      me._sqlinit = True
      _sql_ensure_table(cxn, 'logtrie', ('mix','val','key'), [['mix']])
      _sql_ensure_table(cxn, 'keybag', ('key','hash'), [['hash']])
  
  def _encode_tagkey(me, cxn, tag, key):
    tk = (tag, key)
    h = valtool.Hasher().eat(tk).digest()
    if h not in me._keyenc:
      h1 = struct.unpack_from("<i", h)[0]
      cur = cxn.cursor()
      cur.execute('select rowid,key from keybag where hash=?', (h1,))
      row = None
      for got in cur.fetchall():
        #if pickle.loads(str(got[1])) == tk:
        if valtool.unpack(got[1]) == tk:
          row = got[0]
          break
      if row is None:
        #k = pickle.dumps(tk, protocol=pickle.HIGHEST_PROTOCOL)
        k = valtool.pack(tk)
        cur.execute('insert into keybag(key,hash) values(?,?)', (buffer(k),h1))
        row = cur.lastrowid
      me._keyenc[h] = row
      me._keydec[row] = tk
      cur.close()
    return me._keyenc[h]
  
  def _decode_tagkey(me, cxn, tagkey):
    row = tagkey
    if row not in me._keydec:
      cur = cxn.cursor()
      cur.execute('select key from keybag where rowid=?', (row,))
      #tk = pickle.loads(str(cur.fetchone()[0]))
      tk = valtool.unpack(cur.fetchone()[0])
      me._keydec[row] = tk
      me._keyenc[valtool.Hasher().eat(tk).digest()] = row
      cur.close()
    return me._keydec[row]
  
  def memo_a(me, funval, view, calc_a):
    # return: _Log
    # calc_a: _Log -> result
    
    # check that we aren't subsumed by any wip
    disjoint = set() # set(_Log)
    while True:
      disjoint.intersection_update(me._wips)
      wip = None
      for log in me._wips:
        if log not in disjoint:
          wip = log
          break
      
      if wip is None: # disjoint with all wips
        new_wip = yield async.WaitFor(me._lock.acquire_a())
        if not new_wip:
          break
        else:
          me._lock.release(False)
      else: # test disjointness with wip
        ix = 0
        val = funval
        while True:
          if val != wip._vals[ix]:
            disjoint.add(wip)
            break
          if ix == len(wip._tags):
            yield async.WaitFor(wip._bar)
          err = wip.error()
          if err is not None:
            yield async.Result(wip)
          tag, key = wip._tags[ix], wip._keys[ix]
          if tag == _tag_done:
            yield async.Result(wip) # this wip computed the value we need
          elif tag == _tag_arg:
            val = view._hash_arg(key)[1]
          else:
            assert tag == _tag_inp
            val = wip._vals[ix+1]
          ix += 1
    
    def step(cxn, par, val):
      me._ensure_schema(cxn)
      cur = cxn.cursor()
      mix = par ^ struct.unpack_from("<i", val)[0]
      cur.execute("select rowid,key from logtrie where mix=? and val=?", (mix,buffer(val)))
      got = cur.fetchone()
      cur.close()
      if got is None:
        return None
      row, (tag, key) = got[0], me._decode_tagkey(cxn, got[1])
      return (row, tag, key)
    
    # we have the lock, test the memo cache
    par, val = -1, funval
    tag, key = -1, 'fun'
    log = _Log(funval) # rebuild as we traverse trie
    while True:
      got = yield me._oven._WaitFor_db(lambda cxn:step(cxn,par,val))
      if got is None:
        #print >> sys.stderr, 'FAILED', tag, key, repr(val)
        log = None
        break
      par, tag, key = got
      if tag == _tag_done:
        log.finish(key)
        break
      else:
        val = yield async.WaitFor(view._hash_tagkey_a(tag, key))
        log.add(tag, key, val)
    
    if log is not None:
      me._lock.release(False)
    else: # must compute
      log = _Log(funval)
      me._wips.add(log)
      me._lock.release(True) # signal new wip created
      
      try:
        result = yield async.WaitFor(calc_a(log))
        log.finish(result)
      except Exception, e:
        log.explode(e, sys.exc_traceback)
      
      # done computing, put in cache
      def insert(cxn, log):
        me._ensure_schema(cxn)
        try:
          cur = cxn.cursor()
          ixs = range(len(log._tags))
          par = -1
          ix = -1
          while len(ixs) > 0:
            val = log._vals[ix+1]
            mix = par ^ struct.unpack_from("<i", val)[0]
            cur.execute("select rowid,key from logtrie where mix=? and val=?", (mix, buffer(val)))
            got = cur.fetchone()
            if got is None: break
            
            par, (tag, key) = got[0], me._decode_tagkey(cxn, got[1])
            assert tag != _tag_done
            i = 0
            while True:
              #if i == len(ixs):
              #  print 'TAGKEY', tag, key
              #  print 'IXS', ixs
              #  for i in xrange(len(log._tags)):
              #    print i, log._tags[i], log._keys[i]
              assert i < len(ixs)
              ix = ixs[i]
              if log._tags[ix] == tag and log._keys[ix] == key:
                break
              i += 1
            del ixs[i]
          
          while len(ixs) > 0:
            val = log._vals[ix+1]
            ix = ixs[0]
            del ixs[0]
            mix = par ^ struct.unpack_from("<i", val)[0]
            tagkey = me._encode_tagkey(cxn, log._tags[ix], log._keys[ix])
            cur.execute("insert into logtrie(mix,val,key) values(?,?,?)", (mix,buffer(val),tagkey))
            par = cur.lastrowid
          cxn.commit()
        except:
          cxn.rollback()
          raise
      
      yield async.WaitFor(me._lock.acquire_a())
      me._wips.discard(log)
      if log.error() is None:
        yield me._oven._WaitFor_db(lambda cxn: insert(cxn, log))
      me._lock.release(False)
    
    yield async.Result(log)
