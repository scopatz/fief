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
  for act in activated:
    args['interface', act] = True
    magic.requirements(reqs, activated, magic.interfaces[act])
  oven = bake.Oven(bake.MemoHost(bake.FileHost_a), "oven")
  try:
    tup = yield async.WaitFor(oven.memo_a(top_a, args))
    returncode[0] = 0
    print(tup)
  except subprocess.CalledProcessError, e:
    returncode[0] = e.returncode
  
  yield async.WaitFor(oven.close_a())
