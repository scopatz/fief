import sys

def solve(repo, ifcs):
  """Returns an iterable of dicts that map interfaces to packages.
  Each dict will be complete with all dependencies and subsumed interfaces."""
  
  # solver state
  world = set(ifcs) # all interfaces ever required
  bound = {} # bound interfaces, closed by subsumption
  unbound = set(ifcs) # interfaces required but not yet bound
  
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
    
    for i in repo.ifc_subs(ifc):
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
    
    if ifc not in world:
      world.add(ifc)
      world_adds.append(ifc)
    
    for i in repo.pkg_ifc_reqs(pkg, ifc):
      if i not in world:
        world.add(i)
        world_adds.append(i)
        unbound.add(i)
        unbound_adds.append(i)
    
    return revert
  
  def branch():
    if len(unbound) == 0:
      # report a solution
      yield dict((i,bound[i]) for i in world)
    else:
      # pick the interface with the least number of implementing packages
      i_min, ps_min = None, None
      for i in unbound:
        ps = repo.ifc_imps(i)
        if i_min is None or len(ps) < len(ps_min):
          i_min, ps_min = i, ps
      i, ps = i_min, ps_min
      # bind interface to each possible package and recurse
      for p in ps:
        least = repo.least_ifcs(i1 for i1 in repo.pkg_imps(p) if i in repo.ifc_subs(i1))
        for i1 in least:
          revert = bind(i1, p)
          if revert is not None:
            for x in branch():
              yield x
            revert()
  
  return branch()
