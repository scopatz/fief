import sys

from repository import Repo, Imp
import valtool

class Soln(object):
  def __init__(me, repo, ifc2pkg, pkg2soln):
    me._nd_pkg = {}
    me._nd_imps = {}
    me._nd_ifc_nd = {}
    for s in pkg2soln.itervalues():
      me._nd_pkg.update(s._nd_pkg)
      me._nd_imps.update(s._nd_imps)
      me._nd_ifc_nd.update(s._nd_ifc_nd)
    
    for p in set(ifc2pkg.itervalues()):
      imps = frozenset(i for i in ifc2pkg if ifc2pkg[i] == p)
      nd = valtool.Hasher().eat(p).eat(pkg2soln[p]).digest()
      me._nd_ifc_nd[nd] = me._nd_ifc_nd.get(nd, {})
      me._nd_ifc_nd[nd][
    me._v = (frozenset(ifc2pkg.iteritems()), frozenset(pkg2soln.iteritems()))
  def __getstate__(me):
    return (me.ifc2pkg, me.pkg2soln)
  def __setstate__(me, s):
    me.ifc2pkg, me.pkg2soln = s
    me._v = (frozenset(me.ifc2pkg.iteritems()), frozenset(me.pkg2soln.iteritems()))
  def __hash__(me):
    return hash(me._v)
  def __eq__(me, that):
    return me._v == that._v
  def __ne__(me, that):
    return me._v != that._v
  def __str__(me):
    def indent(s):
      return ' ' + s.replace('\n','\n ')
    return 'ifc2pkg=' + repr(me.ifc2pkg) + '\n' + \
      '\n'.join('pkg ' + str(p) + ':\n' + indent(str(s)) for p,s in me.pkg2soln.items())
  def pkgids(me):
    
class SolveError(Exception):
  pass

def implicate(repo, ifcs, imply=lambda x,on: False):
  on = set(ifcs)
  off = set(repo.interfaces())
  tog = on
  while len(tog) > 0:
    off.difference_update(tog)
    tog = []
    for x in off:
      if imply(x, on.__contains__):
        on.add(x)
        tog.append(x)
  return on

def solve(repo, ifcs, pref=lambda i,ps:None):
  @_memoize
  def down(ifcs, above):
    pkgs = set(p for p in repo.packages() if above.count(p) < 2)
    s, cycs = _solve_acyclic(repo, pkgs, ifcs, pref)
    @_memoize
    def soln(ifcs):
      i2p = dict((i,s[i]) for i in _runset(repo, s, ifcs))
      p2s = {}
      for p in set(i2p.itervalues()):
        reqs = frozenset(repo.pkg_ifcs_buildreqs(p, _impset(repo, i2p, p)))
        if p in cycs:
          p2s[p] = down(reqs, above + (p,))
        else:
          p2s[p] = soln(reqs)
      return Soln(i2p, p2s)
    return soln(ifcs)
  
  return down(frozenset(ifcs), ())

def _impset(repo, soln, pkg):
  return set(i for i in repo.pkg_implements(pkg) if soln.get(i) == pkg)
  
def _runset(repo, soln, ifcs):
  ifcs = set(ifcs)
  more = ifcs
  pkgs = set()
  while len(more) > 0:
    more0 = more
    more = []
    for i in more0:
      p = soln[i]
      ifcs1 = set(i for i in repo.pkg_implements(p) if soln.get(i)==p)
      ifcs1.update(repo.pkg_ifcs_runreqs(p, _impset(repo, soln, p)))
      more += (i for i in ifcs1 if i not in ifcs)
      ifcs.update(ifcs1)
  return ifcs
  
def _memoize(f):
  m = {}
  def g(*a, **kw):
    x = (tuple(a), frozenset(kw.iteritems()))
    if x not in m:
      m[x] = f(*a,**kw)
    return m[x]
  return g

def _solve_acyclic(repo, pkgs, unbound, pref=lambda i,ps:None):
  """
  Returns the dict that maps interfaces to packages.
  It will be complete with all buildtime/runtime dependencies and subsumed
  interfaces.
  
  repo: repository.Repo
  pkgs: iterable of packages to consider
  unbound: iterable of initial required interfaces
  bound: bound interfaces, must be closed under subsumption
  pref: (ifc,pkgs)->(pkg|None) -- given a choice of implementing packages,
        is there one that would be best?  Solutions beyond those found with
        one of these bindings will be skipped.
  """
  
  pkgs = set(pkgs)
  
  # solver state
  unbound = set(unbound)
  bound = {}
  world = repo.ifcs_subsets(unbound) # all interfaces ever required closed by subsumption
  cyclic = set()
  
  # returns revert lambda if successful, otherwise None
  def bind(ifc, pkg):
    world_adds = []
    bound_adds = []
    unbound_dels = []
    unbound_adds = []
    cyclic_adds = []
    
    def revert():
      world.difference_update(world_adds)
      for i in bound_adds:
        del bound[i]
      unbound.difference_update(unbound_adds)
      unbound.update(unbound_dels)
      cyclic.difference_update(cyclic_adds)
    
    for i in repo.ifc_subsets(ifc):
      if i not in world:
        world.add(i)
        world_adds.append(i)
    
      if i in bound:
        if bound[i] != pkg:
          revert()
          return None
      else:
        bound[i] = pkg
        bound_adds.append(i)

      if i in unbound:
        unbound.discard(i)
        unbound_dels.append(i)
    
    rreqs = repo.pkg_ifc_runreqs(pkg, ifc)
    breqs = repo.pkg_ifc_buildreqs(pkg, ifc)
    cycle = False
    for br in breqs:
      if any(r in repo.ifc_subsets(ifc) for r in repo.ifc_subsets(br)) or \
         any(r in repo.ifc_subsets(br) for r in repo.ifc_subsets(ifc)):
        cycle = True
        break
    
    if not cycle:
      reqs = list(rreqs)
      reqs += breqs
    else:
      reqs = rreqs
      if pkg not in cyclic:
        cyclic.add(pkg)
        cyclic_adds.append(pkg)
    
    for i in reqs:
      if i not in world:
        unbound.add(i)
        unbound_adds.append(i)
        for i1 in repo.ifc_subsets(i):
          if i1 not in world:
            world.add(i1)
            world_adds.append(i1)
    
    return revert
  
  def branch():
    if len(unbound) == 0:
      # report a solution
      assert all(i in bound for i in world)
      yield dict(bound), frozenset(cyclic)
    else:
      # pick the interface with the least number of implementing packages
      i_min = None
      ps_min = None
      for i in unbound:
        ps = set(repo.ifc_implementors(i))
        ps.intersection_update(pkgs)
        if i_min is None or len(ps) < len(ps_min):
          i_min = i
          ps_min = ps
      
      i = i_min
      ps = set(ps_min) # make our own copy
      
      # bind interface to preferred packages first
      while len(ps) > 0:
        best = pref(i, ps)
        if best is not None:
          p = best
          ps.discard(p)
        else:
          p = ps.pop()
        mins = (i1 for i1 in repo.pkg_implements(p) if i in repo.ifc_subsets(i1))
        mins = repo.min_ifcs(mins)
        solved = False
        for i1 in mins:
          revert = bind(i1, p)
          if revert is not None:
            for soln in branch():
              solved = True
              yield soln
            revert()
        if best is not None and solved:
          break
  
  numsoln = 0
  for soln in branch():
    if numsoln == 1:
      raise SolveError("Interface solution ambiguity.")
    ans = soln
    numsoln += 1
  if numsoln == 0:
    raise SolveError("Interfaces unsolvable.")
  return ans
