import os
import shutil
from fief import async, Cmd, easy, EnvDelta, Imp

implements = {
  'zlib': Imp(buildreqs='cc')
}

def deliverable_envdelta(ifc, built, delv):
  root = built
  return EnvDelta(
    sets={
      'PATH': (os.path.join(root, 'bin'),),
      'LD_LIBRARY_PATH': (os.path.join(root, 'lib'),),
      'INCLUDE_PATH': (os.path.join(root, 'include'),)
    }
  )

def deliverable_libs(ifc, built, delv):
  return frozenset(['z'])

def build_a(ctx):
  root = yield async.Sync(ctx.outdir_a())
  if os.name == 'nt':
    c = ctx.command()
    c.lit('make', '-f', 'win32/Makefile.gcc')
    yield async.Sync(c.exec_a())
    
    # NOTE: not BINARY_PATH != 'bin' root replicate unix install behaviour
    c = ctx.command(envmod=lambda e: (e.update({
      'BINARY_PATH': os.path.join(root, 'lib'),
      'INCLUDE_PATH': os.path.join(root, 'include'),
      'LIBRARY_PATH': os.path.join(root, 'lib'),
    }), e)[1])
    c.lit('make', 'install', '-f', 'win32/Makefile.gcc', 'SHARED_MODE=1')
    yield async.Sync(c.exec_a())
    shutil.copy(os.path.join(root, 'lib', 'zlib1.dll'), 
                os.path.join(root, 'lib', 'libz.dll'))
  else:
    c = ctx.command()
    c.lit('./configure', '--prefix=' + root)
    yield async.Sync(c.exec_a())
    
    c = ctx.command()
    c.lit('make', ctx.option_soft('make-opt-parallel'))
    yield async.Sync(c.exec_a())
    
    c = ctx.command()
    c.lit('make','install')
    yield async.Sync(c.exec_a())
  
  yield async.Result(root)
