import os
from fief import repo
from fief import conf
from fief.repo import ifc, async, Cmd

interfaces = {'zlib': ifc(libs='z')}

def realize(delivs):
  env = repo.c_realize(delivs)
  del env['PATH']
  return env

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
  
  delivs = {'root': to, 'libs': ('z',), 'pkg': pkg}
  yield async.Result(delivs)
