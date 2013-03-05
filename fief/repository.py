import os

import bake
import async

#ensure_frozenset = lambda x: frozenset(x if hasattr(x, '__iter__') else (x,))
ensure_frozenset = lambda x: set(x if hasattr(x, '__iter__') else (x,))

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
  def realize(me, delivs):
    """returns EnvDelta"""
    raise Exception('Not implemented.')
  def builder(me):
    """returns async function ctx,pkg_name,src_dir -> delivs"""
    raise Exception('Not implemented.')

class PackageScript(Package):
  def __init__(me source, py_file):
    me._src = source
    me._py = py_file
    me._ifx = None
    me._ns = None

  def source(me):
    return me._src

  def interfaces_a(me, oven):
    def pack_ifx(ifx):
      return dict((nm,x.__getstate__()) for nm,x in ifx.iteritems())
    
    def unpack_ifx(s):
      def unpack(t):
        i = ifc()
        i.__setstate__(t)
        return i
      return dict((nm,unpack(x)) for nm,x in s.iteritems())

    def packed_ifx_a(ctx):
      ns = {}
      execfile(ctx['py'], ns, ns)
      yield async.Result(pack_ifx(ns['interfaces']))

    if me._ifx is None:
      me._ifx = yield async.WaitFor(oven.memo_a(packed_ifx, {'py':me._py}))
      me._ifx = unpack_ifx(me._ifx)
    
    yield async.Result(me._ifx)
  
  def _ensure_ns(me):
    if me._ns is None:
      me._ns = {}
      execfile(me._py, me._ns, me._ns)

  def realize(me, delivs):
    me._ensure_ns()
    return me._ns['realize'](delivs)

  def builder(me):
    me._ensure_ns()
    return me._ns['build_a']

class Repo(object):
  @classmethod
  def new_a(cls, oven, pkgs):
    pkg_ifc_reqs = {} # {(pkg,ifc):set(ifc)}
    ifcs = set()
    ifc_imps = {}
    ifc_subs = {}
    
    for pkg,pobj in pkgs.iteritems():
      ifx = yield async.WaitFor(pobj.interfaces_a(oven))
      for ifc in ifx:
        ifcs.add(ifc)
        ifc_imps[ifc] = ifc_imps.get(ifc, set())
        ifc_imps[ifc].add(pkg)
        ifc_subs[ifc] = ifc_subs.get(ifc, set())
        ifc_subs[ifc].update(ifx[ifc].subsumes)
        pkg_ifc_reqs[pkg,ifc] = ifx[ifc].requires
    
    me = cls()
    me._pkgs = dict(pkgs)
    me._pkg_ifc_reqs = pkg_ifc_reqs
    me._ifcs = frozenset(ifcs)
    me._ifc_imps = dict((ifc,frozenset(imps)) for ifc,imps in ifc_imps.iteritems())
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
  
  def ifc_imps(me, ifc):
    """Maps interface to set of packages that implements it."""
    return me._ifc_imps.get(ifc, frozenset())
  
  def pkg_ifc_reqs(me, pkg, ifc):
    """Returns set of interfaces that are required if `pkg` were to implement `ifc`."""
    return me._pkg_ifc_reqs.get((pkg,ifc), frozenset())
