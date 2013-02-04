import sys

make = 'make'
make_install = ['make', 'install']

def _init(config):
    currmod = sys.modules[__name__]
    for k, v in config.iteritems():
        setattr(currmod, k, v)
