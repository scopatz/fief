import os
import sys
import _magic

USAGE = ("Removes interfaces from a fief active set.\n\n"
         "usage: fief deactivate [-v] [-c] ifc [ifc ...]")

def main(ns, conf):
    """Adds interfaces to a fief active set."""
    activated = _magic.env_active_set(conf)
    activated -= set(ns.ifcs)
    env = {'FIEF_ACTIVE_SET': ','.join(activated)}
    if ns.verbose:
        sys.stderr.write("currently active interfaces: " + ', '.join(activated) + '\n')
    _magic.exportvars(env)
    exit(0)
