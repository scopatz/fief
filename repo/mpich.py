from fief import repo

interfaces = {'mpi3': repo.ifc(requires='cc'),
              'mpi2': repo.ifc(requires='cc'),
              'mpi1': repo.ifc(requires='cc'),
              }

realize = repo.c_realize

build_a = repo.configure_make_make_install(interfaces, libs=('mpich', 'fmpich', 
                                           'mpichcxx', 'mpichf90', 'mpl', 'opa'))
