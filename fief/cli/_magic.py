import os
import sys

HOME = os.path.expanduser('~')


def exportvars(currenv=None, origenv=None):
    """Takes an original envionment and prints out the environmental variable
    that have changed.  This file is exportable to the environment."""
    origenv = origenv or {}
    if currenv is None:
        currenv = dict(os.environ)
    changed = ['{0}={1}'.format(k, v) for k, v in currenv.iteritems() \
               if (k not in origenv) or (v != origenv[k])]
    s = " ".join(changed)
    sys.stdout.write(s)

def env_selection(conf=None):
    """Gets the current interface selections from the environment."""
    selenv = os.getenv('FIEF_SELECTION', '')    
    selenv = set([s.strip() for s in selenv.split(',')])
    selenv.discard('')
    if 0 == len(selenv):
        conf = conf or {}
        selenv = set(conf.get('interfaces', ()))
    return selenv
