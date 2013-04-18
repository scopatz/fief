import os

from fief import async, Cmd, easy, EnvDelta, Imp

implements = {
  'mpi1': Imp(requires='cc'),
  'mpi2': Imp(requires='cc'),
  'mpi3': Imp(requires='cc'),
  'mpi1-wrap-fortran': Imp(subsumes='mpi1', requires='fortran'),
  'mpi2-wrap-fortran': Imp(subsumes='mpi2', requires='fortran'),
  'mpi3-wrap-fortran': Imp(subsumes='mpi3', requires='fortran'),
}

def deliverable_envdelta(ifc, built, delv):
  return easy.c_envdelta(built['root'])

def deliverable_libs(ifc, built, delv):
  return ('mpich',)

def build_a(ctx):
  root = yield async.Sync(ctx.outfile_a(os.path.join('build', ctx.package)))
  os.mkdir(root)
  
  env = yield async.Sync(easy.gather_env_a(ctx))
  cmdkws = {'cwd': ctx.source, 'tag': ctx.package, 'env': env}
  
  c = Cmd(ctx, **cmdkws)
  c.lit('./configure', '--prefix=' + root)
  imps = ctx.argstup(*[('implementor','mpi%d-wrap-fortran'%v) for v in (1,2,3)])
  if not any(ctx.package == p for p in imps):
    c.lit('--disable-f77','--disable-fc')
  yield async.Sync(c.exec_a())
  
  c = Cmd(ctx, **cmdkws)
  c.lit('make', ctx.option('make-opt-parallel'))
  yield async.Sync(c.exec_a())
  
  c = Cmd(ctx, **cmdkws)
  c.lit('make','install')
  yield async.Sync(c.exec_a())
  
  yield async.Result({'root':root})
