from fief import repo

interfaces = {'atlas': repo.ifc(libs='atlas')}

realize = repo.c_realize

build_a = repo.configure_make_make_install(interfaces, configure_opts='--shared')

