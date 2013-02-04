#!/usr/bin/env python
import os
import sys
import shutil
import subprocess

import async
import bake
import magic

returncode = [None]
deliverables = []

def top_a(ctx):
  pkg = ctx['pkg']
  delivs = yield async.WaitFor(ctx(magic.builders[pkg]))
  yield async.Result(delivs)

def main_a(activated):
  args = {}
  reqs = set()
  pkgs = set()
  for act in activated:
    reqs |= magic.requirements(act)
    reqs.add(act)
  ifc2pkg = magic.packages(reqs)
  for ifc in reqs:
    pkg = ifc2pkg[ifc]
    args['interface', ifc] = pkg
    pkgs.add(pkg)
  oven = bake.Oven(bake.MemoHost(bake.FileHost_a), "oven")
  try:
    for pkg in pkgs:
      pkgargs = {'pkg': pkg}
      pkgargs.update(dict(args))
      yield async.Task(pkg, oven.memo_a(top_a, pkgargs))
    while True:
      got = yield async.WaitAny
      if got is None:
        break
      pkg, delivs = got
      deliverables.append(delivs)
    returncode[0] = 0
    from pprint import pformat; sys.stderr.write(pformat(deliverables) + '\n')
  except subprocess.CalledProcessError, e:
    returncode[0] = e.returncode
  
  yield async.WaitFor(oven.close_a())
