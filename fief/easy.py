import os
import sys
from itertools import chain

import async

from bake import Cmd
from envdelta import EnvDelta
from repository import Imp, Package

class PackageSys(Package):
  def __init__(me, ifc):
    me._ifc = ifc
  
  def source(me):
    return None
  
  def implements_a(me, oven):
    yield async.Result({me._ifc: Imp()})
  
  def deliverer(me):
    return lambda ifc,what,built,delv: None
  
  def builder(me):
    def build_a(ctx):
      yield async.Result(None)
    return build_a

class PackageScript(Package):
  def __init__(me, source, py_file):
    me._src = source
    me._py = py_file
    me._imps = None
    me._ns = None
  
  def source(me):
    return me._src
  
  def implements_a(me, oven):
    box = [None]
    def load_imps_a(ctx):
      py = ctx['py']
      ctx.infile(py)
      box[0] = {}
      execfile(py, box[0], box[0])
      yield async.Result(box[0]['implements'])
    
    if me._imps is None:
      if me._ns is None:
        me._imps = yield async.Sync(oven.memo_a(load_imps_a, {'py':me._py}))
        me._ns = box[0]
      else:
        me._imps = me._ns['implements']
    
    yield async.Result(me._imps)
  
  def _ensure_ns(me):
    if me._ns is None:
      me._ns = {}
      execfile(me._py, me._ns, me._ns)

  def deliverer(me):
    me._ensure_ns()
    ns = me._ns
    if 'deliverable' in ns:
      return ns['deliverable']
    else:
      pre = 'deliverable_'
      d = dict((nm[len(pre):],ns[nm]) for nm in ns if nm.startswith(pre))
      return lambda ifc,what,built,delv: d.get(what, lambda *_:None)(ifc,built,delv)
  
  def builder(me):
    me._ensure_ns()
    return me._ns['build_a']

class PackageConfigMakeInstall(Package):
  def __init__(me, source, imps, libs=()):
    me._src = source
    me._imps = imps
    me._libs = libs
  
  def source(me):
    return me._src
  
  def implements_a(me, oven):
    yield async.Result(me._imps)
  
  def deliverer(me):
    def deliverable(ifc, what, built, delv):
      if what == 'envdelta':
        return c_envdelta(built['root'])
      else:
        return built.get(what)
    return deliverable
  
  def builder(me):
    # put members of me into function scope variables so that build_a doesnt
    # close over me
    libs = me._libs
    
    def build_a(ctx):
      root = yield async.Sync(ctx.outfile_a(os.path.join('build', ctx.package)))
      os.mkdir(root)
      
      env = yield async.Sync(gather_env_a(ctx))
      cmdkws = {'cwd': ctx.source, 'tag': ctx.package, 'env': env}
      
      c = Cmd(ctx, **cmdkws)
      c.lit('./configure', '--prefix=' + root)
      yield async.Sync(c.exec_a())
      
      c = Cmd(ctx, **cmdkws)
      c.lit('make', ctx.option_soft('make-opt-parallel'))
      yield async.Sync(c.exec_a())
      
      c = Cmd(ctx, **cmdkws)
      c.lit('make','install')
      yield async.Sync(c.exec_a())
      
      yield async.Result({'root':root, 'libs':libs})
    
    return build_a

class PackageAptGet(Package):
  thread = async.Pool(size=1)
  
  def __init__(me, aptpkg, ifcs, libs=()):
    me._aptpkg = aptpkg
    me._ifcs = ifcs
    me._libs = libs
  
  def source(me):
    return None
  
  def implements_a(me, oven):
    yield async.Result(dict((i,Imp()) for i in me._ifcs))
  
  def deliverer(me):
    def deliverable(ifc, what, built, delv):
      return None
    return deliverable
  
  def builder(me):
    aptpkg = me._aptpkg
    def build_a(ctx):
      c = Cmd(ctx, tag=ctx.package, pool=PackageAptGet.thread)
      c.lit('apt-get','-y','install',aptpkg)
      yield async.Sync(c.exec_a())
      yield async.Result(None)
    return build_a
  
def required_ifcs(ctx, ifcs):
  def args_notag(xs):
    a = ctx.args(xs)
    return dict((x[1:] if len(x)>2 else x[1], y) for x,y in a.iteritems())
  
  ifcs = set(ifcs)
  more = list(ifcs)
  while len(more) > 0:
    ifc_imp = args_notag(('implementor',i) for i in more)
    del more[:]
    pkg_ifc_reqs = args_notag(('pkg_ifc_requires',p,i) for i,p in ifc_imp.iteritems() if p is not None)
    reqs = set(chain(*pkg_ifc_reqs.values()))
    for i in reqs:
      if i not in ifcs:
        ifcs.add(i)
        more.append(i)
  
  return ifcs

def dependent_ifcs(ctx, pkg):
  def args_notag(xs):
    a = ctx.args(xs)
    return dict((x[1:] if len(x)>2 else x[1], y) for x,y in a.iteritems())
  
  ifcs = set(ctx['pkg_implements',pkg])
  imps = args_notag(('implementor',i) for i in ifcs)
  ifcs = set(i for i,p in imps.iteritems() if p==pkg)
  reqs = required_ifcs(ctx, ifcs)
  reqs -= ifcs
  return reqs

def dependent_pkgs(ctx, pkg):
  """For a given package, will compute the set of all packages that fulfill
  the required interfaces of that package and all packages found in this process.
  """
  def args_notag(xs):
    a = ctx.args(xs)
    return dict((x[1:] if len(x)>2 else x[1], y) for x,y in a.iteritems())
  
  ifcs = dependent_ifcs(ctx, pkg)
  pkgs = set(args_notag(('implementor',i) for i in ifcs).itervalues())
  assert pkg not in pkgs
  return pkgs

def deliverabler(pkgobjs, ifc2pkg, pkg2built):
  def cb(ifc, what):
    pkg = ifc2pkg[ifc]
    return pkgobjs[pkg].deliverer()(ifc, what, pkg2built[pkg], cb)
  return cb

def deliverabler_a(ctx):
  deps = dependent_pkgs(ctx, ctx.package)
  a = ctx.args([('builder',p) for p in deps] + [('deliverer',p) for p in deps])
  bldrs = dict((x,y) for (tag,x),y in a.iteritems() if tag=='builder')
  delvs = dict((x,y) for (tag,x),y in a.iteritems() if tag=='deliverer')
  
  builts = {}
  for dep in deps:
    builts[dep] = yield async.Sync(ctx.memo_a(bldrs[dep]))
  
  def cb(ifc, what):
    pkg = ctx['implementor',ifc]
    return delvs[pkg](ifc, what, builts[pkg], cb)
  
  yield async.Result(cb)

def gather_envdelta_a(ctx):
  ed = EnvDelta()
  ifcs = dependent_ifcs(ctx, ctx.package)
  delv = yield async.Sync(deliverabler_a(ctx))
  for i in ifcs:
    e = delv(i, 'envdelta')
    if e is not None:
      ed.merge(e)
  yield async.Result(ed)

def gather_env_a(ctx):
  ed = yield async.Sync(gather_envdelta_a(ctx))
  yield async.Result(ed.apply(os.environ))

def c_envdelta(root):
  return EnvDelta(
    sets=dict((var, path) for var,path in [
      ('PATH', os.path.join(root, 'bin')),
      ('CPATH', os.path.join(root, 'include')),
      ('LD_LIBRARY_PATH', os.path.join(root, 'lib')),
      ('PKG_CONFIG_PATH', os.path.join(root, 'lib', 'pkgconfig')),
      ('MANPATH', os.path.join(root, 'share', 'man')),
    ] if os.path.isdir(path))
  )

def find_libs(built):
  root = built['root']
  # FIXME posix only
  files = glob(os.path.join(root, '*',  'lib*.[alos][oa]?'))
  return set([os.path.split(f)[1][3:].rsplit('.', 1) for f in files])


def _repo_py(f):
  return os.path.join(os.path.split(__file__)[0], 'repo', f)

# keeping this around as reference, it is overwritten below
p = _repo_py
packages = {
  'atlas': PackageScript('http://sourceforge.net/projects/math-atlas/files/Stable/3.10.1/atlas3.10.1.tar.bz2/download', p('atlas.py')),
  'bzip2': PackageScript('http://www.bzip.org/1.0.6/bzip2-1.0.6.tar.gz', p('bzip2.py')),
  'boost': PackageScript('http://sourceforge.net/projects/boost/files/boost/1.53.0/boost_1_53_0.tar.bz2/download', p('boost.py')),
  'cmake': PackageScript('http://www.cmake.org/files/v2.8/cmake-2.8.10.2.tar.gz', p('cmake.py')),
  'cython': PackageScript('http://cython.org/release/Cython-0.18.tar.gz', p('cython.py')),
  'glibmm': PackageScript('http://ftp.gnome.org/pub/GNOME/sources/glibmm/2.28/glibmm-2.28.2.tar.xz', p('glibmm.py')),
  'hdf5': PackageScript('http://www.hdfgroup.org/ftp/HDF5/releases/hdf5-1.8.10-patch1/src/hdf5-1.8.10-patch1.tar.bz2', p('hdf5.py')),
  'lapack': PackageScript('http://www.netlib.org/lapack/lapack-3.4.2.tgz', p('lapack.py')),
  'libxml2': PackageScript('ftp://xmlsoft.org/libxml2/libxml2-2.9.0.tar.gz', p('libxml2.py')),
  'libxml++': PackageScript('http://ftp.gnome.org/pub/GNOME/sources/libxml++/2.30/libxml++-2.30.1.tar.bz2', p('libxml++.py')),
  'mpich': PackageScript('http://www.mpich.org/static/tarballs/3.0.1/mpich-3.0.1.tar.gz', p('mpich.py')),
  'numpy': PackageScript('https://github.com/numpy/numpy/archive/v1.7.0rc2.tar.gz', p('numpy.py')),
  'openmpi': PackageScript('http://www.open-mpi.org/software/ompi/v1.6/downloads/openmpi-1.6.3.tar.bz2', p('openmpi.py')),
  'sqlite': PackageScript('http://www.sqlite.org/2013/sqlite-autoconf-3071601.tar.gz', p('sqlite.py')),
  'sympy': PackageScript('https://github.com/sympy/sympy/archive/sympy-0.7.2.rc1.tar.gz', p('sympy.py')),
  'sys_cc': PackageScript(None, p('sys_cc.py')),
  'sys_fortran': PackageScript(None, p('sys_fortran.py')),
  #'sys_glibmm': PackageScript(None, p('sys_glibmm.py')),
  'sys_py': PackageScript(None, p('sys_py.py')),
  'zlib': PackageScript('http://zlib.net/zlib-1.2.7.tar.gz', p('zlib.py')),
  }
del p

packages = {
  'hdf5': PackageScript(
      source='http://www.hdfgroup.org/ftp/HDF5/releases/hdf5-1.8.10-patch1/src/hdf5-1.8.10-patch1.tar.bz2',
      py_file=_repo_py('hdf5.py')
    ),
  'mpich': PackageScript(
      source='http://www.mpich.org/static/tarballs/3.0.1/mpich-3.0.1.tar.gz',
      py_file=_repo_py('mpich.py')
    ),
  'openmpi': PackageConfigMakeInstall(
      source='http://www.open-mpi.org/software/ompi/v1.6/downloads/openmpi-1.6.3.tar.bz2',
      imps={'mpi3': Imp(requires='cc', subsumes=['mpi1','mpi2'])},
      libs=['openmpi']
    ),
  'sys_cc': PackageSys('cc'),
  #'sys_fortran': PackageAptGet('gfortran', ['fortran']),
  'sys_fortran': PackageSys('fortran'),
  'zlib': PackageScript(
      source='http://zlib.net/zlib-1.2.7.tar.gz',
      py_file=_repo_py('zlib.py')
    ),
}

def implied(x, on):
  return {
    'mpi1-fortran': lambda: on('fortran') and on('mpi1'),
    'mpi2-fortran': lambda: on('fortran') and on('mpi2'),
    'mpi3-fortran': lambda: on('fortran') and on('mpi3')
  }.get(x, lambda: False)()
