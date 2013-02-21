import os
import sys
import urllib
import time
import re
from collections import deque
from hashlib import md5
from base64 import urlsafe_b64encode

import async

def canonify_resource(rsrc):
  if isinstance(rsrc, basestring):
    if re.match('https?://', rsrc) is not None:
      return [('url','tarball',rsrc)]
    else:
      return [('tarball', rsrc)]
  elif isinstance(rsrc, tuple) and len(rsrc) > 0 and isinstance(rsrc[0], basestring):
    return [rsrc]
  else:
    xs = []
    for x in rsrc:
      xs += canonify_resource(x)
    return xs

class Fetch(object):
  def __init__(me, stash_path, find_file):
    me._stash = stash_path
    me._find = find_file
    me._maxlive = 8
    me._live = 0
    me._bar = async.Barrier()
  
  def procure(me, ctx, rsrc):
    """returns (path,cleanup)"""
    rsrc = canonify_resource(rsrc)
    for x in rsrc:
      got = _actions[x[0]](me, ctx, *x[1:])
      if got is None:
  
  def _download_a(me, url):
    def localize(url):
      name = os.path.split(url)[-1]
      h = urlsafe_b64encode(md5(url).digest())
      return os.path.join(me._stash, name + '-' + h)
    locf = localize(url)
    
    if not os.path.exists(locf):
      def task():
        try:
          sys.stderr.write('downloading {0} ...\n'.format(url))
          urllib.urlretrieve(url, locf)
          got = loc
        except urllib.ContentTooShort, e:
          got = None
        sys.stderr.write('finished    {0}\n'.format(url))
        return got
      
      while me._live == me._maxlive:
        yield async.WaitFor(me._bar)
      me._live += 1
      got = yield async.WaitFor(task)
      me._live -= 1
      me._bar.fire_one()
    
    yield async.Result(got)


_procure = {} # procuring returns either (path,cleanup) or None

def _procure_url_a(me, ctx, kind, url):
  f = yield async.WaitFor(me._download_a(url))
  if f is None:
    yield async.Result(None)
  got = yield async.WaitFor(_procure[kind](ctx, f))
  yield async.Result(got)

_procure['url'] = _procure_url_a

def _procure_tarball_a(me, ctx, path):
  if not os.path.exists(path):
    return None
  
  exts = {
    '.tgz': ('tar', 'xzf'),
    '.tar.gz': ('tar', 'xzf'),
    '.tar.gzip': ('tar', 'xzf'),
    '.tar.bz2': ('tar', 'xjf')
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

def _init(pkgs):
  for pkg, (rsrc, _) in pkgs.items():
    resources[pkg] = _canonical_resource(rsrc)

def retrieve_http(url, filename, tag=None):
  def hook(nblks, bytes_per_blk, fsize):
    r = min(max(3, int(fsize/1048576)), 1000) 
    totblks = 1 + fsize / bytes_per_blk
    if not (0 == nblks%(totblks/r) or totblks == nblks):
      return 
    msg = '[GET' + ('] ' if tag is None else ': {0}] '.format(tag))
    if nblks == 0:
      msg += 'downloading {0} -> {1}\n'.format(url, filename)
    else:
      msg += '{0:.1%} completed\n'.format(nblks / float(totblks))
    sys.stderr.write(msg)
  
  def retriever():
    try:
      dname = os.path.split(filename)[0]
      if not os.path.exists(dname):
        os.makedirs(dname)
      fname, hdrs = urllib.urlretrieve(url, filename, hook)
      got = True
    except urllib.ContentTooShortError:
      got = False
    return got

  return retriever

retrieve_https = retrieve_http

def retrieve_git(url, filename, tag=None):
  raise RuntimeError('git retrieval not yet implemented')

def retrieve_hg(url, filename, tag=None):
  raise RuntimeError('mercurial retrieval not yet implemented')

def retrieve_ssh(url, filename, tag=None):
  raise RuntimeError('secure shell retrieval not yet implemented')

def retrieve_source_a(pkg):
  glbs = globals()
  rsrcs = resources[pkg]
  got = None
  for proto, url, path in rsrcs:
    if os.path.exists(path):
      got = path
      break
    retriever = glbs['retrieve_' + proto]
    got = yield async.WaitFor(retriever(url, path, pkg))
    if got:
      got = path
      break
  yield async.Result(got)
