_undo_key = 'FIEF_UNDO'

class EnvDelta(object):
  def merge(me, that):
    assert(set(me._sca_defs).isdisjoint(that._set_adds))
    assert(set(me._set_adds).isdisjoint(that._sca_defs))
    assert all(
      me._sca_defs[k] == that._sca_defs[k]
      for k in set(me._sca_defs) & set(that._sca_defs.keys()))
    
    for k in that._set_adds:
      if k not in me._set_adds:
        me._set_adds[k] = set()
      me._set_adds[k].union_update(that._set_adds[k])
    
    for k in that._sca_defs:
      me._sca_defs[k] = that._sca_defs[k]
  
  def apply(me, env):
    pass
  
  def unapply(me, env):
    pass
  
  def add(me, var, vals):
    me.merge(EnvDeltaSetAdd(var, vals))
  
  def define(me, var, val):
    me.merge(EnvDeltaScalarDefine(var, val))

class EnvDeltaSetAdd(EnvDelta):
  def __init__(me, var, vals):
    me._set_adds = {var: set(vals)}
    me._sca_defs = {}

class EnvDeltaScalarDefine(EnvDelta):
  def __init__(me, var, val):
    me._set_adds = {}
    me._sca_defs = {var: val}
    
    
