import os
from fief import repo
from fief.repo import ifc, async, bake

interfaces = {'numpy': ifc(requires='atlas')}

def build_a(ctx):
    pkg = ctx['pkg']
    src, cleanup = yield async.WaitFor(repo.fetch_nomemo_a(ctx, pkg))
    paths = yield async.WaitFor(repo.build_deps_a(ctx, interfaces))
  
    to = yield async.WaitFor(ctx.outfile_a('build'))
    to = os.path.abspath(to)
    os.mkdir(to)
  
    c = bake.Cmd(ctx)
    c.cwd = src
    c.lit('python', 'setup.py', 'install', '--prefix=' + to)
    yield async.WaitFor(c.exec_a())
  
    cleanup()

    delivs = {'root': to, 'pkg': pkg}
    yield async.Result(delivs)  
