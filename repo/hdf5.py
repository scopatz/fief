import async
import bake
import os
import magic

def depends_a(ctx):
  yield async.Result({'zlib':()})

def build_a(ctx):
  src, cleanup = yield async.WaitFor(magic.fetch_nomemo_a(ctx, 'hdf5'))
  
  parl = ctx['feature','hdf5','parallel']
  
  zlib_bld_a = yield async.WaitFor(magic.builder_nomemo_a(ctx, 'zlib'))
  zlib_dir = yield async.WaitFor(ctx(zlib_bld_a))
  
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
  c.lit('make')
  yield async.WaitFor(c.exec_a())
  
  c = bake.Cmd(ctx)
  c.cwd = src
  c.lit('make', 'install')
  yield async.WaitFor(c.exec_a())
  
  cleanup()
  
  yield async.Result(to, magic.merge_lib_deps(('zlib',), zlib_deps))
