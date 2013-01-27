import async
import bake
import os
import shutil
import tempfile
import itertools

def fetch_nomemo_a(ctx, pkg):
  """Returns a tuple (path, cleanup)"""
  src = ctx['source',pkg]
  repo = ctx['repo']
  
  if src[0] == 'tarball':
    ball = os.path.abspath(os.path.join(repo, src[1]))
    name = os.path.split(ball)[-1].rsplit('.', 2)[0]
    
    bld = tempfile.mkdtemp()
    bld2 = os.path.join(bld, name)
    
    c = bake.Cmd(ctx)
    c.cwd = bld
    c.lit('tar', 'xzf').inf(ball)
    yield async.WaitFor(c.exec_a())
    
    cleanup = lambda: shutil.rmtree(bld)
    yield async.Result((bld2, cleanup))
  else:
    assert False # invalid source tuple

def load_nomemo_a(ctx, pkg):
  """Returns an asynchronous build bake function"""
  repo = ctx['repo']
  script = os.path.join(repo, pkg + '.py')
  ns = {}
  execfile(script, ns, ns)
  yield async.Result((ns['depends_a'], ns['build_a']))

def merge_lib_deps(*depss):
  seen = set()
  seen_add = seen.add
  seq = itertools.chain(*depss)
  return tuple(x for x in seq if x not in seen and not seen_add(x))
