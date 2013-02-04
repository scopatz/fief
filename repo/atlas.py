import os
from fief import repo
from fief.repo import ifc, async, bake

interfaces = {'atlas': ifc(libs='atlas')}

def build_a(ctx):
  pkg = ctx['pkg']
  src, cleanup = yield async.WaitFor(repo.fetch_nomemo_a(ctx, pkg))
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
    if ctx['interface', key] is not None:
      libs |= ifc.libs
  delivs = {'root': to, 'libs': libs, 'pkg': pkg}
  yield async.Result(delivs)
