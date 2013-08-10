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
  rank = 2
  while rank >= 0:
    s = solve2(repo, ifcs, pref)
    ps = set(s.itervalues())
    p_breq = {} # pkg -> ifcs needed for building
    for p in ps:
      imps = set(i for i in repo.pkg_implements(p) if i in s and s[i] == p)
      p_breq[p] = set(s[i] for i in repo.pkg_ifcs_buildreqs(p, imps))
    rank -= 1
    
    pkg2soln = {}
    for p in ps:
      def rank1():
        p0 = p
        return lambda p: rank(p) + (1 if p == p0 else 0)
      rank1 = rank1()
      pkg2soln[p] = solve(
        constrain(repo, rank1, s),
        ifcs=p_breq[p], pref=pref, rank=rank1
      )
  
  return Soln(ifc2pkg=s, pkg2soln=pkg2soln)

def solve2(repo, unbound, bound={}, pref=lambda i,ps:None):
  """Returns the dict that maps interfaces to packages.
  It will be complete with all runtime dependencies and subsumed interfaces.
  
  repo: repository.Repo
  unbound: iterable of initial required interfaces
  bound: bound interfaces, must be closed under subsumption
  pref: (ifc,pkgs)->[pkg] -- given a choice of implementing packages,
        are there some that would be best?  Solutions beyond those found with
        one of these bindings will be skipped.
  """
  
  # solver state
  unbound = set(unbound)
  bound = dict(bound)
  world = repo.ifcs_subsets(unbound) | set(bound) # all interfaces ever required closed by subsumption
  
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
        ps = repo.ifc_implementors(i)
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
