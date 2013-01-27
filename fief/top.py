#!/usr/bin/env python
import async
import bake
import subprocess
import sys
import shutil
import magic

returncode = [None]

def top_a(ctx):
  pkg = ctx['pkg']
  bld_a = yield async.WaitFor(magic.builder_nomemo_a(ctx, pkg))
  path = yield async.WaitFor(ctx(bld_a))
  yield async.Result(path)

def main_a():
  oven = bake.Oven(bake.MemoHost(bake.FileHost_a), "oven")
  try:
    args = {
      'pkg': 'hdf5',
      'repo': 'repo',
      ('source','zlib'): ('tarball','zlib-1.2.7.tar.gz'),
      ('source','hdf5'): ('tarball','hdf5-1.8.10-patch1.tar.gz'),
      ('feature','hdf5','parallel'): False,
    }
    path = yield async.WaitFor(oven.memo_a(top_a, args))
    returncode[0] = 0
    sys.stdout.write(path)
  except subprocess.CalledProcessError, e:
    returncode[0] = e.returncode
  
  yield async.WaitFor(oven.close_a())

async.run(main_a())
exit(returncode[0])
