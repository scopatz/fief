import os
from glob import glob

from fief import conf
from fief import repo
from fief.repo import ifc, async, bake

interfaces = {'sympy': ifc(), 
              'sympy-cython': ifc(subsumes='sympy', requires='cython')}

def realize(delivs):
    root = delivs['root']
    env = {'PATH': [os.path.join(root, 'bin')],
           'PYTHONPATH': glob(os.path.join(root, 'lib', 'python[0-9].[0-9]', 'site-packages')),
           }
    return env

def build_a(ctx):
    pkg = ctx['pkg']
    cythonize = (ctx['interface', 'sympy-cython'] == pkg)
    psrc = yield async.WaitFor(repo.fetch_nomemo_a(ctx, pkg))
    env = yield async.WaitFor(repo.realize_deps_a(ctx, interfaces))

    try:
        src, cleanup = yield async.WaitFor(repo.stage_nomemo_a(ctx, pkg))
        to = yield async.WaitFor(ctx.outfile_a('build', pkg))
        to = os.path.abspath(to)
        os.mkdir(to)

        c = bake.Cmd(ctx)
        c.cwd = src
        c.tag = pkg
        c.env = env
        c.lit('python', 'setup.py', 'install', '--prefix=' + to)
        yield async.WaitFor(c.exec_a())

        if cythonize:
            c = bake.Cmd(ctx)
            c.cwd = src
            c.tag = pkg
            c.env = env
            c.lit('python', 'build.py', 'install', '--prefix=' + to)
            yield async.WaitFor(c.exec_a())
    finally:
        cleanup()
  
    delivs = {'root': to, 'pkg': pkg}
    yield async.Result(delivs)
