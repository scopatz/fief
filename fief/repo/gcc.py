import os
import shutil
import tempfile
import shutil
from fief import async, easy, EnvDelta, Imp

implements = {
  'cc': Imp(buildreqs=['cc','c++','mpc','gmp','mpfr'], runreqs=['mpc','gmp','mpfr']),
  'c++': Imp(buildreqs=['cc','c++','mpc','gmp','mpfr'], runreqs=['mpc','gmp','mpfr']),
}

def deliverable_root(ifc, built, delv):
  return built

def deliverable_envdelta(ifc, built, delv):
  root = built
  return EnvDelta(
    sets={
      'PATH': (os.path.join(root, 'bin'),),
      'LD_LIBRARY_PATH': (os.path.join(root, 'lib'),),
      'INCLUDE_PATH': (os.path.join(root, 'include'),)
    }
  )

def build_a(ctx):
  root = yield async.Sync(ctx.outdir_a())
  bld = tempfile.mkdtemp()
  try:
    c = ctx.command(cwd=bld)
    c.lit(
      os.path.join(ctx.source,'configure'),
      '--prefix=' + root,
      '--enable-languages=' + ','.join(
        ['c']*(1 if ctx.implementing('cc') else 0) +
        ['c++']*(1 if ctx.implementing('c++') else 0)),
      '--disable-bootstrap'
    )
    yield async.Sync(c.exec_a())
    
    c = ctx.command(cwd=bld)
    c.lit('make', ctx.option_soft('make-opt-parallel'))
    yield async.Sync(c.exec_a())

    c = ctx.command(cwd=bld)
    c.lit('make','install')
    yield async.Sync(c.exec_a())
  
    yield async.Result(root)
  
  finally:
    shutil.rmtree(bld)
