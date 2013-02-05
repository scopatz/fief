from fief import repo

_libs = ('mpich', 'fmpich', 'mpichcxx', 'mpichf90', 'mpl', 'opa')
interfaces = {'mpi3': repo.ifc(libs=_libs),
              'mpi2': repo.ifc(libs=_libs),
              'mpi1': repo.ifc(libs=_libs),
              }

realize = repo.c_realize

build_a = repo.configure_make_make_install(interfaces)
