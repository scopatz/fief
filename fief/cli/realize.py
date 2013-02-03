import os
from .. import async
from .. import magic
from .. import top
import _magic

USAGE = ("Realizes a fief active set."
         "usage: fief [realize]")

def main(ns, conf):
    """Realizes a fief active set."""
    origenv = dict(os.environ)
    repo = {}
    execfile(os.path.join('repo', '__repo__.py'), repo, repo)
    magic.Cmd.showout = ns.verbose
    magic.init(repo['packages'])
    magic.preferences.update(conf.get('preferences', ()))
    activated = set(conf.get('interfaces', []))
    activated |= set(_magic.env_active_set())
    async.run(top.main_a(activated))
    _magic.exportvars(origenv)
    exit(top.returncode[0])
