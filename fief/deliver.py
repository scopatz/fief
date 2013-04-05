#!/usr/bin/env python
import os
import sys
import shutil
import subprocess

import async
import fief
import solve

def deliver_a(fief, ifcs):
  """ returns (ifc2pkg, pkg2built) where:
    ifc2pkg: dict that maps interfaces to chosen packages
    pkg2built: dict that maps package to built value
  """
  
  oven = fief.oven
  repo = fief.repo
  procurer = fief.procurer
  
  def less(ifc, a, b):
    return a == fief.preferred_package(ifc)
  
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
  for a in solve.solve(repo, ifcs):
    dont_add = False
    for b in list(least):
      c = compare_soln(a, b)
      if c < 0:
        least.remove(b)
      elif c > 0:
        dont_add = True
    if not dont_add:
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
  barrier = async.Future()
  
  def procure_and_build_a(pkg):
    pobj = repo.package(pkg)
    src = pobj.source()
    rest = yield async.Sync(procurer.begin_a(src))
    
    # stall until all futures are created
    yield async.Wait(barrier)
    
    # wait for all dependencies to build
    dep_built = {}
    for dep in pkg_deps.get(pkg, ()):
      dep_built[dep] = yield async.Wait(pkg2fut[dep])
    
    # time to build
    def args(x):
      if x == 'pkg':
        return pkg
      elif type(x) is tuple and len(x)==2:
        if x[0]=='implementor':
          return soln.get(x[1])
        elif x[0]=='option':
          return fief.option(pkg, x[1])
        else:
          return None
      elif type(x) is tuple and len(x)==3:
        if x[0]=='deliverable':
          return repo.package(x[2]).deliverable(x[1], dep_built[x[2]])
        else:
          return None
      else:
        return None
    
    builder_a = repo.package(pkg).builder()
    opts = lambda x: fief.option(pkg, x)
    opts.__valtool_ignore__ = True
    
    def build_a(ctx):
      path, cleanup = yield async.Sync(rest(ctx))
      try:
        delvs = yield async.Sync(builder_a(ctx, pkg, path, opts))
      finally:
        cleanup()
      yield async.Result(delvs)
    
    built = yield async.Sync(oven.memo_a(build_a, args))
    yield async.Result(built)
  
  # launch each package
  for pkg in pkg_list:
    fut = yield async.Begin(procure_and_build_a(pkg))
    fut2pkg[fut] = pkg
    pkg2fut[pkg] = fut
  barrier.finish() # done creating futures
  
  # wait for all packages
  for f in fut2pkg:
    yield async.Wait(f)
  
  yield async.Result((soln, dict(
    (pkg, fut.result()) for pkg,fut in pkg2fut.items()
  )))
