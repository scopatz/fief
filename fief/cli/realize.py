import os
import sys
from .. import async
from .. import bake
from .. import repo
from .. import deliver
from .. import conf
import _magic

USAGE = ("Realizes a fief active set."
         "usage: fief [realize]")

def main(ns, config):
  """Realizes a fief active set."""
  repos = {}
  execfile(os.path.join('repo', '__repo__.py'), repos, repos)
  
  def top_a():
    oven = bake.Oven(bake.MemoHost(bake.FileHost_a), "oven")
    repo.Cmd.showout = ns.verbose
    yield async.WaitFor(repo.init_a(oven, repos['packages']))
    conf._init(config)
    activated = _magic.env_active_set(config)
    ans = yield async.WaitFor(deliver.deliver_a(oven, activated, ns.lazy))
    yield async.Result(ans)
  
  try:
    deliverables = async.run(top_a())
  except Exception, e:
    print>>sys.stderr, e.async_traceback
    raise
  env = repo.envrealize(deliverables)
  _magic.exportvars(env)
  return 0
