import os
import sys
from fief import repo
from fief import conf
from fief.repo import ifc, async, Cmd

interfaces = {'hdf5': ifc(requires=('zlib', 'cmake')), 
              'hdf5-cpp': ifc(subsumes='hdf5'), 
              'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi2'),
              }

realize = repo.c_realize

def build_a(ctx):
  pkg = ctx['pkg']
  assert any([ctx['interface', ifc] == pkg for ifc in interfaces])
  cpp = (ctx['interface', 'hdf5-cpp'] == pkg)
  parl = (ctx['interface', 'hdf5-parallel'] == pkg)
  psrc = yield async.WaitFor(repo.fetch_nomemo_a(ctx, pkg))
  env = yield async.WaitFor(repo.realize_deps_a(ctx, interfaces))

  try:
    src, cleanup = yield async.WaitFor(repo.stage_nomemo_a(ctx, pkg))
    cmdkws = {'cwd': src, 'tag': pkg, 'env': env}
    to = yield async.WaitFor(ctx.outfile_a('build', pkg))
    to = os.path.abspath(to)
    os.mkdir(to)

    if os.name == 'nt':
      srcbld = os.path.join(src, 'build')
      os.mkdir(srcbld)
      cmdkws['cwd'] = srcbld
      c = Cmd(ctx, **cmdkws)
      c.lit('cmake', '-C', '../config/cmake/cacheinit.cmake', 
            '-G', 'MSYS Makefiles', 
            '-DHDF5_ENABLE_SZIP_SUPPORT:BOOL=OFF',
            '-DHDF5_ENABLE_Z_LIB_SUPPORT:BOOL=ON', 
            '-DCMAKE_INSTALL_PREFIX:PATH=' + to)
      if parl: 
        c.lit('-DHDF5_ENABLE_PARALLEL:BOOL=ON')
      c.lit('..')
      yield async.WaitFor(c.exec_a())
    else:
      c = Cmd(ctx, **cmdkws)
      c.lit('./configure', '--prefix=' + to)
      if parl: 
        c.lit('--enable-parallel')
      yield async.WaitFor(c.exec_a())
  
    c = Cmd(ctx, **cmdkws)
    c.lit(conf.make)
    yield async.WaitFor(c.exec_a())
  
    c = Cmd(ctx, **cmdkws)
    c.lit(conf.make_install)
    yield async.WaitFor(c.exec_a())
  finally:
    cleanup()

  libs = set(('hdf5', 'hdf5_hl'))
  if cpp:
    libs |= set(('hdf5_cpp', 'hdf5_hl_cpp'))
  delivs = {'root': to, 'libs': libs, 'pkg': pkg}
  yield async.Result(delivs)
