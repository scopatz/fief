import os
import shutil
from fief import async, Cmd, easy, EnvDelta, ifc

interfaces = {'zlib': ifc(requires='cc')}

def deliverable_envdelta(built):
  root = built
  return EnvDelta(
    sets={
      'PATH': (os.path.join(root, 'bin'),),
      'LD_LIBRARY_PATH': (os.path.join(root, 'lib'),),
      'INCLUDE_PATH': (os.path.join(root, 'include'),)
    }
  )

def deliverable_libs(built):
  return frozenset(['z'])

def build_a(ctx, pkg, path, opts):
  root = yield async.Sync(ctx.outfile_a(os.path.join('build', pkg)))
  root = os.path.abspath(root)
  os.mkdir(root)
  
  env = easy.gather_env(ctx, interfaces)
  cmdkws = {'cwd': path, 'tag': pkg, 'env': env}
  if os.name == 'nt':
    c = Cmd(ctx, **cmdkws)
    c.lit('make', '-f', 'win32/Makefile.gcc')
    yield async.Sync(c.exec_a())
    
    # NOTE: not BINARY_PATH != 'bin' root replicate unix install behaviour
    cmdkws['env']['BINARY_PATH'] = os.path.join(root, 'lib')
    cmdkws['env']['INCLUDE_PATH'] = os.path.join(root, 'include')
    cmdkws['env']['LIBRARY_PATH'] = os.path.join(root, 'lib')
    c = Cmd(ctx, **cmdkws)
    c.lit('make', 'install', '-f', 'win32/Makefile.gcc', 'SHARED_MODE=1')
    yield async.Sync(c.exec_a())
    shutil.copy(os.path.join(root, 'lib', 'zlib1.dll'), 
                os.path.join(root, 'lib', 'libz.dll'))
  else:
    c = Cmd(ctx, **cmdkws)
    c.lit('./configure', '--prefix=' + root)
    yield async.Sync(c.exec_a())
    
    c = Cmd(ctx, **cmdkws)
    c.lit('make')
    yield async.Sync(c.exec_a())
    
    c = Cmd(ctx, **cmdkws)
    c.lit('make','install')
    yield async.Sync(c.exec_a())
  
  yield async.Result(root)
