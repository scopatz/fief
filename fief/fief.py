import os
import sys
import shutil

import async
import bake
import envdelta
import procurer
import repository

class Fief(object):
  @classmethod
  def new_a(cls, rcpath):
    assert rcpath is not None
    
    me = cls()
    
    conf = {'__file__': os.path.abspath(rcpath)}
    execfile(rcpath, conf, conf)
    me._path_stash = conf['stash']
    me._deft_ifcs = frozenset(conf.get('interfaces', frozenset()))
    me._prefs = conf.get('preferences', {})
    me._opts = conf.get('options', lambda pkg,x: None)
    me.packages = conf.get('packages', {})
    
    me.procurer = procurer.Procurer(os.path.join(me._path_stash, 'procured'))
    me.oven = bake.Oven(bake.MemoHost(bake.FileHost), os.path.join(me._path_stash, 'oven'))
    
    pkg_ifx = {}
    for pkg,pobj in me.packages.iteritems():
      pkg_ifx[pkg] = yield async.Sync(pobj.interfaces_a(me.oven))
    
    me.repo = repository.Repo(pkg_ifx)
    
    yield async.Result(me)
  
  def default_interfaces(me):
    return me._deft_ifcs
  
  def preferred_package(me, ifc):
    return me._prefs.get(ifc, None)
  
  def option(me, pkg, x):
    return me._opts.get((pkg, x))
