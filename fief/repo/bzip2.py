import os
import shutil
from fief import async, Cmd, easy, EnvDelta, ifc, c_envdelta

interfaces = {'bzip2': ifc(requires='cc')}

deliverable_envdelta = c_envdelta

def deliverable_libs(built):
  return frozenset(['bz2'])

def build_a(ctx, pkg, path, opts):
  root = yield async.Sync(ctx.outfile_a(os.path.join('build', pkg)))
  root = os.path.abspath(root)
  os.mkdir(root)
  
  env = easy.gather_env(ctx, interfaces)
  cmdkws = {'cwd': path, 'tag': pkg, 'env': env}
  c = Cmd(ctx, **cmdkws)
  c.lit('make', '-f', 'win32/Makefile.gcc')
  yield async.Sync(c.exec_a())
    
  c = Cmd(ctx, **cmdkws)
  c.lit('make','install', 'PREFIX='+root)
  yield async.Sync(c.exec_a())
  
  built = {'root': root}
  yield async.Result(built)
