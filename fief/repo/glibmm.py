from fief import ifc, configure_make_make_install, c_envdelta, find_libs

interfaces = {'glibmm': ifc()}

deliverable_envdelta = c_envdelta

deliverable_libs = find_libs

build_a = configure_make_make_install(interfaces)
