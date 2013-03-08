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

def check_case(pkgs, ifcs, exp):
  def a():
    repo = yield async.WaitFor(Repo.new_a(None, pkgs))
    obs = [s for s in solve(repo, ifcs)][0]
    assert_equal(obs, exp)
  async.run(a())

cases = ( # pkgs, exp
# 1 pkg, no deps
({'zlib': MockPackage({'zlib': ifc()})}, ['zlib'], {'zlib': 'zlib'}),
# 2 pkgs, 1 dep
({'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'sys_cc':  MockPackage({'cc': ifc()})}, 
 ['zlib'],
 {'zlib': 'zlib', 'cc': 'sys_cc'}),
# 3 pkgs, 2 deps, realize middle
({'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib')}), 
  'sys_cc':  MockPackage({'cc': ifc()})}, 
 ['zlib'],
 {'zlib': 'zlib', 'cc': 'sys_cc'}),
# 3 pkgs, 2 deps, realize all
({'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib')}), 
  'sys_cc':  MockPackage({'cc': ifc()})}, 
 ['hdf5'],
 {'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5'}),
# 3 pkgs, 2 deps, realize all, skip subsumption
({'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'), 
                        'hdf5-parallel': ifc(subsumes='hdf5')}), 
  'sys_cc':  MockPackage({'cc': ifc()})}, 
 ['hdf5'],
 {'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5'}),
# 3 pkgs, 2 deps, realize all, use subsumption
({'zlib': MockPackage({'zlib': ifc(requires='cc')}), 
  'hdf5':  MockPackage({'hdf5': ifc(requires='zlib'), 
                        'hdf5-parallel': ifc(subsumes='hdf5')}), 
  'sys_cc':  MockPackage({'cc': ifc()})}, 
 ['hdf5-parallel'],
 {'zlib': 'zlib', 'cc': 'sys_cc', 'hdf5': 'hdf5', 'hdf5-parallel': 'hdf5'}),
)

def test_cases():
  for pkgs, ifcs, exp in cases:
    yield check_case, pkgs, ifcs, exp
