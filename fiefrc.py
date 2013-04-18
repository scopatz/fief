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
implied = easy.implied
