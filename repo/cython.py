import os
from fief import async
from fief import bake
from fief import magic

ifc = magic.ifc

interfaces = {'cython': ifc()}

def build_a(ctx):
    pkg = ctx['pkg']
    src, cleanup = yield async.WaitFor(magic.fetch_nomemo_a(ctx, pkg))
  
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
