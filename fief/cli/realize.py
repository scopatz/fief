import os
import sys
from .. import async
from .. import bake
from .. import repo
from .. import deliver
from .. import fetch
import _magic

USAGE = ("Realizes the current fief selection."
         "usage: fief [realize]")

def main(ns, config):
  """Realizes the current fief selection."""
  repos = {}
  execfile(os.path.join('repo', '__repo__.py'), repos, repos)
  
  def top_a():
    oven = bake.Oven(bake.MemoHost(bake.FileHost_a), "oven")
    repo.Cmd.showout = ns.verbose
    pkgs = repos['packages']
    yield async.WaitFor(repo.init_a(oven, pkgs))
    fetch._init(pkgs)
    activated = _magic.env_selection(config)
    ans = yield async.WaitFor(deliver.deliver_a(oven, activated, ns.lazy))
    yield async.Result(ans)

  try:
    deliverables = async.run(top_a())
  except Exception, e:
    sys.stderr.write(str(e.async_traceback) + '\n')
    raise
  env = repo.envrealize(deliverables)
  env['FIEF_KNOWN_INTERFACES'] = " ".join(set([ifc for ifc, pkg in repo.ifcpkg]))
  _magic.exportvars(env)
  return 0
