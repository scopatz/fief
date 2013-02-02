import os
import sys
from fief import magic
from fief.magic import ifc, async, Cmd

interfaces = {'hdf5': ifc(requires='zlib', libs=('hdf5', 'hdf5_hl')), 
              'hdf5-cpp': ifc(subsumes='hdf5', libs=('hdf5_cpp', 'hdf5_hl_cpp')), 
              'hdf5-mp3': ifc(subsumes='hdf5', requires='ffmpeg'), 
              'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi3'),
              }

def build_a(ctx):
  pkg = ctx['pkg']
  src, cleanup = yield async.WaitFor(magic.fetch_nomemo_a(ctx, pkg))

  try:
    parl = ctx['interface','hdf5-parallel']
    paths = yield async.WaitFor(magic.build_deps_a(ctx, interfaces))
    zlib_dir = paths['zlib']  
    mpi_dir = paths['mpi3'] if parl is not None else None
  
    to = yield async.WaitFor(ctx.outfile_a('build'))
    to = os.path.abspath(to)
    os.mkdir(to)
  
    c = Cmd(ctx)
    c.cwd = src
    c.lit('./configure', '--prefix=' + to)\
      .lit('--with-zlib=' + zlib_dir)
    if mpi_dir is not None:
      c.lit('--enable-parallel')
      newpath = os.path.join(mpi_dir, 'bin') + os.pathsep + os.getenv('PATH',"")
      c.env = {'PATH': newpath}
    yield async.WaitFor(c.exec_a())
  
    c = Cmd(ctx)
    c.cwd = src
    c.lit('make', '-j')
    yield async.WaitFor(c.exec_a())
  
    c = Cmd(ctx)
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
