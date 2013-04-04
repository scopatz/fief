from fief.repository import PackageScript

packages = {
  'sys_cc': (None, 'sys_cc.py'),
  'sys_py': (None, 'sys_py.py'),
  'sys_fortran': (None, 'sys_fortran.py'),
  'lapack': ('http://www.netlib.org/lapack/lapack-3.4.2.tgz', 'lapack.py'), 
  'atlas': ('http://sourceforge.net/projects/math-atlas/files/Stable/3.10.1/atlas3.10.1.tar.bz2/download', 'atlas.py'),
  'cython': ('http://cython.org/release/Cython-0.18.tar.gz', 'cython.py'),
  'hdf5': ('http://www.hdfgroup.org/ftp/HDF5/releases/hdf5-1.8.10-patch1/src/hdf5-1.8.10-patch1.tar.bz2', 'hdf5.py'),
  'mpich': ('http://www.mpich.org/static/tarballs/3.0.1/mpich-3.0.1.tar.gz', 'mpich.py'),
  'numpy': ('https://github.com/numpy/numpy/archive/v1.7.0rc2.tar.gz', 'numpy.py'),
  'openmpi': ('http://www.open-mpi.org/software/ompi/v1.6/downloads/openmpi-1.6.3.tar.bz2', 'openmpi.py'),
  'sympy': ('https://github.com/sympy/sympy/archive/sympy-0.7.2.rc1.tar.gz', 'sympy.py'),
  'zlib': ('http://zlib.net/zlib-1.2.7.tar.gz', 'zlib.py'),
  'cmake': ('http://www.cmake.org/files/v2.8/cmake-2.8.10.2.tar.gz', 'cmake.py'),
  }

stash = ".fief-stash"

def path(p):
  return 'repo/' + p
  
packages = {
  'sys_cc': PackageScript(None, path('sys_cc.py')),
  'sys_py': PackageScript(None, path('sys_py.py')),
  'zlib': PackageScript('http://zlib.net/zlib-1.2.7.tar.gz', path('zlib.py')),
}
