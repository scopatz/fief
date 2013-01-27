import async
import bake
import os
import shutil
import tempfile

import build_zlib

def build_hdf5_a(ctx):
  ball = os.path.abspath(ctx['tarball', 'hdf5'])
  name = os.path.split(ball)[-1].rsplit('.', 2)[0]
  
  parl = ctx['feature','hdf5','parallel']
  
  bld = tempfile.mkdtemp()
  bld2 = os.path.join(bld, name)
  
  c = bake.Cmd(ctx)
  c.cwd = bld
  c.lit('tar', 'xzf').inf(ball)
  yield async.WaitFor(c.exec_a())
  
  zlib_dir = yield async.WaitFor(ctx(build_zlib.build_zlib_a))
  
  mpi_dir = None
  #if parl:
  #  mpi_dir = yield async.WaitFor(ctx(build_mpi.build_mpi_a))
  
  to = yield async.WaitFor(ctx.outfile_a('build'))
  to = os.path.abspath(to)
  os.mkdir(to)
  
  c = bake.Cmd(ctx)
  c.cwd = bld2
  c.lit('./configure', '--prefix=' + to)\
    .lit('--with-zlib=' + zlib_dir)\
    .lit(() if mpi_dir is None else ('--with-mpi=' + mpi_dir))
  yield async.WaitFor(c.exec_a())
  
  c = bake.Cmd(ctx)
  c.cwd = bld2
  c.lit('make')
  yield async.WaitFor(c.exec_a())
  
  c = bake.Cmd(ctx)
  c.cwd = bld2
  c.lit('make', 'install')
  yield async.WaitFor(c.exec_a())
  
  shutil.rmtree(bld)
  
  yield async.Result(to)
