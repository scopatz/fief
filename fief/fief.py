import os
import sys
import shutil

import async
import bake
import downloader
import respository

def canonify_source(src):
  if isinstance(src, basestring):
    if re.match('(https?|s?ftp)://', src) is not None:
      return [('url','tarball',src)]
    else:
      return [('tarball', src)]
  elif isinstance(src, tuple) and len(src) > 0 and isinstance(src[0], basestring):
    return [src]
  else:
    xs = []
    for x in src:
      xs += canonify_source(x)
    return xs

def default_conf_path():
  path = os.getcwd()
  root = os.path.splitdrive(path)[0] + os.path.sep
  rellocs = ['fiefconf.py', 'fiefconf', 
             os.path.join('.config', 'fiefconf.py'),
             os.path.join('.config', 'fiefconf'),]
  while True:
    for relloc in rellocs:
      p = os.path.join(path, relloc)
      if os.path.isfile(p):
        return p
    if path == root:
      break
    path = os.path.split(path)
  
  return None

class Fief(object):
  def __init__(me, conf_path=default_conf_path()):
    conf = {}
    execfile(conf_path, conf, conf)
    me._path_stash = conf['stash']
    me._path_oven = os.path.join(me._path_stash, 'oven')
    me._path_down = os.path.join(me._path_stash, 'down')
    me._deft_ifcs = conf.get('interfaces', frozenset())
    me._prefs = conf.get('preferences', {})
    me._opts = conf.get('options', lambda x,y: (None, False))
    me._pkg_defs = conf.get('packages', {})
    me._oven = bake.Oven(bake.MemoHost(bake.FileHost_a), me._path_oven)
    me._repo = None
  
  def repo_a(me):
    if me._repo is None:
      me._repo = repository.Repo()
      me._repo.init_a(me._oven
    return me._repo
  def procure_a(me, ctx, src):
    """returns (path,cleanup)"""
    for x in canonify_source(src):
      got = yield async.WaitFor(_procure_source[x[0]](me, ctx, *x[1:]))
      if got is not None:
        yield async.Result(got)
    raise Exception("Failed to acquire source %r." % src)
  
  def deliver_a(me):
    pass


_procure_source = {} # procuring returns either (path,cleanup) or None

def _procure_url_a(me, ctx, subkind, url):
  f = yield async.WaitFor(me.download_a(url))
  if f is None:
    yield async.Result(None)
  got = yield async.WaitFor(_procure[subkind](ctx, f))
  yield async.Result(got)

_procure_source['url'] = _procure_url_a

def _procure_tarball_a(me, ctx, path):
  if not os.path.exists(path):
    return None
  
  exts = {
    '.tgz'     : ('tar', 'xzf'),
    '.tar.gz'  : ('tar', 'xzf'),
    '.tar.gzip': ('tar', 'xzf'),
    '.tar.bz2' : ('tar', 'xjf')
  }
  rex = '.*(' + '|'.join(e.replace('.','\\.') for e in exts.keys()) + ')$'
  lits = exts[re.match(rex, path).group(1)]
  
  tmpd = tempfile.mkdtemp()
  c = bake.Cmd(ctx)
  c.cwd = tmpd
  c.tag = ctx['pkg']
  if os.name == 'nt':
    path = path.split(':',1)[1]
  c.lit(lits).inf(path)
  yield async.WaitFor(c.exec_a())
  
  ls = os.listdir(tmpd)
  if len(ls) == 1:
    top = os.path.join(tmpd, ls[0])
    if not os.path.isdir(top):
      top = tmpd
  else:
    top = tmpd
  
  cleanup = lambda: shutil.rmtree(tmpd)
  yield async.Result((top, cleanup))

_procure_source['tarball'] = _procure_tarball_a
