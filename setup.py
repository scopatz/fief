#!/usr/bin/env python
 
from distutils.core import setup

setup(name="fist",
	version='0.1-dev',
	description='The fist package manager',
	author='John Bachan, Anthony Scopatz',
	author_email='john.bachan@gmail.com, scopatz@gmail.com',
	url='https://github.com/scopatz/fist',
	packages=['fist',],
	package_dir={'fist': 'fist'}, 
    scripts=['scripts/fist'],
	)

