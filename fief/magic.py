import async
import bake
import os
import tempfile

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
    
    lambda cleanup: shutil.rmtree(bld)
    yield async.Result((bld2, cleanup))
  else:
    assert False # invalid source tuple

def builder_nomemo_a(ctx, pkg):
  """Returns an asynchronous build bake function"""
  repo = ctx['repo']
  script = os.path.join(repo, pkg + '.py')
  glbs, locs = globals(), {}
  execfile(script, glbs, locs)
  return locs['build_a']
