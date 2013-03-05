from nose.tools import assert_equal, assert_raises

from fief.envdelta import EnvDelta


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
