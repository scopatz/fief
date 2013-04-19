import os
import sys

import async

ensure_frozenset = lambda x: frozenset(x if hasattr(x, '__iter__') else (x,))

class Imp(object):
  def __init__(me, subsumes=(), requires=()):
    me.subsumes = ensure_frozenset(subsumes)
    me.requires = ensure_frozenset(requires)
  
  def __repr__(self):
    s = "Imp(subsumes={0!r}, requires={1!r})"
    return s.format(self.subsumes, self.requires)
  
  def __getstate__(me):
    return (me.subsumes, me.requires)
  
  def __setstate__(me, st):
    me.subsumes, me.requires = st

class Package(object):
  def source(me):
    raise Exception('Not implemented.')
  
  def implements_a(me, oven):
    """returns {ifc: Imp}"""
    raise Exception('Not implemented.')
  
  def deliverer(me):
    """returns function (ifc,what,built,delv) -> deliverable where:
    ifc: the interface for which this deliverable is being requested
    what: the deliverable kind ('envdelta',...)
    built: the value returned from the builder
    delv: function(ifc,what)->deliverable -- a view into the deliverables of any
          interfaces required by this package build.
    """
    raise Exception('Not implemented.')
  
  def builder(me):
    """returns async function ctx~>built"""
    raise Exception('Not implemented.')

class Repo(object):
  def __init__(me, pkg_imps):
    """pkg_imps: {pkg: {ifc: Imp}}"""
    pkg_ifc_reqs = {} # {(pkg,ifc):set(ifc)}
    ifcs = set()
    pkg_imps = dict(pkg_imps)
    ifc_imps = {}
    ifc_subs = {}
    ifc_bigs = {}
    
    for pkg,imps in pkg_imps.iteritems():
      for ifc,imp in imps.iteritems():
        ifcs.add(ifc)
        
        if ifc not in ifc_imps:
          ifc_imps[ifc] = set()
        ifc_imps[ifc].add(pkg)
        
        if ifc not in ifc_subs:
          ifc_subs[ifc] = set([ifc])
        ifc_subs[ifc].update(imp.subsumes)
        
        pkg_ifc_reqs[pkg,ifc] = set(imp.requires)
        
        ifcs.update(ifc_subs[ifc])
        ifcs.update(pkg_ifc_reqs[pkg,ifc])
    
    for ifc in ifcs:
      if ifc not in ifc_subs:
        ifc_subs[ifc] = set([ifc])
    
    # transitively close ifc_subs
    while True:
      changed = False
      for a,asubs in ifc_subs.iteritems():
        for b in tuple(asubs):
          len0 = len(asubs)
          asubs.update(ifc_subs[b])
          changed = changed or len0 != len(asubs)
      if not changed: break
    
    # inverse ifc_subs
    for a in ifc_subs:
      for b in ifc_subs[a]:
        if b not in ifc_bigs:
          ifc_bigs[b] = set()
        ifc_bigs[b].add(a)
    
    # if a subsumes b, then anyone who implements a also implements b.
    # we are purposely not updating pkg_imps, it should not be closed.
    for a in ifc_subs:
      for b in ifc_subs[a]:
        if b not in ifc_imps:
          ifc_imps[b] = set()
        ifc_imps[b].update(ifc_imps.get(a, ()))
    
    ## to require an interface a is to also require all the interfaces it subsumes
    #for (pkg,ifc),reqs in pkg_ifc_reqs.iteritems():
    #  for req in tuple(reqs):
    #    reqs.update(ifc_subs.get(req, ()))
    #  assert ifc not in reqs
    
    # requirements subsume
    for (pkg,a),reqs in pkg_ifc_reqs.iteritems():
      for b in ifc_subs[a]:
        reqs.update(pkg_ifc_reqs.get((pkg,b), ()))
    
    # partition into equivalence classes
    eqrep = {}
    eqset = {}
    for a in ifcs:
      for b in ifc_subs[a]:
        if a in ifc_subs[b]:
          r = min(eqrep.get(a,a), eqrep.get(b,b))
          eqrep[a] = r
          eqrep[b] = r
    for a in eqrep:
      b = a
      while b != eqrep[b]:
        b = eqrep[b]
      eqrep[a] = b
    
    for a in eqrep:
      r = eqrep[a]
      if r not in eqset:
        eqset[r] = set()
      eqset[r].add(a)
      eqset[a] = eqset[r]
    
    # topsort eq class representatives
    topreps = []
    topset = set()
    def topsort(them):
      for a in them:
        r = eqrep[a]
        if r not in topset:
          topset.add(r)
          topsort(ifc_subs[r])
          topreps.append(r)
    topsort(ifcs)
    
    glbs = {}
    lubs = {}
    for a in topreps:
      glbs[a] = set(eqrep[b] for b in ifc_subs[a] if eqrep[b] != a)
      for b in ifc_subs[a]:
        b = eqrep[b]
        if a != b:
          glbs[a].difference_update(eqrep[c] for c in ifc_subs[b] if eqrep[c] != b)
    
      lubs[a] = set(eqrep[b] for b in ifc_bigs[a] if eqrep[b] != a)
      for b in ifc_bigs[a]:
        b = eqrep[b]
        if a != b:
          lubs[a].difference_update(eqrep[c] for c in ifc_bigs[b] if eqrep[c] != b)
    
    me._pkg_imps = pkg_imps
    me._pkgs = frozenset(pkg_imps)
    me._pkg_ifc_reqs = pkg_ifc_reqs
    me._ifcs = frozenset(ifcs)
    me._ifc_imps = dict((ifc,frozenset(pkgs)) for ifc,pkgs in ifc_imps.iteritems())
    me._ifc_subs = dict((ifc,frozenset(subs)) for ifc,subs in ifc_subs.iteritems())
    me._ifc_bigs = dict((ifc,frozenset(bigs)) for ifc,bigs in ifc_bigs.iteritems())
    me._eqrep = eqrep
    me._eqset = dict((i,frozenset(s)) for i,s in eqset.iteritems())
    me._topreps = topreps
    me._glbreps = glbs
    me._lubreps = lubs
  
  def packages(me):
    return me._pkgs
  
  def interfaces(me):
    return me._ifcs
  
  def ifc_subsets(me, ifc):
    """Maps interface to set of interfaces it subsumes, not necessarily 
    closed under transitivity."""
    return me._ifc_subs.get(ifc, frozenset())
  
  def ifcs_subsets(me, ifcs):
    """union(ifc_subs(i) for i in ifcs)"""
    un = set()
    for i in ifcs:
      if i in me._ifc_subs:
        un.update(me._ifc_subs[i])
    return un
  
  def ifc_subsumers(me, ifc):
    return me._ifc_bigs.get(ifc, frozenset())
  
  def ifc_equivalents(me, ifc):
    return me._eqset[me._eqrep[ifc]]
  
  def ifc_implementors(me, ifc):
    """Maps interface to set of packages that implements it directly or indirectly via subsumption."""
    return me._ifc_imps.get(ifc, frozenset())
  
  def pkg_implements(me, pkg):
    """Maps package to {ifc:Imp} dictionary."""
    return me._pkg_imps.get(pkg, {})
  
  def pkg_ifc_requires(me, pkg, ifc):
    """Returns set of interfaces that are required if `pkg` were to implement `ifc`.
    Returned set of interfaces not closed under subsumption."""
    return me._pkg_ifc_reqs.get((pkg,ifc), frozenset())
  
  def pkg_ifcs_requires(me, pkg, ifcs):
    """union(pkg_ifc_subs(pkg,i) for i in ifcs)"""
    un = set()
    for i in ifcs:
      if (pkg,i) in me._pkg_ifc_reqs:
        un.update(me._pkg_ifc_reqs[pkg,i])
    return un
  
  def min_ifcs(me, ifcs):
    """Given an iterable of interfaces, returns a set of those which are minimal
    in the subsumption heirarchy."""
    eqrep = me._eqrep
    eqset = me._eqset
    bigs = me._ifc_bigs
    ifcs = set(ifcs)
    mins = set(eqrep[a] for a in ifcs)
    for a in list(mins):
      mins.difference_update(eqrep[b] for b in bigs[a] if eqrep[b] != a)
    u = set()
    for r in mins:
      u.update(eqset[r])
    u.intersection_update(ifcs)
    return u
  
  def choose_least(me, ifcs, proj):
    """within a set of interfaces and given a projection function that to each
    interfaces assigns either a name or None, find the name (or None) of the set
    of interfaces which are minimal in the graph of subgraphs."""
    
    eqrep = me._eqrep
    eqset = me._eqset
    subs = me._ifc_subs
    m = {}
    for i in ifcs:
      i = eqrep[i]
      x = None
      for i1 in eqset[i]:
        x1 = proj(i)
        if x is None:
          x = x1
        elif x1 is not None and x != x1:
          assert False # proj function is choosing different values for equivalent interfaces
      if x is not None:
        m[x] = m.get(x, set())
        m[x].add(i)
    
    def less(a, b):
      return all(any(i in subs[j] for j in m[b]) for i in m[a])
    
    mins = set()
    for a in m:
      dont_add = False
      for b in list(mins):
        if less(a, b):
          mins.discard(b)
        elif not less(b, a):
          dont_add = True
      if not dont_add:
        mins.add(a)
    
    return list(mins)[0] if len(mins) == 1 else None
