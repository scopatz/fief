#!/usr/bin/env python
import os
import sys
import shutil
import subprocess

import async
import easy
import fief
import solve

def deliver_a(fief, ifcs, lazy=False):
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
  
  assert not lazy
  
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
  
  def memoize(f):
    m = {}
    def g(*x):
      if x not in m:
        m[x] = f(*x)
      return m[x]
    return g
  
  @memoize
  def package_builder(pkg):
    pobj = repo.package(pkg)
    kw = {
      'procurer': procurer,
      'pkg': pkg,
      'src': pobj.source(),
      'builder_a': pobj.builder(),
      'opts': lambda x: fief.option(pkg, x)
    }
    kw['opts'].__valtool_ignore__ = True
    return _package_memo_build(**kw)
  
  def argmode(x):
    return bake.ArgMode.group_hashed
  
  def argget(x):
    if type(x) is tuple and len(x)==2:
      if x[0]=='builder':
        return package_builder(x[1])
      elif x[0]=='deliverer':
        return repo.package(x[1]).deliverer()
      elif x[0]=='env':
        return os.environ.get(x[1])
      elif x[0]=='implementor':
        return soln.get(x[1])
      elif x[0]=='option':
        return fief.option(pkg, x[1])
      elif x[0]=='pkg_imps':
        return repo.pkg_imps(x[1])
      else:
        return None
    elif type(x) is tuple and len(x)==3:
      if x[0]=='pkg_ifc_reqs':
        return repo.pkg_ifc_reqs(x[1], x[2])
      else:
        return None
    else:
      return None
  
  # preemptively begin procurements in dependency order
  for pkg in pkg_list:
    yield async.Begin(procurer.begin_a(repo.package(pkg).source()))
  
  # launch all package builds
  fut2pkg = {}
  for pkg in pkg_list:
    bldr = package_builder(pkg)
    fut = yield async.Begin(oven.memo_a(bldr, argget))
    fut2pkg[fut] = pkg
  
  # wait for all packages
  for fut in fut2pkg:
    yield async.WaitAny([fut])
  
  yield async.Result((soln, dict(
    (pkg, fut.result()) for fut,pkg in fut2pkg.items()
  )))

def _package_memo_build(procurer, pkg, src, builder_a, opts):
  assert opts.__valtool_ignore__
  assert procurer.__valtool_ignore__
  
  def build_a(ctx):
    # wait for all dependency packages to build before we untar source
    deps = easy.dependencies(ctx, pkg)
    for dep in deps:
      yield async.Sync(ctx.memo_a(ctx['builder',dep]))
    
    # procure our source
    site, cleanup = yield async.Sync(procurer.procure_a(ctx, src))
    
    # now build
    try:
      class WrapCtx(object):
        package = pkg
        source = site
        def __getattr__(me, x):
          return getattr(ctx, x)
        def __getitem__(me, x):
          return ctx[x]
        def option(me, x):
          return opts(x)

      built = yield async.Sync(builder_a(WrapCtx()))
    finally:
      cleanup()

    yield async.Result(built)
  
  return build_a
