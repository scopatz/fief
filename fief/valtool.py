import array
import binascii
import hashlib
import struct

class Hasher(object):
  def _make():
    act = {}
    
    def f(h,s,x):
      code = x.func_code
      cells = x.func_closure
      h.update('func.%x.%x.%x.' % (len(code.co_code), len(code.co_consts or ()), len(cells or ())))
      h.update(code.co_code)
      s += code.co_consts or ()
      for cell in cells or ():
        s.append(cell.cell_contents)
    act[type(f)] = f
    
    def f(h,s,x):
      h.update('list.%x.' % len(x))
      s += x
    act[list] = f

    def f(h,s,x):
      h.update('tuple.%x.' % len(x))
      s += x
    act[tuple] = f
    
    def f(h,s,x):
      h.update('dict.%x.' % len(x))
      for k,v in sorted(x.iteritems()):
        s.append(k)
        s.append(v)
    act[dict] = f
    
    def f(h,s,x):
      h.update('set.%x.' % len(x))
      s += sorted(x)
    act[set] = f
    
    def f(h,s,x):
      h.update('str.%x.' % len(x))
      h.update(x)
    act[str] = f
    
    def f(h,s,x):
      h.update('bytearray.%x.' % len(x))
      h.update(x)
    act[bytearray] = f
    
    def f(h,s,x):
      h.update('array.%s.%x.' % (x.typecode, len(x)))
      h.update(x)
    act[array.array] = f
    
    def f(h,s,x):
      h.update('buffer.%x.' % len(x))
      h.update(x)
    act[buffer] = f
    
    def f(h,s,x):
      h.update('int.%x.' % x)
    act[int] = f
    
    def f(h,s,x):
      h.update('long.%x.' % x)
    act[long] = f
    
    def f(h,s,x):
      h.update('float.')
      h.update(struct.pack('<d', x))
    act[float] = f
    
    def f(h,s,x):
      h.update('true.' if x else 'false.')
    act[bool] = f
    
    def f(h,s,x):
      h.update('none.')
    act[type(None)] = f
    
    return act
  
  _act = _make()
  
  def __init__(me, that=None):
    if that is None:
      me._h, me._dig = hashlib.md5(), None
    else:
      me._h, me._dig = that._h.copy(), that._dig
  
  def raw(me, x):
    if x is not None:
      me._h.update(x)
      me._dig = None
    return me
    
  def eat(me, x):
    act = me._act
    h = me._h
    s = [x] # stack of unprocessed values
    open_stk = []
    open_num = array.array('i')
    open_set = {}
    xc = 0
    while len(s) > 0:
      x = s.pop()
      if id(x) in open_set:
        h.update('cycle.%x.' % open_set[x])
        n = 0
      else:
        t = type(x)
        a = act.get(t, None)
        if a is not None:
          n = len(s)
          a(h,s,x)
          n = len(s) - n
        else:
          h.update('?')
          n = 0
      if n == 0:
        while True:
          if len(open_num) == 0:
            assert len(s) == 0
            break
          n = open_num[-1] - 1
          if n > 0:
            open_num[-1] = n
            break
          else:
            open_num.pop()
            del open_set[id(open_stk.pop())]
      else:
        open_stk.append(x)
        open_num.append(n)
        open_set[id(x)] = xc
        xc += 1
    
    me._dig = None
    return me
    
  def digest(me):
    if me._dig is None:
      me._dig = me._h.digest()
    return me._dig

# opcodes:
#  0: <pointer>
#  1: im -> 0:None, 1:True, 2:False, 3-15: <wrap 1-13>
#  2: buffer
#  3: <backref>
#  4: im -> 0:float, 1-15: integers 0-14
#  5: int
#  6: <unused>
#  7: long
#  8: -long
#  9: list
#  10: tuple
#  11: dict
#  12: set
#  13: str
#  14: array
#  15: bytearray
def _make():
  c_act = {} # cata actions by type
  a_act = {} # ana actions by opcode
  
  def putopim(op, im, b):
    b.append(op + (im<<4))
  
  def putref(op, n, b):
    i = len(b)
    b.append(0)
    im = -1
    while True:
      b.append(n & 0xff)
      n = n >> 8
      im += 1
      if n == 0: break
    b[i] = op + (im<<4)
  
  def takeref(im, b):
    im += 1
    return (sum(ord(b[i])<<(8*i) for i in xrange(im)), buffer(b,im))
  
  c_act[type(None)] = lambda cata, x, b: putopim(1, 0, b)
  c_act[bool] = lambda cata, x, b: putopim(1, (1 if x else 2), b)
  
  def act(op, im, ana, b):
    assert im < 3
    return ((None,True,False)[im], b)
  a_act[1] = act
  
  def make():
    nb = struct.calcsize('<d')
    def c_act(cata, x, b):
      putopim(4, 0, b)
      b[len(b):len(b)] = struct.pack('<d', x)
    def a_act(op, im, ana, b):
      if im == 0:
        return (struct.unpack_from('<d', b)[0], buffer(b,nb))
      else:
        return (im-1, b)
    return c_act, a_act
  c_act[float], a_act[4] = make()
  
  ty_op = {buffer:2, list:9, tuple:10, dict:11, set:12, str:13, array.array:14, bytearray:15}
  op_ty = dict((op,ty) for ty,op in ty_op.iteritems())
  
  def act(cata, x, b):
    if 0 <= x and x < 15:
      putopim(4, x+1, b)
    else:
      x -= 15 if x > 0 else 0
      i = len(b)
      b.append(0)
      nb = 0
      while True:
        last = x & 0xff
        b.append(last)
        x = (x >> 8)
        nb += 1
        if x == 0 or x == -1:
          break
      if (x < 0) != ((last & 0x80) != 0):
        b.append(x & 0xff)
        nb += 1
      b[i] = 5 + ((nb-1)<<4)
  c_act[int] = act
  
  def act(op, im, ana, b):
    x = 0
    i = 0
    while i < im+1:
      last = ord(b[i])
      x += last<<(8*i)
      i += 1
    if (last & 0x80) != 0:
      x -= 1<<(8*i)
    else:
      x += 15
    return (int(x), buffer(b,im+1))
  a_act[5] = act
  
  def putlen(op, n, b):
    i = len(b)
    b.append(0)
    nb = 0
    while n != 0:
      b.append(n & 0xff)
      n = (n >> 8)
      nb += 1
    b[i] = op + (nb<<4)
  
  def takelen(op, im, b):
    return (sum(ord(b[i])<<(8*i) for i in xrange(im)), buffer(b,im))
  
  def act(cata, x, b):
    op = 7 + (1 if x < 0 else 0)
    x = bytearray(hex(abs(x)))
    n = len(x) - 2 - (1 if x[-1] == ord('L') else 0)
    if (n & 1) == 1:
      x[1] = ord('0')
      x = buffer(x, 1, n+1)
    else:
      x = buffer(x, 2, n)
    x = binascii.unhexlify(x)
    putlen(op, len(x), b)
    b.extend(x)
  c_act[long] = act
  
  def act(op, im, ana, b):
    n, b = takelen(op, im, b)
    x = binascii.hexlify(buffer(b,0,n))
    x = eval("0x" + x)
    x *= -1 if op==8 else 1
    return (x, buffer(b,n))
  a_act[7] = act
  a_act[8] = act
  
  def act(cata, x, b):
    putlen(11, len(x), b)
    for k,v in sorted(x.iteritems()):
      cata(k)
      cata(v)
  c_act[dict] = act
  
  def act(op, im, ana, b):
    n, b = takelen(op, im, b)
    d = {}
    for i in xrange(n):
      k, b = ana(b)
      v, b = ana(b)
      d[k] = v
    return (d, b)
  a_act[ty_op[dict]] = act
  
  def act(cata, x, b):
    putlen(ty_op[type(x)], len(x), b)
    b.extend(x)
  c_act[buffer] = act
  c_act[str] = act
  c_act[bytearray] = act
  
  def act(op, im, ana, b):
    n, b = takelen(op, im, b)
    return (op_ty[op](buffer(b,0,n)), buffer(b,n))
  a_act[ty_op[buffer]] = act
  a_act[ty_op[str]] = act
  a_act[ty_op[bytearray]] = act
  
  def act(cata, x, b):
    putlen(14, len(x), b)
    b.append(x.typecode)
    b.extend(buffer(x))
  c_act[array.array] = act
  
  def act(op, im, ana, b):
    n, b = takelen(op, im, b)
    a = array.array(b[0])
    nb = n*a.itemsize
    a.fromstring(buffer(b,1,nb))
    return (a, buffer(b,nb+1))
  a_act[ty_op[array.array]] = act
  
  def act(cata, x, b):
    putlen(ty_op[type(x)], len(x), b)
    for x1 in x:
      cata(x1)
  c_act[list] = act
  c_act[tuple] = act

  def act(op, im, ana, b):
    n, b = takelen(op, im, b)
    xs = []
    for i in xrange(n):
      x, b = ana(b)
      xs.append(x)
    return (op_ty[op](xs), b)
  a_act[ty_op[list]] = act
  a_act[ty_op[tuple]] = act
  
  def act(cata, x, b):
    putlen(ty_op[type(x)], len(x), b)
    for x1 in sorted(x):
      cata(x1)
  c_act[set] = act  
  
  def act(op, im, ana, b):
    n, b = takelen(op, im, b)
    xs = set()
    for i in xrange(n):
      x, b = ana(b)
      xs.add(x)
    return (xs, b)
  a_act[ty_op[set]] = act
  
  def make():
    ty_m = {}
    ty_m[long] = lambda x: True
    test = lambda x: len(x) > 2
    for ty in (str,buffer,bytearray):
      ty_m[ty] = test
    test = lambda x: len(x) > 0
    for ty in (array.array,list,tuple,dict,set):
      ty_m[ty] = test
    never = lambda x:False
    return lambda x: ty_m.get(type(x), never)(x)
  is_memoizeable = make()
  
  def make():
    ty_m = {}
    ty_m[long] = lambda x: True
    test = lambda x: len(x) > 2
    for ty in (str,buffer,bytearray):
      ty_m[ty] = test
    test = lambda x: len(x) > 0
    for ty in (array.array,list,tuple,dict,set):
      ty_m[ty] = test
    def was_memoized(op, im, x):
      return op == 0 or \
        (op == 1 and im > 2) or \
        (op != 3 and ty_m.get(type(x), lambda x:False)(x))
    return was_memoized
  was_memoized = make()
  
  def pack(x, control=None):
    if control is None:
      control = lambda x, cata, ptr, wrap: cata(x)
    
    b = bytearray()
    memo_ix = {} # md5 -> ix
    memo_id = [] # ix -> md5
    class box:
      h = hashlib.md5()
      hlen = 0
    
    def reset(st):
      off, mems = st
      del b[off:]
      for i in xrange(mems, len(memo_id)):
        del memo_ix[memo_id[i]]
      del memo_id[mems:]
    
    def putx(x, st):
      reset(st)
      box.h = hashlib.md5() if is_memoizeable(x) else None
      box.hlen = len(b)
      c_act[type(x)](cata, x, b)
      return len(b)-st[0] # len(b[st[0]:])
      #return buffer(b,st[0])
    
    def putptr(x, n, st):
      reset(st)
      box.h = hashlib.md5()
      box.hlen = len(b)
      putref(0, n, b)
      #return buffer(b,st[0])
    
    def putwrap(x, comps, st):
      assert 1 <= len(comps) and len(comps) <= 13
      reset(st)
      box.h = hashlib.md5()
      box.hlen = len(b)
      b.append(1 + ((2+len(comps))<<4))
      for c in comps:
        cata(c)
      #return buffer(b,st[0])
    
    def cata(x):
      h0 = box.h
      if h0 is not None:
        h0.update(buffer(b, box.hlen))
      box.hlen = len(b)
      
      box.h = None
      st = (len(b), len(memo_ix))
      control(x, lambda x:putx(x,st), lambda n:putptr(x,n,st), lambda *comps:putwrap(x,comps,st))
      
      h = box.h
      if h is not None:
        h.update(buffer(b, box.hlen))
        dig = h.digest()
        if dig in memo_ix:
          reset(st)
          putref(3, memo_ix[dig], b)
        else:
          memo_ix[dig] = len(memo_id)
          memo_id.append(dig)
        if h0 is not None:
          h0.update(dig)
      else:
        h0.update(buffer(b, box.hlen))
      box.h = h0
      box.hlen = len(b)
    
    cata(x)
    return b
  
  def unpack(b, getptr=None, unwrap=None):
    memo = []
    def ana(b):
      c = ord(b[0])
      op = c & 0xf
      im = c >> 4
      b = buffer(b,1)
      if op == 0:
        n, b = takeref(im, b)
        ans = getptr(n)
      elif op == 1 and im > 2:
        comps = []
        for i in xrange(im-2):
          x, b = ana(b)
          comps.append(x)
        ans = unwrap(*comps)
      elif op == 3:
        n, b = takeref(im, b)        
        ans = memo[n]
      else:
        ans, b = a_act[op](op, im, ana, b)
      
      if was_memoized(op, im, ans):
        memo.append(ans)
      return (ans, b)
    
    return ana(buffer(b))[0]
  
  return (pack, unpack)

pack, unpack = _make()
