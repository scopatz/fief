import os

class Conf(object):
  """An unbound configuration class."""

  def __init__(me):
    rellocs = ['fiefconf.py', 'fiefconf', 
               os.path.join('.config', 'fiefconf.py'),
               os.path.join('.config', 'fiefconf'),]
    path = os.getcwd()
    drive, _ = os.path.split(path)
    root = drive + os.path.sep
    me.oven = 'oven'
    me.interfaces = set()
    me.preferences = {}
    me.options = lambda x,y: (None, False)
    while True:
      for relloc in rellocs:
        p = os.path.join(path, relloc)
        if os.path.isfile(p):
          config = {}
          execfile(p, config, config)
          if 'oven' in config:
            me.oven = config['oven']
          if 'interfaces' in config:
            me.interfaces = set(config['interfaces'])
          if 'preferences' in config:
            me.preferences = config['preferences']
          if 'options' in config:
            me.options = config['options']
      path = os.path.split(path)
      if path == root:
        break
