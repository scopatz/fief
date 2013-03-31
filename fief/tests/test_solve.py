from nose.tools import assert_equal, assert_raises

import os
from fief import async
from fief.solve import solve, DisjointSets
from fief.repository import Repo, Package, ifc

class MockPackage(Package):
  """A package class with an alternate interfaces_a() for testing."""

  def __init__(me, ifx=None):
    super(MockPackage, me).__init__()
    me._ifx = ifx or {}

  def interfaces_a(me, oven):
    yield async.Result(me._ifx)

def run_async(f):
  def test_runner():
    async.run(f())
  return test_runner

# destroy order! chaos reigns!
sditems = lambda x: set(frozenset(d.iteritems()) for d in x)

def check_case(pkgs, ifcs, exp):
  def a():
    repo = yield async.Sync(Repo.new_a(None, pkgs))
    obs = sditems(solve(repo, ifcs))
    assert_equal(obs, sditems(exp))
  async.run(a())

cases = ( # pkgs, exp
# 1 pkg, no deps
({'zlib': MockPackage({'zlib': ifc()})}, ['zlib'], [{'zlib': 'zlib'}]),
# 2 pkgs, 1 dep
({'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}),}, 
 ['zlib'],
 [{'zlib': 'zlib', 'cc': 'sys_cc'}]),
# 3 pkgs, 2 deps, realize middle
({'sys_cc':  MockPackage({'cc': ifc()}), 
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib')}), 
  },
 ['zlib'],
 [{'zlib': 'zlib', 'cc': 'sys_cc'}]),
# 3 pkgs, 2 deps, realize all
({'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib')}), 
  }, 
 ['hdf5'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5'}]),
# 3 pkgs, 2 deps, realize all, skip subsumption
({'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib')}), 
  }, 
 ['hdf5'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5'}]),
# 3 pkgs, 2 deps, realize all, use subsumption
({'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
   'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'),
                        'hdf5-parallel': ifc(subsumes='hdf5')}),
  },
 ['hdf5-parallel'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5'}]),
# 4 pkgs, 3 deps, realize all, use subsumption
({'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'mpich': MockPackage({'mpi2': ifc(requires='cc')}),
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'), 
                        'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi2')}), 
  }, 
 ['hdf5-parallel'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5', 
   'mpi2': 'mpich'}]),
# 4 pkgs, 3 deps, realize all, multiple interfaces in subsumption, use lowest
({'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'mpich': MockPackage({'mpi2': ifc(requires='cc'), 'mpi3': ifc(subsumes='mpi2')}),
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'), 
                        'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi2')}), 
  }, 
 ['hdf5-parallel'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5', 
   'mpi2': 'mpich'}]),
# 4 pkgs, 3 deps, realize all, multiple interfaces in subsumption, use highest
({'sys_cc':  MockPackage({'cc': ifc()}),
  'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'mpich': MockPackage({'mpi2': ifc(requires='cc'), 'mpi3': ifc(subsumes='mpi2')}),
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'), 
                        'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi3')}), 
  }, 
 ['hdf5-parallel'],
 [{'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5', 
   'mpi3': 'mpich', 'mpi2': 'mpich'}]),
# 4 pkgs, 3 deps, realize all, multiple interfaces in subsumption, ambiguous interface
({'sys_cc':  MockPackage({'cc': ifc()}),
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
({'sys_cc':  MockPackage({'cc': ifc()}),
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
   'mpi': 'openmpi'}]),
)

def test_cases():
  for pkgs, ifcs, exp in cases:
    yield check_case, pkgs, ifcs, exp
