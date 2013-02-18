import os
import sys
import shutil
import tempfile
import itertools

import conf
import bake
import async
import fetch

#ensure_frozenset = lambda x: frozenset(x if hasattr(x, '__iter__') else (x,))
ensure_frozenset = lambda x: set(x if hasattr(x, '__iter__') else (x,))

class ifc(object):
  def __init__(me, subsumes=(), requires=()):
    me.subsumes = ensure_frozenset(subsumes)
    me.requires = ensure_frozenset(requires)
  
  def __repr__(self):
    s = "ifc(subsumes={0!r}, requires={1!r})"
    return s.format(self.subsumes, self.requires)
  
  def __getstate__(me):
    return (me.subsumes, me.requires)
  
  def __setstate__(me, st):
    me.subsumes, me.requires = st

class DisjointSets(object):
  """ implements http://en.wikipedia.org/wiki/Disjoint-set_data_structure
  Path compression is not done so that all merge operations are easily reversible.
  """
  def __init__(me):
    me._rep = {} # set representative, follow until x == rep[x]
    me._dep = {} # representative tree depth
    me._mbr = {} # representative members
    me._log = [] # maintains the history of changes
  
  def __getitem__(me, x):
    """Get the canonical representative for the set containing x."""
    rep = me._rep
    if x in rep:
      x1 = rep[x]
      while x != x1:
        x = x1
        x1 = rep[x1]
    return x
  
  def members(me, x):
    """Get all members of the set that contains x."""
    x = me[x]
    if x in me._mbr:
      return frozenset(me._mbr[x])
    else:
      return frozenset([x])
  
  def state(me):
    return len(me._log)
  
  def merge(me, a, b):
    """Union the two sets containing a and b."""
    rep = me._rep
    dep = me._dep
    mbr = me._mbr
    log = me._log
    
    def can(x):
      if x not in rep:
        rep[x] = x
        dep[x] = 0
        mbr[x] = set([x])
      else:
        x1 = rep[x]
        while x != x1:
          x = x1
          x1 = rep[x1]
      return x
    
    a = can(a)
    b = can(b)
    
    if a != b:
      if dep[a] <= dep[b]:
        log.extend((a, dep[b]))
        rep[a] = b
        mbr[b].union_update(mbr[a])
        if dep[a] == dep[b]:
          dep[b] += 1
      else:
        log.extend((b, dep[a]))
        rep[b] = a
        mbr[a].union_update(mbr[b])
  
  def revert(me, st):
    rep, dep, mbr = me._rep, me._dep, me._mbr
    log = me._log
    while st < len(log):
      dep_b, a = log.pop(), log.pop()
      b = rep[a]
      rep[a] = a
      mbr[b].difference_update(mbr[a])
      dep[b] = dep_b

class Repo(object):
  def init_a(me, oven, pkg_defs):
    def pack_ifx(ifx):
      return dict((nm,x.__getstate__()) for nm,x in ifx.iteritems())
    
    def unpack_ifx(s):
      def unpack(t):
        i = ifc()
        i.__setstate__(t)
        return i
      return dict((nm,unpack(x)) for nm,x in s.iteritems())
    
    def packed_ifx_a(ctx):
      py = ctx['py']
      ns = {}
      execfile(os.path.join('repo', py), ns, ns)
      yield async.Result(pack_ifx(ns['interfaces']))
    
    pkgs = set()
    pkg_src = {}
    pkg_py = {}
    pkg_ifx = {}
    pkg_ifc_reqs = {} # {(pkg,ifc):set(ifc)}
    ifcs = set()
    ifc_imps = {}
    ifc_subs = {}
    
    for pkg,(src,py) in pkg_defs.iteritems():
      pkgs.add(pkg)
      pkg_src[pkg] = src
      pkg_py[pkg] = py
      ifx = yield async.WaitFor(oven.memo_a(packed_ifx_a, {'py':py}))
      ifx = unpack_ifx(ifx)
      pkg_ifx[pkg] = ifx
      
      for ifc in ifx:
        ifcs.add(ifc)
        ifc_imps[ifc] = ifc_imps.get(ifc, set())
        ifc_imps[ifc].add(pkg)
        ifc_subs[ifc] = ifc_subs.get(ifc, set())
        ifc_subs[ifc].union_update(ifx[ifc].subsumes)
        pkg_ifc_reqs[pkg,ifc] = ifx[ifc].requires
    
    me._pkgs = frozenset(pkgs)
    me._pkg_src = pkg_src
    me._pkg_py = pkg_py
    me._pkg_ifx = pkg_ifx
    me._pkg_stuff = {}
    me._pkg_ifc_reqs = pkg_ifc_reqs
    me._ifcs = frozenset(ifcs)
    me._ifc_imps = dict((ifc,frozenset(imps)) for ifc,imps in ifc_imps.iteritems())
    me._ifc_subs = dict((ifc,frozenset(subs)) for ifc,subs in ifc_subs.iteritems())
  
  def packages(me):
    return me._pkgs
    
  def interfaces(me):
    return me._ifcs
  
  def pkg_source(me, pkg):
    return me._pkg_src[pkg]
  
  def _pkg_get_stuff(me, pkg, 
    if pkg not in me._pkg_stuff:
      ns = {}
      execfile(me._pkg_py[pkg], ns, ns)
      me._pkg_stuff[pkg] = (ns['build_a'], ns.get('realize', lambda _:{}))
    return me._pkg_stuff[pkg]
  
  def pkg_builder(me, pkg):
    return me._pkg_get_stuff(pkg)[0]
  
  def pkg_realizer(me, pkg):
    return me._pkg_get_stuff(pkg)[1]
  
  def ifc_subs(me, ifc):
    """Maps interface to set of interfaces it subsumes, not necessarily 
    closed under transitivity."""
    return me._ifc_subs.get(ifc, frozenset())
  
  def ifc_imps(me, ifc):
    """Maps interface to set of packages that implements it."""
    return me._ifc_imps.get(ifc, frozenset())
  
  def pkg_ifc_reqs(me, pkg, ifc):
    """Returns set of interfaces that are required if `pkg` were to implement `ifc`."""
    return me._pkg_ifc_reqs.get((pkg,ifc), frozenset())
  
  def solve_pkgs(me, ifcs):
    """Returns an iterable of dicts that map interfaces to packages.
    Each dict will be complete with all dependencies and subsumed interfaces."""
    
    # solver state
    part = DisjointSets() # equivalence partition for interface subsumption
    world = set() # all interfaces seen so far
    bound = {} # bound interfaces to packages
    unbound = set(ifcs) # interfaces not yet bound
    
    # modify state of solver by binding ifc to pkg, returns `revert` lambda if
    # successful, otherwise None.
    def bind(ifc, pkg):
      assert all(i not in bound for i in unbound)
      assert ifc not in bound
      assert ifc in unbound
      
      bound[ifc] = pkg
      unbound.discard(ifc)
      
      world_adds = []
      part_st = part.state()
      
      loop = set([ifc])
      loop.union_update(me.pkg_ifc_reqs(pkg, ifc))
      
      while len(loop) > 0:
        more = []
        for i in loop:
          if i not in world:
            world.add(i)
            world_adds.append(i)
            for s in me.ifc_subs(i):
              if s not in world:
                more.append(s)
              part.merge(i, s)
        loop = more
      
      bound_adds = set()
      unbound_adds = []
      unbound_dels = set()
      
      def revert():
        part.revert(part_st)
        world.difference_update(world_adds)
        
        for i in bound_adds:
          del bound[i]
        del bound[ifc]
        
        unbound.difference_update(unbound_adds)
        unbound.union_update(unbound_dels)
        unbound.add(ifc)
      
      for i in bound.keys():
        i1 = part[i]
        if i1 != i:
          if i1 in bound:
            if bound[i] != bound[i1]:
              revert()
              return None
          else:
            bound[i1] = bound[i]
            bound_adds.add(i1)
      
      for i in unbound:
        i1 = part[i]
        if i1 in bound:
          unbound_dels.add(i1)
      unbound.difference_update(unbound_dels)
      
      for i in world_adds:
        i1 = part[i]
        if i1 not in bound and i1 not in unbound:
          unbound.add(i1)
          unbound_adds.append(i1)
      
      return revert
    
    def branch():
      if len(unbound) == 0:
        # report a solution
        yield dict((i,bound[part[i]]) for i in world)
      else:
        # pick the interface with the least number of implementing packages
        i_min, ps_min = None, None
        for i in unbound:
          ps = me.ifc_imps(i)
          if i_min is None or len(ps) < len(ps_min):
            i_min, ps_min = i, ps
        i, ps = i_min, ps_min
        # bind interface to each possible package and recurse
        for p in ps:
          revert = bind(i, p)
          if revert is not None:
            for x in branch():
              yield x
            revert()
    
    return branch()
