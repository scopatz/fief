import os
import sys
from .. import async
from .. import bake
from .. import magic
from .. import deliver
import _magic

USAGE = ("Realizes a fief active set."
         "usage: fief [realize]")

def main(ns, conf):
  """Realizes a fief active set."""
  repo = {}
  execfile(os.path.join('repo', '__repo__.py'), repo, repo)
  
  def top_a():
    oven = bake.Oven(bake.MemoHost(bake.FileHost_a), "oven")
    magic.Cmd.showout = ns.verbose
    yield async.WaitFor(magic.init_a(oven, repo['packages']))
    magic.preferences.update(conf.get('preferences', ()))
    activated = _magic.env_active_set(conf)
    ans = yield async.WaitFor(deliver.deliver_a(oven, activated))
    yield async.Result(ans)
  
  try:
    deliverables = async.run(top_a())
  except Exception, e:
    print>>sys.stderr, e.async_traceback
    raise
  env = magic.evnrealize(deliverables)
  _magic.exportvars(env)
  return 0
