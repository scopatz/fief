import os
import sys
from fief import repo
from fief import conf
from fief.repo import ifc, async, Cmd

interfaces = {'hdf5': ifc(requires='zlib', libs=('hdf5', 'hdf5_hl')), 
              'hdf5-cpp': ifc(subsumes='hdf5', libs=('hdf5_cpp', 'hdf5_hl_cpp')), 
              'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi2'),
              }

realize = repo.c_realize

def build_a(ctx):
  pkg = ctx['pkg']
  src, cleanup = yield async.WaitFor(repo.fetch_nomemo_a(ctx, pkg))

  try:
    parl = ctx['interface','hdf5-parallel']
    env = yield async.WaitFor(repo.build_deps_a(ctx, interfaces))
  
    to = yield async.WaitFor(ctx.outfile_a('build', pkg))
    to = os.path.abspath(to)
    os.mkdir(to)
  
    c = Cmd(ctx)
    c.cwd = src
    c.tag = pkg
    c.env = env
    c.lit('./configure', '--prefix=' + to)
    if parl:
      c.lit('--enable-parallel')
    yield async.WaitFor(c.exec_a())
  
    c = Cmd(ctx)
    c.cwd = src
    c.tag = pkg
    c.env = env
    c.lit(conf.make)
    yield async.WaitFor(c.exec_a())
  
    c = Cmd(ctx)
    c.cwd = src
    c.tag = pkg
    c.env = env
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
