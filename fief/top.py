#!/usr/bin/env python
import os
import async
import bake
import subprocess
import sys
import shutil
import magic

returncode = [None]

def top_a(ctx):
  pkg = ctx['pkg']
  path, libs = yield async.WaitFor(ctx(magic.builders[pkg]))
  yield async.Result((path, libs))

config = {
  'zlib': ('zlib-1.2.7.tar.gz', 'zlib.py'), 
  'hdf5': ('hdf5-1.8.10-patch1.tar.gz', 'hdf5.py'), 
  'mpich3': ('mpich-3.0.1.tar.gz', 'mpich.py'), 
  'cython': ('Cython-0.18.tar.gz', 'cython.py'), 
  'numpy': ('numpy-1.7.0rc1.tar.gz', 'numpy.py'),
  'atlas': ('atlas3.10.1.tar.bz2', 'atlas.py')
  }

def main_a():
  oven = bake.Oven(bake.MemoHost(bake.FileHost_a), "oven")
  try:
    # args = {
    #   'pkg': 'zlib',
    #   ('interface','zlib'): True,
    #   }
    # args = {
    #   'pkg': 'mpich3',
    #   ('interface','mpi3'): True,
    #   }
#    args = {
#      'pkg': 'hdf5',
#      ('interface','hdf5-parallel'): True,
#    }
#    args = {
#      'pkg': 'cython',
#      ('interface','cython'): True,
#    }
    args = {
      'pkg': 'numpy',
      ('interface','numpy'): True,
    }
#    args = {
#      'pkg': 'sympy',
#      'repo': 'repo',
#      ('source', 'sympy'): ('tarball', 'sympy-0.7.2.tar.gz'),
#    }
    tup = yield async.WaitFor(oven.memo_a(top_a, args))
    returncode[0] = 0
    print(tup)
  except subprocess.CalledProcessError, e:
    returncode[0] = e.returncode
  
  yield async.WaitFor(oven.close_a())

magic.init(config)
async.run(main_a())
exit(returncode[0])
