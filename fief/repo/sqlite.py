import os
from glob import glob
from fief import ifc, easy, async, Cmd, EnvDelta, configure_make_make_install, \
    c_envdelta, find_libs

interfaces = {'sqlite': ifc(requires='cc')}

deliverable_envdelta = c_envdelta

deliverable_libs = find_libs

build_a = configure_make_make_install(interfaces)
