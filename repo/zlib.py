import os
from fief import magic
from fief.magic import ifc, async, bake

interfaces = {'zlib': ifc(libs='z')}

def build_a(ctx):
  pkg = ctx['pkg']
  src, cleanup = yield async.WaitFor(magic.fetch_nomemo_a(ctx, pkg))
  try:  
    to = yield async.WaitFor(ctx.outfile_a('build'))
    to = os.path.abspath(to)
    os.mkdir(to)
  
    c = bake.Cmd(ctx)
    c.cwd = src
    c.lit('./configure', '--prefix=' + to)
    yield async.WaitFor(c.exec_a())
  
    c = bake.Cmd(ctx)
    c.cwd = src
    c.lit('make')
    yield async.WaitFor(c.exec_a())
  
    c = bake.Cmd(ctx)
    c.cwd = src
    c.lit('make', 'install')
    yield async.WaitFor(c.exec_a())
  finally:
    cleanup()
  
  yield async.Result((to, ('z',)))
