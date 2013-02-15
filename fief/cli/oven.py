import os
import sys
import shutil

import _magic

def _checkrm(p):
    if os.path.isdir(p):
        shutil.rmtree(p)
    elif os.path.isfile(p):
        os.remove(p)

def clean(ns, config):
    if ns.clean == 'all':
        _checkrm('oven')
    elif ns.clean == 'fetch':
        _checkrm(os.path.join('oven', 'i'))
    elif ns.clean == 'build':
        _checkrm(os.path.join('oven', 'o'))
        _checkrm(os.path.join('oven', 'db'))

def main(ns, config):
    """Manipulates the current oven."""
    if ns.clean is not None:
        clean(ns, config)
