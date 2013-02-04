import os
import sys
import _magic

USAGE = ("Prints the currently active interfaces.\n\n"
         "usage: fief activate")

def main(ns, conf):
    """Prints the currently active interfaces."""
    activated = _magic.env_active_set(conf)
    sys.stderr.write("currently active interfaces: " + ', '.join(activated) + '\n')
    exit(0)
