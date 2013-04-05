import os
import re
import sys

HOME = os.path.expanduser('~')
WIN32 = (os.name == 'nt')
WHITESPACE = re.compile("\s")

def _ensure_config():
    confdir = os.path.join(HOME, '.config')
    if not os.path.exists(confdir):
        os.makedirs(confdir)

def exportvars(currenv=None, origenv=None):
    """Takes an original envionment and prints out the environmental variable
    that have changed.  This file is exportable to the environment."""
    origenv = origenv or {}
    if currenv is None:
        currenv = dict(os.environ)
    changed = []
    for k, v in currenv.iteritems():
        if (k not in origenv) or (v != origenv[k]):
            m = WHITESPACE.search(v)
            var = '{0}={1}'.format(k, v) if m is None or WIN32 else '{0}="{1}"'.format(k, v)
            changed.append(var)

    # write exports
    if WIN32:
        s = "set " + "\nset ".join(changed) if 0 < len(changed) else ""
        _ensure_config()
        with open(os.path.join(HOME, '.config', 'fiefexport.bat'), 'w') as f:
            f.write(s)
    else:
        s = " ".join(changed)
        sys.stdout.write(s)

def env_selection(finst=None):
    """Gets the current interface selections from the environment."""
    selenv = os.getenv('FIEF_SELECTION', '')    
    selenv = set(selenv.replace("'", '').replace('"', '').split())
    selenv.discard('')
    if 0 == len(selenv):
        if finst is None:
            selenv = set()
        else:
            selenv = finst.default_interfaces()
    return selenv


_bashcomptemplate = """# fief bash completion

_fiefcomp()
{{
    local cur prev cmds curcmd 
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    cmds="{cmds}"
    curcmd="${{COMP_WORDS[1]}}"

    # complete the command
    if [[ $COMP_CWORD == 1 ]] ; then
        # match the command anme
        COMPREPLY=( $(compgen -W "${{cmds}} -m" -- ${{cur}}) )
    elif [[ $prev == "--conf" ]] ; then
        # match configuration files 
        COMPREPLY=( $(compgen -f ${{cur}}) )
{cmdswitch}
    fi

    return 0
}}
complete -o filenames -F _fiefcomp fief
"""

_bashcaseargs = """    elif [[ $curcmd == "{name}" ]] ; then
        # match {name} arguments
        COMPREPLY=( $(compgen -W "{args}" -- ${{cur}}) )"""

def bashcompgen(parser):
    """Generates a BASH completion script for fief by partially crawling the 
    ArgumentParser object."""
    kw = {}
    cmds = []
    for a in parser._actions:
        if a.dest == 'help':
            cmds += a.option_strings
        elif a.dest == 'cmd':
            subparsers = a.choices
            cmds += subparsers.keys()
    kw['cmds'] = " ".join(sorted(cmds))
    cmdswitch = []
    for name, subparser in subparsers.items():
        args = []
        for a in subparser._actions:
            args += a.option_strings
            if a.dest == 'ifcs':
                args.append("${FIEF_KNOWN_INTERFACES}")
        cmdswitch.append(_bashcaseargs.format(name=name, args=" ".join(args)))
    kw['cmdswitch'] = "\n".join(cmdswitch)
    bashcomp = _bashcomptemplate.format(**kw)
    return bashcomp
