#!/usr/bin/env python
import os
import sys
import shutil
import subprocess

import async
import bake
import magic

returncode = [None]

def top_a(ctx):
  pkg = ctx['pkg']
  path, libs = yield async.WaitFor(ctx(magic.builders[pkg]))
  yield async.Result((path, libs))

def main_a(activated):
  args = {}
  reqs = set()
  pkgs = set()
  for act in activated:
    reqs |= magic.requirements(act)
  print reqs
  for ifc in reqs:
    args['interface', ifc] = True
    #pkgs.add(magic.ifc2pkg[act])
  exit(0)
  oven = bake.Oven(bake.MemoHost(bake.FileHost_a), "oven")
  try:
    pathlibs = []
    for pkg in pkgs:
      pkgargs = {'pkg': pkg}
      pkgargs.update(dict(args))
      pathlib = yield async.WaitFor(oven.memo_a(top_a, pkgargs))
      pathlibs.append(pathlib)
    returncode[0] = 0
    print(pathlibs)
  except subprocess.CalledProcessError, e:
    returncode[0] = e.returncode
  
  yield async.WaitFor(oven.close_a())
