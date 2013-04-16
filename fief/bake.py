import array
import async
import binascii
import collections
import hashlib
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import types
import valtool

deque = collections.deque
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

def _remove_clean(keep, rest):
  """Remove file or tree at 'os.path.join(keep,rest)'.  Then remove all empty dirs
  up to but not including 'keep'.  Does not fail when things don't exist."""
  assert not os.path.isabs(rest)
  rest = rest.rstrip(os.path.sep)
  
  if rest != '':
    p = os.path.join(keep, rest)
    if os.path.isdir(p):
      shutil.rmtree(p)
    elif os.path.isfile(p):
      os.remove(p)
    
    while True:
      rest = os.path.dirname(rest)
      if rest == '': break
      p = os.path.join(keep, rest)
      try:
        os.rmdir(p)
      except:
        if os.path.isdir(p):
          break

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
  def __init__(me, ctx, cwd=None, env=None, executable=None, tag=None, 
               showout=False, showerr=True):
    me._ctx = ctx
    me._toks = []
    me._oxs = {}
    me.cwd = cwd
    me.env = env or dict(os.environ)
    me.executable = executable # if os.name == 'nt' else None
    me.tag = tag
    me.showout = showout
    me.showerr = showerr
  
  def lit(me, *toks):
    me._toks += _flatten(toks)
    return me
  
  def inf(me, path, fmt="%s"):
    path = os.path.normpath(path)
    me._ctx.infile(path)
    me._toks.append(fmt % path)
    return me
  
  def infs(me, paths, fmt="%s"):
    ps = []
    for p in paths:
      path = os.path.normpath(p)
      ps.append(path)
      me._toks.append(fmt % path)
    me._ctx.infiles(ps)
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
    
    if len(me._oxs) == 0:
      yield async.Sync(me._ctx.flush_a())
    
    me.shline = subprocess.list2cmdline(me._toks)
    me.outs = me._oxs
  
  def exec_a(me):
    if not hasattr(me, 'shline'):
      yield async.Sync(me.prepare_a())
    
    def go():
      pipe = subprocess.PIPE
      p = subprocess.Popen(me._toks, cwd=me.cwd, env=me.env, stdin=pipe, stdout=pipe, stderr=pipe)
      me.stdout, me.stderr = p.communicate()
      me.returncode = p.returncode
    
    if me.tag is not None:
      tag = me.tag + ': '
    else:
      tag = ''
    
    if me.showerr:
      print >> sys.stderr, '[RUN] ' + tag + me.shline
    yield async.Sync(go)
    
    if me.showerr and me.stderr != '':
      print >> sys.stderr, '-'*72 + '\n[MSG] ' + tag + me.shline + '\n' + \
        me.stderr + ('' if me.stderr[-1] == '\n' else '\n') + '-'*72
    
    if me.showout and me.stdout != '':
      print >> sys.stderr, '-'*72 + '\n[OUT] ' + tag + me.shline + '\n' + \
        me.stdout + ('' if me.stdout[-1] == '\n' else '\n') + '-'*72
    
    if me.returncode != 0:
      raise subprocess.CalledProcessError(me.returncode, me.shline)

class Host(object):
  def canonify(me, x):
    return x
  def lift_file(me, path):
    assert False
  def unlift_file(me, x):
    assert False
  def query_a(me, keys, stash):
    assert False

class MemoHost(Host):
  """Given a host, memoize it so that redundant key lookups are cached.  This
  makes sense when we expect the state of the world to remain frozen for the
  lifetime of this host object.
  """
  def __init__(me, host):
    me.host = host
    me.cache = {}
  
  def canonify(me, x):
    return me.host.canonify(x)
  
  def lift_file(me, path):
    return me.host.lift_file(path)
  
  def unlift_file(me, x):
    return me.host.unlift_file(x)
  
  def query_a(me, keys, stash):
    host = me.host
    cache = me.cache
    keys = keys if type(keys) is set else set(keys)
    vals = {}
    for k in keys:
      if k in cache:
        vals[k] = cache[k]
    if len(vals) != len(keys):
      keys1 = tuple(k for k in keys if k not in vals)
      vals1 = yield async.Sync(host.query_a(keys1, stash))
      vals.update(vals1)
      cache.update(vals1)
      assert len(vals) == len(keys)
    yield async.Result(vals)

class _FileHost(Host):
  """A host whose keys are interpreted as filesystem paths, the returned hashes values are content hashes.
  """
  def __call__(*a,**kw):
    raise Exception("FileHost is an instance, not a constructor!")
  
  def canonify(me, x):
    return os.path.abspath(x)
  
  def lift_file(me, path):
    return path
  
  def unlift_file(me, x):
    return x
  
  def query_a(me, paths, stash):
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

FileHost = _FileHost()

def TestNo(y):
  return MatchNone

class Match(object):
  def inputs_a(me, xs, query_a):
    """given tuple of input names 'xs', returns test over tuples of hashes"""
    assert False
  def args(me, xs):
    """given tuple of arg names 'xs', returns test over tuple of values"""
    assert False
  def result(me, y):
    """reached function return of value y"""
    assert False

class _MatchNone(Match):
  def inputs_a(me, xs, query_a):
    yield async.Result(TestNo)
  def args(me, xs):
    return TestNo
  def result(me, y):
    pass
  def __call__(*a,**b):
    assert False # MatchNone is not a constructor!
MatchNone = _MatchNone()

class TestEqualAny(object):
  def __init__(me, values, next_match):
    """vals: list of values to test equality, next_match: val->Match"""
    me.values = values if isinstance(values, tuple) else tuple(values)
    me.next_match = next_match
  def __call__(me, y):
    return me.next_match(y) if y in me.values else MatchNone

class TestNotEqualAll(object):
  def __init__(me, values, next_match):
    """vals: list of values to test equality, next_match: val->Match"""
    me.values = values if isinstance(values, tuple) else tuple(values)
    me.next_match = next_match
  def __call__(me, y):
    return me.next_match(y) if y not in me.values else MatchNone

class MatchArgs(Match):
  Accept = object()
  
  def __init__(me, argstest, collector,
    seed={}, merge=lambda old,xys:(lambda d:(d.update(xys),d)[1])(dict(old))):
    """accepts only inputs that match current host hash value, defers to
    argstest to generate test lambda for args.
    argstest: takes (acc, xs, next_match), returns tester
    collector: takes ({x:y}, result) for argument name and values x,y
    """
    me._argstest = argstest
    me._collector = collector
    me._acc = seed
    me._merge = merge
  
  def inputs_a(me, xs, query_a):
    hs = yield async.Sync(query_a(xs))
    hs = tuple(hs[x] for x in xs)
    yield async.Result(TestEqualAny((hs,), lambda _: me))
  
  def args(me, xs):
    def next_match(ys):
      xys = dict((xs[i],ys[i]) for i in xrange(len(xs)))
      return MatchArgs(me._argstest, me._collector, me._merge(me._acc, xys), me._merge)
    return me._argstest(me._acc, xs, next_match)
  
  def result(me, ans):
    return me._collector(me._acc, ans)

class ArgMode: # enum
  stored = object()
  group_stored = object()
  hashed = object()
  group_hashed = object()

class Oven(object):
  def __init__(me, host, path):
    object.__init__(me)
    me._host = host
    me._path = os.path.abspath(path)
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
        me._dbcxn.execute('pragma synchronous=off')
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
        me._dbcxn.commit()
        me._dbcxn.close()
        me._dbcxn = None
    yield async.Sync(close_it)
  
  def host(me):
    return me._host
  
  def query_a(me, keys):
    return me._host.query_a(keys, _Stash(me))
  
  def _outfile_a(me, path):
    """ returns a tuple (abs-path,stuff), stuff is only used to delete the file later.
    """
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
      cxn.commit()
      return got
    
    n = yield async.Sync(me._dbjob(bump))
    opath = os.path.join(me._path, 'o', path, str(n))
    assert not os.path.exists(opath)
    _ensure_dirs(opath)
    yield async.Result((opath,(path,n)))
  
  def _is_outfile(me, path):
    o = os.path.join(me._path, 'o')
    p = os.path.abspath(path)
    return p.startswith(o + os.path.sep) # ugly, should use os.path.samefile
  
  def _memo_a(me, argmode, par, fun_a, argmap):
    def calc_a(log):
      ctx = _Context(me, argmode, par, argmap, log)
      try:
        result = yield async.Sync(fun_a(ctx))
      except:
        e = sys.exc_info()
        for p,n in ctx._outfs:
          _remove_clean(me._path, os.path.join('o', p, str(n)))
        raise e[0], e[1], e[2]
      finally:
        yield async.Sync(ctx.flush_a())
      yield async.Result(result)
    
    funval = valtool.Hasher().eat(fun_a).digest()
    view = _View(me, par, argmap)
    log = yield async.Sync(me._logdb.memo_a(funval, view, calc_a))
    yield async.Result(log)
  
  def memo_a(me, fun_a, argroot, argmode=lambda x: ArgMode.group_hashed):
    assert argroot is not None
    if isinstance(argroot, dict):
      argmap = lambda x,up: argroot.get(x, None)
    else:
      argmap = lambda x,up: argroot(x)
    
    log = yield async.Sync(me._memo_a(argmode, None, fun_a, argmap))
    yield async.Result(log.result()) # will throw if fun_a did, but thats ok
  
  def search_a(me, funtest):
    return me._logdb.search_a(funtest)

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
        changed = False
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
            changed = True
          elif row is None and new is not None:
            val = valtool.pack(new)
            cur.execute('insert into stash(hk0,hk1,val) values(?,?,?)', (hk0,hk1,buffer(val)))
            changed = True
          elif old is not new:
            val = valtool.pack(new)
            cur.execute('update stash set val=? where hk0=? and hk1=?', (buffer(val),hk0,hk1))
            changed = True
        if changed:
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
  
  def _hash_input_a(me, inp):
    ans = yield async.Sync(me._oven.query_a([inp]))
    yield async.Result(ans[inp])
  
  def _hash_inputs_a(me, inps):
    return me._oven.query_a(inps)
  
  def _arg(me, x):
    if x not in me._argmemo:
      me._argmemo[x] = me._argmap(x, lambda x: me._par._arg(x))
    return me._argmemo[x]
  
  def _tagkey_a(me, tag, key):
    if tag == _tag_inp:
      h = yield async.Sync(me._oven.query_a((key,)))
      yield async.Result(h[key])
    else:
      yield async.Result(me._arg_tagkey(tag, key))
  
  def _arg_tagkey(me, tag, key):
    if tag == _tag_arg:
      return me._arg(key)
    elif tag == _tag_argh:
      return valtool.Hasher().eat(me._arg(key)).digest()
    elif tag in (_tag_args_wip, _tag_argsh_wip):
      return dict((x,me._arg(x)) for x in key)
    elif tag == _tag_args_db:
      return tuple(me._arg(x) for x in key)
    elif tag == _tag_argsh_db:
      return valtool.Hasher().eatseq(me._arg(x) for x in key).digest()
    else:
      assert False

class _Context(_View):
  def __init__(me, oven, argmode, par, argmap, log):
    super(_Context, me).__init__(oven, par, argmap)
    me._argmode = argmode
    me._log = log
    me._inpset = set()
    me._inphold = []
    me._argset = set()
    me._outfs = []
  
  def input(me, x):
    x = me._oven.host().canonify(x)
    if x not in me._inpset:
      p = me._oven.host().unlift_file(x)
      if p is None or not me._oven._is_outfile(p):
        me._inpset.add(x)
        me._inphold.append(x)
    return x
  
  def inputs(me, xs):
    for x in xs:
      me.input(x)
    return xs
  
  def infile(me, path):
    x = me._oven.host().lift_file(path)
    x = me._oven.host().canonify(x)
    if x not in me._inpset:
      if not me._oven._is_outfile(path):
        me._inpset.add(x)
        me._inphold.append(x)
    return path
  
  def infiles(me, paths):
    for p in paths:
      me.infile(p)
    return paths
  
  def flush_a(me):
    if len(me._inphold) > 0:
      h = yield async.Sync(me._hash_inputs_a(me._inphold))
      for x in me._inphold:
        me._log.add(_tag_inp, x, h[x])
      del me._inphold[:]
  
  def outfile_a(me, path):
    yield async.Sync(me.flush_a())
    opath, o = yield async.Sync(me._oven._outfile_a(path))
    me._outfs.append(o)
    yield async.Result(opath)
  
  def __getitem__(me, x):
    y = me._arg(x)
    if x not in me._argset:
      me._argset.add(x)
      tag = _argmode_wip_tag[me._argmode(x)]
      if tag == _tag_arg:
        key = x
        val = y
      elif tag == _tag_argh:
        key = x
        val = valtool.Hasher().eat(y).digest()
      elif tag in (_tag_args_wip, _tag_argsh_wip):
        key = (x,)
        val = {x: y}
      else:
        assert False
      me._log.add(tag, key, val)
    return y
  
  def args(me, xs):
    ys = {}
    xst = {_tag_arg: [], _tag_args_wip: [], _tag_argh: [], _tag_argsh_wip: []}
    for x in xs:
      ys[x] = me._arg(x)
      if x not in me._argset:
        me._argset.add(x)
        tag = _argmode_wip_tag[me._argmode(x)]
        xst[tag].append(x)
    
    for tag in (_tag_args_wip, _tag_argsh_wip):
      if len(xst[tag]) > 0:
        xs1 = tuple(xst[tag])
        me._log.add(tag, xs1, dict((x,ys[x]) for x in xs1))
    
    for x in xst[_tag_arg]:
      me._log.add(_tag_arg, x, ys[x])
    
    for x in xst[_tag_argh]:
      me._log.add(_tag_argh, x, valtool.Hasher().eat(ys[x]).digest())
    
    return ys
  
  def argstup(me, *xs):
    a = me.args(xs)
    return tuple(a[x] for x in xs)
  
  def __call__(me, *a, **kw):
    return me.memo_a(*a, **kw)
  
  def memo_a(me, fun_a, argmap=(lambda x,up: up(x))):
    assert argmap is not None
    if isinstance(argmap, dict):
      d = argmap
      argmap = lambda x,up: d[x] if x in d else up(x)
    
    log = yield async.Sync(me._oven._memo_a(me._argmode, me, fun_a, argmap))
    
    # add dependencies from subroutine to caller
    for tag,key,val in log.records():
      if tag == _tag_inp:
        if key not in me._inpset:
          me._inpset.add(key)
          me._log.add(tag, key, val)
      elif tag in (_tag_arg, _tag_argh):
        argmap(key, lambda x: me[x])
      elif tag in (_tag_args_wip, _tag_args_db, _tag_argsh_wip, _tag_argsh_db):
        seen = set()
        def up(x):
          seen.add(x)
          return me._arg(x)
        for x in key:
          argmap(x, up)
        me.args(seen)
      else:
        assert False
    
    yield async.Result(log.result())

_tag_done = 0
_tag_inp = 1
_tag_arg = 2
_tag_argh = 3
_tag_args_wip = 4
_tag_args_db = 5
_tag_argsh_wip = 6
_tag_argsh_db = 7

_argmode_wip_tag = { 
  ArgMode.stored: _tag_arg,
  ArgMode.group_stored: _tag_args_wip,
  ArgMode.hashed: _tag_argh,
  ArgMode.group_hashed: _tag_argsh_wip
}

_tag_keyval_check = {
  _tag_inp: lambda k,v: type(v) is str and len(v) == 16,
  _tag_arg: lambda k,v: True,
  _tag_argh: lambda k,v: type(v) is str and len(v) == 16,
  _tag_args_db: lambda k,v: type(k) is tuple and type(v) is tuple,
  _tag_args_wip: lambda k,v: type(k) is tuple and type(v) is dict,
  _tag_argsh_db: lambda k,v: type(k) is tuple and type(v) is str and len(v) == 16,
  _tag_argsh_wip: lambda k,v: type(k) is tuple and type(v) is dict
}

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
    assert _tag_keyval_check[tag](key, val)
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
    if True:
      h = valtool.Hasher().eat(val).digest()
      if h not in me._valenc:
        h1 = struct.unpack_from("<i", h)[0]
        cur = cxn.cursor()
        cur.execute('select rowid,val from valbag where hash=?', (h1,))
        row = None
        for got in cur.fetchall():
          if valtool.unpack(got[1]) == val:
            row = got[0]
            break
        if row is None:
          v = valtool.pack(val)
          cur.execute('insert into valbag(val,hash) values(?,?)', (buffer(v),h1))
          row = cur.lastrowid
        me._valenc[h] = row
        me._valdec[row] = val
        cur.close()
      return me._valenc[h]
    else:
      return buffer(valtool.pack(val))
  
  def _decode_val(me, cxn, row):
    if True:
      if row not in me._valdec:
        cur = cxn.cursor()
        cur.execute('select val from valbag where rowid=?', (row,))
        val = valtool.unpack(cur.fetchone()[0])
        me._valdec[row] = val
        me._valenc[valtool.Hasher().eat(val).digest()] = row
        cur.close()
      return me._valdec[row]
    else:
      return valtool.unpack(row)
  
  _sizeof_int = struct.calcsize("<i")
  
  def _split_val(me, tag, val):
    assert tag not in (_tag_args_wip, _tag_argsh_wip)
    if tag in (-1, _tag_inp, _tag_argh, _tag_argsh_db): # val is a hash
      a = struct.unpack_from("<i", val)[0]
      b = buffer(val, me._sizeof_int)
    else: # val is object
      val = valtool.pack(val)
      a = struct.unpack_from("<i", valtool.Hasher().raw(val).digest())[0]
      b = buffer(val)
    return a, b
  
  def _merge_val(me, tag, a, b):
    assert tag not in (_tag_args_wip, _tag_argsh_wip)
    if tag in (-1, _tag_inp, _tag_argh, _tag_argsh_db):
      return struct.pack("<i", a) + str(b)
    else:
      return valtool.unpack(b)

  def memo_a(me, funval, view, calc_a):
    # return: _Log
    # calc_a: _Log -> result
    
    #print>>sys.stderr, 'funval=', _bin2hex(funval)
    
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
        tag = -1
        key = None
        while True:
          if tag == _tag_argsh_wip:
            eqproj = lambda x: valtool.Hasher().eat(x).digest()
          else:
            eqproj = lambda x: x
          
          if eqproj(val) != eqproj(wip._vals[ix]):
            #print>>sys.stderr, 'disjoint tag=',tag,'key=',key
            disjoint.add(wip)
            break
          
          if ix == len(wip._tags):
            yield async.Wait(wip._bar.enlist())
          
          err = wip.error()
          if err is not None:
            yield async.Result(wip)
          
          tag = wip._tags[ix]
          key = wip._keys[ix]
          if tag == _tag_done:
            yield async.Result(wip) # this wip computed the value we need
          elif tag == _tag_inp:
            val = wip._vals[ix+1] # FIXME we assume MemoHost so inputs will match, this is bad
          else:
            val = view._arg_tagkey(tag, key)
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
      got = yield async.Sync(me._oven._dbjob(
        lambda cxn, enstab: step(cxn, enstab, par, tag, val)
      ))
      if got is None:
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
        
        # copy log._keys & log._vals so we can modify _tag_args(h) entries
        log_tags = log._tags
        log_keys = []
        log_vals = [log._vals[0]]
        for i in xrange(len(log_tags)):
          tag = log_tags[i]
          if tag in (_tag_args_wip, _tag_argsh_wip):
            val = log._vals[i+1]
            assert type(val) is dict
            val = dict(val)
            log_keys.append(val) # they both get the same, 'key' is only used as a set
            log_vals.append(val)
          else:
            log_keys.append(log._keys[i])
            if tag != _tag_done:
              log_vals.append(log._vals[i+1])
        
        cur = cxn.cursor()
        ixs = range(len(log._tags))
        par, tag = -1, -1
        val = log_vals[0]
        assert val == funval
        
        while len(ixs) > 0:
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
          if tag in (_tag_args_db, _tag_argsh_db):
            val = dict((k,None) for k in key)
            need = len(val)
          
          i = 0
          while True:
            assert i < len(ixs) # possible if an argmode doesn't match, bad user
            ix = ixs[i]
            tag1 = log_tags[ix]
            key1 = log_keys[ix]
            if (tag,tag1) in ((_tag_args_db,_tag_args_wip),(_tag_argsh_db,_tag_argsh_wip)):
              for x in val:
                if x in key1:
                  val[x] = key1.pop(x)
                  need -= 1
              if len(key1) == 0:
                del ixs[i]
              else:
                i += 1
              if need == 0:
                if tag == _tag_argsh_db:
                  val = valtool.Hasher().eatseq(val[x] for x in key).digest()
                else:
                  val = tuple(val[x] for x in key)
                break
            elif tag1 == tag and key1 == key:
              val = log_vals[ix+1]
              del ixs[i]
              break
            else:
              i += 1
          
        try:
          for ix in ixs:
            val_a, val_b = me._split_val(tag, val)
            tag = log_tags[ix]
            key = log_keys[ix]
            if tag != _tag_done:
              val = log_vals[ix+1]
              if tag in (_tag_args_wip, _tag_argsh_wip):
                assert key is val
                tag = {_tag_args_wip:_tag_args_db, _tag_argsh_wip:_tag_argsh_db}[tag]
                key = tuple(sorted(key))
                val = tuple(val[x] for x in key)
                if tag == _tag_argsh_db:
                  val = valtool.Hasher().eatseq(val).digest()
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

  def search_a(me, funtest):
    def find(cxn, enstab, par, partag, test):
      me._ensure_schema(enstab)
      cur = cxn.cursor()

      if test is TestNo:
        rows = ()
      elif isinstance(test, TestEqualAny):
        rows = []
        for val in test.values:
          val_a, val_b = me._split_val(partag, val)
          cur.execute(
            "select rowid,val_a,val_b,tagkey " +
            "from logtrie " +
            "where par=? and val_a=? and val_b=?",
            (par, val_a, val_b))
          rows += cur.fetchall()
      else:
        cur.execute(
          "select rowid,val_a,val_b,tagkey " +
          "from logtrie " +
          "where par=?",
          (par,))
        rows = cur.fetchall()
      
      ans = []
      for row, val_a, val_b, tagkey in rows:
        val = me._merge_val(partag, val_a, val_b)
        m = test(val)
        if m is not MatchNone:
          tag, key = me._decode_val(cxn, tagkey)
          ans.append((row, tag, key, m))
      return ans
    
    oven = me._oven
    query_a = oven.query_a
    
    def untuple_test(test):
      if type(test) in (TestEqualAny, TestNotEqualAll):
        return type(test)(
          tuple(v[0] for v in test.values),
          lambda y: test.next_match((y,))
        )
      else:
        return lambda y: test((y,))
    
    def hashed_test(test, tup):
      if tup:
        hash = lambda xs: valtool.Hasher().eatseq(xs).digest()
      else:
        hash = lambda x: valtool.Hasher().eat(x).digest()
      
      if type(test) is TestEqualAny:
        h2v = dict((hash(v),v) for v in test.values)
        return TestEqualAny(h2v.keys(), lambda h: test(h2v[h]))
      elif type(test) is TestNotEqualAll:
        hs = tuple(hash(v) for v in test.values)
        if tup:
          class T(tuple):
            def __getitem__(me, i):
              raise Exception("you should't be looking at this")
          return TestNotEqualAll(hs, lambda h: test(T()))
        else:
          return TestNotEqualAll(hs, lambda h: test("you should't be looking at this"))
      else:
        assert False
    
    def cont_found_a(fut):
      assert fut is find_futs[0]
      find_futs.popleft()
      if len(find_futs) > 0:
        futs[find_futs[0]] = (cont_found_a, find_futs[0])
      
      for row,tag,key,m in fut.result():
        if tag == _tag_inp:
          fut = yield async.Begin(m.inputs_a((key,), query_a))
          futs[fut] = (cont_input_a, fut, row, tag, key)
        elif tag in (_tag_arg, _tag_args_db, _tag_argh, _tag_argsh_db):
          if tag in (_tag_args_db, _tag_argsh_db):
            test = m.args(key)
            if tag == _tag_argsh_db:
              test = hashed_test(test, True)
          else:
            test = m.args((key,))
            test = untuple_test(test)
            if tag == _tag_argh:
              test = hashed_test(test, False)
          
          fut = yield async.Begin(oven._dbjob(
            (lambda row, tag, test:\
              lambda cxn, enstab: find(cxn, enstab, row, tag, test)
            )(row, tag, test)
          ))
          if len(find_futs) == 0:
            futs[fut] = (cont_found_a, fut)
          find_futs.append(fut)
        else:
          assert tag == _tag_done
          m.result(key)
    
    def cont_input_a(fut, row, tag, key):
      test = fut.result()
      if test is not TestNo:
        test = untuple_test(test)
        fut = yield async.Begin(oven._dbjob(
          lambda cxn, enstab: find(cxn, enstab, row, tag, test)
        ))
        if len(find_futs) == 0:
          futs[fut] = (cont_found_a, fut)
        find_futs.append(fut)
    
    fut = yield async.Begin(oven._dbjob(
      lambda cxn, enstab: find(
        cxn, enstab, -1, -1, hashed_test(funtest, False)
      )
    ))
    find_futs = deque([fut])
    futs = {fut: (cont_found_a, fut)}
    
    while len(futs) > 0:
      fut = yield async.WaitAny(futs)
      cont = futs.pop(fut)
      yield async.Sync(cont[0](*cont[1:]))
