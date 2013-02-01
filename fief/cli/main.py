import os
import sys

if sys.version_info[0] == 3 or sys.version_info[:2] == (2, 7):
    import argparse
else:
    from . import _argparse as argparse

CONFIGS = [os.path.abspath('fiefconf.py'), 
           os.path.abspath('fiefconf'), 
           os.path.join(os.path.expanduser('~'), '.fiefconf.py'),
           os.path.join(os.path.expanduser('~'), '.fiefconf'),
           ]


def main(args=None):
    """Entry point for fief command line interface."""
    # Parse the command line arguments
    parser = _make_argparser()
    ns = parser.parse_args(args)
    if hasattr(ns, 'options'):
        ns.options = ns.options[1:] if ['--'] == ns.options[:1] else ns.options
    if "conf" not in ns:
        for conffile in CONFIGS:
            if os.path.isfile(conffile):
                ns.conf = conffile
                break

    # open run-control file, if present
    conf = {}
    if os.path.isfile(ns.conf):
        execfile(ns.conf, {}, conf)

    # Run the fief command, use dynamic import
    if '.' not in sys.path:
        sys.path.insert(0, '.')
    cmdmod = __import__(ns.cmd, globals(), locals(), fromlist=[None])
    mainfunc = getattr(cmdmod, 'main')
    rtn = mainfunc(ns, conf)

    # Handle some edge cases
    if rtn is NotImplemented:
        print "Command '{0}' has not yet been implemented.".format(cmd)
        raise SystemExit(1)
    elif 0 < rtn:
        print "fief encountered an error."
        raise SystemExit(rtn)


def _make_argparser():
    """Creates agrument parser for fief."""
    commands = set(['realize'])

    cmds = set()
    parser = argparse.ArgumentParser(description='FLASH make utility.', )
    subparsers = parser.add_subparsers(title='subcommands',
                                       description='valid subcommands',
                                       dest="cmd",
                                       help='sub-command help')

    # convenience addition functions
    add_message = lambda p: p.add_argument('-m', metavar="MESSAGE", default=None, 
                                           type=str, help='message to log', 
                                           required=False, dest="message")
    add_dry_run = lambda p: p.add_argument('--dry-run', default=False, 
                                           action='store_true', 
                                           help='simulates running this command', 
                                           required=False, dest="dry_run")
    add_nprocs  = lambda p: p.add_argument('-n', '-np', '--n', '--np', '--nprocs',
                                           default=None, dest='nprocs')
    add_target  = lambda p: p.add_argument('-t', '--target', type=str, dest='target', 
                                           help='target file/dir name', default=None)
    add_source  = lambda p: p.add_argument('src', type=str, help='source file or dir')
    add_destin  = lambda p: p.add_argument('dst', type=str, 
                                           help='destination file or dir')
    add_options = lambda p: p.add_argument('options', type=str, 
                                           nargs=argparse.REMAINDER, 
                                           help='build command to execute')

    add_conf    = lambda p: p.add_argument('--conf', type=str, dest='conf', 
                                           required=False,
                                           help='configuration file path', 
                                           default=CONFIGS[0])

    # add build command
    cmds.add('realize')
    subparser = subparsers.add_parser('realize')
    add_conf(subparser)

    # add default parser for remaining commands
    for key in set(commands) - cmds:
        subparser = subparsers.add_parser(key)
        add_rc(subparser)
        add_options(subparser)
    return parser
