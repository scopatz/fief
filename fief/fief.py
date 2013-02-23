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
  def __init__(me, conf_path=default_conf_path()):
    conf = {}
    execfile(conf_path, conf, conf)
    me._path_stash = conf['stash']
    me._path_down = 
    me._deft_ifcs = conf.get('interfaces', frozenset())
    me._prefs = conf.get('preferences', {})
    me._opts = conf.get('options', lambda x,y: (None, False))
    me._pkgs = conf.get('packages', {})
    
    me.oven = bake.Oven(bake.MemoHost(bake.FileHost_a), os.path.join(me._path_stash, 'oven'))
    me.downloader = downloader.Downloader(os.path.join(me._path_stash, 'down'))
    me._repo = None
  
  def repo_a(me):
    if me._repo is None:
      me._repo = repository.Repo()
      yield async.WaitFor(me._repo.init_a(me.oven, me._pkgs))
    yield async.Result(me._repo)
