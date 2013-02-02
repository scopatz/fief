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
    async.run(top.main_a(conf.get('interfaces', [])))
    exit(top.returncode[0])
