"""Execute the generated command subset locally. Not a Minecraft server substitute."""
import json,re,copy,sys,math
from pathlib import Path
sys.setrecursionlimit(30000)
ROOT=Path(__file__).parent/'tinylisp/data/tinylisp/function'
def snbt(s):
 s=re.sub(r'(?<=[{,])\s*([A-Za-z_][\w.-]*)\s*:',r'"\1":',s)
 s=re.sub(r'(?<![\w"])(-?\d+)[bBsSlL](?=[,}\]]|$)',r'\1',s)
 return json.loads(s)
def words(s):
 out=[];start=0;level=0;quote=None;escape=False
 for i,c in enumerate(s):
  if quote:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c==quote:quote=None
  elif c in '\"\u0027':quote=c
  elif c in '{[':level+=1
  elif c in '}]':level-=1
  elif c==' ' and level==0:
   if i>start:out.append(s[start:i])
   start=i+1
 if start<len(s):out.append(s[start:])
 return out
def match(a,b):return all(k in a and match(a[k],v) for k,v in b.items()) if isinstance(b,dict) and isinstance(a,dict) else a==b
class Return(Exception):
 def __init__(self,r):self.r=r
class VM:
 def __init__(self):self.d={};self.s={};self.commands=0;self.macros=0
 def path(self,p):
  filt=None
  if '{' in p:p,f=p.split('{',1);filt=snbt('{'+f)
  keys=[]
  for m in re.finditer(r'([^.[\]]+)|\[(-?\d+)\]',p):keys.append(m[1] if m[1] is not None else int(m[2]))
  return keys,filt
 def get(self,p):
  keys,filt=self.path(p);v=self.d
  for k in keys:v=v[k]
  if filt is not None and not match(v,filt):raise KeyError(p)
  return v
 def exists(self,p):
  try:self.get(p);return True
  except (KeyError,IndexError,TypeError):return False
 def set(self,p,v):
  keys,_=self.path(p);a=self.d
  for k in keys[:-1]:
   if isinstance(k,str) and k not in a:a[k]={}
   a=a[k]
  old=a.get(keys[-1],object()) if isinstance(a,dict) else a[keys[-1]]
  a[keys[-1]]=copy.deepcopy(v);return int(old!=v)
 def func(self,n,macro=None):
  try:
   for line in (ROOT/(n+'.mcfunction')).read_text().splitlines():
    if not line or line.startswith('#'):continue
    if line.startswith('$'):
     self.macros+=1
     if macro is None:raise AssertionError(f'missing macro args: {n}')
     line=re.sub(r'\$\((\w+)\)',lambda m:str(macro[m[1]]),line[1:])
    self.cmd(line)
  except Return as r:return r.r
  return 1
 def cmd(self,c):
  self.commands+=1
  if self.commands>1000000:raise RuntimeError('runaway command loop')
  if c.startswith('execute '):
   pre,cmd=c[8:].split(' run ',1);w=words(pre);i=0;stores=[];ok=True
   while i<len(w):
    if w[i]=='store':
     mode=w[i+1];kind=w[i+2]
     if kind=='score':stores.append((mode,'score',w[i+3]));i+=5
     else:stores.append((mode,'storage',w[i+4]));i+=7
    else:
     positive=w[i]=='if';kind=w[i+1]
     if kind=='data':truth=self.exists(w[i+4]);i+=5
     else:
      val=self.s.get(w[i+2],0);op=w[i+4]
      if op=='matches':
       rng=w[i+5]
       if '..' in rng:
        lo,hi=rng.split('..');truth=(not lo or val>=int(lo)) and (not hi or val<=int(hi))
       else:truth=val==int(rng)
       i+=6
      else:
       other=self.s.get(w[i+5],0);truth={'=':val==other,'<':val<other,'>':val>other,'<=':val<=other,'>=':val>=other}[op];i+=7
     ok &= truth==positive
   result=self.cmd(cmd) if ok else 0
   for mode,kind,key in stores:
    val=int(result!=0) if mode=='success' else result
    if kind=='score':self.s[key]=val
    else:self.set(key,val)
   return result
  if c.startswith('return run '):raise Return(self.cmd(c[11:]))
  if c.startswith('return '):raise Return(int(c[7:]))
  w=words(c)
  try:
   if w[0]=='function':
    macro=copy.deepcopy(self.get(w[5])) if len(w)>2 else None
    return self.func(w[1].split(':',1)[1],macro)
   if w[:3]==['scoreboard','objectives','add']:return 1
   if w[:2]==['scoreboard','players']:
    op,key=w[2:4]
    if op=='get':return self.s.get(key,0)
    if op in ['set','add','remove']:
     v=int(w[5]);v=v if op=='set' else self.s.get(key,0)+(v if op=='add' else -v)
    else:
     a=self.s.get(key,0);b=self.s.get(w[6],0);o=w[5]
     if o=='=':v=b
     elif o=='+=':v=a+b
     elif o=='-=':v=a-b
     elif o=='*=':v=a*b
     elif o=='/=':v=a//b
     elif o=='%=':v=a%b
     else:raise AssertionError(c)
    self.s[key]=(v+2**31)%2**32-2**31;return 1
   if w[:2]==['data','get']:
    v=self.get(w[4]);return len(v) if isinstance(v,(dict,list,str)) else int(v)
   if w[:2]==['data','remove']:
    keys,_=self.path(w[4]);a=self.d
    for k in keys[:-1]:a=a[k]
    del a[keys[-1]];return 1
   if w[:2]==['data','modify']:
    p,op,src=w[4:7]
    if src=='value':v=snbt(' '.join(w[7:]))
    elif src=='from':v=self.get(w[9])
    elif src=='string':v=self.get(w[9])[int(w[10]):int(w[11])]
    else:raise AssertionError(c)
    if op=='set':return self.set(p,v)
    self.get(p).append(copy.deepcopy(v));return 1
   if w[0]=='tellraw':return 1
  except (KeyError,IndexError,TypeError):return 0
  raise AssertionError(c)
 def run(self,source):
  self.d['source_input']=source;self.commands=0;self.func('run')
  return ''.join(self.d['output']),self.d['result']

cases=[
 ('(+ 1 2 3)','6'),('(- 9 2 3)','4'),('(* 2 3 4)','24'),('(/ -7 2)','-3'),('(/ 7 -2)','-3'),('(/ -7 -2)','3'),
 ('(int 5)','5'),('(< 2 3)','#t'),('(eq? 4 4)','#t'),('(eq? 4 5)','()'),("'(a b . c)",'(a b . c)'),
 ('(car (cons 1 2))','1'),('(cdr (cons 1 2))','2'),('(pair? (lambda (x) x))','()'),('(pair? (cons 1 2))','#t'),
 ('(not ())','#t'),('(not 0)','()'),('(or () 7 (/ 1 0))','7'),('(and 3 () (/ 1 0))','()'),('(and)','\u0023t'),('(or)','()'),
 ('(if () (/ 1 0) 4)','4'),('(cond (() 1) (#t 8))','8'),('(let* (a 3) (b (+ a 2)) (* a b))','15'),
 ('((lambda (x) (+ x 1)) 5)','6'),('((lambda args (car args)) 8 9)','8'),('((lambda (x . rest) (car rest)) 1 2 3)','2'),
 ('(define square (lambda (x) (* x x))) (square 9)','square\n81'),
 ('(define make (lambda (x) (lambda (y) (+ x y)))) (define add7 (make 7)) (add7 3)','make\nadd7\n10'),
 ('(define fact (lambda (n) (if (< n 2) 1 (* n (fact (- n 1)))))) (fact 5)','fact\n120'),
 ("(eval '(+ 3 4))",'7'),('()','()'),('',''),("'foo",'foo'),("'a.b",'a.b'),
]
if __name__=='__main__':
 vm=VM();vm.func('load');passed=0
 for src,want in cases:
  got,value=vm.run(src)
  assert got==want,(src,got,want,value,vm.s)
  assert vm.d['frames']==[],src
  assert vm.s['#depth']==0,src
  passed+=1
 for src in ['(+ 1 ())','(/ 1 0)','(1 2','\u0029','x'*513]:
  got,value=vm.run(src);assert value=={'t':1,'s':'ERR'},(src,got,value)
  passed+=1
 # Globals and captured closures survive GC at the next invocation.
 for src,want in [('(add7 5)','12'),('(square 10)','100'),('(fact 4)','24')]:
  got,_=vm.run(src);assert got==want,(src,got,want);passed+=1
 print(f'PASS: {passed} behavior cases, generated mcfunction command subset simulator')
 # Resolve every static function target and macro body.
 for path in ROOT.rglob('*.mcfunction'):
  for line in path.read_text().splitlines():
   for name in re.findall(r'function tinylisp:([a-z0-9_/]+)(?![$(])',line):
    if line.startswith('$'):continue
    assert (ROOT/(name+'.mcfunction')).exists(),(path,line,name)
 print('PASS: all static function references resolve')
