#!/usr/bin/env python
import os
import sys
import shutil
import subprocess

import async
import bake
import magic

def deliver_a(oven, active_ifcs):
  reqs = set()
  for ifc in active_ifcs:
    reqs |= magic.requirements(ifc)
    reqs.add(ifc)
  
  ifc2pkg = magic.packages(reqs)
  
  args = {}
  pkgs = set()
  for ifc in reqs:
    pkg = ifc2pkg[ifc]
    args['interface', ifc] = pkg
    pkgs.add(pkg)
  
  for pkg in pkgs:
    args1 = dict(args)
    args1['pkg'] = pkg
    yield async.Task(pkg, oven.memo_a(magic.builders[pkg], args1))
  
  deliverables = {}
  while True:
    got = yield async.WaitAny
    if got is None: break
    pkg, delivs = got
    deliverables[pkg] = delivs
  #from pprint import pformat; sys.stderr.write(pformat(deliverables) + '\n')
  yield async.Result(deliverables)
