import os
from glob import glob
from fief import ifc, easy, async, Cmd, EnvDelta, configure_make_make_install

#interfaces = {'libxml++': ifc(requires=['libxml2', 'glibmm'])}
interfaces = {'libxml++': ifc()}

def deliverable_envdelta(built):
  root = built['root']
  sets={
    'PATH': [os.path.join(root, 'bin')],
    'LD_LIBRARY_PATH': [os.path.join(root, 'lib')],
    'INCLUDE_PATH': [os.path.join(root, 'include')],
    }
  pypath = glob(os.path.join(root, '*',  'site-packages')) + \
           glob(os.path.join(root, '*', '*',  'site-packages'))
  if 0 < len(pypath):
    sets['PYTHONPATH'] = set(pypath)
  return EnvDelta(sets=sets)

def deliverable_libs(built):
  return set(['xml2'])

build_a = configure_make_make_install(interfaces)
