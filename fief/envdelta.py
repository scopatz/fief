import os
from copy import deepcopy

_undo_key = 'FIEF_UNDO'

class EnvDelta(object):
  def __init__(me, sets=None, scalars=None):
    me._set_adds = sets or {}
    me._sca_defs = scalars or {}

  @classmethod
  def fromiter(cls, var, vals):
    return cls(sets={var: set(vals if hasattr(vals, '__iter__') else (vals,))})

  @classmethod
  def fromscalar(cls, var, val):
    return cls(scalars={var: val})

  def add(me, var, vals):
    if not hasattr(vals, '__iter__'):
        vals = (vals,)
    me.merge(EnvDelta.fromiter(var, vals))
  
  def define(me, var, val):
    me.merge(EnvDelta.fromscalar(var, val))

  def merge(me, that):
    assert(set(me._sca_defs).isdisjoint(that._set_adds))
    assert(set(me._set_adds).isdisjoint(that._sca_defs))
    assert all(
      me._sca_defs[k] == that._sca_defs[k]
      for k in set(me._sca_defs) & set(that._sca_defs))
    
    for k in that._set_adds:
      if k not in me._set_adds:
        me._set_adds[k] = set()
      me._set_adds[k].update(that._set_adds[k])
    
    for k in that._sca_defs:
      me._sca_defs[k] = that._sca_defs[k]
  
  # this has to be wrong
  def apply(me, env):
    newenv = deepcopy(env)
    undo = eval(env.get(_undo_key, 'None').strip('"')) or EnvDelta()
    for key, val in me._set_adds.items():
      undoval = undo._set_adds.get(key, ())
      origval = env.get(key, None)
      origval = [] if origval is None else origval.split(os.pathsep)
      origset = set(origval)
      newval = [v for v in val if v not in origset]
      newval += [v for v in origval if (v in undoval and v in val) or
                                       (v not in val)]
      newenv[key] = os.pathsep.join(newval)
    newenv.update(me._sca_defs)
    newenv[_undo_key] = repr(me)
    return newenv
  
  def unapply(me, env):
    pass
  
  def __repr__(me):
    r = "{0}(sets={1!r}, scalars={2!r})"
    return r.format(me.__class__.__name__, me._set_adds, me._sca_defs)

  def __eq__(me, other):
    if not isinstance(other, EnvDelta):
      return NotImplemented
    return (me._set_adds == other._set_adds) and (me._sca_defs == other._sca_defs)
