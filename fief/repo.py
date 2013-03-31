import os
import sys
import shutil
import tempfile
import itertools
from glob import glob

import conf
import bake
import async
import fetch


def fetch_nomemo_a(ctx, pkg):
  """Returns a tuple (path, cleanup)"""
  got = yield async.Sync(fetch.retrieve_source_a(pkg))
  if not got:
    raise RuntimeError("failed to retrieve {0}".format(pkg))
  packages[pkg].source = got
  yield async.Result(got)

def stage_nomemo_a(ctx, pkg):
  """Returns a tuple (path, cleanup)"""
  repo = 'repo'
  p = packages[pkg]
  ball = p.source
  if ball.endswith('.tgz'):
    ndots = 1
  elif ball.endswith('.tar.gz') or ball.endswith('.tar.bz2'):
    ndots = 2
  name = os.path.split(ball)[-1].rsplit('.', ndots)[0]
  bld = tempfile.mkdtemp()
  if os.name == 'nt':
    ball = ball.split(':', 1)[-1]

  c = bake.Cmd(ctx)
  c.cwd = bld
  c.tag = pkg
  if ball.endswith('.tar.gz') or ball.endswith('.tgz'):
    c.lit('tar', 'xzf').inf(ball)
  elif ball.endswith('.tar.bz2'):
    c.lit('tar', 'xjf').inf(ball)
  yield async.Sync(c.exec_a())

  bld2 = os.path.join(bld, name)
  if not os.path.exists(bld2):
    unzipped = os.listdir(bld)
    if 1 == len(unzipped):
      bld2 = os.path.join(bld, unzipped[0]) 

  cleanup = lambda: shutil.rmtree(bld)
  yield async.Result((bld2, cleanup))

def merge_lib_deps(*depss):
  seen = set()
  seen_add = seen.add
  seq = reverse(itertools.chain(*depss))
  return reverse(tuple(x for x in seq if x not in seen and not seen_add(x)))

#ensure_frozenset = lambda x: frozenset(x if hasattr(x, '__iter__') else (x,))
ensure_frozenset = lambda x: set(x if hasattr(x, '__iter__') else (x,))

class ifc(object):

  def __init__(self, subsumes=(), requires=()):
    self.subsumes = ensure_frozenset(subsumes)
    self.requires = ensure_frozenset(requires)

  def __repr__(self):
    s = "ifc(subsumes={0!r}, requires={1!r})"
    return s.format(self.subsumes, self.requires)
  
  @staticmethod
  def pack(me):
    return (me.subsumes, me.requires)

  @staticmethod
  def unpack(x):
    return ifc(x[0], x[1])

def requirements(act):
  """Given an activated interface act, compute all requirements."""
  reqs = set()
  for ifc, pkg in ifcpkg:
    if ifc != act:
      continue
    ifx = packages[pkg].interfaces[ifc]
    reqs |= ifx.requires
    for subs in ifx.subsumes:
      reqs |= requirements(subs)
  return reqs

def active_packages(activated):
  """Computes unique package names that implement the activated interfaces."""
  ifc2pkg = {}
  for act in activated:
    pkgs = [pkg for ifc, pkg in ifcpkg if ifc == act]
    pkgslen = len(pkgs)
    if 1 == pkgslen:
      ifc2pkg[act] = pkgs[0]
    elif 1 < pkgslen:
      pref = conf.preferences.get(act, None)
      if pref in pkgs:
        ifc2pkg[act] = pref
      else:
        msg = ("\n\nmultiple packages implement the {0} interface!\n"
               "Please select a preference from the following:\n  {1}")
        raise LookupError(msg.format(act, "\n  ".join(sorted(pkgs))))
    elif 0 == pkgs:
      msg = "no package implements the {0} interface!"
      raise LookupError(msg.format(act))
  return ifc2pkg

def upgrade_to_avoid_a(oven, ifc2pkg):
  """The name says it all!"""
  built = {}
  pkgs = set(ifc2pkg.values())
  for pkg in pkgs:
    built[pkg] = []
    def argtest(x, nextmatch):
      if isinstance(x, tuple) and x[0] == 'interface':
        if ifc2pkg[x[1]] is not None:
          return bake.TestEqual(x[1], nextmatch)
        else:
          return nextmatch
      elif x == 'pkg':
        return bake.TestEqual(pkg, nextmatch)
      else:
        assert False

    def collector(args, result):
      d = {}
      for arg in args:
        if isinstance(arg, tuple) and arg[0] == 'interface':
          d[arg[1]] = args[arg]
      built[pkg].append(d)

    yield async.Sync(oven.search_a(packages[pkg].builder, 
                                      bake.MatchArgs(argtest, collector)))

  i2p = {}
  for pkg in pkgs:
    for d in built[pkg]:
      for ifc in d:
        if ifc in i2p:
          if d[ifc] != i2p[ifc]:
            i2p[ifc] = None
        else:
          i2p[ifc] = d[ifc]
  ifc2pkg.update(i2p)
  for pkg in pkgs:
    for d in built[pkg]:
      for ifc in d:
        ifc2pkg[ifc] == d[ifc]


def dep2pkg(ctx, interfaces):
  """Computes an ifc2pkg mapping for dependencies."""
  deps = set()
  for ifc in interfaces:
    pkg = ctx['interface', ifc]
    if pkg is None:
      continue
    deps |= requirements(ifc)
  ifc2pkg = dict((dep, ctx['interface', dep]) for dep in deps)
  return ifc2pkg


def realize_deps_a(ctx, interfaces):
  """Given interfaces data structure, return the deliverables from all 
  activated requirements, which of course, enforces that they have been
  realized."""
  ifc2pkg = dep2pkg(ctx, interfaces)
  deliverables = {}
  for ifc, pkg in ifc2pkg.iteritems():
    bld_a = packages[pkg].builder
    yield async.Task(ifc, ctx(bld_a, {'pkg': pkg}))
  while True:
    got = yield async.WaitAny
    if got is None:
      break
    ifc, delivs = got
    deliverables[ifc2pkg[ifc]] = delivs
  env = envrealize(deliverables)
  yield async.Result(env)


def _pack_ifx(ifx):
  return dict((nm,ifc.pack(x)) for nm,x in ifx.iteritems())

def _unpack_ifx(s):
  return dict((nm,ifc.unpack(x)) for nm,x in s.iteritems())

class Package(object):
  def __init__(me, name, tup):
    me.name = name
    me.source = tup[0]
    me.builder_py = tup[1]
    me._realizer = None
    me._builder = None
  
  def _load(me):
    ns = {}
    execfile(os.path.join('repo', me.builder_py), ns, ns)
    me._builder = ns['build_a']
    me._realizer = ns.get('realize', lambda _:{})
  
  @property
  def builder(me):
    if me._builder is None: me._load()
    return me._builder
  
  @property
  def realizer(me):
    if me._realizer is None: me._load()
    return me._realizer

packages = {}
ifcpkg = set()

def init_a(oven, repo_pkgs):
  def packed_ifx_a(ctx):
    builder_py = ctx['builder_py']
    ns = {}
    execfile(os.path.join('repo', builder_py), ns, ns)
    yield async.Result(_pack_ifx(ns['interfaces']))
  
  for name, tup in repo_pkgs.iteritems():
    pkg = Package(name, tup)
    packages[name] = pkg
    ifx = yield async.Sync(oven.memo_a(packed_ifx_a, {'builder_py':pkg.builder_py}))
    ifx = _unpack_ifx(ifx)
    pkg.interfaces = ifx
    for ifc in ifx:
      ifcpkg.add((ifc, name))

class Cmd(bake.Cmd):
  """Proxy class for bake Cmd, to enable globally setting showout & showerr."""

  showout = False
  showerr = True
  
  def __init__(me, *args, **kwargs):
    super(Cmd, me).__init__(*args, **kwargs)
    me.showout = Cmd.showout
    me.showerr = Cmd.showerr

ensure_envvalue = lambda v: set(v) if hasattr(v, '__iter__') else str(v)

def envrealize(deliverables):
  """Returns an environment realized from a list of delivs tuples."""
  fief_envvars = {}
  for pkg, delivs in deliverables.iteritems():
    realizer = packages[pkg].realizer
    pkgenv = realizer(delivs)
    for k, v in pkgenv.iteritems():
      if k not in fief_envvars:
        fief_envvars[k] = ensure_envvalue(v)
      elif hasattr(v, '__iter__'):
        if not hasattr(fief_envvars[k], '__iter__'):
          msg = ("environment variables must both be containers or both be "
                 "scalars. For key {0!r} got {1!r} and {2!r}.")
          raise ValueError(k, sorted(v), fief_envvars[k])
        fief_envvars[k] |= ensure_envvalue(v)
      else:
        if v != k[v]:
          msg = ("scalars must have the same value. "
                 "For key {0!r} got {1!r} and {2!r}.")
          raise ValueError(k, v, fief_envvars[k])
  env = {}
  fief_envvars_orig = eval(os.getenv('FIEF_ENVVARS', '{}').strip('"'))
  for key, val in fief_envvars.items():
    if hasattr(val, '__iter__'):
      # sets lists (like PATH)
      fevorigval = fief_envvars_orig.get(key, ())
      origval = os.getenv(key, None)
      origval = [] if origval is None else origval.split(os.pathsep)
      origset = set(origval)
      newval = [v for v in val if v not in origset]
      newval += [v for v in origval if (v in fevorigval and v in val) or 
                                       (v not in fevorigval)]
      env[key] = os.pathsep.join(newval)
    else:
      # sets scalars
      env[key] = val
  env['FIEF_ENVVARS'] = repr(fief_envvars)
  return env

#
# build script convience functions
#

def c_realize(delivs):
  """Creates a basic environment with PATH, LD_LIBRARY_PATH, and C_INCLUDE_PATH."""
  root = delivs['root']
  env = {'PATH': [os.path.join(root, 'bin')],
         'LD_LIBRARY_PATH': [os.path.join(root, 'lib')],
         'C_INCLUDE_PATH': [os.path.join(root, 'include')]}
  return env

def configure_make_make_install(interfaces, libs=(), configure_args=(), 
                                make_args=(), make_install_args=()):
  """Constructs an asynchronous builder for a standard configure, 
  make, make install package.
  """
  def build_a(ctx):
    pkg = ctx['pkg']
    assert any([ctx['interface', ifc] == pkg for ifc in interfaces])
    psrc = yield async.Sync(fetch_nomemo_a(ctx, pkg))
    env = yield async.Sync(realize_deps_a(ctx, interfaces))

    try:
      src, cleanup = yield async.Sync(stage_nomemo_a(ctx, pkg))
  
      to = yield async.Sync(ctx.outfile_a('build', pkg))
      to = os.path.abspath(to)
      os.mkdir(to)
  
      c = Cmd(ctx)
      c.cwd = src
      c.tag = pkg
      c.env = env
      c.lit('./configure', '--prefix=' + to, configure_args)
      yield async.Sync(c.exec_a())
  
      c = Cmd(ctx)
      c.cwd = src
      c.tag = pkg
      c.env = env
      c.lit(conf.make, make_args)
      yield async.Sync(c.exec_a())

      c = Cmd(ctx)
      c.cwd = src
      c.tag = pkg
      c.env = env
      c.lit(conf.make_install, make_install_args)
      yield async.Sync(c.exec_a())
    finally:
      cleanup()

    delivs = {'root': to, 'libs': ensure_frozenset(libs), 'pkg': pkg}
    yield async.Result(delivs)

  return build_a


def py_realize(delivs):
  """Creates a basic environment with PATH and PYTHONPATH."""
  root = delivs['root']
  env = {}
  if os.path.exists(os.path.join(root, 'bin')):
    env['PATH'] = [os.path.join(root, 'bin')]
  elif os.path.exists(os.path.join(root, 'Scripts')):
    env['PATH'] = [os.path.join(root, 'Scripts')]
  pypath = glob(os.path.join(root, '*',  'site-packages')) + \
           glob(os.path.join(root, '*', '*',  'site-packages'))
  if 0 < len(pypath):
    env['PYTHONPATH'] = set(pypath)
  return env


def python_setup_install(interfaces):
  """Constructs an asynchronous builder for a standard "python setup.py install"
  package.  This only requires an interface.
  """
  def build_a(ctx):
    pkg = ctx['pkg']
    psrc = yield async.Sync(fetch_nomemo_a(ctx, pkg))
    env = yield async.Sync(realize_deps_a(ctx, interfaces))

    try:
      src, cleanup = yield async.Sync(stage_nomemo_a(ctx, pkg))
      to = yield async.Sync(ctx.outfile_a('build', pkg))
      to = os.path.abspath(to)
      os.mkdir(to)

      c = bake.Cmd(ctx)
      c.cwd = src
      c.tag = pkg
      c.env = env
      c.lit('python', 'setup.py', 'install', '--prefix=' + to)
      yield async.Sync(c.exec_a())
    finally:
      cleanup()

    delivs = {'root': to, 'pkg': pkg}
    yield async.Result(delivs)

  return build_a
