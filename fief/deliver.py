#!/usr/bin/env python
import os
import sys
import shutil
import subprocess

import async
import bake
import fief
import procure
import repository
ifc = respository.ifc

def deliver_a(me, fief, ifcs):
  oven = fief.oven
  repo = fief.repo
  procurer = fief.procurer
  
  def less(ifc, a, b):
    return a == conf.preferences.get(ifc)
  
  def compare_soln(a, b):
    a_less, b_less = False, False
    for x in set(a.keys() + b.keys()):
      ax, bx = a.get(x), b.get(x)
      if ax != bx:
        if ax is None or less(x, ax, bx):
          a_less = True
        elif bx is None or less(x, bx, ax):
          b_less = True
    if a_less and not b_less:
      return -1
    if b_less and not a_less:
      return 1
    return 0
  
  least = []
  for a in repo.solve_pkgs(ifcs):
    add_a = False
    for b in list(least):
      c = compare_soln(a, b)
      if c < 0:
        add_a = True
        least.remove(b)
      elif c == 0:
        add_a = True
      else:
        assert not add_a
    if add_a:
      least.append(a)
  
  if len(least) > 1:
    ambig = {}
    for soln in least:
      for x in soln:
        ambig[x] = ambig.get(x, set())
        ambig[x].add(soln[x])
    msg = "Package selection for the following interface(s) is ambiguous:"
    msg += '\n  '.join(i + ': ' + ', '.join(ps) for i,ps in ambig.items() if len(ps) > 1)
    raise Exception(msg)
  elif len(least) == 0:
    empt = [i for i in repo.interfaces() if len(repo.ifc_imps(i)) == 0]
    msg = "No package solution could be found."
    if len(empt) > 0:
      msg += "  The following interfaces have no implementing packages: " + ", ".join(empt)
    raise Exception(msg)
  
  soln = least[0]
  
  pkg_deps = {} # package to package dependencies, not transitively closed
  for ifc,pkg in soln.iteritems():
    pkg_deps[pkg] = pkg_deps.get(pkg, set())
    pkg_deps[pkg].update(soln[req] for req in repo.pkg_ifc_reqs(pkg, ifc))
  
  pkg_list = [] # packages topsorted by dependencies
  def topsort(pkgs):
    for pkg in pkgs:
      if pkg not in pkg_list:
        topsort(pkg_deps.get(pkg, ()))
      if pkg not in pkg_list:
        pkg_list.append(pkg)
  topsort(pkg_deps)
  
  # begin procuring and building
  pkg2fut = {}
  fut2pkg = {}
  bar = async.Future()
  
  def procure_and_build_a(pkg):
    src = repo.package(pkg).source()
    rest = yield async.Sync(procurer.begin_a(src))
    
    # stall until all futures are created
    yield async.Wait(bar)
    
    # wait for all dependencies to build
    dep_delvs = {}
    for dep in pkg_deps.get(pkg, ()):
      dep_delvs[dep] = yield async.Wait(pkg2fut[dep])
    
    # time to build
    def args(x):
      if type(x) is tuple and len(x)==2:
        if x[0]=='interface':
          return soln.get(x[1])
        elif x[0]=='option':
          return conf.option(pkg, x[1])
        else:
          return None
      elif type(x) is tuple and len(x)==3:
        if x[0]=='deliverable':
          return dep_delvs.get(x[2],{}).get(x[1])
        else:
          return None
      else:
        return None
    
    def build_a(ctx):
      path, cleanup = yield async.Sync(rest(ctx))
      try:
        b = repo.package(pkg).builder()
        delvs = yield async.Sync(b(ctx, pkg, path))
      finally:
        cleanup()
      yield async.Result(delvs)
    
    delvs = yield async.Sync(oven.memo_a(bld_a, args))
    yield async.Result(delvs)
  
  # launch each package
  for pkg in pkg_list:
    fut = yield async.Begin(procure_and_build_a(pkg))
    fut2pkg[fut] = pkg
    pkg2fut[pkg] = fut
  bar.finish() # done creating futures
  
  # wait for all packages
  for f in fut2pkg:
    yield async.Wait(f)
  
  yield async.Result(dict((pkg,fut.result()) for pkg,fut in pkg2fut.items()))
