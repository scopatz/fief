import sys

def solve(repo, ifcs, pref=lambda i,ps:None, imply=lambda x,on: False):
  """Returns an iterable of dicts that map interfaces to packages.
  Each dict will be complete with all dependencies and subsumed interfaces.
  
  repo: repository.Repo
  ifcs: iterable of initial required interfaces
  pref: lambda (ifc,pkgs)->[pkg] -- given a choice of implementing packages,
        are there some that would be best?  Solutions beyond those found with
        one of these bindings will be skipped.
  """
  
  # solver state
  world = repo.ifcs_subsets(ifcs) # all interfaces ever required
  impldep = {}
  
  more = repo.interfaces()
  while len(more) > 0:
    more0 = more
    more = []
    for x in more0:
      if x not in world:
        def spy(y):
          impldep[y] = impldep.get(y, set())
          impldep[y].add(x)
          return y in world
        if imply(x, spy):
          world.add(x)
          more.extend(impldep.get(x, ()))
  
  bound = {} # bound interfaces, closed by subsumption
  unbound = set(world) # interfaces required but not yet bound
  
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
    
    for i in repo.pkg_ifc_requires(pkg, ifc):
      if i not in world:
        world.add(i)
        world_adds.append(i)
        unbound.add(i)
        unbound_adds.append(i)
    
    more = world_adds
    while len(more) > 0:
      wake = set()
      for x in more:
        wake.update(impldep.get(x, ()))
      more = []
      for x in wake:
        if x not in world:
          def spy(y):
            impldep[y] = impldep.get(y, set())
            impldep[y].add(x)
            return y in world
          if imply(x, spy):
            world.add(x)
            world_adds.append(x)
            unbound.add(x)
            unbound_adds.append(x)
            more.append(x)
    
    return revert
  
  def branch():
    if len(unbound) == 0:
      # report a solution
      yield dict((i,bound[i]) for i in world if i in bound)
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
      
      # bind interface to remainnig non-preferred packages
      for p in ps:
        mins = (i1 for i1 in repo.pkg_implements(p) if i in repo.ifc_subsets(i1))
        mins = repo.min_ifcs(mins)
        for i1 in mins:
          revert = bind(i1, p)
          if revert is not None:
            for soln in branch():
              yield soln
            revert()
  
  return branch()
