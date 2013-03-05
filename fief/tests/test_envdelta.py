from nose.tools import assert_equal, assert_raises

import os
from fief.envdelta import EnvDelta, _undo_key

def test_fromiter():
  e = EnvDelta.fromiter('x', range(10))
  o = EnvDelta(sets={'x': set(range(10))})
  assert_equal(e, o)

def test_fromscalar():
  e = EnvDelta.fromscalar('x', 'XXX')
  o = EnvDelta(scalars={'x': 'XXX'})
  assert_equal(e, o)

def test_add_sca():
  e = EnvDelta.fromiter('x', range(10))
  e.add('x', 10)
  o = EnvDelta(sets={'x': set(range(11))})
  assert_equal(e, o)

def test_add_iter():
  e = EnvDelta.fromiter('x', range(10))
  e.add('x', range(11))
  o = EnvDelta(sets={'x': set(range(11))})
  assert_equal(e, o)

def test_add_other():
  e = EnvDelta.fromiter('x', range(10))
  e.add('y', range(11))
  o = EnvDelta(sets={'x': set(range(10)), 'y': set(range(11))})
  assert_equal(e, o)

def test_define():
  e = EnvDelta.fromscalar('x', 'XXX')
  e.define('x', 'XXX')
  o = EnvDelta(scalars={'x': 'XXX'})
  assert_equal(e, o)

def test_define_other():
  e = EnvDelta.fromscalar('x', 'XXX')
  e.define('y', 'YYY')
  o = EnvDelta(scalars={'x': 'XXX', 'y': 'YYY'})
  assert_equal(e, o)

def test_merge_sca():
  e = EnvDelta.fromscalar('x', 'XXX')
  f = EnvDelta.fromscalar('y', 'YYY')
  e.merge(f)
  o = EnvDelta(scalars={'x': 'XXX', 'y': 'YYY'})
  assert_equal(e, o)

def test_merge_sca_bad():
  e = EnvDelta.fromscalar('x', 'XXX')
  f = EnvDelta.fromscalar('x', 'YYY')
  assert_raises(AssertionError, e.merge, f)

def test_merge_set_sca():
  e = EnvDelta.fromiter('x', range(10))
  f = EnvDelta.fromscalar('y', 'YYY')
  e.merge(f)
  o = EnvDelta(sets={'x': set(range(10))}, scalars={'y': 'YYY'})
  assert_equal(e, o)

def test_merge_set_sca_bad():
  e = EnvDelta.fromiter('x', range(10))
  f = EnvDelta.fromscalar('x', 'YYY')
  assert_raises(AssertionError, e.merge, f)

def test_merge_set():
  e = EnvDelta.fromiter('x', range(10))
  f = EnvDelta.fromiter('y', range(11))
  e.merge(f)
  o = EnvDelta(sets={'x': set(range(10)), 'y': set(range(11))})
  assert_equal(e, o)

def test_merge_set_bad():
  e = EnvDelta.fromiter('x', range(10))
  f = EnvDelta.fromiter('x', range(11))
  e.merge(f)
  o = EnvDelta(sets={'x': set(range(11))})
  assert_equal(e, o)

def test_apply_iter():
  env = {'x': '1', 'PATH': os.pathsep.join(['orig', 'paths'])}
  e = EnvDelta.fromiter('PATH', ['my', 'fun/paths'])
  exp = {'x': '1', 'PATH': os.pathsep.join(['fun/paths', 'my', 'orig', 'paths']),
         _undo_key: repr(e)}
  obs = e.apply(env)
  assert_equal(exp, obs)

def test_apply_sca():
  env = {'x': '1', 'PATH': os.pathsep.join(['orig', 'paths'])}
  e = EnvDelta(scalars={'x': '2', 'y': 'fun/paths'})
  exp = {'x': '2', 'PATH': os.pathsep.join(['orig', 'paths']), 'y': 'fun/paths',
         _undo_key: repr(e)}
  obs = e.apply(env)
  assert_equal(exp, obs)
  
def test_apply_sca_with_undo():
  env = {'x': '1', 'PATH': os.pathsep.join(['orig', 'paths'])}
  e = EnvDelta(scalars={'x': '2', 'y': 'fun/paths'})
  env = e.apply(env)
  f = EnvDelta(scalars={'x': '3', 'z': 'machine'})
  exp = {'x': '3', 'PATH': os.pathsep.join(['orig', 'paths']), 'y': 'fun/paths',
         'z': 'machine', _undo_key: repr(f)}
  obs = f.apply(env)
  assert_equal(exp, obs)
  
def test_apply_iter_with_undo():
  env = {'x': '1', 'PATH': os.pathsep.join(['orig', 'paths'])}
  e = EnvDelta.fromiter('PATH', ['my', 'fun/paths'])
  env = e.apply(env)
  f = EnvDelta.fromiter('PATH', ['truth', 'lies'])
  exp = {'x': '1', 'PATH': os.pathsep.join(['lies', 'truth', 
         'fun/paths', 'my', 'orig', 'paths']), _undo_key: repr(f)}
  obs = f.apply(env)
  assert_equal(exp, obs)
