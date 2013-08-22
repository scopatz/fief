import sys

from repository import Repo, Imp
import valtool

class Soln(object):
  def __init__(me, ifc2pkg, pkg2soln):
    me._env = set()
    me._i2n = None
    me._nd_pkg = {}
    me._nd_imps = {}
    me._nd_env = {}
    for s in pkg2soln.itervalues():
      me._nd_pkg.update(s._nd_pkg)
      me._nd_imps.update(s._nd_imps)
      me._nd_env.update(s._nd_env)
    
    for p in set(ifc2pkg.itervalues()):
      imps = frozenset(i for i in ifc2pkg if ifc2pkg[i] == p)
      nd = valtool.Hasher().eatseq([p, imps, pkg2soln[p]._env]).digest()
      me._env.add(nd)
      me._nd_pkg[nd] = p
      me._nd_imps[nd] = imps
      me._nd_env[nd] = pkg2soln[p]._env
  
    me._env = frozenset(me._env)
  
  def env_nodes(me):
    return me._env
  def node_pkg(me, nd):
    return me._nd_pkg[nd]
  def node_imps(me, nd):
    return me._nd_imps[nd]
  def node_env(me, nd):
    return me._nd_env[nd]
  
  def all_nodes(me, initial=None):
    if initial is None:
      initial = me._env
    xset = set()
    xlist = []
    def drill(xs):
      for x in xs:
        if x not in xset:
          drill(me._nd_env[x])
          xset.add(x)
          xlist.append(x)
    drill(initial)
    return xlist
  
  def node_soln(me, nd):
    s = Soln.__new__(Soln)
    s._i2n = None
    s._env = me._nd_env[nd]
    s._nd_pkg = me._nd_pkg
    s._nd_imps = me._nd_imps
    s._nd_env = me._nd_env
    return s
  
  def ifc2node(me):
    if me._i2n is None:
      i2n = {}
      for e in me._env:
        for i in me._nd_imps[e]:
          i2n[i] = e
      me._i2n = i2n
    return me._i2n
  
  def __getstate__(me):
    a = me.all_nodes()
    def shrink(d):
      return d if len(a) == len(d) else dict((x,d[x]) for x in a)
    return (me._env, shrink(me._nd_pkg), shrink(me._nd_imps), shrink(me._nd_env))
  def __setstate__(me, s):
    me._env, me._nd_pkg, me._nd_imps, me._nd_env = s
  def __hash__(me):
    return hash(me._env)
  def __eq__(me, that):
    return me._env == that._env
  def __ne__(me, that):
    return me._env != that._env
  
  def __repr__(me):
    return 'Soln(\n' + str(me) + ')'
  def __str__(me):
    def indent(s):
      return '' if len(s)==0 else '\n'.join(['  '+l for l in s.split('\n')])
    return '\n'.join([
      'pkg='+str(me._nd_pkg[n]) + '; imps=' + str(me._nd_imps[n])+'\n'+\
      indent(str(me.node_soln(n)))
      for n in me._env
    ])

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
  more = list(ifcs)
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
      print 'soln 1:', ans
      print 'soln 2:', soln
      raise SolveError("Interface solution ambiguity.")
    ans = soln
    numsoln += 1
  if numsoln == 0:
    raise SolveError("Interfaces unsolvable.")
  return ans
