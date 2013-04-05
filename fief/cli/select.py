import os
import sys
import _magic

USAGE = ("Adds interfaces to the current fief selection.\n\n"
         "usage: fief select [-v] [-c] ifc [ifc ...]")

def main(ns, rc):
    """Adds interfaces to a fief selection."""
    selection = _magic.env_selection()
    selection |= set(ns.ifcs)
    env = {'FIEF_SELECTION': ' '.join(sorted(selection))}
    if ns.verbose:
        sys.stderr.write("current interface selection: " + ' '.join(selection) + '\n')
    _magic.exportvars(env)
    return 0
