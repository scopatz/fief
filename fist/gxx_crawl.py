import async
import bake
import os
import shlex
import sys


def includes_a(ctx):
  """returns a list of paths which are the files this source file is dependent on (list includes this file)
  args: "path":string, "g++":[string]
  """
  h_lib = ctx['h_lib']
  path = ctx['path']
  ext = os.path.splitext(path)[1]
  compiler = ctx[('compiler',ext)]
  if compiler and os.path.exists(ctx.input(path)):
    cmd = bake.Cmd(ctx)
    cmd.lit(compiler,"-M","-MT","x").inf(path)
    
    yield async.WaitFor(cmd.exec_a())
    rule = cmd.stdout
    rule = rule[rule.index(":")+1:]
    deps = map(os.path.normpath, shlex.split(rule.replace("\\\n","")))
    for dep in deps:
      ctx.input(dep)
    yield async.Result(deps[1:])
  else:
    yield async.Result(())

def compile_a(ctx):
  """returns a path to the compiled object file, or None if source file does not exist
  args: "path":string, "g++":[string]
  """
  path = ctx['path']
  ext = os.path.splitext(path)[1]
  if os.path.exists(ctx.input(path)):
    compiler = ctx[('compiler', ext)]
    if compiler:
      deps = yield async.WaitFor(ctx(includes_a, {'path':path}))
      for dep in deps:
        ctx.input(dep)
      compile_flags = ctx[('compile_flags', ext)]
      # execute shell command like: $(g++) $(CXXFLAGS)-c $(path) -o $o
      cmd = bake.Cmd(ctx)
      cmd.lit(compiler, compile_flags, "-c").inf(path).lit("-o").outf(path)
      yield async.WaitFor(cmd.exec_a())
      yield async.Result(cmd.outs[path])
    else:
      yield async.Result(path)
  else:
    yield async.Result(None)

def crawl_a(ctx):
  """given a source a path 'main' to some source file, will compile that and all other source files found by matching
  included '.hxx' files with corresponding '.cxx' files.  then all the objects get linked and the exe path is returned
  args: "paths":[string]
  """
  h_lib = ctx['h_lib'] # dict of header file -> library nickname
  lib_libs = ctx['lib_libs'] # dict of lib nick -> [required lib nicks]
  linker = ctx['linker']
  libpaths = ctx['libpaths']
  
  more = [ctx['main']]
  objs = {} # maps source file paths to compiled object files, or None if source does not exist
  libs = set()
  while True:
    for p in more:
      if p not in objs:
        objs[p] = None
        if os.path.exists(p):
          yield async.Task(('inc',p), ctx(includes_a, {'path':p}))
          yield async.Task(('obj',p), ctx(compile_a, {'path':p}))
    del more[:]
    
    try:
      got = yield async.WaitAny
      if got is None: break
    except async.TaskError, e:
      e.reraise()
    
    (tag, p), res = got
    if tag == 'obj':
      objs[p] = res
    else:
      assert tag == 'inc'
      for inc in res:
        base, ext = os.path.splitext(inc)
        if inc in h_lib:
          libs.add(h_lib[inc])
        if ext in ('.h','.hpp','.hxx'):
          for ext in ('.c','.cpp','.cxx','.C'):
            more.append(base + ext)
  
  def topsort(xs, deps):
    # transitive close xs
    A = set(xs)
    B = set()
    while len(A) > 0:
      for a in A:
        A1 = deps.get(a,())
        for a1 in A1:
          if a1 not in xs:
            xs.add(a1)
            B.add(a1)
      A = B
      B = set()
    # sort
    m = dict([(x,set(deps.get(x,()))) for x in xs])
    l = []
    while len(m) > 0:
      for x in [x for x in m if len(m[x]) == 0]:
        del m[x]
        l.append(x)
        for y in m:
          m[y].discard(x)
    l.reverse()
    return l
  
  libs = topsort(libs, lib_libs)
  
  # link it
  cmd = bake.Cmd(ctx)
  cmd.\
    lit(linker).\
    lit("-o").outf("exe").\
    infs(o for o in objs.values() if o).\
    lit("-L%s" % lp for lp in libpaths).\
    lit("-l%s" % lib for lib in libs)
  yield async.WaitFor(cmd.exec_a())
  yield async.Result(cmd.outs["exe"])
