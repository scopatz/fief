import async
import bake
import os
import shutil
import tempfile
import itertools

def fetch_nomemo_a(ctx, pkg):
  """Returns a tuple (path, cleanup)"""
  repo = 'repo'
  
  ball = os.path.abspath(os.path.join(repo, tarballs[pkg]))
  name = os.path.split(ball)[-1].rsplit('.', 2)[0]
  bld = tempfile.mkdtemp()
    
  c = bake.Cmd(ctx)
  c.cwd = bld
  if ball.endswith('.tar.gz'):
    c.lit('tar', 'xzf').inf(ball)
  elif ball.endswith('.tar.bz2'):
    c.lit('tar', 'xjf').inf(ball)
  yield async.WaitFor(c.exec_a())

  bld2 = os.path.join(bld, name)
  if not os.path.exists(bld2):
    unzipped = os.listdir(bld)
    if 1 == len(unzipped):
      bld2 = os.path.join(bld, unzipped[0]) 

  cleanup = lambda: shutil.rmtree(bld)
  yield async.Result((bld2, cleanup))

def load_nomemo(ifc):
  return builders[ifc2pkg[ifc]]

def merge_lib_deps(*depss):
  seen = set()
  seen_add = seen.add
  seq = reverse(itertools.chain(*depss))
  return reverse(tuple(x for x in seq if x not in seen and not seen_add(x)))

ensure_frozenset = lambda x: frozenset(x if hasattr(x, '__iter__') else (x,))

class ifc(object):

  def __init__(self, subsumes=(), requires=(), libs=()):
    self.subsumes = ensure_frozenset(subsumes)
    self.requires = ensure_frozenset(requires)
    self.libs = ensure_frozenset(libs)

def requirements(reqs,on_ifcs,ifcs):
  """given interfaces data structure, recursively adds interface 
  requirements."""  
  for key in on_ifcs:
    reqs |= ifcs[key].requires
    requirements(reqs,ifcs[key].subsumes,ifcs)

def built_dirs_a(ctx, ifcs):
  """Given interfaces data structure, return built hash directories of all 
  active requirements."""
  on_ifcs = [key for key in ifcs if ctx['interface',key]]
  reqs = set()
  requirements(reqs,on_ifcs,ifcs)
  built_dirs = {}
  for ifc in reqs:
    bld = load_nomemo(ifc)
    yield async.Task(ifc, ctx(bld, {'pkg': ifc2pkg[ifc]}))
  while True:
    got = yield async.WaitAny
    if got is None:
      break
    built_dirs[got[0]] = got[1][0]
  yield async.Result(built_dirs)

builders = {}
tarballs = {}
interfaces = {}
ifc2pkg = {}

def init(config):
  for pkg, (tarball, f) in config.iteritems():
    ns = {}
    execfile(os.path.join('repo', f), ns, ns)
    builders[pkg] = ns['build_a']
    tarballs[pkg] = tarball
    interfaces[pkg] = ns['interfaces']
    for ifc in interfaces[pkg]:
      assert ifc not in ifc2pkg
      ifc2pkg[ifc] = pkg

