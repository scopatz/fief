import async
import bake
import os
import magic

ifc = magic.ifc

interfaces = {'hdf5': ifc(requires='zlib', libs=('hdf5', 'hdf5_hl')), 
              'hdf5-cpp': ifc(subsumes='hdf5', libs=('hdf5_cpp', 'hdf5_hl_cpp')), 
              'hdf5-mp3': ifc(subsumes='hdf5', requires='ffmpeg'), 
              'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi2'),
              }

def build_a(ctx):
  pkg = ctx['pkg']
  src, cleanup = yield async.WaitFor(magic.fetch_nomemo_a(ctx, pkg))

  try:
    parl = ctx['feature','hdf5','parallel']
    paths = yield async.WaitFor(magic.built_dirs_a(ctx, interfaces))
    zlib_dir = paths['zlib']
  
    mpi_dir = None
    #if parl:
    #  mpi_dir = yield async.WaitFor(ctx(build_mpi.build_mpi_a))
  
    to = yield async.WaitFor(ctx.outfile_a('build'))
    to = os.path.abspath(to)
    os.mkdir(to)
  
    c = bake.Cmd(ctx)
    c.cwd = src
    c.lit('./configure', '--prefix=' + to)\
      .lit('--with-zlib=' + zlib_dir)\
      .lit(() if mpi_dir is None else ('--with-mpi=' + mpi_dir))
    yield async.WaitFor(c.exec_a())
  
    c = bake.Cmd(ctx)
    c.cwd = src
    c.lit('make', '-j')
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
