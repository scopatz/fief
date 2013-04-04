from array import array
import binascii
from collections import deque
import hashlib
import struct
import sys

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
    act[array] = f
    
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
    
    def act_unk(h,s,x):
      ty = type(x)
      if ty is getattr(sys.modules[ty.__module__], ty.__name__, None):
        h.update('unk.%s.%s.' % (ty.__module__, ty.__name__))
        if hasattr(x, '__getstate__'):
          h.update('st.')
          s.append(x.__getstate__())
        else:
          fs = getattr(ty,'__slots__',None) or x.__dict__.iterkeys()
          fs = list(f for f in sorted(fs) if hasattr(x, f))
          h.update('fs.%x.' % len(fs))
          for f in fs:
            s.append(f)
            s.append(getattr(x, f))
      else:
        h.update('?')
    
    return lambda ty: act.get(ty, act_unk)
  
  _act = (_make(),) # hide it from class
  
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
    act = me._act[0]
    h = me._h
    s = [x] # stack of unprocessed values
    open_stk = []
    open_num = array('i')
    open_set = {}
    xc = 0
    while len(s) > 0:
      x = s.pop()
      if id(x) in open_set:
        h.update('cycle.%x.' % open_set[x])
        n = 0
      else:
        t = type(x)
        a = act(t)
        n = len(s)
        a(h,s,x)
        n = len(s) - n
      
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

def _make():
  cata_tbl = {} # maps types to catamorphism actions
  ana_tbl = [] # maps leading bytes (opcodes) to anamorphism actions
  # during _make, len(ana_tbl) represents the next free opcode
  
  identity = lambda x: x
  
  def putnat(n, b):
    while True:
      c = n & 0x7f
      n >>= 7
      c = c | (0x80 if n != 0 else 0)
      b.append(c)
      if n == 0: break
  
  def takenat(b, p):
    n = 0
    i = 0
    while True:
      c = ord(b[p+i])
      n += (c & 0x7f) << (7*i)
      i += 1
      if (c & 0x80) == 0: break
    return n, p+i
  
  # None,True,False
  def make():
    op_n = len(ana_tbl)
    op_t = op_n+1
    op_f = op_n+2
    mc = {None:op_n, True:op_t, False:op_f}
    def cact(x, b, cata):
      b.append(mc[x])
    def aact(op, b, p, ana):
      return (None, True, False)[op-op_n], p
    cata_tbl[type(None)] = cact
    cata_tbl[bool] = cact
    ana_tbl.extend([aact]*3)
  make()
  
  # int,long: distinction not preserved, 1L will be treated as int(1)
  def make():
    op0 = len(ana_tbl)
    lb, ub = -16, 48
    op_pos = op0 + ub-lb
    op_neg = op0 + ub-lb + 1
    def cact(x, b, cata):
      if x < lb:
        b.append(op_neg)
        putnat(lb-1 - x, b)
      elif ub <= x:
        b.append(op_pos)
        putnat(x - ub, b)
      else:
        b.append(op0 + x - lb)
    def aact(op, b, p, ana):
      if op < op_pos:
        return op - op0 + lb, p
      else:
        n, p = takenat(b, p)
        n = ub + n if op == op_pos else lb-1 - n
        return n, p
    cata_tbl[int] = cact
    cata_tbl[long] = cact
    ana_tbl.extend([aact]*66)
  make()
  
  # string,bytearray,buffer
  def make(ty,small):
    op0 = len(ana_tbl)
    def cact(x, b, cata):
      if len(x) < small:
        b.append(op0 + len(x))
      else:
        b.append(op0 + small)
        putnat(len(x) - small, b)
      b.extend(x)
    def aact(op, b, p, ana):
      op -= op0
      if op < small:
        n = op
      else:
        n, p = takenat(b, p)
        n += small
      return ty(buffer(b, p, n)), p + n
    cata_tbl[ty] = cact
    ana_tbl.extend([aact]*(small + 1))
  make(str, 16)
  make(bytearray, 0)
  make(buffer, 0)
  
  # list,tuple,dict,set,frozenset,deque
  def make(ty, items, small):
    op0 = len(ana_tbl)
    def cact(x, b, cata):
      if len(x) < small:
        b.append(op0 + len(x))
      else:
        b.append(op0 + small)
        putnat(len(x) - small, b)
      for x1 in items(x):
        cata(x1)
    def aact(op, b, p, ana):
      op -= op0
      if op < small:
        n = op
      else:
        n, p = takenat(b, p)
        n += small
      xs = []
      for i in xrange(n):
        x, p = ana(b, p)
        xs.append(x)
      return (xs if ty is list else ty(xs)), p
    cata_tbl[ty] = cact
    ana_tbl.extend([aact]*(small + 1))
  make(tuple, identity, 8)
  make(list, identity, 4)
  make(dict, lambda xs: sorted(xs.iteritems()), 4)
  make(set, sorted, 4)
  make(frozenset, sorted, 4)
  make(deque, identity, 0)
  
  # array
  def make():
    op = len(ana_tbl)
    def cact(x, b, cata):
      b.append(op)
      b.append(x.typecode)
      putnat(len(x), b)
      for x1 in x:
        cata(x1)
    def aact(op, b, p, ana):
      tc = b[p]
      n, p = takenat(b, p+1)
      a = array(tc)
      for i in xrange(n):
        x1, p = ana(b, p)
        a.append(x1)
      return a, p
    cata_tbl[array] = cact
    ana_tbl.append(aact)
  make()
  
  # unknown object
  def make():
    op_st = len(ana_tbl)
    op_fs = len(ana_tbl) + 1
    def cact(x, b, cata):
      ty = type(x)
      mod = ty.__module__
      cls = ty.__name__
      assert ty is getattr(sys.modules[mod], cls, None)
      if hasattr(x, '__getstate__'):
        b.append(op_st)
        cata((mod,cls))
        cata(x.__getstate__())
      else:
        b.append(op_fs)
        fs = getattr(ty, '__slots__', None) or x.__dict__.iterkeys()
        fs = tuple(f for f in sorted(fs) if hasattr(x, f))
        cata((mod,cls) + fs)
        for f in fs:
          cata(getattr(x, f))
    def aact(op, b, p, ana):
      if op == op_st:
        (mod, cls), p = ana(b, p)
        x = getattr(sys.modules[mod], cls)()
        st, p = ana(b, p)
        x.__setstate__(st)
      else:
        tup, p = ana(b, p)
        mod, cls, flds = tup[0], tup[1], tup[2:]
        x = getattr(sys.modules[mod], cls)()
        for f in flds:
          val, p = ana(b, p)
          setattr(x, f, val)
      return x, p
    # cata_tbl has no entries because type is unknown
    ana_tbl.extend([aact]*2)
    return cact
  unk_cact = make()
  
  ref_aact = object()
  ref_op0 = len(ana_tbl)
  ana_tbl.extend(ref_aact for i in xrange(65))
  
  def putref(n, b):
    nbyt = 0
    while nbyt < 4 and n >= (1<<(5-nbyt + 8*nbyt)):
      nbyt += 1
    byt0 = ((1<<nbyt)-1)<<(6-nbyt)
    byt0 += n & (1<<(5-nbyt))-1
    n >>= 5-nbyt
    b.append(ref_op0 + byt0)
    while nbyt > 0:
      b.append(n & 0xff)
      n >>= 8
      nbyt -= 1
  
  def takeref(op, b, p):
    byt0 = op - ref_op0
    nbyt = 0
    while byt0 & (1<<(5-nbyt)) != 0:
      nbyt += 1
    sh = 5-nbyt
    n = byt0 & (1<<sh)-1
    i = 0
    while i < nbyt:
      n += b[p+i]<<sh
      sh += 8
      i += 1
    return n, p+i
  
  wrap_aact = object()
  wrap_op0 = len(ana_tbl)
  ana_tbl.extend([wrap_aact]*4)
  
  ptr_aact = object()
  ptr_op = len(ana_tbl)
  ana_tbl.append(ptr_aact)
  
  assert len(ana_tbl) < 256
  #print 'OPCODES:', len(ana_tbl)
  
  def make():
    never = lambda x: False
    always = lambda x: True

    ty_m = {}
    ty_m[type(None)] = never
    ty_m[bool] = never
    ty_m[int] = never
    ty_m[long] = always
    
    test = lambda x: len(x) > 2
    for ty in (str,buffer,bytearray):
      ty_m[ty] = test
    
    test = lambda x: len(x) > 0
    for ty in (array,list,tuple,dict,set,frozenset):
      ty_m[ty] = test
    
    def is_memoed(x):
      return ty_m.get(type(x), always)(x)
    
    def was_memoed(op, x):
      if ref_op0 <= op and op < ref_op0+64: return False
      if op == ptr_op: return True
      return ty_m.get(type(x), always)(x)
    
    return is_memoed, was_memoed
  is_memoed, was_memoed = make()
  
  def pack(x, control=None):
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

    def putx(x, cata, st):
      reset(st)
      box.h = hashlib.md5() if is_memoed(x) else None
      box.hlen = len(b)
      cata_tbl.get(type(x), unk_cact)(x, b, cata)
      return len(b)-st[0]
    
    def putptr(n, st):
      reset(st)
      box.h = hashlib.md5()
      box.hlen = len(b)
      b.append(ptr_op)
      putnat(n, b)
    
    def putwrap(ctrl, comps, st):
      assert 1 <= len(comps) and len(comps) <= 4
      reset(st)
      box.h = hashlib.md5()
      box.hlen = len(b)
      b.append(wrap_op0 + len(comps)-1)
      for c in comps:
        cata(c, ctrl)
    
    def deft_control(x, cata, ptr, wrap):
      return cata(x, deft_control)
    
    def cata(x, control=None):
      if control is None:
        control = deft_control
      
      h0 = box.h
      if h0 is not None:
        h0.update(buffer(b, box.hlen))
      box.hlen = len(b)
      
      box.h = None
      st = (len(b), len(memo_ix))
      
      control(
        x,
        lambda x,ctrl=None: putx(x, lambda x: cata(x,ctrl), st),
        lambda n: putptr(n, st),
        lambda ctrl,*comps: putwrap(ctrl, comps, st)
      )
      
      h = box.h
      if h is not None:
        h.update(buffer(b, box.hlen))
        dig = h.digest()
        if dig in memo_ix:
          reset(st)
          putref(memo_ix[dig], b)
        else:
          memo_ix[dig] = len(memo_id)
          memo_id.append(dig)
        if h0 is not None:
          h0.update(dig)
      else:
        h0.update(buffer(b, box.hlen))
      box.h = h0
      box.hlen = len(b)
    
    cata(x, control)
    return b
  
  def unpack(b, getptr=None, unwrap=None):
    memo = []
    def ana(b, p):
      op = ord(b[p])
      p += 1
      act = ana_tbl[op]
      if act is ptr_aact:
        n, p = takenat(b, p)
        ans = getptr(n)
      elif act is wrap_aact:
        comps = []
        for i in xrange(op-wrap_op0+1):
          x, p = ana(b, p)
          comps.append(x)
        ans = unwrap(*comps)
      elif act is ref_aact:
        n, p = takeref(op, b, p)
        ans = memo[n]
      else:
        ans, p = act(op, b, p, ana)
      
      if was_memoed(op, ans):
        memo.append(ans)
      return ans, p
    
    return ana(buffer(b), 0)[0]
  
  return pack, unpack

pack, unpack = _make()

if False: # test
  x = {
    (1,2): "hello",
    (-1,1<<31): bytearray('ba'),
    "": frozenset([9,8,2]),
    None: array('i',range(4))
  }  
  print unpack(pack(x))
  print 'equal:', x == unpack(pack(x))
  
  class Class1(object):
    def __init__(me,x):
      me.a = x
      me.hello = 'world'
      me.hell = 666
  class Class2(object):
    __slots__ = ('__a', 'b')
    def __init__(me):
      me.__a = 5
  class Class3(object):
    def __getstate__(me):
      return frozenset('yay')
    def __setstate__(me, x):
      assert x == frozenset('yay')
  
  print pack((Class1('ONE'),Class1('TWO')))
  
  x = unpack(pack(Class2()))
  print x._Class2__a, hasattr(x,'b')
  
  x = unpack(pack(Class3()))
