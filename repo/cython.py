from fief import repo

interfaces = {'cython': repo.ifc(requires=('cc', 'py'))}

realize = repo.py_realize

build_a = repo.python_setup_install(interfaces)
