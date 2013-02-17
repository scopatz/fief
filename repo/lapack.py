import os
from fief import async
from fief import repo
from fief import conf
from fief.repo import ifc, Cmd

interfaces = {'lapack': ifc(requires=('cc', 'cmake', 'fortran'))}

def realize(delivs):
  root = delivs['root']
  return {'LD_LIBRARY_PATH': os.path.join(root, 'lib'), 
          'C_INCLUDE_PATH': os.path.join(root, 'include'),}

def build_a(ctx):
  pkg = ctx['pkg']
  assert any([ctx['interface', ifc] == pkg for ifc in interfaces])
  psrc = yield async.WaitFor(repo.fetch_nomemo_a(ctx, pkg))
  env = yield async.WaitFor(repo.realize_deps_a(ctx, interfaces))

  try:
    src, cleanup = yield async.WaitFor(repo.stage_nomemo_a(ctx, pkg))
    srcbld = os.path.join(src, 'build')
    os.mkdir(srcbld)
    cmdkws = {'cwd': srcbld, 'tag': pkg, 'env': env}
    to = yield async.WaitFor(ctx.outfile_a('build', pkg))
    to = os.path.abspath(to)
    os.mkdir(to)

    c = Cmd(ctx, **cmdkws)
    c.lit('cmake', '-DCMAKE_INSTALL_PREFIX:PATH=' + to, 
          '-DLAPACKE:BOOL=ON', '-DBUILD_SHARED_LIBS:BOOL=ON', '..')
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

