#! /usr/bin/env python
import os
import sys

if sys.version_info[0] == 3 or sys.version_info[:2] == (2, 7):
    import argparse
else:
    from . import _argparse as argparse

def default_rcpath():
  path = os.getcwd()
  root = os.path.splitdrive(path)[0] + os.path.sep
  rellocs = ['fiefrc.py', 'fiefrc', 
             os.path.join('.config', 'fiefrc.py'),
             os.path.join('.config', 'fiefrc'),]
  while True:
    for relloc in rellocs:
      p = os.path.join(path, relloc)
      if os.path.isfile(p):
        return p
    if path == root:
      break
    path = os.path.split(path)[0]
  
  return None

def main(args=None):
    """Entry point for fief command line interface."""
    # Parse the command line arguments
    parser = _make_argparser()
    ns = parser.parse_args(args)
    if hasattr(ns, 'options'):
        ns.options = ns.options[1:] if ['--'] == ns.options[:1] else ns.options
    
    # Run the fief command, use dynamic import
    if '.' not in sys.path:
        sys.path.insert(0, '.')
    cmdmod = __import__(ns.cmd, globals(), locals(), fromlist=[None])
    mainfunc = getattr(cmdmod, 'main')
    rtn = mainfunc(ns, ns.rc)

    # Handle some edge cases
    if rtn is NotImplemented:
        print "Command '{0}' has not yet been implemented.".format(cmd)
        raise SystemExit(1)
    elif 0 < rtn:
        print "fief encountered an error."
        raise SystemExit(rtn)


def _make_argparser():
    """Creates agrument parser for fief."""
    parser = argparse.ArgumentParser(description='fief package manager', )
    subparsers = parser.add_subparsers(title='subcommands',
                                       description='valid subcommands',
                                       dest="cmd",
                                       help='sub-command help')

    # convenience addition functions
    add_ifcs = lambda p: p.add_argument('ifcs', type=str, nargs='+', metavar='ifc', 
                                        help='activate additional interfaces')
    add_rc = lambda p: p.add_argument('--rc', type=str, dest='rc', 
                                        required=False,
                                        help='configuration file path', 
                                        default=default_rcpath())
    add_verbose = lambda p: p.add_argument('-v', '--verbose', 
                                           dest='verbose', action='store_true',
                                           help='show more information', default=False)
    add_lazy = lambda p: p.add_argument('-l', '--lazy', 
                                        dest='lazy', action='store_true',
                                        help='modify env only if no building needed', 
                                        default=False)
    add_clean = lambda p: p.add_argument('-c', '--clean', dest='clean', 
                                        choices=['all', 'build', 'fetch'],
                                        help='removes optional components',
                                        default=None)

    # realize command
    subparser = subparsers.add_parser('realize', 
                    help="creates a selection of interfaces.")
    add_rc(subparser)
    add_lazy(subparser)
    add_verbose(subparser)

    # selection
    subparser = subparsers.add_parser('selection', 
                    help="displays the current interface selections.")
    add_rc(subparser)

    # select
    subparser = subparsers.add_parser('select', 
                    help="add interfaces to the current environment.")
    add_rc(subparser)
    add_verbose(subparser)
    add_ifcs(subparser)

    # deselect
    subparser = subparsers.add_parser('deselect',
                    help="removes interfaces from the current environment.")
    add_rc(subparser)
    add_verbose(subparser)
    add_ifcs(subparser)

    # oven
    subparser = subparsers.add_parser('stash', help="manipulates the current stash.")
    add_rc(subparser)
    add_verbose(subparser)
    add_clean(subparser)

    return parser


if __name__ == '__main__':
    main()
