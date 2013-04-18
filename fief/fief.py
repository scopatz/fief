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
    me._implied = conf.get('implied', lambda x,on: False)
    me.packages = conf.get('packages', {})
    
    me.procurer = procurer.Procurer(os.path.join(me._path_stash, 'procured'))
    me.oven = bake.Oven(bake.MemoHost(bake.FileHost), os.path.join(me._path_stash, 'oven'))
    
    pkg_ifx = {}
    for pkg,pobj in me.packages.iteritems():
      pkg_ifx[pkg] = yield async.Sync(pobj.implements_a(me.oven))
    
    me.repo = repository.Repo(pkg_ifx)
    
    yield async.Result(me)
  
  def default_interfaces(me):
    return me._deft_ifcs
  
  def preferred_packages(me, ifc, pkg_ok=lambda p:True):
    # this is wrong, but works for now
    pref = me._pref
    for some in me.repo.walk_above(ifc):
      ps = set()
      for i in some:
        p = pref(i)
        if pkg_ok(p):
          ps.add(p)
      if len(ps) > 0:
        return ps
    return ()
  
  def option(me, pkg, x):
    return me._opt(pkg, x)
  
  def implicate(me, ifcs):
    implied = me._implied
    ifcs = set(ifcs)
    sucs = {}
    more = me.repo.interfaces()
    while len(more) > 0:
      more0 = more
      more = []
      for x in more0:
        if x not in ifcs:
          def spy(y):
            sucs[y] = sucs.get(y, set())
            sucs[y].add(x)
            return y in ifcs
          if implied(x, spy):
            ifcs.add(x)
            more.extend(sucs.get(x,()))
    return ifcs
