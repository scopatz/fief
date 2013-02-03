import os
import _magic

USAGE = ("Removes interfaces from a fief active set.\n\n"
         "usage: fief deactivate [-v] [-c] ifc [ifc ...]")

def main(ns, conf):
    """Adds interfaces to a fief active set."""
    origenv = dict(os.environ)
    activated = _magic.env_active_set()
    activated -= set(ns.ifcs)
    os.environ['FIEF_ACTIVE_SET'] = ','.join(activated)
    if ns.verbose:
        print "currently active interfaces: " + ', '.join(activated)
    _magic.exportvars(origenv)
    exit(0)
