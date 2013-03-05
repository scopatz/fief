import os
import sys
import shutil

import async

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

def procure_a(fief, ctx, src):
  """returns (path,cleanup)"""
  for x in canonify_source(src):
    got = yield async.WaitFor(_procure_source[x[0]](fief, ctx, *x[1:]))
    if got is not None:
      yield async.Result(got)
  raise Exception("Failed to acquire source %r." % src)

_prime_source {}
_procure_source = {} # procuring returns either (path,cleanup) or None

def _prime_url_a(fief, subkind, url):
  f = yield async.WaitFor(fief.download_a(url))
  yield async.Result(f)

_prime_source['url'] = _prime_url_a

def _procure_url_a(fief, ctx, primed, subkind, url):
  if primed is None:
    yield async.Result(None)
  got = yield async.WaitFor(_procure[subkind](ctx, primed))
  yield async.Result(got)

_procure_source['url'] = _procure_url_a

_prime_source['tarball'] = lambda fief,path: None

def _procure_tarball_a(fief, ctx, primed, path):
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

