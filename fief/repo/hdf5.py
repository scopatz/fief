import os
import sys

from fief import async, Cmd, easy, EnvDelta, ifc

interfaces = {
  'hdf5': ifc(requires=('zlib',)), # and cmake?
  'hdf5-cpp': ifc(subsumes='hdf5'), 
  'hdf5-parallel': ifc(subsumes='hdf5', requires='mpi2'),
}

def deliverable_envdelta(built):
  root = built['root']
  return EnvDelta(
    sets={
      'PATH': (os.path.join(root, 'bin'),),
      'LD_LIBRARY_PATH': (os.path.join(root, 'lib'),),
      'INCLUDE_PATH': (os.path.join(root, 'include'),)
    }
  )

def deliverable_libs(built):
  return built['libs']

def build_a(ctx, pkg, src, opts):
  parl, cpp = False, False
  
  to = yield async.Sync(ctx.outfile_a(os.path.join('build', pkg)))
  to = os.path.abspath(to)
  os.mkdir(to)

  env = easy.gather_env(ctx, interfaces)
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
  c.lit('make','-j')
  yield async.Sync(c.exec_a())

  c = Cmd(ctx, **cmdkws)
  c.lit('make','install')
  yield async.Sync(c.exec_a())

  libs = set(['hdf5','hdf5_hl'])
  if cpp:
    libs |= set(('hdf5_cpp', 'hdf5_hl_cpp'))
  delivs = {'root': to, 'libs': libs, 'pkg': pkg}
  yield async.Result(delivs)
