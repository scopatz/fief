import os
import sys

HOME = os.path.expanduser('~')


def exportvars(currenv=None, origenv=None, 
               fname=os.path.join(HOME, '.config', 'fiefexport')):
    """Takes an original envionment and prints out the environmental variable
    that have changed.  This file is exportable to the environment."""
    origenv = origenv or {}
    if currenv is None:
        currenv = dict(os.environ)
    changed = ['{0}={1}'.format(k, v) for k, v in currenv.iteritems() \
               if (k not in origenv) or (v != origenv[k])]
    s = " ".join(changed)
    sys.stdout.write(s)

def env_active_set(conf=None):
    """Gets the active set of interfaces from the environment."""
    actenv = os.getenv('FIEF_ACTIVE_SET', '')    
    actenv = set([ae.strip() for ae in actenv.split(',')])
    actenv.discard('')
    if 0 == len(actenv):
        conf = conf or {}
        actenv = set(conf.get('interfaces', ()))
    return actenv
