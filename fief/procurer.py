import os
import sys
import urllib
import time
import re
from hashlib import md5
from base64 import urlsafe_b64encode

import async

def canonify(rsrc):
  if isinstance(rsrc, basestring):
    if re.match('(https?|s?ftp)://', rsrc) is not None:
      return [('url','tarball',rsrc)]
    else:
      return [('tarball', rsrc)]
  elif isinstance(rsrc, tuple) and len(rsrc) > 0 and isinstance(rsrc[0], basestring):
    return [rsrc]
  else:
    xs = []
    for x in rsrc:
      xs += canonify(x)
    return xs

class Procurer(object):
  def __init__(me, stash_path, find_file):
    me._stash = stash_path
    me._find = find_file
    me._maxlive = 8
    me._live = 0
    me._bar = async.Barrier()
  
  def procure_a(me, ctx, rsrc):
    """returns (path,cleanup)"""
    for x in canonify(rsrc):
      got = yield async.WaitFor(_procure[x[0]](me, ctx, *x[1:]))
      if got is not None:
        yield async.Result(got)
    raise Exception("Failed to acquire resource %r." % rsrc)
  
  def download_a(me, url):
    def localize(url):
      name = os.path.split(url)[-1]
      h = urlsafe_b64encode(md5(url).digest())
      return os.path.join(me._stash, name + '-' + h)
    locf = localize(url)
    
    if not os.path.exists(locf):
      def task():
        try:
          def hook(nb, bsz, fsz):
            if nb == 0:
              sys.stderr.write('downloading {0} ...\n'.format(url))
          urllib.urlretrieve(url, locf, hook)
          got = locf
          sys.stderr.write('finished    {0}\n'.format(url))
        except urllib.ContentTooShort, e:
          got = None
        return got
      
      while me._live == me._maxlive:
        yield async.WaitFor(me._bar)
      me._live += 1
      got = yield async.WaitFor(task)
      me._live -= 1
      me._bar.fire_one()
    
    yield async.Result(got)


_procure = {} # procuring returns either (path,cleanup) or None

def _procure_url_a(me, ctx, subkind, url):
  f = yield async.WaitFor(me.download_a(url))
  if f is None:
    yield async.Result(None)
  got = yield async.WaitFor(_procure[subkind](ctx, f))
  yield async.Result(got)

_procure['url'] = _procure_url_a

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

_procure['tarball'] = _procure_tarball_a
