import sys
from collections import namedtuple

from repository import Repo, Imp

Soln = namedtuple('Soln', ['ifc2pkg','pkg2soln'])

class SolutionError(Exception):
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
  """
  Returns value of type Soln such that
  Soln = (ifc2pkg:{ifc:pkg}, pkg2soln:{pkg:Soln})
  """
  ifcs = frozenset(ifcs)
  solns = {}
  holes = {}
  def down(ifcs, path):
    def rank(p):
      return sum(1 if p in hole else 0 for hole in path)
    def pref2(i, ps):
      p = pref(i, ps)
      return () if p is None else (p,)
    pkgs = set(p for p in repo.packages() if rank(p) < 2)
    s = solve2(repo, pkgs, ifcs, pref2)
    solns[path] = s
    ps = set(s.itervalues())
    
    p_reqi = {} # pkg -> set(ifc) needed for building
    p_reqp = {} # pkg -> set(pkg) needed for building (implementing p_reqi)
    for p in ps:
      imps = set(i for i in repo.pkg_implements(p) if i in s and s[i] == p)
      p_reqi[p] = repo.pkg_ifcs_buildreqs(p, imps)
      p_reqp[p] = set(s[i] for i in p_reqi[p])
    
    holes[path] = cycle_sets(p_reqp)
    for hole in holes[path]:
      ifcs = set()
      for p in hole:
        ifcs.update(p_reqi[p])
      down(ifcs, path + (hole,))
  down(ifcs, ())
  
  def tree(path):
    s = solns[path]
    hole = holes[path]
    ps = set(s.itervalues())
    pkg2soln = {}
    for p in ps:
      imps = set(i for i in repo.pkg_implements(p) if s.get(i) == p)
      reqs = repo.pkg_ifcs_runreqs(p, imps)
      pkg2soln[p] = Soln(ifc2pkg=dict((i,s[i]) for i in reqs)
    return Soln(ifc2pkg=s, pkg2soln=pkg2soln)
  
    
def cycle_sets(xs):
  def tclose(xs):
    xs = dict((x,set(xs[x])) for x in xs)
    again = True
    while again:
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

def solve2(repo, pkgs, unbound, pref=lambda i,ps:None):
  """
  Returns the dict that maps interfaces to packages.
  It will be complete with all buildtime/runtime dependencies and subsumed
  interfaces.
  
  repo: repository.Repo
  pkgs: iterable of packages to consider
  unbound: iterable of initial required interfaces
  bound: bound interfaces, must be closed under subsumption
  pref: (ifc,pkgs)->[pkg] -- given a choice of implementing packages,
        are there some that would be best?  Solutions beyond those found with
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
        if len(best or ()) == 0:
          break
        solved = False
        for p in best:
          ps.discard(p)
          mins = (i1 for i1 in repo.pkg_implements(p) if i in repo.ifc_subsets(i1))
          mins = repo.min_ifcs(mins)
          for i1 in mins:
            revert = bind(i1, p)
            if revert is not None:
              for soln in branch():
                solved = True
                yield soln
              revert()
        if solved:
          ps = ()
          break
      
      # bind interface to remaining non-preferred packages
      for p in ps:
        mins = (i1 for i1 in repo.pkg_implements(p) if i in repo.ifc_subsets(i1))
        mins = repo.min_ifcs(mins)
        for i1 in mins:
          revert = bind(i1, p)
          if revert is not None:
            for soln in branch():
              yield soln
            revert()
  
  numsoln = 0
  for soln in branch():
    if numsoln == 1:
      raise SolutionError("Interface solution ambiguity.")
    ans = soln
    numsoln += 1
  if numsoln == 0:
    raise SolutionError("Interfaces unsolvable.")
  return ans

def test(ifcs=['cc']):
  repo = Repo({
    'gcc':{'cc':Imp(buildreqs=['cc','mpr'])},
    'bad':{'cc':Imp()},
    'gmpr':{'mpr':Imp(buildreqs=['cc'])}
  })
  def pref(i,ps):
    if i=='cc' and 'gcc' in ps:
      return ['gcc']
    else:
      return []
  return solve(repo, ifcs, pref)
