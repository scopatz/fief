#!/usr/bin/env python
import os
import sys
import shutil
import subprocess

import async
import bake
import repo

def deliver_a(oven, active_ifcs):
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
    yield async.Task(pkg, oven.memo_a(repo.packages[pkg].builder, args1))
  
  deliverables = {}
  while True:
    got = yield async.WaitAny
    if got is None: break
    pkg, delivs = got
    deliverables[pkg] = delivs
  #from pprint import pformat; sys.stderr.write(pformat(deliverables) + '\n')
  yield async.Result(deliverables)
