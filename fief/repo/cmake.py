import os
from fief import ifc, easy, async, Cmd, EnvDelta

interfaces = {'cmake': ifc(requires='cc')}

def deliverable_envdelta(built):
  return EnvDelta(sets={'PATH': [os.path.join(built['root'], 'bin')]})

def build_a(ctx, pkg, src, opts):
  root = yield async.Sync(ctx.outfile_a(os.path.join('build', pkg)))
  root = os.path.abspath(root)
  os.mkdir(root)

  env = easy.gather_env(ctx, interfaces)
  cmdkws = {'cwd': src, 'tag': pkg, 'env': env}

  c = Cmd(ctx, **cmdkws)
  bootstrap = ('bash', 'bootstrap') if os.name == 'nt' else './bootstrap'
  c.lit(bootstrap, '--prefix=' + root)
  yield async.Sync(c.exec_a())

  c = Cmd(ctx, **cmdkws)
  c.lit('make', '-j', '3')
  yield async.Sync(c.exec_a())

  c = Cmd(ctx, **cmdkws)
  c.lit('make', 'install')
  yield async.Sync(c.exec_a())

  delivs = {'root': root, 'pkg': pkg}
  yield async.Result(delivs)
