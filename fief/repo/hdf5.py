import os
import sys

from fief import async, Cmd, easy, EnvDelta, Imp

implements = {
  'hdf5': Imp(requires=('zlib',)), # and cmake?
  'hdf5-cpp': Imp(subsumes=('hdf5',)), 
  'hdf5-parallel': Imp(subsumes=('hdf5',), requires=('mpi2',)),
}

def deliverable_envdelta(ifc, built, delv):
  root = built['root']
  return EnvDelta(
    sets={
      'PATH': (os.path.join(root, 'bin'),),
      'LD_LIBRARY_PATH': (os.path.join(root, 'lib'),),
      'INCLUDE_PATH': (os.path.join(root, 'include'),)
    }
  )

def deliverable_libs(ifc, built, delv):
  return built['libs']

def build_a(ctx):
  pkg = ctx.package
  src = ctx.source
  
  cpp = pkg == ctx['implementor','hdf5-cpp']
  parl = pkg == ctx['implementor','hdf5-parallel']
  
  to = yield async.Sync(ctx.outfile_a(os.path.join('build', pkg)))
  os.mkdir(to)
  
  env = yield async.Sync(easy.gather_env_a(ctx))
  cmdkws = {'cwd': src, 'tag': pkg, 'env': env}
  
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
    yield async.Sync(c.exec_a())
  else:
    c = Cmd(ctx, **cmdkws)
    c.lit('./configure', '--prefix=' + to)
    if parl: 
      c.lit('--enable-parallel')
    yield async.Sync(c.exec_a())

  c = Cmd(ctx, **cmdkws)
  c.lit('make', ctx.option('make-opt-parallel'))
  yield async.Sync(c.exec_a())

  c = Cmd(ctx, **cmdkws)
  c.lit('make','install')
  yield async.Sync(c.exec_a())

  libs = set(['hdf5','hdf5_hl'])
  if cpp:
    libs |= set(('hdf5_cpp', 'hdf5_hl_cpp'))
  
  yield async.Result({'root': to, 'libs': libs})
