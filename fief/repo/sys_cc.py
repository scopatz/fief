from fief import async
from fief.repository import Imp

implements = {
  'cc': Imp()
}

def build_a(ctx):
  yield async.Result(None)
