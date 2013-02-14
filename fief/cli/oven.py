import os
import sys
import shutil

import _magic

def clean(ns, config):
    if ns.clean == 'all':
        shutil.rmtree('oven')
    elif ns.clean == 'fetch':
        shutil.rmtree(os.path.join('oven', 'i'))
    elif ns.clean == 'build':
        shutil.rmtree(os.path.join('oven', 'o'))
        os.remove(os.path.join('oven', 'db'))

def main(ns, config):
    """Manipulates the current oven."""
    if ns.clean is not None:
        clean(ns, config)
