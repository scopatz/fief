import sys

def _init(conf):
    currmod = sys.modules[__name__]
    for k, v in conf.iteritems():
        setattr(currmod, k, v)
