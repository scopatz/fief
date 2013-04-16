import os
import sys

from fief import async, Cmd, easy, EnvDelta, ifc

interfaces = {
  'mpi3': ifc(requires='cc'),
  'mpi2': ifc(requires='cc'),
  'mpi1': ifc(requires='cc'),
}

def deliverable_envdelta(built):
  root = built
  return EnvDelta(
    sets={
      'PATH': (os.path.join(root, 'bin'),),
      'LD_LIBRARY_PATH': (os.path.join(root, 'lib'),),
      'INCLUDE_PATH': (os.path.join(root, 'include'),)
    }
  )

def build_a(ctx):
  to = yield async.Sync(ctx.outfile_a(os.path.join('build', ctx.package)))
  to = os.path.abspath(to)
  os.mkdir(to)
  env = yield async.Sync(easy.gather_env_a(ctx))
  yield async.Result(to)

#realize = repo.c_realize

#build_a = repo.configure_make_make_install(interfaces, libs=('mpich', 'fmpich', 
#                                           'mpichcxx', 'mpichf90', 'mpl', 'opa'))
