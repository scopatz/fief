from fief import repo

interfaces = {'mpi3': repo.ifc(libs=('openmpi')),
              'mpi2': repo.ifc(libs=('openmpi')),
              'mpi1': repo.ifc(libs=('openmpi')),
              }

realize = repo.c_realize

build_a = repo.configure_make_make_install(interfaces, make_opts='all')
