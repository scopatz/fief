import os
import sys
from .. import async
from .. import bake
from .. import *
from .. import fief
from .. import deliver
import _magic

def main(ns, rcpath):
  """Realizes the current fief selection."""
  
  Cmd.showout = ns.verbose
  
  def top_a():
    finst = yield async.Sync(fief.Fief.new_a(rcpath))
    activated = _magic.env_selection(finst)
    soln, delv = yield async.Sync(deliver.deliver_a(finst, activated))
    
    ed = EnvDelta()
    for ifc in soln.ifc2node():
      e = delv(ifc, 'envdelta')
      if e is not None:
        ed.merge(e)
    
    env0 = dict(os.environ)
    env1 = ed.apply(env0)
    env1['FIEF_KNOWN_INTERFACES'] = " ".join(sorted(finst.repo.interfaces()))
    _magic.exportvars(env1, env0)  

  try:
    async.run(top_a())
  except Exception, e:
    if hasattr(e, 'async_traceback'):
      sys.stderr.write(str(e.async_traceback) + '\n')
    raise
  return 0
