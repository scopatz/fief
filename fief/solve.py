
def solve(repo, ifcs):
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
    
    loop = [ifc]
    loop.extend(repo.pkg_ifc_reqs(pkg, ifc))
    
    # THIS LOOP NEEDS ATTENTION
    while len(loop) > 0:
      more = set()
      for i in loop:
        if i not in world:
          world.add(i)
          world_adds.append(i)
        for s in repo.ifc_subs(i):
          if s not in world:
            if part[i] == part[ifc]:
              more.update(repo.pkg_ifc_reqs(pkg, s))
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
      unbound.update(unbound_dels)
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
        ps = repo.ifc_imps(i)
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
        mbr[b].update(mbr[a])
        if dep[a] == dep[b]:
          dep[b] += 1
      else:
        log.extend((b, dep[a]))
        rep[b] = a
        mbr[a].update(mbr[b])
  
  def state(me):
    return len(me._log)
  
  def revert(me, st):
    rep, dep, mbr = me._rep, me._dep, me._mbr
    log = me._log
    while st < len(log):
      dep_b, a = log.pop(), log.pop()
      b = rep[a]
      rep[a] = a
      mbr[b].difference_update(mbr[a])
      dep[b] = dep_b
