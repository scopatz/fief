import async
import bake
import os
import shutil
import tempfile

def build_zlib_a(ctx):
  ball = os.path.abspath(ctx['tarball'])
  name = os.path.split(ball)[-1].rsplit('.', 2)[0]
  
  bld = tempfile.mkdtemp()
  bld2 = os.path.join(bld, name)
  
  c = bake.Cmd(ctx)
  c.cwd = bld
  c.lit('tar', 'xzf').inf(ball)
  yield async.WaitFor(c.exec_a())
  
  to = yield async.WaitFor(ctx.outfile_a('build'))
  to = os.path.abspath(to)
  os.mkdir(to)
  
  c = bake.Cmd(ctx)
  c.cwd = bld2
  c.lit('./configure', '--prefix=' + to)
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
