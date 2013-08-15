import sys

from repository import Repo, Imp

class Soln(object):
  def __init__(me, ifc2pkg, pkg2soln):
    me._ifc2pkg = ifc2pkg
    me._pkg2soln = pkg2soln
    me._v = (frozenset(ifc2pkg.iteritems()), frozenset(pkg2soln.iteritems()))
  def __getstate__(me):
    return (me._ifc2pkg, me._pkg2soln)
  def __setstate__(me, s):
    me._ifc2pkg, me._pkg2soln = s
    me._v = (frozenset(me._ifc2pkg.iteritems()), frozenset(me._pkg2soln.iteritems()))
  def __hash__(me):
    return hash(me._v)
  def __eq__(me, that):
    return me._v == that._v
  def __ne__(me, that):
    return me._v != that._v
  def __str__(me):
    def indent(s):
      return ' ' + s.replace('\n','\n ')
    return 'ifc2pkg=' + repr(me._ifc2pkg) + '\n' + \
      '\n'.join('pkg ' + str(p) + ':\n' + indent(str(s)) for p,s in me._pkg2soln.items())
  def ifc2pkg(me, ifc):
    return me._ifc2pkg.get(ifc)
  def pkg2soln(me, pkg):
    return me._pkg2soln.get(pkg)
  def ifcs(me):
    return set(me._ifc2pkg.iterkeys())
  def pkgs(me):
    return set(me._pkg2soln.iterkeys())

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
  def imps(soln, pkg):
    return set(i for i in repo.pkg_implements(pkg) if soln.get(i) == pkg)
  
  @_memoize
  def down(ifcs, above):
    pkgs = set(p for p in repo.packages() if above.count(p) < 2)
    s = _solve_flat(repo, pkgs, ifcs, pref)
    i2p = dict((i,s[i]) for i in _runset(repo, s, ifcs))
    pkgs = set(i2p.itervalues())
    p2s = {}
    for p in pkgs:
      reqs = repo.pkg_ifcs_buildreqs(p, imps(i2p, p))
      if any(s[r]==p for r in reqs): # cyclic package
        p2s[p] = down(frozenset(reqs), above + (p,))
      else:
        p2s[p] = 
      p2s[p] = down(frozenset(reqs), above + (p,))
    return Soln(i2p, p2s)
  
  return down(frozenset(ifcs), ())

def _runset(repo, soln, ifcs):
  ifcs = set(ifcs)
  more = ifcs
  while len(more) > 0:
    more0 = more
    more = []
    for i in more0:
      p = soln[i]
      imps = set(i for i in repo.pkg_implements(p) if soln.get(i) == p)
      reqs = repo.pkg_ifcs_runreqs(p, imps)
      for r in reqs:
        if r not in ifcs:
          ifcs.add(r)
          more.append(r)
  return repo.ifcs_subsets(ifcs)
  
def _memoize(f):
  m = {}
  def g(*a, **kw):
    x = (tuple(a), frozenset(kw.iteritems()))
    if x not in m:
      m[x] = f(*a,**kw)
    return m[x]
  return g

def _cycle_sets(xs):
  def tclose(xs):
    xs = dict((x,set(xs[x])) for x in xs)
    again = True
    while again:
      again = False
      for x in xs:
        for y in list(xs[x]):
          n0 = len(xs[x])
          xs[x].update(xs[y])
          again = again or n0 != len(xs[x])
    return xs

  xs = tclose(xs)
  cy = {}
  for x in xs:
    if x in xs[x]:
      for y in xs[x]:
        if x in xs[y]:
          cy[x] = cy.get(x, set((x,)))
          cy[y] = cy.get(y, set((y,)))
          cy[x] |= cy[y]
          for z in cy[y]:
            cy[z] = cy[x]
  them = dict((id(s),s) for s in cy.itervalues())
  return [frozenset(s) for s in them.itervalues()]

def _solve_flat(repo, pkgs, unbound, pref=lambda i,ps:None):
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
  
  # returns revert lambda if successful, otherwise None
  def bind(ifc, pkg):
    world_adds = []
    bound_adds = []
    unbound_dels = []
    unbound_adds = []
    
    def revert():
      world.difference_update(world_adds)
      for i in bound_adds:
        del bound[i]
      unbound.difference_update(unbound_adds)
      unbound.update(unbound_dels)
    
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
    
    reqs = list(repo.pkg_ifc_runreqs(pkg, ifc))
    reqs += repo.pkg_ifc_buildreqs(pkg, ifc)
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
      yield dict(bound)
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
      while len(ps) > 1:
        best = pref(i, ps)
        if best is not None:
          p = best
          ps.discard(p)
        else:
          p = ps.pop()
        mins = (i1 for i1 in repo.pkg_implements(p) if i in repo.ifc_subsets(i1))
        mins = repo.min_ifcs(mins)
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

def test(ifcs=['cc']):
  repo = Repo({
    'gcc':{'cc':Imp(buildreqs=['cc','mpr'])},
    'bad':{'cc':Imp()},
    'gmpr':{'mpr':Imp(buildreqs=['cc'])}
  })
  def pref(i,ps):
    if i=='cc' and 'gcc' in ps:
      return 'gcc'
    else:
      return None
  print str(solve(repo, ifcs, pref))
