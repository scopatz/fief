#!/usr/bin/env python
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

def deliver_a(fief, ifcs, lazy=False):
  """ returns (ifc2pkg, pkg2built) where:
    ifc2pkg: dict that maps interfaces to chosen packages
    pkg2built: dict that maps package to built value
  """
  
  packages = fief.packages
  oven = fief.oven
  repo = fief.repo
  procurer = fief.procurer
  
  assert not lazy
  
  def memoize(f):
    m = {}
    def g(*x):
      if x not in m:
        m[x] = f(*x)
      return m[x]
    return g
  
  @memoize
  def package_builder(pkg):
    pobj = packages[pkg]
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
    if type(x) is tuple and len(x)>1 and x[0]=='implementor':
      return bake.ArgMode.group_stored
    else:
      return bake.ArgMode.group_hashed
  
  def argget(x):
    if type(x) is tuple and len(x)>1:
      if x[0]=='builder':
        return package_builder(x[1]) if x[1] in packages else None
      elif x[0]=='deliverer':
        return packages[x[1]].deliverer() if x[1] in packages else None
      elif x[0]=='env':
        return os.environ.get(x[1])
      elif x[0]=='implementor':
        return soln.get(x[1])
      elif x[0]=='option':
        return fief.option(pkg, x[1])
      elif x[0]=='pkg_ifc_reqs':
        return repo.pkg_ifc_reqs(x[1], x[2])
      elif x[0]=='pkg_imps':
        return repo.pkg_imps(x[1])
      else:
        return None
    else:
      return None
  
  # search memo cache for all built packages
  def argstest(hist, xs, nextm):
    if any(type(x) is tuple and len(x)>1 and x[0]=='implementor' for x in xs):
      return nextm # == lambda x: nextm(m) -- this means match anything
    else:
      return bake.TestEqualAny((tuple(argget(x) for x in xs),), nextm)
  
  def argstore(hist, x, y):
    if type(x) is tuple and len(x)>1 and x[0]=='implementor':
      hist[x[1]] = y
  
  bldr2pkg = dict((package_builder(p),p) for p in packages)
  found = []
  yield async.Sync(oven.search_a(
    bake.TestEqualAny(
      tuple(package_builder(p) for p in packages),
      lambda bldr: bake.MatchArgs(
        argstest,
        lambda args,built: found.append((bldr2pkg[bldr], args)),
        argstore
      )
    )
  ))
  
  h2soln = {}
  def soln_hash(soln):
    h = valtool.Hasher().eat(soln).digest()
    if h not in h2soln:
      h2soln[h] = soln
    return h
  
  # build a fake repo with dummy packages representing those already built
  def soln_fragment(soln, pkg):
    more = list(i for i in repo.pkg_imps(pkg) if soln.get(i)==pkg)
    frag = set(more)
    while len(more) > 0:
      more0 = more
      more = []
      for a in more0:
        reqs = repo.pkg_ifcs_reqs(soln[a], (b for b in repo.pkg_imps(soln[a]) if soln.get(b)==soln[a]))
        for req in reqs:
          if req not in frag:
            frag.add(req)
            more.append(req)
    return dict((i,soln[i]) for i in frag)
  
  fake_pkgs = {}
  for pkg in packages:
    ifx = {}
    for i,ifc in repo.pkg_imps(pkg).iteritems():
      ifx['real',i] = repository.ifc(
        (('real',i) for i in ifc.subsumes),
        (('real',i) for i in ifc.requires)
      )
    fake_pkgs['real',pkg] = ifx
  
  for pkg,soln in found:
    solnh = soln_hash(soln_fragment(soln, pkg))
    pkg_imps = repo.pkg_imps(pkg)
    imps = frozenset(i for i in pkg_imps if soln[i]==pkg)
    req_pkgs = set(soln[i] for i in repo.pkg_ifcs_reqs(pkg, imps))
    ifx = {('fake',pkg,solnh): repository.ifc(
      subsumes=(('real',i) for i in imps),
      requires=(('fake',p,soln_hash(soln_fragment(soln,p))) for p in req_pkgs)
    )}
    fake_pkgs['fake',pkg,solnh] = ifx
    
  fake_repo = repository.Repo(fake_pkgs)
  fake_ifcs = set(('real',i) for i in ifcs)
  
  def less(ifc, a, b):
    if ifc[0] != 'real':
      print>>sys.stderr, a, b
    assert ifc[0] == 'real'
    if a[0] != b[0]:
      return a[0] == 'fake'
    if a[1] != b[1]:
      pref = fief.preferred_package(ifc[1])
      return a[1] == pref
    assert a[0] == 'fake'
    asoln = h2soln[a[2]]
    bsoln = h2soln[b[2]]
    return all(bsoln.get(x)==y for x,y in asoln.iteritems())
  
  def compare_soln(a, b):
    a_less, b_less = False, False
    for x in set(a.keys() + b.keys()):
      ax, bx = a.get(x), b.get(x)
      if ax != bx:
        if ax is None:
          a_less = True
        elif bx is None:
          b_less = True
        elif less(x, ax, bx):
          a_less = True
        elif less(x, bx, ax):
          b_less = True
    if a_less and not b_less:
      return -1
    if b_less and not a_less:
      return 1
    return 0
  
  def real_soln(soln):
    s1 = {}
    for i,p in soln.iteritems():
      if i[0]=='real':
        s1[i[1]] = p[1]
    return s1

  least = []
  for a in solve.solve(fake_repo, fake_ifcs):
    #print>>sys.stderr, 'cand', a
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
    print>>sys.stderr, 'least', least
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
  
  soln = real_soln(least[0])
  
  pkg_list = _topsort_pkgs(repo, soln) # packages topsorted by dependencies
  
  # preemptively begin procurements in dependency order
  for pkg in pkg_list:
    yield async.Begin(procurer.begin_a(packages[pkg].source()))
  
  # launch all package builds
  fut2pkg = {}
  for pkg in pkg_list:
    bldr = package_builder(pkg)
    fut = yield async.Begin(oven.memo_a(bldr, argget, argmode))
    fut2pkg[fut] = pkg
  
  # wait for all packages
  for fut in fut2pkg:
    yield async.WaitAny([fut])
  
  yield async.Result((soln, dict(
    (pkg, fut.result()) for fut,pkg in fut2pkg.items()
  )))

def _topsort_pkgs(repo, soln):
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
  
  return pkg_list

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
