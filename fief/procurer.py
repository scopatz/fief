from base64 import urlsafe_b64encode
from hashlib import md5
import os
import re
import sys
import shutil
import tempfile
import urllib

import async
import bake

def _ensure_dirs(path):
  d = os.path.split(path)[0]
  if not os.path.exists(d):
    os.makedirs(d)

def canonify_source(src):
  if src is None:
    return []
  elif isinstance(src, basestring):
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

class Procurer(object):
  __valtool_ignore__ = True
  
  def __init__(me, stash_path):
    me._pool = async.Pool(size=4)
    me._stash = stash_path
    me._downing = {} # maps url to Future
    me._lock = async.Lock()
  
  def _download_a(me, url):
    def a():
      """downloads url into the stash_path if it isn't there already.
      returns path into stash_path if successful else None.
      """
      def localize(url):
        name = os.path.split(url)[-1]
        h = urlsafe_b64encode(md5(url).digest())
        return os.path.join(me._stash, h + '-' + name)
      
      locf = localize(url)
      _ensure_dirs(locf)
      
      if not os.path.exists(locf):
        @async.assign_pool(me._pool)
        def task():
          try:
            def hook(nb, bsz, fsz):
              if nb == 0:
                #sys.stderr.write('downloading {0} ...\n'.format(url))
                pass
            sys.stderr.write('downloading {0} ...\n'.format(url))
            urllib.urlretrieve(url, locf, hook)
            got = locf
            sys.stderr.write('finished    {0}\n'.format(url))
          except urllib.ContentTooShort, e:
            got = None
          return got
        got = yield async.Sync(task)
      else:
        got = locf
      yield async.Result(got)
    
    yield async.Wait(me._lock.acquire())
    if url not in me._downing:
      me._downing[url] = yield async.Begin(a())
    me._lock.release()
    got = yield async.Wait(me._downing[url])
    yield async.Result(got)
  
  def begin_a(me, src):
    """returns async lambda ctx ~> (path,cleanup)"""
    src = canonify_source(src)
    for x in src:
      got = yield async.Sync(_begin[x[0]](me, *x[1:]))
      if got is not None:
        yield async.Result(got)

    if len(src) > 0:
      raise Exception("Failed to acquire source %r." % src)
    else:
      def rest_a(ctx):
        yield async.Result((None, lambda:None))
      yield async.Result(rest_a)
  
  def procure_a(me, ctx, src):
    """returns (path,cleanup)"""
    rest = yield async.Sync(me.begin_a(src))
    site, cleanup = yield async.Sync(rest(ctx))
    yield async.Result((site, cleanup))

_begin = {} # a begin method asynchronously returns either ctx~>(path,cleanup) or None

def _begin_url_a(me, subkind, url):
  f = yield async.Sync(me._download_a(url))
  if f is None:
    yield async.Result(None)
  else:
    got = yield async.Sync(_begin[subkind](me, f))
    yield async.Result(got)

_begin['url'] = _begin_url_a

def _begin_tarball_a(me, path):
  if not os.path.exists(path):
    yield async.Result(None)
  
  def rest_a(ctx):
    exts = {
      '.zip': ('unzip',),
      '.tgz': ('tar', 'xzf'),
      '.tar.xz': ('tar', 'xf'),
      '.tar.gz': ('tar', 'xzf'),
      '.tar.bz2': ('tar', 'xjf'),
      '.tar.gzip': ('tar', 'xzf'),
    }
    rex = '.*(' + '|'.join(e.replace('.','\\.') for e in exts.keys()) + ')$'
    lits = exts[re.match(rex, path).group(1)]
    
    tmpd = tempfile.mkdtemp()
    c = bake.Cmd(ctx)
    c.cwd = tmpd
    c.tag = ctx['pkg']
    if os.name == 'nt':
      path1 = path.split(':',1)[1]
    else:
      path1 = path
    path1 = os.path.abspath(path1)
    c.lit(lits).inf(path1)
    yield async.Sync(c.exec_a())
    
    ls = os.listdir(tmpd)
    if len(ls) == 1:
      top = os.path.join(tmpd, ls[0])
      if not os.path.isdir(top):
        top = tmpd
    else:
      top = tmpd
    
    cleanup = lambda: shutil.rmtree(tmpd)
    yield async.Result((top, cleanup))

  yield async.Result(rest_a)

_begin['tarball'] = _begin_tarball_a

