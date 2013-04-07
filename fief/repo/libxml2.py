import os
from glob import glob
from fief import ifc, easy, async, Cmd, EnvDelta

interfaces = {'libxml2': ifc(requires='cc')}

def deliverable_envdelta(built):
  root = built['root']
  sets={
    'PATH': [os.path.join(root, 'bin')],
    'LD_LIBRARY_PATH': [os.path.join(root, 'lib')],
    'INCLUDE_PATH': [os.path.join(root, 'include')],
    }
  pypath = glob(os.path.join(root, '*',  'site-packages')) + \
           glob(os.path.join(root, '*', '*',  'site-packages'))
  if 0 < len(pypath):
    sets['PYTHONPATH'] = set(pypath)
  return EnvDelta(sets=sets)

def deliverable_libs(built):
  return set(['xml2'])


def build_a(ctx, pkg, src, opts):
  root = yield async.Sync(ctx.outfile_a(os.path.join('build', pkg)))
  root = os.path.abspath(root)
  os.mkdir(root)

  env = easy.gather_env(ctx, interfaces)
  cmdkws = {'cwd': src, 'tag': pkg, 'env': env}

  c = Cmd(ctx, **cmdkws)
  c.lit('./configure', '--prefix=' + root)
  yield async.Sync(c.exec_a())

  c = Cmd(ctx, **cmdkws)
  c.lit('make', '-j', '3')
  yield async.Sync(c.exec_a())

  c = Cmd(ctx, **cmdkws)
  c.lit('make', 'install')
  yield async.Sync(c.exec_a())

  delivs = {'root': root, 'pkg': pkg}
  yield async.Result(delivs)
