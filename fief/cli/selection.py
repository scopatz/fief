import os
import sys
import _magic

USAGE = ("Prints the current interface selection.\n\n"
         "usage: fief selection")

def main(ns, rcpath):
    """Prints the current interface selection."""
    selection = _magic.env_selection()
    sys.stderr.write("current interface selection: " + ' '.join(selection) + '\n')
    exit(0)
