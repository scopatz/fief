import os
import sys
import shutil

from .. import fief
from .. import async

import _magic

def _checkrm(p):
    if os.path.isdir(p):
        shutil.rmtree(p)
    elif os.path.isfile(p):
        os.remove(p)

def clean(ns, finst):
    if ns.clean == 'all':
        _checkrm(finst._path_stash)
    elif ns.clean == 'fetch':
        _checkrm(finst.procurer._stash)
    elif ns.clean == 'build':
        _checkrm(finst.oven._path)

def main(ns, rcpath):
    """Manipulates the current stash."""
    finst = async.run(fief.Fief.new_a(rcpath))
    if ns.clean is not None:
        clean(ns, finst)
