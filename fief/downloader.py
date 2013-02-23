import os
import sys
import urllib
import time
import re
from hashlib import md5
from base64 import urlsafe_b64encode

import async

max_concurrent_download = 8

def _ensure_dirs(path):
  d = os.path.split(path)[0]
  if not os.path.exists(d):
    os.makedirs(d)

class Downloader(object):
  def __init__(me, stash_path):
    me._stash = stash_path
    me._maxlive = max_concurrent_download
    me._live = 0
    me._bar = async.Barrier()
  
  def download_a(me, url):
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
      
      while me._live == me._maxlive:
        yield async.WaitFor(me._bar)
      me._live += 1
      got = yield async.WaitFor(task)
      me._live -= 1
      me._bar.fire_one()
    
    yield async.Result(got)
