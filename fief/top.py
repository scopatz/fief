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
