import os
import sys

import async
import envdelta

ensure_frozenset = lambda x: frozenset(x if hasattr(x, '__iter__') else (x,))

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

class Package(object):
  def source(me):
    raise Exception('Not implemented.')
  def interfaces_a(me, oven):
    """returns dict ifc_name -> ifc (object)"""
    raise Exception('Not implemented.')
  def deliverer(me):
    """returns function (what,built) -> deliverable"""
    raise Exception('Not implemented.')
  def builder(me):
    """returns async function ctx,pkg_name,src_dir,opts ~> delivs"""
    raise Exception('Not implemented.')

class PackageScript(Package):
  def __init__(me, source, py_file):
    me._src = source
    me._py = py_file
    me._ifx = None
    me._ns = None
  
  def source(me):
    return me._src
  
  def interfaces_a(me, oven):
    box = [None]
    def load_ifx_a(ctx):
      py = ctx['py']
      ctx.infile(py)
      box[0] = {}
      execfile(py, box[0], box[0])
      yield async.Result(box[0]['interfaces'])
    
    if me._ifx is None:
      if me._ns is None:
        me._ifx = yield async.Sync(oven.memo_a(load_ifx_a, {'py':me._py}))
        me._ns = box[0]
      else:
        me._ifx = me._ns['interfaces']
    
    yield async.Result(me._ifx)
  
  def _ensure_ns(me):
    if me._ns is None:
      me._ns = {}
      execfile(me._py, me._ns, me._ns)

  def deliverer(me):
    me._ensure_ns()
    ns = me._ns
    pre = 'deliverable_'
    d = dict((nm[len(pre):],ns[nm]) for nm in ns if nm.startswith(pre))
    return lambda what,built: d.get(what, lambda _:None)(built)
  
  def builder(me):
    me._ensure_ns()
    return me._ns['build_a']

class Repo(object):
  @classmethod
  def new_a(cls, oven, pkgs):
    pkg_ifc_reqs = {} # {(pkg,ifc):set(ifc)}
    ifcs = set()
    pkg_imps = {}
    ifc_imps = {}
    ifc_subs = {}
    
    for pkg,pobj in pkgs.iteritems():
      ifx = yield async.Sync(pobj.interfaces_a(oven))
      pkg_imps[pkg] = set(ifx)
      
      for ifc in ifx:
        ifcs.add(ifc)
        
        if ifc not in ifc_imps:
          ifc_imps[ifc] = set()
        ifc_imps[ifc].add(pkg)
        
        if ifc not in ifc_subs:
          ifc_subs[ifc] = set([ifc])
        ifc_subs[ifc].update(ifx[ifc].subsumes)
        
        pkg_ifc_reqs[pkg,ifc] = set(ifx[ifc].requires)
        
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
    
    # if a subsumes b, then anyone who implements a also implements b
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
    
    me = cls()
    me._pkgs = dict(pkgs)
    me._pkg_ifc_reqs = pkg_ifc_reqs
    me._ifcs = frozenset(ifcs)
    me._ifc_imps = dict((ifc,frozenset(pkgs)) for ifc,pkgs in ifc_imps.iteritems())
    me._pkg_imps = dict((pkg,frozenset(ifcs)) for pkg,ifcs in pkg_imps.iteritems())
    me._ifc_subs = dict((ifc,frozenset(subs)) for ifc,subs in ifc_subs.iteritems())
    yield async.Result(me)
  
  def packages(me):
    return me._pkgs
  
  def package(me, pkg):
    return me._pkgs[pkg]
  
  def interfaces(me):
    return me._ifcs
  
  def ifc_subs(me, ifc):
    """Maps interface to set of interfaces it subsumes, not necessarily 
    closed under transitivity."""
    return me._ifc_subs.get(ifc, frozenset())
  
  def ifcs_subs(me, ifcs):
    """union(ifc_subs(i) for i in ifcs)"""
    un = set()
    for i in ifcs:
      if i in me._ifc_subs:
        un.update(me._ifc_subs[i])
    return un
  
  def ifc_imps(me, ifc):
    """Maps interface to set of packages that implements it directly or indirectly via subsumption."""
    return me._ifc_imps.get(ifc, frozenset())
  
  def pkg_imps(me, pkg):
    """Maps package to set of interfaces it can directly implement."""
    return me._pkg_imps.get(pkg, frozenset())
  
  def pkg_ifc_reqs(me, pkg, ifc):
    """Returns set of interfaces that are required if `pkg` were to implement `ifc`.
    Returned set of interfaces not closed under subsumption."""
    return me._pkg_ifc_reqs.get((pkg,ifc), frozenset())
  
  def pkg_ifcs_reqs(me, pkg, ifcs):
    """union(pkg_ifc_subs(pkg,i) for i in ifcs)"""
    un = set()
    for i in ifcs:
      if (pkg,i) in me._pkg_ifc_reqs:
        un.update(me._pkg_ifc_reqs[pkg,i])
    return un
  
  def least_ifcs(me, ifcs):
    """Given an iterable of interfaces, returns a set of those which are least
    points in the subsumption heirarchy."""
    least = set()
    for a in ifcs:
      dont_add = False
      for b in tuple(least):
        if b in me._ifc_subs[a]:
          dont_add = True
          break
        elif a in me._ifc_subs[b]:
          least.discard(b)
      if not dont_add:
        least.add(a)
    return least
