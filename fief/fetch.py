import os
import sys
import urllib
import time
import re
from collections import deque
from hashlib import md5
from base64 import urlsafe_b64encode

import async

PROTOCOLS = set(['http', 'https', 'git', 'hg', 'ssh', 'file', 'dummy'])

_actions = {}

def _act_url_a(me, url):
  tar = yield async.WaitFor(me._download_a(rest))
  d, cleanup = yield async.WaitFor(_actions['file'](f))
  return d, cleanup
_acions['url'] = _act_url_a

def _act_tar_a(me, tar):
  m = re.match('(.*)\\.(tgz|tar\\.(gz|bz2))', tar)
  assert m is not None
  
  if tar.endswith('.
def stage_nomemo_a(ctx, pkg):
  """Returns a tuple (path, cleanup)"""
  repo = 'repo'
  p = packages[pkg]
  ball = p.source
  if ball.endswith('.tgz'):
    ndots = 1
  elif ball.endswith('.tar.gz') or ball.endswith('.tar.bz2'):
    ndots = 2
  name = os.path.split(ball)[-1].rsplit('.', ndots)[0]
  bld = tempfile.mkdtemp()
  if os.name == 'nt':
    ball = ball.split(':', 1)[-1]

  c = bake.Cmd(ctx)
  c.cwd = bld
  c.tag = pkg
  if ball.endswith('.tar.gz') or ball.endswith('.tgz'):
    c.lit('tar', 'xzf').inf(ball)
  elif ball.endswith('.tar.bz2'):
    c.lit('tar', 'xjf').inf(ball)
  yield async.WaitFor(c.exec_a())

  bld2 = os.path.join(bld, name)
  if not os.path.exists(bld2):
    unzipped = os.listdir(bld)
    if 1 == len(unzipped):
      bld2 = os.path.join(bld, unzipped[0]) 

  cleanup = lambda: shutil.rmtree(bld)
  yield async.Result((bld2, cleanup))  
class Fetch(object):
  def __init__(me, stash_path, find_file):
    me._stash = stash_path
    me._find = find_file
    me._maxlive = 8
    me._live = 0
    me._bar = async.Barrier()
  
  def procure(me, rsrc):
    """returns (path,cleanup)"""
    pass
  
  def _canonify(me, rsrc):
    pass
  
  def _download_a(me, url):
    def localize(url):
      name = os.path.split(url)[-1]
      h = urlsafe_b64encode(md5(url).digest())
      return os.path.join(me._stash, name + '-' + h)
    
    loc = localize(url)
    
    if not os.path.exists(loc):
      def task():
        sys.stderr.write('downloading {0} ...\n'.format(url))
        urllib.urlretrieve(url, loc)
        sys.stderr.write('finished    {0}\n'.format(url))
      
      while me._live == me._maxlive:
        yield async.WaitFor(me._bar)
      me._live += 1
      yield async.WaitFor(task)
      me._live -= 1
      me._bar.fire_one()
    
    yield async.Result(loc)
  
def _canonical_resource(rsrc):
  if isinstance(rsrc, basestring):
    if rsrc.startswith('http://'):
      return [('http', rsrc, _url2local(rsrc))]
    elif rsrc.startswith('https://'):
      return [('https', rsrc, _url2local(rsrc))]
    elif rsrc.startswith('git://') or rsrc.startswith('git@') or \
       rsrc.endswith('.git'):
      return [('git', rsrc, os.path.abspath(rsrc))]
    elif rsrc == 'dummy':
      return [('dummy', None, None)]
    else:
      return [('file', rsrc, os.path.abspath(os.path.join('repo', rsrc)))]
      #msg = "protocol not inferred for resource {0!r}"
      #raise ValueError(msg.format(rsrc))
  elif rsrc is None:
    return [('dummy', None, None)]
  elif 3 == len(rsrc) and rsrc[0] in PROTOCOLS:
    return [rsrc]
  else:
    rtn = []
    for r in rsrc:
      rtn += _canonical_resource(r) 
    return rtn

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
