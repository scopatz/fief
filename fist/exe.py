#!/usr/bin/env python
import async
import bake
import gxx_crawl
import os
import subprocess
import sys

returncode = [None]

def main_a():
  src = sys.argv[1] if len(sys.argv) > 1 else 'main.cxx'

  args = {
    "main": src,
    "libpaths": eval(os.environ.get("libpaths","[]"),{},{}),
    "h_lib": eval(os.environ.get("h_lib","{}"),{},{}),
    "lib_libs": eval(os.environ.get("lib_libs","{}"),{},{}),
    "linker": eval(os.environ.get("linker"),{},{})
  }
  def argroot(x):
    if x in args:
      return args[x]
    elif isinstance(x, tuple) and len(x)==2:
      if x[0] == 'env':
        return os.environ.get(x[1])
      elif x[0] in ('compiler','compile_flags'):
        return eval(os.environ.get(x[0],'{}'),{},{}).get(x[1],[])
      else:
        return None
    else:
      return None
  
  oven = bake.Oven(bake.MemoHost(bake.FileHost_a), ".oven")
  try:
    exe = yield async.WaitFor(oven.memo_a(gxx_crawl.crawl_a, argroot))
    returncode[0] = 0
    sys.stdout.write(exe)
  except subprocess.CalledProcessError, e:
    returncode[0] = e.returncode
  
  yield async.WaitFor(oven.close_a())

async.run(main_a())

if returncode[0] != 0:
  print >> sys.stderr, 'HALF BAKED: error occurred.'
exit(returncode[0])

