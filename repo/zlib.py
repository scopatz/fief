import os
import shutil
from fief import repo
from fief import conf
from fief.repo import ifc, async, Cmd

interfaces = {'zlib': ifc()}

def realize(delivs):
  env = repo.c_realize(delivs)
  del env['PATH']
  return env

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

    cmdkws = {'cwd': src, 'tag': pkg, 'env': env}
    if os.name == 'nt':
      c = Cmd(ctx, **cmdkws)
      c.lit(conf.make, '-f', 'win32/Makefile.gcc')
      yield async.WaitFor(c.exec_a())

      # NOTE: not BINARY_PATH != 'bin' to replicate unix install behaviour
      cmdkws['env']['BINARY_PATH'] = os.path.join(to, 'lib')
      cmdkws['env']['INCLUDE_PATH'] = os.path.join(to, 'include')
      cmdkws['env']['LIBRARY_PATH'] = os.path.join(to, 'lib')
      c = Cmd(ctx, **cmdkws)
      c.lit(conf.make_install, '-f', 'win32/Makefile.gcc', 'SHARED_MODE=1')
      yield async.WaitFor(c.exec_a())
      shutil.copy(os.path.join(to, 'lib', 'zlib1.dll'), 
                  os.path.join(to, 'lib', 'libz.dll'))
    else:
      c = Cmd(ctx, **cmdkws)
      c.lit('./configure', '--prefix=' + to)
      yield async.WaitFor(c.exec_a())

      c = Cmd(ctx, **cmdkws)
      c.lit(conf.make)
      yield async.WaitFor(c.exec_a())

      c = Cmd(ctx, **cmdkws)
      c.lit(conf.make_install)
      yield async.WaitFor(c.exec_a())
  finally:
    cleanup()

  delivs = {'root': to, 'libs': set('z'), 'pkg': pkg}
  yield async.Result(delivs)
