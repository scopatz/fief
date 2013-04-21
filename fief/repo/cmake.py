import os

from fief import async, Cmd, easy, EnvDelta, Imp

implements = {
  'cmake': Imp(requires=['cc'])
}

def deliverable_envdelta(ifc, built, delv):
  return EnvDelta(
    sets={
      'PATH': [os.path.join(built['root'], 'bin')]
    }
  )

def build_a(ctx):
  root = yield async.Sync(ctx.outfile_a(os.path.join('build', ctx.package)))
  os.mkdir(root)

  env = yield async.Sync(easy.gather_env_a(ctx))
  cmdkws = {'cwd': ctx.source, 'tag': ctx.package, 'env': env}
  
  c = Cmd(ctx, **cmdkws)
  bootstrap = ('bash', 'bootstrap') if os.name == 'nt' else './bootstrap'
  c.lit(bootstrap, '--prefix=' + root)
  yield async.Sync(c.exec_a())

  c = Cmd(ctx, **cmdkws)
  c.lit('make', ctx.option_soft('make-opt-parallel'))
  yield async.Sync(c.exec_a())

  c = Cmd(ctx, **cmdkws)
  c.lit('make', 'install')
  yield async.Sync(c.exec_a())

  built = {'root': root}
  yield async.Result(built)
