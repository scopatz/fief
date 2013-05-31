#!/usr/bin/env python
import binascii
import os
import sys
import shutil
import subprocess

import async
import bake
import easy
import fief
import repository
import solve
import valtool

Imp = repository.Imp

class SolutionError(Exception):
  pass

def deliver_a(fief, ifcs, lazy=False):
  """
  When lazy=True, returns (ifc2pkg, will_build) where:
    ifc2pkg: dict that maps interfaces to chosen packages
    will_build: set of packages that will require building
    
  When lazy=False, returns (ifc2pkg, delv) where:
    ifc2pkg: dict that maps interfaces to chosen packages
    delv: (ifc,what)->deliverable -- lambda to retrieve deliverables
  """
   
  def slim_pref(ifc, pkgs):
    return [p for p in [fief.preferred_package(ifc)] if p is not None and p in pkgs]
  
  soln = None # this will eventually be the used solution
  slim_soln = _unique_soln(fief, solve.solve(fief.repo, ifcs, slim_pref, fief.implied))
  
  @_memoize(None)
  def package_builder(pkg):
    pobj = fief.packages[pkg]
    kw = {
      'procurer': fief.procurer,
      'pkg': pkg,
      'src': pobj.source(),
      'builder_a': pobj.builder(),
      'opts': lambda pkg,x: fief.option(pkg, x)
    }
    kw['opts'].__valtool_ignore__ = True
    return _package_memo_build(**kw)
  
  def argmode(x):
    if type(x) is tuple and len(x)>1 and x[0]=='implementor':
      return bake.ArgMode.group_stored
    else:
      return bake.ArgMode.group_hashed
  
  def argget(x):
    if type(x) is tuple and len(x)>1:
      if x[0]=='builder':
        return package_builder(x[1]) if x[1] in fief.packages else None
      elif x[0]=='deliverer':
        return fief.packages[x[1]].deliverer() if x[1] in fief.packages else None
      elif x[0]=='env':
        return os.environ.get(x[1])
      elif x[0]=='implementor':
        return soln.get(x[1])
      elif x[0]=='option':
        return fief.option(x[1], x[2])
      elif x[0]=='pkg_ifc_buildreqs':
        return fief.repo.pkg_ifc_buildreqs(x[1], x[2])
      elif x[0]=='pkg_ifc_runreqs':
        return fief.repo.pkg_ifc_runreqs(x[1], x[2])
      elif x[0]=='pkg_implements':
        return fief.repo.pkg_implements(x[1])
      else:
        return None
    else:
      return None
  
  # search memo cache for all built packages
  def argstest(soln, xs, nextm):
    if any(type(x) is tuple and len(x)>1 and x[0]=='implementor' for x in xs):
      return nextm # == lambda x: nextm(x) -- this means match anything
    else:
      return bake.TestEqualAny((tuple(argget(x) for x in xs),), nextm)
  
  def argmerge(soln0, xys):
    soln1 = dict(soln0)
    for x,y in xys.iteritems():
      if type(x) is tuple and len(x)>1 and x[0]=='implementor':
        soln1[x[1]] = y
    return soln1
  
  bldr2pkg = dict((package_builder(p),p) for p in fief.packages)
  found = []
  yield async.Sync(fief.oven.search_a(
    bake.TestEqualAny(
      tuple(package_builder(p) for p in fief.packages),
      lambda bldr: bake.MatchArgs(
        argstest,
        lambda soln,built: found.append((bldr2pkg[bldr], soln)),
        {}, argmerge
      )
    )
  ))
  
  h2soln = {}
  @_memoize(id)
  def soln_hash(soln):
    h = valtool.Hasher().eat(soln).digest()
    h = binascii.hexlify(h)
    if h not in h2soln:
      h2soln[h] = soln
    return h
  
  def soln_subsumes(a, b):
    for x in b:
      if a.get(x) != b[x]:
        return False
    return True
  
  @_memoize(id, None)
  def soln_fragment(soln, pkg):
    more = list(i for i in fief.repo.pkg_implements(pkg) if soln.get(i)==pkg)
    frag = set(more)
    while len(more) > 0:
      more0 = more
      more = []
      for a in more0:
        on = (b for b in fief.repo.pkg_implements(soln[a]) if soln.get(b)==soln[a])
        reqs = fief.repo.pkg_ifcs_requires(soln[a], on)
        for req in reqs:
          if req not in frag:
            frag.add(req)
            more.append(req)
    return dict((i,soln[i]) for i in frag)
  
  # build a fat repo with dummy packages representing those already built
  fat_pkgs = {}
  for pkg,soln in found:
    # only create a fat package if it subsumes the slim solution
    if soln_subsumes(soln, soln_fragment(slim_soln, pkg)):
      solnh = soln_hash(soln_fragment(soln, pkg))
      pkg_imps = fief.repo.pkg_implements(pkg)
      imps = frozenset(i for i in pkg_imps if soln[i]==pkg)
      breqs = fief.repo.pkg_ifcs_buildreqs(pkg, imps)
      breq_slims = [('slim',i) for i in breqs]
      breq_fats = set(soln[i] for i in breqs)
      breq_fats = [('fat',p,soln_hash(soln_fragment(soln,p))) for p in breq_fats]
      rreqs = fief.repo.pkg_ifcs_runreqs(pkg, imps)
      rreqs = [('slim',i) for i in rreqs]
      
      fat_pkgs['fat',pkg,solnh] = {
        ('fat',pkg,solnh): Imp(
          subsumes=(('slim',i) for i in fief.repo.ifcs_subsets(imps)),
          buildreqs=breq_slims + breq_fats,
          runreqs=rreqs
        )
      }
  
  for pkg in fief.packages:
    solnh = soln_hash(soln_fragment(slim_soln, pkg))
    if ('fat',pkg,solnh) not in fat_pkgs:
      imps_slim = {}
      for i,imp in fief.repo.pkg_implements(pkg).iteritems():
        imps_slim['slim',i] = Imp(
          subsumes=(('slim',i) for i in imp.subsumes),
          buildreqs=(('slim',i) for i in imp.buildreqs),
          runreqs=(('slim',i) for i in imp.runreqs)
        )
      fat_pkgs['slim',pkg] = imps_slim

  fat_repo = repository.Repo(fat_pkgs)
  fat_ifcs = set(('slim',i) for i in ifcs)
  
  def fat_pref(ifc, pkgs):
    assert ifc[0]=='slim'
    ifc = ifc[1]
    fav = fief.preferred_package(ifc)
    def better(a, b):
      if (a[1] == fav) != (b[1] == fav):
        return a[1] == fav
      if a[1] != b[1]:
        return False
      if (a[0]=='fat') != (b[0]=='fat'):
        return a[0]=='fat'
      if a[0]=='slim':
        return False
      return soln_subsumes(h2soln[b[2]], h2soln[a[2]])
    
    best = []
    for p in pkgs:
      if not any(better(b, p) for b in best):
        best = list(b for b in best if not better(p, b))
        best.append(p)
    return best
  
  def fat_implied(x, on):
    return x[0]=='slim' and fief.implied(x[1], lambda y: on(('slim',y)))
  
  try:
    fat_soln = _unique_soln(None, solve.solve(fat_repo, fat_ifcs, fat_pref, fat_implied))
    soln = {}
    will_build = set()
    for i,p in fat_soln.iteritems():
      if i[0]=='slim':
        soln[i[1]] = p[1]
        if p[0]=='slim':
          will_build.add(p[1])
      else:
        for _,i1 in fat_pkgs[p][i].subsumes:
          assert soln.get(i1, p[1]) == p[1]
          soln[i1] = p[1]
  except SolutionError:
    soln = slim_soln
    will_build = set(p for p in slim_soln.itervalues() if ('slim',p) in fat_pkgs)
  
  if lazy:
    yield async.Result((soln, will_build))
  else:
    # not being lazy, actually build
    pkg_list = _topsort_pkgs(fief.repo, soln) # packages topsorted by dependencies
    
    # preemptively begin procurements in dependency order
    for pkg in pkg_list:
      yield async.Begin(fief.procurer.begin_a(fief.packages[pkg].source()))
    
    # launch all package builds
    pkg2fut = {}
    for pkg in pkg_list:
      bldr = package_builder(pkg)
      pkg2fut[pkg] = yield async.Begin(fief.oven.memo_a(bldr, argget, argmode))
    
    # wait for all packages
    builts = {}
    for pkg,fut in pkg2fut.iteritems():
      builts[pkg] = yield async.Wait(fut)
    
    yield async.Result((soln, easy.deliverabler(fief.packages, soln, builts)))

def _unique_soln(fief, solver):
  num = 0
  ambig = {}
  for soln in solver:
    num += 1
    for x in soln:
      ambig[x] = ambig.get(x, set())
      ambig[x].add(str(soln[x]))
      if len(ambig[x]) > 1:
        break
  
  if num != 1:
    if fief is not None:
      if num > 1:
        msg = "Package selection for the following interface(s) is ambiguous:"
        msg += '\n  '.join(str(i) + ': ' + ', '.join(ps) for i,ps in ambig.items() if len(ps) > 1)
        raise SolutionError(msg)
      else:
        empt = [i for i in fief.repo.interfaces() if len(fief.repo.ifc_implementors(i)) == 0]
        msg = "No package solution could be found."
        if len(empt) > 0:
          msg += "  The following interfaces have no implementing packages: " + ", ".join(empt)
        raise SolutionError(msg)
    else:
      raise SolutionError()
  
  return soln

def _memoize(*ps):
  def decorate(f):
    m = {}
    def g(*xs):
      pxs = tuple((ps[i](xs[i]) if ps[i] is not None else xs[i]) for i in xrange(len(xs)))
      if pxs not in m:
        m[pxs] = f(*xs)
      return m[pxs]
    return g
  return decorate

def _topsort_pkgs(repo, soln):
  pkg_deps = {} # package to package dependencies, not transitively closed
  for ifc,pkg in soln.iteritems():
    pkg_deps[pkg] = pkg_deps.get(pkg, set())
    pkg_deps[pkg].update(soln[req] for req in repo.pkg_ifc_requires(pkg, ifc))
  
  pkg_list = [] # packages topsorted by dependencies
  def topsort(pkgs):
    for pkg in pkgs:
      if pkg not in pkg_list:
        topsort(pkg_deps.get(pkg, ()))
        assert pkg not in pkg_list
        pkg_list.append(pkg)
  topsort(pkg_deps)
  
  return pkg_list

def _package_memo_build(procurer, pkg, src, builder_a, opts):
  assert opts.__valtool_ignore__
  assert procurer.__valtool_ignore__
  
  def build_a(ctx):
    # wait for all dependency packages to build before we untar source
    deps = easy.dependent_pkgs(ctx, pkg)
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

        def option_soft(me, x):
          return opts(pkg, x)
        
        def option_hard(me, x):
          return ctx['option',pkg,x]

      built = yield async.Sync(builder_a(WrapCtx()))
    finally:
      cleanup()
    yield async.Result(built)
  
  return build_a
