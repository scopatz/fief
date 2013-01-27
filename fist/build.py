#!/usr/bin/env python
import async
import bake
import subprocess
import build_zlib
import sys

returncode = [None]

def main_a():
  oven = bake.Oven(bake.MemoHost(bake.FileHost_a), "oven")
  try:
    args = {'tarball': 'zlib-1.2.7.tar.gz'}
    path = yield async.WaitFor(oven.memo_a(build_zlib.build_zlib_a, args))
    returncode[0] = 0
    sys.stdout.write(path)
  except subprocess.CalledProcessError, e:
    returncode[0] = e.returncode
  
  yield async.WaitFor(oven.close_a())

async.run(main_a())
exit(returncode[0])
