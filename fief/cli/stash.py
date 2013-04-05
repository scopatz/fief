import os
import sys
import shutil

from .. import fief
from .. import async

import _magic

def _checkrm(p, verbose=False):
    if os.path.isdir(p):
        shutil.rmtree(p)
    elif os.path.isfile(p):
        os.remove(p)
    if verbose:
        sys.stderr.write('removed: {0}\n'.format(os.path.abspath(p)))

def clean(ns, finst):
    if ns.clean == 'all':
        _checkrm(finst._path_stash, ns.verbose)
    elif ns.clean == 'fetch':
        _checkrm(finst.procurer._stash, ns.verbose)
    elif ns.clean == 'build':
        _checkrm(finst.oven._path, ns.verbose)

def main(ns, rcpath):
    """Manipulates the current stash."""
    finst = async.run(fief.Fief.new_a(rcpath))
    if ns.verbose:
        sys.stderr.write('stash: {0}\n'.format(os.path.abspath(finst._path_stash)))
    if ns.clean is not None:
        clean(ns, finst)
