from fief import repo

interfaces = {'atlas': repo.ifc()}

realize = repo.c_realize

build_a = repo.configure_make_make_install(interfaces, libs='atlas', 
                                           configure_args='--shared')

