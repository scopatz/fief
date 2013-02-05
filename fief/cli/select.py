import os
import sys
import _magic

USAGE = ("Adds interfaces to the current fief selection.\n\n"
         "usage: fief select [-v] [-c] ifc [ifc ...]")

def main(ns, config):
    """Adds interfaces to a fief selection."""
    selection = _magic.env_selection(config)
    selection |= set(ns.ifcs)
    env = {'FIEF_SELECTION': ','.join(selection)}
    if ns.verbose:
        sys.stderr.write("current interface selection: " + ' '.join(selection) + '\n')
    _magic.exportvars(env)
    return 0
