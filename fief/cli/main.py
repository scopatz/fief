#! /usr/bin/env python

import os
import sys

if sys.version_info[0] == 3 or sys.version_info[:2] == (2, 7):
    import argparse
else:
    from . import _argparse as argparse

HOME = os.path.expanduser('~')

CONFIGS = [os.path.join(HOME, '.config', 'fiefconf'),
           os.path.join(HOME, '.config', 'fiefconf.py'),
           os.path.abspath('fiefconf'), 
           os.path.abspath('fiefconf.py'), 
           ]


def main(args=None):
    """Entry point for fief command line interface."""
    # Parse the command line arguments
    parser = _make_argparser()
    ns = parser.parse_args(args)
    if hasattr(ns, 'options'):
        ns.options = ns.options[1:] if ['--'] == ns.options[:1] else ns.options

    config = {}
    CONFIGS.append(ns.conf)
    for conffile in CONFIGS:
        if os.path.isfile(conffile):
            execfile(conffile, config, config)

    # Run the fief command, use dynamic import
    if '.' not in sys.path:
        sys.path.insert(0, '.')
    cmdmod = __import__(ns.cmd, globals(), locals(), fromlist=[None])
    mainfunc = getattr(cmdmod, 'main')
    rtn = mainfunc(ns, config)

    # Handle some edge cases
    if rtn is NotImplemented:
        print "Command '{0}' has not yet been implemented.".format(cmd)
        raise SystemExit(1)
    elif 0 < rtn:
        print "fief encountered an error."
        raise SystemExit(rtn)


def _make_argparser():
    """Creates agrument parser for fief."""
    cmds = set()
    parser = argparse.ArgumentParser(description='FLASH make utility.', )
    subparsers = parser.add_subparsers(title='subcommands',
                                       description='valid subcommands',
                                       dest="cmd",
                                       help='sub-command help')

    # convenience addition functions
    add_ifcs = lambda p: p.add_argument('ifcs', type=str, nargs='+', metavar='ifc', 
                                        help='activate additional interfaces')
    add_conf = lambda p: p.add_argument('--conf', type=str, dest='conf', 
                                        required=False,
                                        help='configuration file path', 
                                        default='<conf-file>')
    add_verbose = lambda p: p.add_argument('-v', '--verbose', 
                                           dest='verbose', action='store_true',
                                           help='show more information', default=False)
    add_lazy = lambda p: p.add_argument('-l', '--lazy', 
                                        dest='lazy', action='store_true',
                                        help='modify env only if no building needed', 
                                        default=False)

    # realize command
    cmds.add('realize')
    subparser = subparsers.add_parser('realize', 
                    help="creates an active set of interfaces.")
    add_conf(subparser)
    add_lazy(subparser)
    add_verbose(subparser)

    # active
    cmds.add('active')
    subparser = subparsers.add_parser('active', 
                    help="displays the active interfaces.")
    add_conf(subparser)

    # activate
    cmds.add('activate')
    subparser = subparsers.add_parser('activate', 
                    help="add interfaces to the current environment.")
    add_conf(subparser)
    add_verbose(subparser)
    add_ifcs(subparser)

    # deactivate
    cmds.add('deactivate')
    subparser = subparsers.add_parser('deactivate',
                    help="removes interfaces from the current environment.")
    add_conf(subparser)
    add_verbose(subparser)
    add_ifcs(subparser)

    return parser


if __name__ == '__main__':
    main()
