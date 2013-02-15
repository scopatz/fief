import os
from fief import repo
from fief import conf
from fief.repo import ifc, async, Cmd

interfaces = {'zlib': ifc()}

def realize(delivs):
  env = repo.c_realize(delivs)
  del env['PATH']
  return env

if os.name == 'nt':
  def build_a(ctx):
    pkg = ctx['pkg']
    assert any([ctx['interface', ifc] == pkg for ifc in interfaces])
    psrc = yield async.WaitFor(repo.fetch_nomemo_a(ctx, pkg))
    env = yield async.WaitFor(repo.realize_deps_a(ctx, interfaces))

    try:
      src, cleanup = yield async.WaitFor(repo.stage_nomemo_a(ctx, pkg))
  
      to = yield async.WaitFor(ctx.outfile_a('build', pkg))
      to = os.path.abspath(to)
      os.mkdir(to)
  
      c = Cmd(ctx)
      c.cwd = src
      c.tag = pkg
      c.env = env
      c.lit(conf.make, '-f', 'win32/Makefile.gcc')
      yield async.WaitFor(c.exec_a())

      env['BINARY_PATH'] = os.path.join(to, 'lib')  # NOTE: not 'bin' to replicate unix install behaviour
      env['INCLUDE_PATH'] = os.path.join(to, 'include')
      env['LIBRARY_PATH'] = os.path.join(to, 'lib')
      c = Cmd(ctx)
      c.cwd = src
      c.tag = pkg
      c.env = env
      c.lit(conf.make_install, '-f', 'win32/Makefile.gcc', 'SHARED_MODE=1')
      yield async.WaitFor(c.exec_a())
    finally:
      cleanup()

    delivs = {'root': to, 'libs': set('z'), 'pkg': pkg}
    yield async.Result(delivs)
else:
  build_a = repo.configure_make_make_install(interfaces, libs='z')
