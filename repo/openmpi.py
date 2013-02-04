import os
from fief import repo
from fief.repo import ifc, async, Cmd

interfaces = {'mpi3': ifc(libs=('openmpi')),
              'mpi2': ifc(libs=('openmpi')),
              'mpi1': ifc(libs=('openmpi')),
              }

def build_a(ctx):
  pkg = ctx['pkg']
  src, cleanup = yield async.WaitFor(repo.fetch_nomemo_a(ctx, pkg))

  try:
    to = yield async.WaitFor(ctx.outfile_a('build'))
    to = os.path.abspath(to)
    os.mkdir(to)
  
    c = Cmd(ctx)
    c.cwd = src
    c.tag = 'openmpi'
    c.lit('./configure', '--prefix=' + to)
    yield async.WaitFor(c.exec_a())
  
    c = Cmd(ctx)
    c.cwd = src
    c.tag = 'openmpi'
    c.lit('make', '-j', 'all')
    yield async.WaitFor(c.exec_a())
  
    c = Cmd(ctx)
    c.cwd = src
    c.tag = 'openmpi'
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
