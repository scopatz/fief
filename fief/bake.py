import async
import array
import binascii
import hashlib
import os
import shutil
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
    me._ctx = ctx
    me._toks = []
    me._oxs = {}
    me.cwd = None
    me.showout = False
    me.showerr = True
    me.env = {}
  
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
      me._oxs[o] = fmt % (yield async.Sync(me._ctx.outfile_a(o)))
      me._toks[ix] = me._oxs[o]
    me.shline = subprocess.list2cmdline(me._toks)
    me.outs = me._oxs
  
  def exec_a(me):
    if not hasattr(me, 'shline'):
      yield async.Sync(me.prepare_a())
    
    def go():
      pipe = subprocess.PIPE
      env = dict(os.environ)
      env.update(me.env)
      p = subprocess.Popen(me._toks, cwd=me.cwd, env=env, stdin=pipe, stdout=pipe, stderr=pipe)
      me.stdout, me.stderr = p.communicate()
      me.returncode = p.returncode
    
    if me.showerr:
      print >> sys.stderr, '[RUN] ' + me.shline
    yield async.Sync(go)
    
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
      vals1 = yield async.Sync(host_a(keys1, stash))
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
  ans = yield async.Sync(stash.updates_a(reals.keys(), action))
  ans = dict((k,th[1]) for k,th in ans.iteritems())
  yield async.Result(ans)

def TestNo(y):
  return MatchNone

class Match(object):
  def input_a(me, x, query_host_a):
    assert False
  def arg(me, x):
    assert False
  def result(me, x):
    assert False

class MatchNone(Match):
  def input_a(me, x, query_host_a):
    yield async.Result(TestNo)
  def arg(me, x):
    return TestNo
  def result(me, x):
    return False

class TestEqual(object):
  def __init__(me, val, next_match):
    me._val = val
    me._next_match = next_match
  def __call__(me, y):
    return me._next_match(y) if me._val == y else MatchNone

class MatchArgs(Match):
  def __init__(me, argtest, collector):
    """accepts only inputs that match current host hash value, defers to
    argtest to generate test lambda for args.
    
    argtest: takes (x, next_match), returns tester
    collector: takes ({x:y}, result) for argument name and values x,y
    """
    me._argtest = argtest
    me._collector = collector
    me._argmem = {}
  
  def input_a(me, x, query_host_a):
    h = yield async.Sync(query_host_a(x))
    yield async.Result(TestEqual(h, lambda y: me))
  
  def arg(me, x):
    def next_match(y):
      m = MatchArgs(me._argtest, me._collector)
      m._argmem.update(me._argmem)
      m._argmem[x] = y
      return m
    return me._argtest(x, next_match)
  
  def result(me, ans):
    return me._collector(me._argmem, ans)

class Oven(object):
  def __init__(me, host_a, path):
    object.__init__(me)
    me._host_a = host_a
    me._path = path
    me._dbcxn = None
    me._dbpath = os.path.join(path, "db")
    me._dbpool = async.Pool(size=1)
    me._dbtabs = set()
    me._logdb = _LogDb(me)
  
  def _dbjob(me, job):
    @async.assign_pool(me._dbpool)
    def wrap():
      if me._dbcxn is None:
        _ensure_dirs(me._dbpath)
        me._dbcxn = sqlite3.connect(me._dbpath)
      def ensure_table(name, cols, ixs=()):
        if name not in me._dbtabs:
          me._dbtabs.add(name)
          _sql_ensure_table(me._dbcxn, name, cols, ixs)
      return job(me._dbcxn, ensure_table)
    return wrap
  
  def close_a(me):
    @async.assign_pool(me._dbpool)
    def close_it():
      if me._dbcxn is not None:
        me._dbcxn.close()
        me._dbcxn = None
    yield async.Sync(close_it)
  
  def query_a(me, keys):
    return me._host_a(keys, _Stash(me))
  
  def _outfile_a(me, path):
    def bump(cxn, ensure_table):
      ensure_table('outdirs', ('path','bump'), [['path']])
      cur = cxn.cursor()
      cur.execute('select bump from outdirs where path=?', (path,))
      got = cur.fetchone()
      if got is None:
        got = 0
        cur.execute('insert into outdirs(path,bump) values(?,?)', (path,got+1))
      else:
        got = got[0]
        cur.execute('update outdirs set bump=? where path=?', (got+1,path))
      return got
    
    n = yield async.Sync(me._dbjob(bump))
    o = os.path.join(me._path, 'o', path, str(n))
    assert not os.path.exists(o)
    _ensure_dirs(o)
    yield async.Result(o)
  
  def _memo_a(me, par, fun_a, argmap):
    def calc_a(log):
      ctx = _Context(me, par, argmap, log)
      try:
        result = yield async.Sync(fun_a(ctx))
      except:
        for o in ctx._outfs:
          if os.path.exists(o):
            shutil.rmtree(o)
        raise
      finally:
        yield async.Sync(ctx._flush_a())        
      yield async.Result(result)
    
    funval = valtool.Hasher().eat(fun_a).digest()
    view = _View(me, par, argmap)
    log = yield async.Sync(me._logdb.memo_a(funval, view, calc_a))
    yield async.Result(log)
  
  def memo_a(me, fun_a, argroot):
    assert argroot is not None
    if isinstance(argroot, dict):
      argmap = lambda x,up: argroot.get(x, None)
    else:
      argmap = lambda x,up: argroot(x)
    log = yield async.Sync(me._memo_a(None, fun_a, argmap))
    yield async.Result(log.result()) # will throw if fun_a did, but thats ok
  
  def search_a(me, fun_a, match):
    funval = valtool.Hasher().eat(fun_a).digest()
    return me._logdb.search_a(funval, match)

class _Stash(object):
  def __init__(me, oven):
    me._oven = oven
  
  def updates_a(me, keys, action):
    size_i = struct.calcsize('<i')
    def go(cxn, ensure_table):
      ensure_table('stash', ('hk0','hk1','val'), [['hk0']])
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
    ans = yield async.Sync(me._oven._dbjob(go))
    yield async.Result(ans)
  
  def gets_a(me, keys):
    return me.updates_a(keys, lambda key,old: old)
  
  def puts_a(me, keyvals):
    return me.updates_a(keyvals.keys(), lambda key,old: keyvals[key])

class _View(object):
  def __init__(me, oven, par, argmap):
    me._oven = oven
    me._par = par
    me._argmap = argmap
    me._argmemo = {}
  
  def _tagkey_a(me, tag, key):
    assert tag in (_tag_inp, _tag_arg)
    if tag == _tag_inp:
      h = yield async.Sync(me._hash_input_a(key))
      yield async.Result(h)
    else:
      yield async.Result(me._arg(key))
  
  def _hash_input_a(me, inp):
    ans = yield async.Sync(me._oven.query_a([inp]))
    yield async.Result(ans[inp])
  
  def _hash_inputs_a(me, inps):
    return me._oven.query_a(inps)
  
  def _arg(me, x):
    if x not in me._argmemo:
      me._argmemo[x] = me._argmap(x, lambda x: me._par._arg(x))
    return me._argmemo[x]

class _Context(_View):
  def __init__(me, oven, par, argmap, log):
    super(_Context, me).__init__(oven, par, argmap)
    me._log = log
    me._inpset = set()
    me._inphold = []
    me._argset = set()
    me._outfs = []
  
  def input(me, key):
    if key not in me._inpset and not me._is_outfile(key):
      me._inpset.add(key)
      me._inphold.append(key)
    return key
  
  def _is_outfile(me, path):
    o = os.path.join(os.path.realpath(me._oven._path), 'o')
    p = os.path.realpath(path)
    return p.startswith(o + os.path.sep) # ugly, should use os.path.samefile
  
  def outfile_a(me, path):
    o = yield async.Sync(me._oven._outfile_a(path))
    me._outfs.append(o)
    yield async.Result(o)
  
  def __getitem__(me, x):
    y = me._arg(x)
    if x not in me._argset:
      me._argset.add(x)
      me._log.add(_tag_arg, x, y)
    return y
  
  def __call__(me, fun_a, argmap=(lambda x,up: up(x))):
    assert argmap is not None
    if isinstance(argmap, dict):
      d = argmap
      argmap = lambda x,up: d[x] if x in d else up(x)
    
    log = yield async.Sync(me._oven._memo_a(me, fun_a, argmap))
    
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
      them = yield async.Sync(me._hash_inputs_a(me._inphold))
      del me._inphold[:]
      for inf in them:
        me._log.add(_tag_inp, inf, them[inf])

_tag_done = 0
_tag_inp = 1
_tag_arg = 2

class _Log(object):
  def __init__(me, funval):
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
    me._bar.fireall()
  
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
    me._oven = oven
    me._lock = async.Lock()
    me._signew = async.Signal(False, lambda a,b: a or b)
    me._wips = set() # set(_Log) -- work-in-progress
    me._valenc = {}
    me._valdec = {}
  
  def _ensure_schema(me, ensure_table):
    ensure_table('logtrie', ('par','val_a','val_b','tagkey'), [['par','val_a']])
    ensure_table('valbag', ('val','hash'), [['hash']])
  
  def _encode_val(me, cxn, val):
    h = valtool.Hasher().eat(val).digest()
    if h not in me._valenc:
      h1 = struct.unpack_from("<i", h)[0]
      cur = cxn.cursor()
      cur.execute('select rowid,val from valbag where hash=?', (h1,))
      row = None
      for got in cur.fetchall():
        #if pickle.loads(str(got[1])) == tk:
        if valtool.unpack(got[1]) == val:
          row = got[0]
          break
      if row is None:
        #k = pickle.dumps(tk, protocol=pickle.HIGHEST_PROTOCOL)
        v = valtool.pack(val)
        cur.execute('insert into valbag(val,hash) values(?,?)', (buffer(v),h1))
        row = cur.lastrowid
      me._valenc[h] = row
      me._valdec[row] = val
      cur.close()
    return me._valenc[h]
  
  def _decode_val(me, cxn, row):
    if row not in me._valdec:
      cur = cxn.cursor()
      cur.execute('select val from valbag where rowid=?', (row,))
      #tk = pickle.loads(str(cur.fetchone()[0]))
      val = valtool.unpack(cur.fetchone()[0])
      me._valdec[row] = val
      me._valenc[valtool.Hasher().eat(val).digest()] = row
      cur.close()
    return me._valdec[row]

  _sizeof_int = struct.calcsize("<i")
  
  def _split_val(me, tag, val):
    if tag in (-1, _tag_inp): # val is a hash
      a = struct.unpack_from("<i", val)[0]
      b = buffer(val, me._sizeof_int)
    else: # val is object
      val = valtool.pack(val)
      a = struct.unpack_from("<i", valtool.Hasher().raw(val).digest())[0]
      b = buffer(val)
    return a, b
  
  def _merge_val(me, tag, a, b):
    if tag in (-1, _tag_inp):
      return struct.pack("<i", a) + str(b)
    else:
      return valtool.unpack(b)

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
        acq = me._lock.acquire()
        new_wip = me._signew.begin_frame()
        yield async.Wait(acq)
        if not new_wip.aggregate():
          break
        else:
          me._lock.release()
      else: # test disjointness with wip
        ix = 0
        val = funval
        while True:
          if val != wip._vals[ix]:
            disjoint.add(wip)
            break
          if ix == len(wip._tags):
            yield async.Wait(wip._bar.enlist())
          err = wip.error()
          if err is not None:
            yield async.Result(wip)
          tag, key = wip._tags[ix], wip._keys[ix]
          if tag == _tag_done:
            yield async.Result(wip) # this wip computed the value we need
          elif tag == _tag_arg:
            val = view._arg(key)
          else:
            assert tag == _tag_inp
            val = wip._vals[ix+1]
          ix += 1
    
    def step(cxn, enstab, par, partag, val):
      me._ensure_schema(enstab)
      cur = cxn.cursor()
      val_a, val_b = me._split_val(partag, val)
      cur.execute(
        "select rowid, tagkey " +
        "from logtrie " +
        "where par=? and val_a=? and val_b=?",
        (par, val_a, val_b))
      r = cur.fetchone()
      if r is None: return None
      cur.close()
      return r[0], me._decode_val(cxn, r[1])
    
    # we have the lock, test the memo cache
    par, val = -1, funval
    tag, key = -1, None
    log = _Log(funval) # rebuild as we traverse trie
    while True:
      got = yield async.Sync(me._oven._dbjob(lambda cxn, enstab: step(cxn, enstab, par, tag, val)))
      if got is None:
        #print >> sys.stderr, 'FAILED', tag, key, repr(val)
        log = None
        break
      par, (tag, key) = got
      if tag == _tag_done:
        log.finish(key)
        break
      else:
        val = yield async.Sync(view._tagkey_a(tag, key))
        log.add(tag, key, val)
    
    if log is not None:
      me._lock.release()
    else: # must compute
      log = _Log(funval)
      me._wips.add(log)
      me._signew.pulse(True) # signal new wip created
      me._lock.release()
      
      try:
        result = yield async.Sync(calc_a(log))
        log.finish(result)
      except Exception, e:
        log.explode(e, sys.exc_traceback)
      
      # done computing, put in cache
      def insert(cxn, enstab, log):
        me._ensure_schema(enstab)
        try:
          cur = cxn.cursor()
          ixs = range(len(log._tags))
          par, tag = -1, -1
          ix = -1
          while len(ixs) > 0:
            val = log._vals[ix+1]
            val_a, val_b = me._split_val(tag, val)
            cur.execute(
              "select rowid, tagkey " +
              "from logtrie " +
              "where par=? and val_a=? and val_b=?",
              (par, val_a, val_b))
            got = cur.fetchone()
            if got is None: break
            
            par, (tag, key) = got[0], me._decode_val(cxn, got[1])
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
            val_a, val_b = me._split_val(tag, log._vals[ix+1])
            ix = ixs[0]
            del ixs[0]
            tag, key = log._tags[ix], log._keys[ix]
            tagkey = me._encode_val(cxn, (tag, key))
            cur.execute(
              "insert into logtrie(par,val_a,val_b,tagkey) " +
              "values(?,?,?,?)",
              (par, val_a, val_b, tagkey))
            par = cur.lastrowid
          cxn.commit()
        except:
          cxn.rollback()
          raise
      
      yield async.Wait(me._lock.acquire())
      me._wips.discard(log)
      if log.error() is None:
        yield async.Sync(me._oven._dbjob(lambda cxn, enstab: insert(cxn, enstab, log)))
      me._lock.release()
    
    yield async.Result(log)

  def search_a(me, funval, match):
    if True:
      def step(cxn, ensure_table, par_tag_tests):
        me._ensure_schema(ensure_table)
        par_tagtest = {}
        conds = ([],[])
        binds = ([],[])
        for par,partag,test in par_tag_tests:
          par_tagtest[par] = (partag,test)
          if isinstance(test, TestEqual):
            val_a, val_b = me._split_val(partag, test._val)
            conds[0].append("(par=? and val_a=? and val_b=?)")
            binds[0].extend((par, val_a, val_b))
          elif test is not TestNo:
            conds[1].append("par=?")
            binds[1].append(par)
        
        conds = conds[0] + conds[1]
        binds = binds[0] + binds[1]
        cur = cxn.cursor()
        cur.execute(
          "select rowid, par, val_a, val_b, tagkey " +
          "from logtrie " +
          ("where " + " or ".join(conds) if len(conds)>0 else ""),
          binds)
        ans = []
        for r in cur:
          row, par, val_a, val_b, tagkey = r
          partag, test = par_tagtest[par]
          if isinstance(test, TestEqual):
            m = test(test._val)
          else:
            m = test(me._merge_val(partag, val_a, val_b))
          if m is not MatchNone:
            tag, key = me._decode_val(cxn, tagkey)
            ans.append((row, tag, key, m))
        return ans
    else:
      def step(cxn, ensure_table, par_tag_tests):
        me._ensure_schema(ensure_table)
        cur = cxn.cursor()
        ans = []
        for par, partag, test in par_tag_tests:
          if isinstance(test, TestEqual):
            val_a, val_b = me._split_val(partag, test._val)
            got = cur.execute(
              "select rowid,val_a,val_b,tagkey " +
              "from logtrie " +
              "where par=? and val_a=? and val_b=?",
              (par, val_a, val_b))
          elif test is TestNo:
            got = ()
          else:
            got = cur.execute(
              "select rowid,val_a,val_b,tagkey " +
              "from logtrie " +
              "where par=?",
              (par,))
          for r in got:
            row, val_a, val_b, tagkey = r
            m = test(me._merge_val(partag, val_a, val_b))
            if m is not MatchNone:
              tag, key = me._decode_val(cxn, tagkey)
              ans.append((row, tag, key, m))
        return ans
      
    """
    class Match(object):
    def input_a(me, x, query_host_a):
      assert False
    def arg(me, x):
      assert False
    def result(me, x):
      assert False
    """
    oven = me._oven
    fings = [(-1, -1, TestEqual(funval, lambda y: match))]
    while len(fings) > 0:
      fings1 = yield async.Sync(oven._dbjob(lambda cxn, enstab: step(cxn, enstab, fings)))
      del fings[:]
      rowtag = {}
      for row, tag, key, m in fings1:
        if tag == _tag_inp:
          def query_a(x):
            y = yield async.Sync(oven.query_a((x,)))
            yield async.Result(y[x])
          fut = yield async.Begin(m.input_a(key, query_a))
          rowtag[fut] = (row,tag)
          #test = yield async.Sync(m.input_a(key, query_a))
        else:
          if tag == _tag_arg:
            test = m.arg(key)
          elif tag == _tag_done:
            m.result(key)
            test = TestNo
          else:
            assert False
          if test is not TestNo:
            fings.append((row, tag, test))
      while len(rowtag) > 0:
        fut = yield async.WaitAny(rowtag)
        row, tag = rowtag.pop(fut)
        test = fut.result()
        if test is not TestNo:
          fings.append((row, tag, test))
