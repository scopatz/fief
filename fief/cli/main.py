import os
import sys

if sys.version_info[0] == 3 or sys.version_info[:2] == (2, 7):
    import argparse
else:
    from . import _argparse as argparse

RCFILES = [os.path.abspath('fiefrc.py'), 
           os.path.abspath('fiefrc'), 
           os.path.join(os.path.expanduser('~'), '.fiefrc.py'),
           os.path.join(os.path.expanduser('~'), '.fiefrc'),
           ]


def main(args=None):
    """Entry point for fief command line interface."""
    # Parse the command line arguments
    parser = _make_argparser()
    ns = parser.parse_args(args)
    if hasattr(ns, 'options'):
        ns.options = ns.options[1:] if ['--'] == ns.options[:1] else ns.options
    if "rc" not in ns:
        for rcfile in RCFILES:
            if os.path.isfile(rcfile):
                ns.rc = rcfile
                break

    # open run-control file, if present
    rc = {}
    if os.path.isfile(ns.rc):
        execfile(ns.rc, {}, rc)

    # Run the fief command, use dynamic import
    if '.' not in sys.path:
        sys.path.insert(0, '.')
    cmdmod, mainfunc = commands[ns.cmd]
    cmdmod = __import__(ns.cmd, globals(), locals(), fromlist=[None])
    mainfunc = getattr(cmdmod, 'main')
    rtn = mainfunc(ns, rc)

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
                                       default="realize",
                                       help='sub-command help')

    # convenience addition functions
    add_message = lambda p: p.add_argument('-m', metavar="MESSAGE", default=None, 
                                           type=str, help='message to log', 
                                           required=False, dest="message")
    add_dry_run = lambda p: p.add_argument('--dry-run', default=False, action='store_true', 
                                           help='simulates running this command', 
                                           required=False, dest="dry_run")
    add_nprocs  = lambda p: p.add_argument('-n', '-np', '--n', '--np', '--nprocs',
                                           default=None, dest='nprocs')
    add_target  = lambda p: p.add_argument('-t', '--target', type=str, dest='target', 
                                           help='target file/dir name', default=None)
    add_source  = lambda p: p.add_argument('src', type=str, help='source file or dir')
    add_destin  = lambda p: p.add_argument('dst', type=str, help='destination file or dir')
    add_options = lambda p: p.add_argument('options', type=str, 
                                           nargs=argparse.REMAINDER, 
                                           help='build command to execute')

    add_rc      = lambda p: p.add_argument('--rc', type=str, dest='rc', required=False,
                                           help='run control file path', 
                                           default=os.getenv("FLASHRC","flashrc.py"))

    # add build command
    cmds.add('build')
    subparser = subparsers.add_parser('build')
    add_rc(subparser)
    subparser.add_argument('-j', help="Number of concurrent make operations", type=str, default="1")

    # add run command
    cmds.add('run')
    subparser = subparsers.add_parser('run')
    add_nprocs(subparser)
    add_target(subparser)
    add_message(subparser)
    add_dry_run(subparser)
    add_rc(subparser)
    add_options(subparser)

    # add restart command
    cmds.add('restart')
    subparser = subparsers.add_parser('restart')
    subparser.add_argument('prev_run', type=str, help='previous run dir or id')
    add_nprocs(subparser)
    add_target(subparser)
    add_message(subparser)
    add_dry_run(subparser)
    add_rc(subparser)
    add_options(subparser)    

    # add merge command
    cmds.add('merge')
    subparser = subparsers.add_parser('merge')
    subparser.add_argument('leaf', type=str, help='leaf dir or id to merge')
    add_target(subparser)
    add_message(subparser)

    # add clean command
    cmds.add('clean')
    subparser = subparsers.add_parser('clean')
    subparser.add_argument('level', default=1, type=int, 
                           help='level of cleanliness')

    # add metadata command
    cmds.add('metadata')
    subparser = subparsers.add_parser('metadata')
    subparser.add_argument('-e', '--edit', default=False, action='store_true', 
                           dest='edit', help='level of cleanliness')

    # add metadata command
    cmds.add('diffpar')
    subparser = subparsers.add_parser('diffpar')
    subparser.add_argument('par1', help='first runtime parameters file')
    subparser.add_argument('par2', help='second runtime parameters file')

    # add mv command
    cmds.add('mv')
    subparser = subparsers.add_parser('mv')
    add_source(subparser)
    add_destin(subparser)
    add_message(subparser)

    # add rm command
    cmds.add('rm')
    subparser = subparsers.add_parser('rm')
    add_source(subparser)
    add_message(subparser)

    # add log command
    cmds.add('log')
    subparser = subparsers.add_parser('log')
    subparser.add_argument('-n', dest='n', type=int, default=None, 
                           help='number of log entries to display')

    # add email command
    cmds.add('email')
    subparser = subparsers.add_parser('email')
    subparser.add_argument('--start', dest='start', default=False, action='store_true',
                           help='default message for run beginning')
    subparser.add_argument('--stop', dest='stop', default=False, action='store_true',
                           help='default message for run finish')
    subparser.add_argument('-b', type=str, dest='body', 
                           help='message body', default=None)
    subparser.add_argument('-s', type=str, dest='subject', 
                           help='message subject', default=None)
    subparser.add_argument('-t', type=str, dest='addr', 
                           help='address to send to', default=None)
    add_rc(subparser)

    # add qsub command
    cmds.add('qsub')
    subparser = subparsers.add_parser('qsub')#, prefix_chars="\0")
    subparser.add_argument("run_cmd", choices=['run', 'restart'], 
                           help="run command to submit to queue")
    add_message(subparser)
    add_rc(subparser)
    add_options(subparser)    

    # add reproduce command
    cmds.add('reproduce')
    subparser = subparsers.add_parser('reproduce')
    subparser.add_argument("desc", help="descrition file to reproduce")
    add_rc(subparser)

    # add pargen command
    cmds.add('pargen')
    subparser = subparsers.add_parser('pargen')
    add_rc(subparser)

    # add sweep command
    cmds.add('sweep')
    subparser = subparsers.add_parser('sweep')
    add_nprocs(subparser)
    add_target(subparser)
    add_message(subparser)
    add_dry_run(subparser)
    add_rc(subparser)
    add_options(subparser)

    # add default parser for remaining commands
    for key in set(commands.keys()) - cmds:
        subparser = subparsers.add_parser(key)
        add_rc(subparser)
        add_options(subparser)
    return parser
