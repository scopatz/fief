import os
import async
import envdelta
from bake import Cmd
from repository import PackageScript

def gather_envdelta(ctx, ifx):
  pkg = ctx['pkg']
  deps = set()
  for i,ifc in ifx.iteritems():
    if ctx['implementor',i] == pkg:
      for req in ifc.requires:
        deps.add(ctx['implementor',req])
  
  ed = envdelta.EnvDelta()
  for dep in deps:
    e = ctx['deliverable','envdelta',dep]
    if e is not None:
      ed.merge(e)
  return ed

def gather_env(ctx, ifx):
  return gather_envdelta(ctx, ifx).apply(os.environ)

# Some convience functions

def configure_make_make_install(ifx=None, libs=None):
  ifx = ifx or {}
  def build_a(ctx, pkg, src, opts):
    root = yield async.Sync(ctx.outfile_a(os.path.join('build', pkg)))
    root = os.path.abspath(root)
    os.mkdir(root)

    env = gather_env(ctx, ifx)
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

    built = {'root': root, 'pkg': pkg, 'libs': libs or set()}
    yield async.Result(built)
  return build_a

def c_envdelta(built):
  root = built['root']
  sets={
    'PATH': [os.path.join(root, 'bin')],
    'CPATH': [os.path.join(root, 'include')],
    'LD_LIBRARY_PATH': [os.path.join(root, 'lib')],
    }
  return envdelta.EnvDelta(sets=sets)  

def find_libs(built):
  root = built['root']
  # FIXME posix only
  files =glob(os.path.join(root, '*',  'lib*.[alos][oa]?'))
  return set([os.path.split(f)[1][3:].rsplit('.', 1) for f in files])


# Set up default packages repo
repopath = os.path.join(os.path.split(__file__)[0], 'repo')
p = lambda x: os.path.join(repopath, x)
packages = {
  'atlas': PackageScript('http://sourceforge.net/projects/math-atlas/files/Stable/3.10.1/atlas3.10.1.tar.bz2/download', p('atlas.py')),
  'cmake': PackageScript('http://www.cmake.org/files/v2.8/cmake-2.8.10.2.tar.gz', p('cmake.py')),
  'cython': PackageScript('http://cython.org/release/Cython-0.18.tar.gz', p('cython.py')),
  'glibmm': PackageScript('http://ftp.gnome.org/pub/GNOME/sources/glibmm/2.28/glibmm-2.28.2.tar.xz', p('glibmm.py')),
  'hdf5': PackageScript('http://www.hdfgroup.org/ftp/HDF5/releases/hdf5-1.8.10-patch1/src/hdf5-1.8.10-patch1.tar.bz2', p('hdf5.py')),
  'lapack': PackageScript('http://www.netlib.org/lapack/lapack-3.4.2.tgz', p('lapack.py')),
  'libxml2': PackageScript('ftp://xmlsoft.org/libxml2/libxml2-2.9.0.tar.gz', p('libxml2.py')),
  'libxml++': PackageScript('http://ftp.gnome.org/pub/GNOME/sources/libxml++/2.36/libxml++-2.36.0.tar.xz', p('libxml++.py')),
  'mpich': PackageScript('http://www.mpich.org/static/tarballs/3.0.1/mpich-3.0.1.tar.gz', p('mpich.py')),
  'numpy': PackageScript('https://github.com/numpy/numpy/archive/v1.7.0rc2.tar.gz', p('numpy.py')),
  'openmpi': PackageScript('http://www.open-mpi.org/software/ompi/v1.6/downloads/openmpi-1.6.3.tar.bz2', p('openmpi.py')),
  'sympy': PackageScript('https://github.com/sympy/sympy/archive/sympy-0.7.2.rc1.tar.gz', p('sympy.py')),
  'sys_cc': PackageScript(None, p('sys_cc.py')),
  'sys_fortran': PackageScript(None, p('sys_fortran.py')),
  #'sys_glibmm': PackageScript(None, p('sys_glibmm.py')),
  'sys_py': PackageScript(None, p('sys_py.py')),
  'zlib': PackageScript('http://zlib.net/zlib-1.2.7.tar.gz', p('zlib.py')),
  }
del p, repopath
