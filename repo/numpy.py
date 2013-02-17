import os
from fief import repo
from fief.repo import ifc, async, bake

interfaces = {'numpy': ifc(requires=('atlas', 'py')}

def build_a(ctx):
    pkg = ctx['pkg']
    env = yield async.WaitFor(repo.realize_deps_a(ctx, interfaces))
    src, cleanup = yield async.WaitFor(repo.stage_nomemo_a(ctx, pkg))
  
    to = yield async.WaitFor(ctx.outfile_a('build'))
    to = os.path.abspath(to)
    os.mkdir(to)
  
    c = bake.Cmd(ctx)
    c.cwd = src
    c.env = env
    c.lit('python', 'setup.py', 'install', '--prefix=' + to)
    yield async.WaitFor(c.exec_a())
  
    cleanup()

    delivs = {'root': to, 'pkg': pkg}
    yield async.Result(delivs)  
