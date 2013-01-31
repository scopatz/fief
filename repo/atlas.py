import async
import bake
import os
import magic
from magic import ifc

interfaces = {'atlas': ifc(libs='atlas')}

def build_a(ctx):
  pkg = ctx['pkg']
  src, cleanup = yield async.WaitFor(magic.fetch_nomemo_a(ctx, pkg))
  try:  
    to = yield async.WaitFor(ctx.outfile_a('build'))
    to = os.path.abspath(to)
    os.mkdir(to)
  
    c = bake.Cmd(ctx)
    c.cwd = src
    c.lit('./configure', '--shared', '--prefix=' + to)
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
  
  libs = set()
  for key, ifc in interfaces.items():
    if ctx['interface', key]:
      libs |= ifc.libs
  yield async.Result((to, libs))
