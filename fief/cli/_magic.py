import os
import sys

HOME = os.path.expanduser('~')


def exportvars(origenv=None, fname=os.path.join(HOME, '.config', 'fiefexport')):
    """Takes an original envionment and writes out the environmental variables
    that have changed.  This file is exportable to the environment."""
    origenv = origenv or {}
    currenv = dict(os.environ)
    changed = ['{0}={1}'.format(k, v) for k, v in currenv.iteritems() \
               if (k not in origenv) or (v != origenv[k])]
    s = " ".join(changed)
    d = os.path.split(fname)[0]
    if not os.path.isdir(d):
        os.path.makedirs(d)
    with open(fname, 'w') as f:
        f.write(s)

def env_active_set():
    """Gets the active set of interfaces from the environment."""
    actenv = os.getenv('FIEF_ACTIVE_SET', '')
    actenv = set([ae.strip() for ae in actenv.split(',')])
    actenv.discard('')
    return actenv
