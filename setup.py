#!/usr/bin/env python
import os 
import sys
from distutils.core import setup

def make_bash_completion():
    sys.path.insert(0, '.')
    from fief.cli import main
    from fief.cli import _magic
    sys.path.pop(0)
    parser = main._make_argparser()
    fiefbc = _magic.bashcompgen(parser)
    configdir = os.path.join(main.HOME, '.config')
    if not os.path.exists(configdir):
        os.makedirs(configdir)
    with open(os.path.join(configdir, 'fiefbc'), 'w') as f:
        f.write(fiefbc)

def main_setup():
    setup(name="fief",
	    version='0.1-dev',
	    description='The fief package manager',
	    author='John Bachan, Anthony Scopatz',
	    author_email='john.bachan@gmail.com, scopatz@gmail.com',
	    url='https://github.com/scopatz/fief',
	    packages=['fief', 'fief.cli', 'fief.repo'],
	    package_dir={'fief': 'fief', 'fief.cli': os.path.join('fief', 'cli'), 
                     'fief.repo': os.path.join('fief', 'repo')}, 
        scripts=[os.path.join('bin', 'fief'), os.path.join('bin', 'fief.bat')],
	    )

def main():
    make_bash_completion()
    main_setup()

if __name__ == '__main__':
    main()
