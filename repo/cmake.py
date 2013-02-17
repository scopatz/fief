import os
from fief import repo
from fief import conf
from fief.repo import ifc, async, Cmd

interfaces = {'cmake': ifc(requires='cc')}

realize  = repo.c_realize

def build_a(ctx):
  pkg = ctx['pkg']
  assert any([ctx['interface', ifc] == pkg for ifc in interfaces])
  psrc = yield async.WaitFor(repo.fetch_nomemo_a(ctx, pkg))
  env = yield async.WaitFor(repo.realize_deps_a(ctx, interfaces))

  try:
    src, cleanup = yield async.WaitFor(repo.stage_nomemo_a(ctx, pkg))
  
    to = yield async.WaitFor(ctx.outfile_a('build', pkg))
    to = os.path.abspath(to)
    os.mkdir(to)

    cmdkws = {'cwd': src, 'tag': pkg, 'env': env}
    c = Cmd(ctx, **cmdkws)
    bootstrap = ('bash', 'bootstrap') if os.name == 'nt' else './bootstrap'
    c.lit(bootstrap, '--prefix=' + to)
    yield async.WaitFor(c.exec_a())

    c = Cmd(ctx, **cmdkws)
    c.lit(conf.make)
    yield async.WaitFor(c.exec_a())

    c = Cmd(ctx, **cmdkws)
    c.lit(conf.make_install)
    yield async.WaitFor(c.exec_a())
  finally:
    cleanup()

  delivs = {'root': to, 'libs': set('z'), 'pkg': pkg}
  yield async.Result(delivs)
