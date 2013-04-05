import os
import envdelta

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
