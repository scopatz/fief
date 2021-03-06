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
    me._deft_ifcs = frozenset(conf.get('interfaces', ()))
    me._pref = conf.get('preference', lambda ifc: None)
    me._opt = conf.get('option', lambda pkg,x: None)
    me.implied = conf.get('implied', lambda x,on: False)
    me.packages = conf.get('packages', {})
    
    me.procurer = procurer.Procurer(os.path.join(me._path_stash, 'procured'))
    me.oven = bake.Oven(bake.MemoHost(bake.FileHost), os.path.join(me._path_stash, 'oven'))
    
    pkg_ifx = {}
    for pkg,pobj in me.packages.iteritems():
      opts = (lambda pkg: lambda x: me._opt(pkg, x))(pkg)
      pkg_ifx[pkg] = yield async.Sync(pobj.implements_a(opts, me.oven))
    
    me.repo = repository.Repo(pkg_ifx)
    
    yield async.Result(me)
  
  def default_interfaces(me):
    return me._deft_ifcs
  
  def preferred_package(me, ifc):
    return me.repo.choose_least(me.repo.ifc_subsumers(ifc), me._pref)
  
  def option(me, pkg, x):
    return me._opt(pkg, x)
