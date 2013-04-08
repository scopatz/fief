import os
from glob import glob
from fief import ifc, easy, async, Cmd, EnvDelta, configure_make_make_install, \
    c_envdelta, find_libs

interfaces = {'boost': ifc(requires='cc')}

deliverable_envdelta = c_envdelta

deliverable_libs = find_libs

def build_a(ctx, pkg, src, opts):
  root = yield async.Sync(ctx.outfile_a(os.path.join('build', pkg)))
  root = os.path.abspath(root)
  os.mkdir(root)

  env = easy.gather_env(ctx, interfaces)
  cmdkws = {'cwd': src, 'tag': pkg, 'env': env}
  
  c = Cmd(ctx, **cmdkws)
  if os.name == 'nt':
    c.lit('bootstap.bat', '--prefix=' + root)
  else:
    c.lit('./bootstrap.sh', '--prefix=' + root)
  yield async.Sync(c.exec_a())

  c = Cmd(ctx, **cmdkws)
  c.lit('./b2', 'install')
  yield async.Sync(c.exec_a())

  built = {'root': root, 'pkg': pkg}
  yield async.Result(built)

