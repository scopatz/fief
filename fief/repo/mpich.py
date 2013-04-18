import os

from fief import async, Cmd, easy, EnvDelta, Imp

implements = {
  i: Imp(requires='cc') for i in ('mpi1','mpi2','mpi3')
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
  if ctx['implementor','fortran'] is None:
    c.lit('--disable-f77','--disable-fc')
  yield async.Sync(c.exec_a())
  
  c = Cmd(ctx, **cmdkws)
  c.lit('make', ctx.option('make-opt-parallel'))
  yield async.Sync(c.exec_a())
  
  c = Cmd(ctx, **cmdkws)
  c.lit('make','install')
  yield async.Sync(c.exec_a())
  
  yield async.Result({'root':root})
