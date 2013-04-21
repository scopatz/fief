import os

from fief import async, Cmd, easy, EnvDelta, Imp

implements = {
  'mpi1': Imp(requires=['cc'], directly=False),
  'mpi2': Imp(subsumes=['mpi1'], directly=False),
  'mpi3': Imp(subsumes=['mpi2']),
  'mpi1-fortran': Imp(requires=['fortran'], subsumes=['mpi1'], directly=False),
  'mpi2-fortran': Imp(subsumes=['mpi2','mpi1-fortran'], directly=False),
  'mpi3-fortran': Imp(subsumes=['mpi3','mpi2-fortran'])
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
  if ctx.package != ctx['implementor','mpi3-fortran']:
    c.lit('--disable-f77','--disable-fc')
  yield async.Sync(c.exec_a())
  
  c = Cmd(ctx, **cmdkws)
  c.lit('make', ctx.option_soft('make-opt-parallel'))
  yield async.Sync(c.exec_a())
  
  c = Cmd(ctx, **cmdkws)
  c.lit('make','install')
  yield async.Sync(c.exec_a())
  
  yield async.Result({'root':root})
