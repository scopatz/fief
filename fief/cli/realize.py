import os
from .. import async
from .. import magic
from .. import top

USAGE = ("Realizes a fief active set."
         "usage: fief [realize]")

def main(ns, conf):
    """Realizes a fief active set."""
    repo = {}
    execfile(os.path.join('repo', '__repo__.py'), repo, repo)
    magic.Cmd.showout = ns.verbose
    magic.init(repo['packages'])
    magic.preferences.update(repo.get('preferencs', ()))
    activated = set(conf.get('interfaces', []))
    activated |= set(ns.activate or ())
    activated -= set(ns.deactivate or ())
    async.run(top.main_a(activated))
    exit(top.returncode[0])
