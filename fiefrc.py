import os
from fief import easy

stash = ".fief-stash"

preference = {
  'mpi2': 'mpich'
}.get

def option(pkg, x):
  return {
    'make-opt-parallel': ('-j', '4')
  }.get(x)

packages = easy.packages

def implied(x, on):
  return {
    'mpi1-wrap-fortran': lambda: on('fortran') and on('mpi1'),
    'mpi2-wrap-fortran': lambda: on('fortran') and on('mpi2'),
    'mpi3-wrap-fortran': lambda: on('fortran') and on('mpi3')
  }.get(x, lambda: False)()
