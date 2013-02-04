import os
from fief import repo
from fief import conf
from fief.repo import ifc, async, Cmd

interfaces = {'mpi3': ifc(libs=('mpich3')),
              'mpi2': ifc(libs=('mpich3')),
              'mpi1': ifc(libs=('mpich3')),
              }

realize = repo.c_realize

def build_a(ctx):
  pkg = ctx['pkg']
  src, cleanup = yield async.WaitFor(repo.fetch_nomemo_a(ctx, pkg))

  try:
    to = yield async.WaitFor(ctx.outfile_a('build', pkg))
    to = os.path.abspath(to)
    os.mkdir(to)
  
    c = Cmd(ctx)
    c.cwd = src
    c.tag = pkg
    c.lit('./configure', '--prefix=' + to)
    yield async.WaitFor(c.exec_a())
  
    c = Cmd(ctx)
    c.cwd = src
    c.tag = pkg
    c.lit(conf.make)
    yield async.WaitFor(c.exec_a())
  
    c = Cmd(ctx)
    c.cwd = src
    c.tag = pkg
    c.lit(conf.make_install)
    yield async.WaitFor(c.exec_a())
  finally:
    cleanup()

  libs = set()
  for key, ifc in interfaces.items():
    if ctx['interface', key] is not None:
      libs |= ifc.libs
  delivs = {'root': to, 'libs': libs, 'pkg': pkg}
  yield async.Result(delivs)
