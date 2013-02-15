from fief import repo

interfaces = {'cython': repo.ifc()}

realize = repo.py_realize

build_a = repo.python_setup_install(interfaces)
