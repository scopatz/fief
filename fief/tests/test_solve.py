from nose.tools import assert_equal, assert_raises

import os
from fief.solve import solve, DisjointSets
from fief.repository import Repo, Package, ifc

def MockPackage(ifx):
  return ifx

# destroy order! chaos reigns!
sditems = lambda x: set(frozenset(d.iteritems()) for d in x)

def check_case(nm, pkgs, ifcs, exp):
  repo = Repo(pkgs)
  obs = sditems(solve(repo, ifcs))
  assert_equal(obs, sditems(exp))

cases = (
# 1 pkg, no deps
('#0', {'zlib': MockPackage({'zlib': ifc()})}, ['zlib'], [{'zlib': 'zlib'}]),
# 2 pkgs, 1 dep
('#1', {'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}),}, 
 ['zlib'],
 [{'zlib': 'zlib', 'cc': 'sys_cc'}]),
# 3 pkgs, 2 deps, realize middle
('#2', {'sys_cc':  MockPackage({'cc': ifc()}), 
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib')}), 
  },
 ['zlib'],
 [{'zlib': 'zlib', 'cc': 'sys_cc'}]),
# 3 pkgs, 2 deps, realize all
('#3', {'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib')}), 
  }, 
 ['hdf5'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5'}]),
# 3 pkgs, 2 deps, realize all, skip subsumption
('#4', {'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib')}), 
  }, 
 ['hdf5'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5'}]),
# 3 pkgs, 2 deps, realize all, use subsumption
('#5', {'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
   'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'),
                        'hdf5-parallel': ifc(subsumes='hdf5')}),
  },
 ['hdf5-parallel'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5'}]),
# 4 pkgs, 3 deps, realize all, use subsumption
('#6', {'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'mpich': MockPackage({'mpi2': ifc(requires='cc')}),
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'), 
                        'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi2')}), 
  }, 
 ['hdf5-parallel'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5', 
   'mpi2': 'mpich'}]),
# 4 pkgs, 3 deps, realize all, multiple interfaces in subsumption, use lowest
('#7', {'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'mpich': MockPackage({'mpi2': ifc(requires='cc'), 'mpi3': ifc(subsumes='mpi2')}),
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'), 
                        'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi2')}), 
  }, 
 ['hdf5-parallel'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5', 
   'mpi2': 'mpich'}]),
# 4 pkgs, 3 deps, realize all, multiple interfaces in subsumption, use highest
('#8', {'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'mpich': MockPackage({'mpi2': ifc(requires='cc'), 'mpi3': ifc(subsumes='mpi2')}),
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'), 
                        'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi3')}), 
  }, 
 ['hdf5-parallel'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5', 
   'mpi3': 'mpich', 'mpi2': 'mpich'}]),
# 4 pkgs, 3 deps, realize all, multiple interfaces in subsumption, ambiguous interface
('#9', {'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'mpich': MockPackage({'mpi': ifc(requires='cc'), 
                        'mpi2': ifc(subsumes='mpi'),
                        'mpi3': ifc(subsumes='mpi')}),
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'), 
                        'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi')}), 
  }, 
 ['hdf5-parallel'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5', 
   'mpi': 'mpich'},]),
# 4 pkgs, 3 deps, realize all, multiple interfaces in subsumption, ambiguous interface
('#10', {'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'mpich': MockPackage({'mpi': ifc(requires='cc'), 
                        'mpi2': ifc(subsumes='mpi'),
                        'mpi3': ifc(subsumes='mpi')}),
  'openmpi': MockPackage({'mpi2': ifc()}),
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'), 
                        'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi')}), 
  }, 
 ['hdf5-parallel'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5', 
   'mpi': 'mpich'},
  {'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5', 
   'mpi2': 'openmpi', 'mpi': 'openmpi'}]),
)

def test_cases():
  for nm, pkgs, ifcs, exp in cases:
    yield check_case, nm, pkgs, ifcs, exp
