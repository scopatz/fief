import os
import _magic

USAGE = ("Adds interfaces to a fief active set.\n\n"
         "usage: fief activate [-v] [-c] ifc [ifc ...]")

def main(ns, conf):
    """Adds interfaces to a fief active set."""
    origenv = dict(os.environ)
    activated = os.getenv('FIEF_ACTIVE_SET', None)
    activated = set() if activated is None else set(activated.split(','))
    activated |= set(ns.ifcs)
    os.environ['FIEF_ACTIVE_SET'] = ','.join(activated)
    if ns.verbose:
        print "currently active interfaces: " + ', '.join(activated)
    _magic.exportvars(origenv)
    exit(0)
