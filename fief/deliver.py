#!/usr/bin/env python
import os
import sys
import shutil
import subprocess

import async
import bake
from repo import ifc

def deliver_a(oven, conf, repo, ifcs):
  def less(ifc, a, b):
    return a == conf.preferences.get(ifc)
  
  def compare_soln(a, b):
    a_less, b_less = False, False
    for x in set(a.keys() + b.keys()):
      ax, bx = a.get(x), b.get(x)
      if ax != bx:
        if ax is None or less(x, ax, bx):
          a_less = True
        elif bx is None or less(x, bx, ax):
          b_less = True
    if a_less and not b_less:
      return -1
    if b_less and not a_less:
      return 1
    return 0
  
  least = []
  for a in repo.solve_pkgs(ifcs):
    add_a = False
    for b in list(least):
      c = compare_soln(a, b)
      if c < 0:
        add_a = True
        least.remove(b)
      elif c == 0:
        add_a = True
      else:
        assert not add_a
    if add_a:
      least.append(a)
  
  if len(least) > 1:
    ambig = {}
    for soln in least:
      for x in soln:
        ambig[x] = ambig.get(x, set())
        ambig[x].add(soln[x])
    msg = "Package selection for the following interface(s) is ambiguous:"
    msg += '\n  '.join(i + ': ' + ', '.join(ps) for i,ps in ambig.items() if len(ps) > 1)
    raise Exception(msg)
  elif len(least) == 0:
    empt = [i for i in repo.interfaces() if len(repo.ifc_imps(i)) == 0]
    msg = "No package solution could be found."
    if len(empt) > 0:
      msg += "  The following interfaces have no implementing packages: " + ", ".join(empt)
    raise Exception(msg)
  
  soln = least[0]
  
  for pkg in set(soln.values()):
    def lam(pkg):
      def args(x):
        if type(x) is tuple and len(x)==2 and x[0]=='interface':
          return soln.get(x[1])
        elif type(x) is tuple and len(x)==2 and x[0]=='option':
          return conf.option(pkg, x[1])
        else:
          return None
      bldr = repo.pkg_builder(pkg)
      bconf = BoundConf(conf, ctx)
      # BROKEN, pick up here
      def build_a(ctx):
        yield async.WaitFor(bldr(ctx))
      yield async.Task(pkg, oven.memo_a(build_a, args))
      

def deliver_a(oven, active_ifcs, lazy=False):
  reqs = set()
  for ifc in active_ifcs:
    reqs |= repo.requirements(ifc)
    reqs.add(ifc)
  
  ifc2pkg = repo.active_packages(reqs)
  
  args = {}
  pkgs = set()
  for ifc in reqs:
    pkg = ifc2pkg[ifc]
    args['interface', ifc] = pkg
    pkgs.add(pkg)
  
  for pkg in pkgs:
    args1 = dict(args)
    args1['pkg'] = pkg
    if lazy:
      assert False
    else:
      yield async.Task(pkg, oven.memo_a(repo.packages[pkg].builder, args1))
  
  deliverables = {}
  while True:
    got = yield async.WaitAny
    if got is None: break
    pkg, delivs = got
    deliverables[pkg] = delivs
  yield async.Result(deliverables)
