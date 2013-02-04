import os
from .. import async
from .. import magic
from .. import top
import _magic

USAGE = ("Realizes a fief active set."
         "usage: fief [realize]")

def main(ns, conf):
    """Realizes a fief active set."""
    repo = {}
    execfile(os.path.join('repo', '__repo__.py'), repo, repo)
    magic.Cmd.showout = ns.verbose
    magic.init(repo['packages'])
    magic.preferences.update(conf.get('preferences', ()))
    activated = _magic.env_active_set(conf)
    async.run(top.main_a(activated))
    env = magic.evnrealize(top.deliverables)
    _magic.exportvars(env)
    exit(top.returncode[0])
