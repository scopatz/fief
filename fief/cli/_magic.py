import os
import sys

HOME = os.path.expanduser('~')


def exportvars(currenv=None, origenv=None):
    """Takes an original envionment and prints out the environmental variable
    that have changed.  This file is exportable to the environment."""
    origenv = origenv or {}
    if currenv is None:
        currenv = dict(os.environ)
    changed = ['{0}={1}'.format(k, v) for k, v in currenv.iteritems() \
               if (k not in origenv) or (v != origenv[k])]
    s = " ".join(changed)
    sys.stdout.write(s)

def env_selection(conf=None):
    """Gets the current interface selections from the environment."""
    selenv = os.getenv('FIEF_SELECTION', '')    
    selenv = set([s for s in selenv.split()])
    selenv.discard('')
    if 0 == len(selenv):
        conf = conf or {}
        selenv = set(conf.get('interfaces', ()))
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
                args.append("${FIEF_SELECTION}")
        cmdswitch.append(_bashcaseargs.format(name=name, args=" ".join(args)))
    kw['cmdswitch'] = "\n".join(cmdswitch)
    bashcomp = _bashcomptemplate.format(**kw)
    return bashcomp
