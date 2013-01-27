import async
import bake
import os
import magic

def depends_a(ctx):
    yield async.Result({})

def build_a(ctx):
    deps = ctx['deps']
    src, cleanup = yield async.WaitFor(magic.fetch_nomemo_a(ctx, 'sympy'))
  
    to = yield async.WaitFor(ctx.outfile_a('build'))
    to = os.path.abspath(to)
    os.mkdir(to)
  
    c = bake.Cmd(ctx)
    c.cwd = src
    c.lit('python', 'setup.py', 'install', '--prefix=' + to)
    yield async.WaitFor(c.exec_a())
  
    cleanup()
  
    yield async.Result(to)
