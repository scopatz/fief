from fief import async
from fief.repository import ifc

interfaces = {'glibmm': ifc()}

def build_a(ctx, pkg, path, opts):
  yield async.Result(None)
