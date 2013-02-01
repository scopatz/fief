#!/usr/bin/env python
 
from distutils.core import setup

setup(name="fief",
	version='0.1-dev',
	description='The fief package manager',
	author='John Bachan, Anthony Scopatz',
	author_email='john.bachan@gmail.com, scopatz@gmail.com',
	url='https://github.com/scopatz/fief',
	packages=['fief',],
	package_dir={'fief': 'fief'}, 
    scripts=[os.path.join('bin', 'fief'), os.path.join('bin', 'fief.bat')],
	)

