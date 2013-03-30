
def solve(repo, ifcs):
  """Returns an iterable of dicts that map interfaces to packages.
  Each dict will be complete with all dependencies and subsumed interfaces."""
  
  # solver state
  part = DisjointSets() # equivalence partition for interface subsumption
  world = set(repo.ifcs_subs(ifcs)) # interfaces seen so far
  
  for a in world:
    for b in repo.ifc_subs(a):
      part.merge(a, b)
  
  bound = {} # bound interface reps to packages
  unbound = set(part[i] for i in world) # interface reps not yet bound
  
  # modify state of solver by binding ifc to pkg, returns `revert` lambda if
  # successful, otherwise None.
  def bind(ifc, pkg):
    assert all(i not in bound for i in unbound)
    assert part[ifc] not in bound
    assert part[ifc] in unbound
    
    part_st = part.state()
    world_adds = []
    changed = set()
    
    for i in repo.pkg_ifc_reqs(pkg, ifc):
      if i not in world:
        world.add(i)
        world_adds.append(i)
        for s in repo.ifc_subs(i):
          if part[i] != part[s]:
            changed.update(part.members(part.merge(i, s)))
    
    bound_adds = set()
    unbound_adds = []
    unbound_dels = set()
    
    def revert():
      part.revert(part_st)
      world.difference_update(world_adds)
      for i in bound_adds:
        del bound[i]
      unbound.difference_update(unbound_adds)
      unbound.update(unbound_dels)
    
    bound[ifc] = pkg
    bound_adds.add(ifc)
    unbound.discard(ifc)
    unbound_dels.add(ifc)
    
    for i in changed:
      if i in bound:
        i1 = part[i]
        if i != i1:
          if i1 in bound:
            if bound[i] != bound[i1]:
              revert()
              return None
          else:
            bound[i1] = bound[i]
            bound_adds.add(i1)
    
    for i in changed:
      if i in unbound:
        i1 = part[i]
        if i1 in bound:
          unbound.discard(i)
          unbound_dels.add(i)
        elif i != i1:
          unbound.discard(i)
          unbound_dels.add(i)
          if i1 not in unbound:
            unbound.add(i1)
            unbound_adds.append(i1)
    
    for i in world_adds:
      i1 = part[i]
      if i1 not in bound and i1 not in unbound:
        unbound.add(i1)
        unbound_adds.append(i1)
    print 'world:', world
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
      return me._mbr[x]
    else:
      return (x,)
  
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
        mbr[x] = [x]
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
        mbr[b].extend(mbr[a])
        if dep[a] == dep[b]:
          dep[b] += 1
        return b
      else:
        log.extend((b, dep[a]))
        rep[b] = a
        mbr[a].extend(mbr[b])
        return a
    else:
      return a
  
  def state(me):
    return len(me._log)
  
  def revert(me, st):
    rep, dep, mbr = me._rep, me._dep, me._mbr
    log = me._log
    while st < len(log):
      dep_b, a = log.pop(), log.pop()
      b = rep[a]
      rep[a] = a
      del mbr[b][len(mbr[b])-len(mbr[a]):]
      dep[b] = dep_b
