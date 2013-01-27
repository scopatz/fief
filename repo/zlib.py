import async
import bake
import os
import magic

def build_a(ctx):
  src, cleanup = yield async.WaitFor(magic.fetch_nomemo_a(ctx, 'zlib'))
  
  to = yield async.WaitFor(ctx.outfile_a('build'))
  to = os.path.abspath(to)
  os.mkdir(to)
  
  c = bake.Cmd(ctx)
  c.cwd = src
  c.lit('./configure', '--prefix=' + to)
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
  
  yield async.Result(to)
