from fief import async
from fief.repository import ifc

interfaces = {'fortran': ifc()}

def build_a(ctx):
    yield async.Result({})
