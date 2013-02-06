from fief import repo
from fief import conf
from fief.repo import ifc, async, Cmd

interfaces = {'zlib': ifc()}

def realize(delivs):
  env = repo.c_realize(delivs)
  del env['PATH']
  return env

build_a = repo.configure_make_make_install(interfaces, libs='z')
