from fief import ifc

interfaces = {'mpi3': ifc(requires='cc'),
              'mpi2': ifc(requires='cc'),
              'mpi1': ifc(requires='cc'),
              }

#realize = repo.c_realize

#build_a = repo.configure_make_make_install(interfaces, libs=('mpich', 'fmpich', 
#                                           'mpichcxx', 'mpichf90', 'mpl', 'opa'))
