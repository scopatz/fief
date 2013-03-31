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

class Procurer(object):
  def __init__(me, stash_path):
    me.maxlive = 8
    me._stash = stash_path
    me._live = 0
    me._bar = async.Barrier()
  
  def _download_a(me, url):
    """downloads url into the stash_path if it isn't there already.
    returns path into stash_path if successful else None.
    """
    def localize(url):
      name = os.path.split(url)[-1]
      h = urlsafe_b64encode(md5(url).digest())
      return os.path.join(me._stash, name + '-' + h)
    
    locf = localize(url)
    _ensure_dirs(locf)
    
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
      got = yield async.Sync(task)
    else:
      got = locf
    yield async.Result(got)
  
  def begin_a(me, src):
    """returns async lambda ctx ~> (path,cleanup)"""
    for x in canonify_source(src):
      while me._live == me.maxlive:
        yield async.Sync(me._bar)
      me._live += 1
      got = yield async.Sync(_begin[x[0]](me, *x[1:]))
      me._live -= 1
      me._bar.fireone()
      if got is not None:
        yield async.Result(got)
    raise Exception("Failed to acquire source %r." % src)

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

