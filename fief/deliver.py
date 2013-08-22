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

def deliver_a(fief, ifcs, lazy=False):
  """
  When lazy=True, returns (soln, will_build) where:
    soln: solve.Soln
    will_build: set of packages that will require building
    
  When lazy=False, returns (ifc2pkg, delv) where:
    soln: solve.Soln
    delv: (ifc,what)->deliverable -- lambda to retrieve deliverables
  """
   
  def slim_pref(ifc, pkgs):
    p = fief.preferred_package(ifc)
    return p if p in pkgs else None
  
  ifcs = solve.implicate(fief.repo, ifcs, fief.implied)
  
  soln = None # this will eventually be the used solution
  slim_soln = solve.solve(fief.repo, ifcs, slim_pref)
  
  @_memoize(None)
  def node_builder(node):
    kw = {
      'procurer': fief.procurer,
      'node': node,
      'opts': lambda pkg,x: fief.option(pkg, x)
    }
    kw['opts'].__valtool_ignore__ = True
    return _memo_build(**kw)
  
  def argmode(x):
    if type(x) is tuple and len(x)>1 and \
      x[0] in ('_node_imps','_node_soln','_node_pkg'):
      return bake.ArgMode.group_stored
    else:
      return bake.ArgMode.group_hashed
  
  def argget(x):
    if type(x) is tuple and len(x)>0:
      if x[0]=='env':
        return os.environ.get(x[1])
      elif x[0]=='_node_builder':
        return node_builder(x[1])
      elif x[0]=='_pkg_source':
        return fief.packages[x[1]].source() if x[1] in fief.packages else None
      elif x[0]=='_pkg_builder':
        return fief.packages[x[1]].builder() if x[1] in fief.packages else None
      elif x[0]=='_pkg_deliverer':
        return fief.packages[x[1]].deliverer() if x[1] in fief.packages else None
      elif x[0]=='_node_soln':
        return soln.node_soln(x[1])
      elif x[0]=='_node_imps':
        return soln.node_imps(x[1])
      elif x[0]=='_node_pkg':
        return soln.node_pkg(x[1])
      elif x[0]=='_option':
        return fief.option(x[1], x[2])
      else:
        return None
    else:
      return None
  
  if False:
    # search memo cache for all built packages
    def argstest(soln, xs, nextm):
      if any(type(x) is tuple and len(x)>0 and \
        x[0] in ('_node_imps','_node_pkg','_node_soln') \
        for x in xs):
        return nextm # == lambda x: nextm(x) -- this means match anything
      else:
        return bake.TestEqualAny((tuple(argget(x) for x in xs),), nextm)
    
    def argmerge(soln0, xys):
      soln1 = dict(soln0)
      for x,y in xys.iteritems():
        if type(x) is tuple and len(x)>0:
          if x[0]=='_node_imps':
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
      for x in b.ifc2pkg:
        if a.ifc2pkg.get(x) != b[x]:
          return False
      for p in b.pkg2soln:
        if p not in a.pkg2soln or not soln_subsumes(a.pkg2soln[p], b.pkg2soln[p]):
          return False
      return True
    
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
  else:
    soln = slim_soln
    will_build = {}
    for nd in soln.all_nodes():
      p = soln.node_pkg(nd)
      will_build[p] = will_build.get(p,0) + 1
  
  if lazy:
    yield async.Result((soln, will_build))
  else:
    # not being lazy, actually build
    nd_list = soln.all_nodes() # topsorted for us
    pkg_list = []
    for nd in nd_list:
      p = soln.node_pkg(nd)
      if p not in pkg_list:
        pkg_list.append(p)
    
    # preemptively begin procurements in dependency order
    for p in pkg_list:
      yield async.Begin(fief.procurer.begin_a(fief.packages[p].source()))
    
    # launch all node builds
    nd2fut = {}
    for nd in nd_list:
      bldr = node_builder(nd)
      nd2fut[nd] = yield async.Begin(fief.oven.memo_a(bldr, argget, argmode))
    
    # wait for all nodes
    nd2blt = {}
    for nd,fut in nd2fut.iteritems():
      nd2blt[nd] = yield async.Wait(fut)
    
    yield async.Result((soln, easy.deliveries(
      soln, nd2blt.get, lambda p: fief.packages[p].deliverer()
    )))

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

def _memo_build(procurer, node, opts):
  assert opts.__valtool_ignore__
  assert procurer.__valtool_ignore__
  
  def build_a(ctx):
    pkg = ctx['_node_pkg',node]
    src = ctx['_pkg_source',pkg]
    pbld = ctx['_pkg_builder',pkg]
    soln = ctx['_node_soln',node]
    
    # wait for all dependency packages to build before we untar source
    for dep in soln.env_nodes():
      yield async.Sync(ctx.memo_a(ctx['_node_builder',dep]))
    
    # procure our source
    site, cleanup = yield async.Sync(procurer.procure_a(ctx, src))
    
    # now build
    try:
      class WrapCtx(object):
        @classmethod
        def new_a(cls):
          me = cls()
          me.package = pkg
          me.source = site
          me.soln = soln
          me.osenv = yield async.Sync(easy.gather_env_a(me))
          yield async.Result(me)
        
        def __getattr__(me, x):
          return getattr(ctx, x)
        
        def __getitem__(me, x):
          return ctx[x]
        
        def outdir_a(me):
          f = yield async.Sync(ctx.outfile_a(os.path.join('build', pkg)))
          os.mkdir(f)
          yield async.Result(f)
        
        def command(me, cwd=None, envmod=lambda e:e):
          return bake.Cmd(ctx,
            tag=me.package,
            env=envmod(me.osenv),
            cwd=me.source if cwd is None else cwd
          )
        
        def implementing(me, ifc):
          return ifc in ctx['_node_imps',node]
        
        def option_soft(me, x):
          return opts(pkg, x)
        
        def option_hard(me, x):
          return ctx['_option',pkg,x]
        
        def deliveries_a(me):
          s = ctx['_node_soln',node]
          ns = s.env_nodes()
          ps = set(s.node_pkg(dep) for dep in ns)
          nd2blt = {}
          for dep in ns:
            nd2blt[dep] = yield async.Sync(
              ctx.memo_a(ctx['_node_builder',dep])
            )
          p2d = ctx.args(('_pkg_deliverer',p) for p in ps)
          pkg_delv = lambda p: p2d['_pkg_deliverer',p]
          yield async.Result(easy.deliveries(s, nd2blt.get, pkg_delv))
      
      wrap = yield async.Sync(WrapCtx.new_a())
      built = yield async.Sync(pbld(wrap))
    finally:
      cleanup()
    yield async.Result(built)
  
  return build_a
