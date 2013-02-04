import os
import sys
import _magic

USAGE = ("Prints the currently active interfaces.\n\n"
         "usage: fief activate")

def main(ns, config):
    """Prints the currently active interfaces."""
    activated = _magic.env_active_set(config)
    sys.stderr.write("currently active interfaces: " + ', '.join(activated) + '\n')
    exit(0)
