import os
from fief import easy

stash = ".fief-stash"

preference = {
  'mpi2': 'openmpi'
}.get

def option(pkg, x):
  return {
    'make-opt-parallel': ('-j', '4')
  }.get(x)

packages = easy.packages
