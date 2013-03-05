import os
import sys
import shutil

import async
import bake
import downloader
import respository

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
  @classmethod
  def new_a(cls, conf_path=default_conf_path()):
    me = cls()

    conf = {}
    execfile(conf_path, conf, conf)
    me._path_stash = conf['stash']
    me._deft_ifcs = conf.get('interfaces', frozenset())
    me._prefs = conf.get('preferences', {})
    me._opts = conf.get('options', lambda x,y: (None, False))
    me._pkgs = conf.get('packages', {})
    
    me._down = downloader.Downloader(os.path.join(me._path_stash, 'down'))

    me.oven = bake.Oven(bake.MemoHost(bake.FileHost_a), os.path.join(me._path_stash, 'oven'))
    me.repo = yield async.WaitFor(repository.Repo.new_a(me.oven, me._pkgs))
    
    yield async.Result(me)
  
  def download_a(me, url):
    return me._down.download_a(url)
