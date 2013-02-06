from fief import repo

interfaces = {'mpi3': repo.ifc(),
              'mpi2': repo.ifc(),
              'mpi1': repo.ifc(),
              }

realize = repo.c_realize

build_a = repo.configure_make_make_install(interfaces, libs=('mpich', 'fmpich', 
                                           'mpichcxx', 'mpichf90', 'mpl', 'opa'))
