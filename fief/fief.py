import os
import sys
import shutil

import async
import bake
import envdelta
import procurer
import repository

Cmd = bake.Cmd
EnvDelta = envdelta.EnvDelta
ifc = repository.ifc
PackageScript = repository.PackageScript

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
    path = os.path.split(path)[0]
  
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
    me._opts = conf.get('options', lambda pkg,x: None)
    me._pkgs = conf.get('packages', {})
    
    me.procurer = procurer.Procurer(os.path.join(me._path_stash, 'procured'))
    me.oven = bake.Oven(bake.MemoHost(bake.FileHost_a), os.path.join(me._path_stash, 'oven'))
    me.repo = yield async.Sync(repository.Repo.new_a(me.oven, me._pkgs))
    
    yield async.Result(me)
  
  def preferred_package(me, ifc):
    return me._prefs.get(ifc, None)
  
  def option(me, pkg, x):
    return me._opts.get((pkg, x))
