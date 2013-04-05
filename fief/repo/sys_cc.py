from fief import async
from fief.repository import ifc

interfaces = {'cc': ifc()}

def build_a(ctx, pkg, path, opts):
  yield async.Result(None)
