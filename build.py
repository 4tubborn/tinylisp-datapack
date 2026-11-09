from pathlib import Path
import json, zipfile
ROOT=Path(__file__).parent/'tinylisp'
F=ROOT/'data/tinylisp/function'
S='storage tinylisp:vm '
funcs={}
def put(name,lines):
    if isinstance(lines,str):lines=lines.strip().splitlines()
    funcs[name]=lines

def setv(dst,val):return f'data modify {S}{dst} set value {val}'
def cp(dst,src):return f'data modify {S}{dst} set from {S}{src}'
def sc(name,val):return f'scoreboard players set #{name} tl {val}'
def call(name,**args):
    out=[setv('call','{}')]
    for k,v in args.items():out.append(cp('call.'+k,v) if not v.startswith('=') else setv('call.'+k,v[1:]))
    out += [f'function tinylisp:{name}']
    return out

def fn(name,body):
    put(name,[ 'execute if score #error tl matches 1.. run return 0',
        'scoreboard players add #steps tl 1',
        'execute if score #steps tl matches 4001.. run return run function tinylisp:error',
        'scoreboard players add #depth tl 1',
        'execute if score #depth tl matches 65.. run function tinylisp:error',
        'execute unless score #error tl matches 1.. run data modify storage tinylisp:vm frames append from storage tinylisp:vm call',
        f'execute unless score #error tl matches 1.. run function tinylisp:body/{name}',
        'execute unless score #depth tl matches 65.. run data remove storage tinylisp:vm frames[-1]',
        'scoreboard players remove #depth tl 1'])
    put('body/'+name,body)

def ret(path):return [cp('r',path),'return 1']
def get(which,src,dst):return call(which,x=src)+[cp(dst,'r')]
def ev(src,dst,env='frames[-1].e'):return call('eval',x=src,e=env)+[cp(dst,'r')]
def cons(a,b,dst):return call('cons',a=a,b=b)+[cp(dst,'r')]
def enderr():return ['execute if score #error tl matches 1.. run return 0']
put('error',[sc('error',1),cp('r','err')])
fn('cons',[ 'execute store result score #id tl run data get storage tinylisp:vm heap',
    setv('node','{}'),cp('node.a','frames[-1].a'),cp('node.b','frames[-1].b'),
    'data modify storage tinylisp:vm heap append from storage tinylisp:vm node',setv('r','{t:2,i:0}'),
    'execute store result storage tinylisp:vm r.i int 1 run scoreboard players get #id tl'])
for which,field in [('car','a'),('cdr','b')]:
    fn(which,[cp('r','err'),
        f'execute if data storage tinylisp:vm frames[-1].x{{t:2}} run function tinylisp:heap/{which} with storage tinylisp:vm frames[-1].x',
        f'execute if data storage tinylisp:vm frames[-1].x{{t:3}} run function tinylisp:heap/{which} with storage tinylisp:vm frames[-1].x'])
    put('heap/'+which,[f'$data modify storage tinylisp:vm r set from storage tinylisp:vm heap[$(i)].{field}'])
fn('equal',[cp('cmp','frames[-1].x'),sc('same',0),
    'execute store success score #same tl run data modify storage tinylisp:vm cmp set from storage tinylisp:vm frames[-1].y',
    cp('r','nil'),'execute if score #same tl matches 0 run data modify storage tinylisp:vm r set from storage tinylisp:vm tru'])
fn('pair',cons('frames[-1].v','frames[-1].x','frames[-1].binding')+cons('frames[-1].binding','frames[-1].e','r'))
fn('assoc',[ 'execute unless data storage tinylisp:vm frames[-1].e{t:2} run return run function tinylisp:missing']+
    get('car','frames[-1].e','frames[-1].binding')+get('car','frames[-1].binding','frames[-1].key')+
    call('equal',x='frames[-1].v',y='frames[-1].key')+
    ['execute unless data storage tinylisp:vm r{t:5} run return run function tinylisp:assoc_found']+
    get('cdr','frames[-1].e','frames[-1].e')+call('assoc',v='frames[-1].v',e='frames[-1].e'))
put('missing',cp('r','err'))
put('assoc_found',call('cdr',x='frames[-1].binding'))
fn('eval',[ 'execute if data storage tinylisp:vm frames[-1].x{t:1} run return run function tinylisp:eval_atom',
    'execute if data storage tinylisp:vm frames[-1].x{t:2} run return run function tinylisp:eval_pair']+ret('frames[-1].x'))
put('eval_atom',call('assoc',v='frames[-1].x',e='frames[-1].e'))
put('eval_pair',get('car','frames[-1].x','frames[-1].head')+get('cdr','frames[-1].x','frames[-1].tail')+
    ev('frames[-1].head','frames[-1].f')+call('apply',f='frames[-1].f',t='frames[-1].tail',e='frames[-1].e'))
fn('evlis',[ 'execute if data storage tinylisp:vm frames[-1].t{t:1} run return run function tinylisp:evlis_atom',
    'execute unless data storage tinylisp:vm frames[-1].t{t:2} run return run function tinylisp:return_nil']+
    get('car','frames[-1].t','frames[-1].head')+get('cdr','frames[-1].t','frames[-1].tail')+
    ev('frames[-1].head','frames[-1].a')+call('evlis',t='frames[-1].tail',e='frames[-1].e')+
    [cp('frames[-1].b','r')]+cons('frames[-1].a','frames[-1].b','r'))
put('return_nil',cp('r','nil'))
put('evlis_atom',call('assoc',v='frames[-1].t',e='frames[-1].e'))
fn('apply',[ 'execute if data storage tinylisp:vm frames[-1].f{t:4} run return run function tinylisp:dispatch with storage tinylisp:vm frames[-1].f',
    'execute if data storage tinylisp:vm frames[-1].f{t:3} run return run function tinylisp:reduce_body']+ret('err'))
put('dispatch',['$function tinylisp:prim/$(p)'])
put('reduce_body',get('car','frames[-1].f','frames[-1].binding')+get('car','frames[-1].binding','frames[-1].vars')+
    get('cdr','frames[-1].binding','frames[-1].body')+get('cdr','frames[-1].f','frames[-1].captured')+
    ['execute if data storage tinylisp:vm frames[-1].captured{t:5} run data modify storage tinylisp:vm frames[-1].captured set from storage tinylisp:vm env']+
    call('evlis',t='frames[-1].t',e='frames[-1].e')+[cp('frames[-1].args','r')]+
    call('bind',v='frames[-1].vars',t='frames[-1].args',e='frames[-1].captured')+[cp('frames[-1].bound','r')]+
    ev('frames[-1].body','r','frames[-1].bound'))
fn('bind',[ 'execute if data storage tinylisp:vm frames[-1].v{t:5} run return run function tinylisp:bind_done',
    'execute unless data storage tinylisp:vm frames[-1].v{t:2} run return run function tinylisp:bind_rest']+
    get('car','frames[-1].v','frames[-1].key')+get('cdr','frames[-1].v','frames[-1].v')+
    get('car','frames[-1].t','frames[-1].value')+get('cdr','frames[-1].t','frames[-1].t')+
    call('pair',v='frames[-1].key',x='frames[-1].value',e='frames[-1].e')+[cp('frames[-1].e','r')]+
    call('bind',v='frames[-1].v',t='frames[-1].t',e='frames[-1].e'))
put('bind_done',cp('r','frames[-1].e'))
put('bind_rest',call('pair',v='frames[-1].v',x='frames[-1].t',e='frames[-1].e'))
# Primitives share apply's current frame. Nested calls always push their own frames.
prims=['eval','quote','cons','car','cdr','add','sub','mul','div','int','lt','eq','pair','or','and','not','cond','if','let','lambda','define']
names=['eval','quote','cons','car','cdr','+','-','*','/','int','<','eq?','pair?','or','and','not','cond','if','let*','lambda','define']
args=call('evlis',t='frames[-1].t',e='frames[-1].e')+[cp('frames[-1].args','r')]
first=get('car','frames[-1].args','frames[-1].a')
second=get('cdr','frames[-1].args','frames[-1].rest')+get('car','frames[-1].rest','frames[-1].b')
put('prim/quote',call('car',x='frames[-1].t'))
put('prim/eval',args+first+ev('frames[-1].a','r'))
put('prim/cons',args+first+second+cons('frames[-1].a','frames[-1].b','r'))
for p in ['car','cdr']:put('prim/'+p,args+first+call(p,x='frames[-1].a'))
put('prim/int',args+first+ret('frames[-1].a'))
put('prim/eq',args+first+second+call('equal',x='frames[-1].a',y='frames[-1].b'))
put('prim/pair',args+first+[cp('r','nil'),'execute if data storage tinylisp:vm frames[-1].a{t:2} run data modify storage tinylisp:vm r set from storage tinylisp:vm tru'])
put('prim/not',args+first+[cp('r','nil'),'execute if data storage tinylisp:vm frames[-1].a{t:5} run data modify storage tinylisp:vm r set from storage tinylisp:vm tru'])
nums=['execute unless data storage tinylisp:vm frames[-1].a{t:0} run return run function tinylisp:missing',
      'execute unless data storage tinylisp:vm frames[-1].b{t:0} run return run function tinylisp:missing',
      'execute store result score #a tl run data get storage tinylisp:vm frames[-1].a.n',
      'execute store result score #b tl run data get storage tinylisp:vm frames[-1].b.n']
put('prim/lt',args+first+second+nums+[cp('r','nil'),'execute if score #a tl < #b tl run data modify storage tinylisp:vm r set from storage tinylisp:vm tru'])
for p,op in [('add','+='),('sub','-='),('mul','*='),('div','/=')]:
    put('prim/'+p,args+first+second+[setv('frames[-1].op',json.dumps(p))]+call('fold',a='frames[-1].a',t='frames[-1].rest',op='frames[-1].op'))
    put('math/'+p,nums+(['execute if score #b tl matches 0 run return run function tinylisp:error'] if p=='div' else [])+
        [f'scoreboard players operation #a tl {op} #b tl',setv('frames[-1].a','{t:0,n:0}'),
         'execute store result storage tinylisp:vm frames[-1].a.n int 1 run scoreboard players get #a tl'])
# score division floors; adjust negative quotient towards zero (C cast behavior for integer variant)
funcs['math/div']=nums+['execute if score #b tl matches 0 run return run function tinylisp:error',
    'scoreboard players operation #rem tl = #a tl','scoreboard players operation #rem tl %= #b tl',
    sc('neg',0),'execute if score #a tl matches ..-1 if score #b tl matches 1.. run scoreboard players set #neg tl 1',
    'execute if score #a tl matches 0.. if score #b tl matches ..-1 run scoreboard players set #neg tl 1',
    'scoreboard players operation #a tl /= #b tl',
    'execute if score #neg tl matches 1 unless score #rem tl matches 0 run scoreboard players add #a tl 1',
    setv('frames[-1].a','{t:0,n:0}'),'execute store result storage tinylisp:vm frames[-1].a.n int 1 run scoreboard players get #a tl']
fn('fold',[ 'execute if data storage tinylisp:vm frames[-1].t{t:5} run return run function tinylisp:fold_done',
    'execute unless data storage tinylisp:vm frames[-1].t{t:2} run return run function tinylisp:missing']+
    get('car','frames[-1].t','frames[-1].b')+get('cdr','frames[-1].t','frames[-1].t')+
    ['function tinylisp:fold_op with storage tinylisp:vm frames[-1]']+enderr()+
    call('fold',a='frames[-1].a',t='frames[-1].t',op='frames[-1].op'))
put('fold_op',['$function tinylisp:math/$(op)'])
put('fold_done',cp('r','frames[-1].a'))
for p,initial,condition in [('or','nil','unless'),('and','tru','if')]:
    put('prim/'+p,[cp('frames[-1].last',initial),setv('frames[-1].mode',json.dumps(p))]+call('logic',t='frames[-1].t',e='frames[-1].e',last='frames[-1].last',mode='frames[-1].mode'))
fn('logic',[ 'execute if data storage tinylisp:vm frames[-1].t{t:5} run return run function tinylisp:logic_done',
    'execute unless data storage tinylisp:vm frames[-1].t{t:2} run return run function tinylisp:missing']+
    get('car','frames[-1].t','frames[-1].head')+get('cdr','frames[-1].t','frames[-1].t')+
    ev('frames[-1].head','frames[-1].last')+
    ['execute if data storage tinylisp:vm frames[-1]{mode:"or"} unless data storage tinylisp:vm frames[-1].last{t:5} run return run function tinylisp:logic_done',
     'execute if data storage tinylisp:vm frames[-1]{mode:"and"} if data storage tinylisp:vm frames[-1].last{t:5} run return run function tinylisp:logic_done']+
    call('logic',t='frames[-1].t',e='frames[-1].e',last='frames[-1].last',mode='frames[-1].mode'))
put('logic_done',cp('r','frames[-1].last'))
put('prim/if',get('car','frames[-1].t','frames[-1].test')+get('cdr','frames[-1].t','frames[-1].branches')+
    ev('frames[-1].test','frames[-1].truth')+
    ['execute if data storage tinylisp:vm frames[-1].truth{t:5} run function tinylisp:if_else']+
    get('car','frames[-1].branches','frames[-1].body')+ev('frames[-1].body','r'))
put('if_else',get('cdr','frames[-1].branches','frames[-1].branches'))
put('prim/cond',call('cond',t='frames[-1].t',e='frames[-1].e'))
fn('cond',['execute unless data storage tinylisp:vm frames[-1].t{t:2} run return run function tinylisp:missing']+
    get('car','frames[-1].t','frames[-1].clause')+get('car','frames[-1].clause','frames[-1].test')+
    ev('frames[-1].test','frames[-1].truth')+
    ['execute unless data storage tinylisp:vm frames[-1].truth{t:5} run return run function tinylisp:cond_yes']+
    get('cdr','frames[-1].t','frames[-1].t')+call('cond',t='frames[-1].t',e='frames[-1].e'))
put('cond_yes',get('cdr','frames[-1].clause','frames[-1].rest')+get('car','frames[-1].rest','frames[-1].body')+ev('frames[-1].body','r'))
put('prim/let',call('let',t='frames[-1].t',e='frames[-1].e'))
fn('let',get('cdr','frames[-1].t','frames[-1].tail')+
    ['execute if data storage tinylisp:vm frames[-1].tail{t:5} run return run function tinylisp:let_done']+
    get('car','frames[-1].t','frames[-1].binding')+get('car','frames[-1].binding','frames[-1].key')+
    get('cdr','frames[-1].binding','frames[-1].rest')+get('car','frames[-1].rest','frames[-1].body')+
    ev('frames[-1].body','frames[-1].value')+call('pair',v='frames[-1].key',x='frames[-1].value',e='frames[-1].e')+
    [cp('frames[-1].e','r')]+call('let',t='frames[-1].tail',e='frames[-1].e'))
put('let_done',get('car','frames[-1].t','frames[-1].body')+ev('frames[-1].body','r'))
put('prim/lambda',get('car','frames[-1].t','frames[-1].vars')+get('cdr','frames[-1].t','frames[-1].rest')+
    get('car','frames[-1].rest','frames[-1].body')+call('equal',x='frames[-1].e',y='env')+
    ['execute unless data storage tinylisp:vm r{t:5} run data modify storage tinylisp:vm frames[-1].e set from storage tinylisp:vm nil']+
    call('pair',v='frames[-1].vars',x='frames[-1].body',e='frames[-1].e')+[setv('r.t','3')])
put('prim/define',get('car','frames[-1].t','frames[-1].key')+get('cdr','frames[-1].t','frames[-1].rest')+
    get('car','frames[-1].rest','frames[-1].body')+ev('frames[-1].body','frames[-1].value')+
    call('pair',v='frames[-1].key',x='frames[-1].value',e='env')+[cp('env','r')]+ret('frames[-1].key'))
# Source parser uses numeric indices only in macros. Symbol text is never substituted into commands.
put('peek',[setv('ch','""'), 'scoreboard players operation #end tl = #pos tl',
    'scoreboard players add #end tl 1','execute store result storage tinylisp:vm indices.start int 1 run scoreboard players get #pos tl',
    'execute store result storage tinylisp:vm indices.end int 1 run scoreboard players get #end tl',
    'execute if score #pos tl < #length tl run function tinylisp:slice_char with storage tinylisp:vm indices'])
put('slice_char',['$data modify storage tinylisp:vm ch set string storage tinylisp:vm source $(start) $(end)'])
put('space',[sc('ws',0)]+[f'execute if data storage tinylisp:vm {{ch:{json.dumps(c)}}} run scoreboard players set #ws tl 1' for c in [' ','\t','\n','\r']])
put('skip',['function tinylisp:peek','function tinylisp:space',
    'execute if score #ws tl matches 0 run return 0','scoreboard players add #pos tl 1','function tinylisp:skip'])
fn('read',['function tinylisp:skip','execute if score #pos tl >= #length tl run return run function tinylisp:error',
    'execute if data storage tinylisp:vm {ch:"("} run return run function tinylisp:read_list',
    'execute if data storage tinylisp:vm {ch:"\u0027"} run return run function tinylisp:read_quote',
    'execute if data storage tinylisp:vm {ch:")"} run return run function tinylisp:error',
    'execute store result storage tinylisp:vm frames[-1].start int 1 run scoreboard players get #pos tl',
    sc('num',0),sc('valid',1),sc('sign',1),sc('digits',0),sc('tokenlen',0),
    'function tinylisp:scan',
    'execute store result storage tinylisp:vm frames[-1].end int 1 run scoreboard players get #pos tl',
    setv('r','{t:1,s:""}'),'function tinylisp:slice_token with storage tinylisp:vm frames[-1]',
    'execute if score #valid tl matches 1 if score #digits tl matches 1.. run function tinylisp:read_number'])
put('slice_token',['$data modify storage tinylisp:vm r.s set string storage tinylisp:vm source $(start) $(end)'])
put('read_number',['scoreboard players operation #num tl *= #sign tl',setv('r','{t:0,n:0}'),
    'execute store result storage tinylisp:vm r.n int 1 run scoreboard players get #num tl'])
put('scan',['function tinylisp:peek','function tinylisp:space',
    'execute if score #pos tl >= #length tl run return 0',
    'execute if score #ws tl matches 1 run return 0']+
    [f'execute if data storage tinylisp:vm {{ch:{json.dumps(c)}}} run return 0' for c in ['(',')',"'"]]+
    [sc('digit',-1)]+[f'execute if data storage tinylisp:vm {{ch:"{i}"}} run scoreboard players set #digit tl {i}' for i in range(10)]+
    ['execute if score #tokenlen tl matches 0 if data storage tinylisp:vm {ch:"-"} run scoreboard players set #sign tl -1',
     sc('signchar',0),'execute if score #tokenlen tl matches 0 if data storage tinylisp:vm {ch:"-"} run scoreboard players set #signchar tl 1',
     'execute if score #tokenlen tl matches 0 if data storage tinylisp:vm {ch:"+"} run scoreboard players set #signchar tl 1',
     'execute if score #digit tl matches ..-1 unless score #signchar tl matches 1 run scoreboard players set #valid tl 0',
     'execute if score #digit tl matches 0.. run function tinylisp:scan_digit',
     'scoreboard players add #tokenlen tl 1','scoreboard players add #pos tl 1','function tinylisp:scan'])
put('scan_digit',['scoreboard players operation #num tl *= #ten tl','scoreboard players operation #num tl += #digit tl','scoreboard players add #digits tl 1'])
put('read_list',['scoreboard players add #pos tl 1']+call('list'))
fn('list',['function tinylisp:skip','execute if score #pos tl >= #length tl run return run function tinylisp:error',
    'execute if data storage tinylisp:vm {ch:")"} run return run function tinylisp:list_end',
    'execute if data storage tinylisp:vm {ch:"."} run return run function tinylisp:list_dot']+
    call('read')+[cp('frames[-1].a','r')]+enderr()+call('list')+[cp('frames[-1].b','r')]+enderr()+cons('frames[-1].a','frames[-1].b','r'))
put('list_end',['scoreboard players add #pos tl 1',cp('r','nil')])
# Recognize dot only when standalone: restore pos and fall back to ordinary list parsing otherwise.
put('list_dot',['scoreboard players add #pos tl 1','function tinylisp:peek','function tinylisp:space',
    'execute if score #ws tl matches 1 run return run function tinylisp:dotted',
    'execute if data storage tinylisp:vm {ch:"("} run return run function tinylisp:dotted',
    'scoreboard players remove #pos tl 1']+call('read')+[cp('frames[-1].a','r')]+call('list')+[cp('frames[-1].b','r')]+cons('frames[-1].a','frames[-1].b','r'))
put('dotted',call('read')+[cp('frames[-1].tail','r'),'function tinylisp:skip',
    'execute unless data storage tinylisp:vm {ch:")"} run return run function tinylisp:error',
    'scoreboard players add #pos tl 1',cp('r','frames[-1].tail')])
put('read_quote',['scoreboard players add #pos tl 1']+call('read')+[cp('frames[-1].quoted','r')]+
    cons('frames[-1].quoted','nil','frames[-1].qlist')+cons('quote','frames[-1].qlist','r'))
# Printing plain fragments through NBT text components; safe for quote/backslash symbols.
fn('print',[ 'execute if data storage tinylisp:vm frames[-1].x{t:5} run return run function tinylisp:print_nil',
    'execute if data storage tinylisp:vm frames[-1].x{t:1} run return run function tinylisp:print_atom',
    'execute if data storage tinylisp:vm frames[-1].x{t:0} run return run function tinylisp:print_number with storage tinylisp:vm frames[-1].x',
    'execute if data storage tinylisp:vm frames[-1].x{t:4} run return run function tinylisp:print_prim with storage tinylisp:vm frames[-1].x',
    'execute if data storage tinylisp:vm frames[-1].x{t:3} run return run function tinylisp:print_closure with storage tinylisp:vm frames[-1].x',
    'data modify storage tinylisp:vm output append value "("']+call('printlist',x='frames[-1].x')+['data modify storage tinylisp:vm output append value ")"'])
put('print_nil',['data modify storage tinylisp:vm output append value "()"'])
put('print_atom',['data modify storage tinylisp:vm output append from storage tinylisp:vm frames[-1].x.s'])
put('print_number',['$data modify storage tinylisp:vm output append value "$(n)"'])
put('print_prim',['$data modify storage tinylisp:vm output append value "<$(p)>"'])
put('print_closure',['$data modify storage tinylisp:vm output append value "{$(i)}"'])
fn('printlist',get('car','frames[-1].x','frames[-1].head')+get('cdr','frames[-1].x','frames[-1].tail')+
    call('print',x='frames[-1].head')+
    ['execute if data storage tinylisp:vm frames[-1].tail{t:5} run return 1',
     'execute unless data storage tinylisp:vm frames[-1].tail{t:2} run return run function tinylisp:print_dot',
     'data modify storage tinylisp:vm output append value " "']+call('printlist',x='frames[-1].tail'))
put('print_dot',['data modify storage tinylisp:vm output append value " . "']+call('print',x='frames[-1].tail'))
# Conservative rollback boundary identical in spirit to C gc: keep allocations made before latest global env.
put('gc',['execute store result score #size tl run data get storage tinylisp:vm heap',
    'execute if score #size tl <= #keep tl run return 0','data remove storage tinylisp:vm heap[-1]','function tinylisp:gc'])
put('load',['scoreboard objectives add tl dummy','execute unless data storage tinylisp:vm initialized run function tinylisp:reset'])
reset=[setv('heap','[]'),setv('frames','[]'),setv('nil','{t:5}'),setv('err','{t:1,s:"ERR"}'),setv('tru','{t:1,s:"#t"}'),
    setv('quote','{t:1,s:"quote"}'),cp('env','nil'),sc('error',0),sc('steps',0),sc('depth',0),sc('ten',10)]+call('pair',v='tru',x='tru',e='env')+[cp('env','r')]
for name,p in zip(names,prims):
    reset+=call('pair',v='='+json.dumps({'t':1,'s':name},separators=(',',':')),x='='+json.dumps({'t':4,'p':p},separators=(',',':')),e='env')+[cp('env','r')]
reset += [setv('initialized','1b'),'execute store result score #keep tl run data get storage tinylisp:vm heap',setv('output','[]')]
put('reset',reset)
put('run',['execute unless data storage tinylisp:vm initialized run function tinylisp:reset',
    'execute if score #busy tl matches 1 run return 0',sc('busy',1),
    sc('error',0),sc('steps',0),sc('depth',0),sc('pos',0),sc('length',0),sc('ten',10),setv('frames','[]'),setv('output','[]'),
    'function tinylisp:gc','data remove storage tinylisp:vm source',cp('source','source_input'),
    'execute unless data storage tinylisp:vm source run function tinylisp:error',
    'execute store result score #length tl run data get storage tinylisp:vm source',
    'execute if score #length tl matches 513.. run function tinylisp:error',
    'execute unless score #error tl matches 1.. run function tinylisp:run_loop',
    'execute if score #error tl matches 1.. run function tinylisp:run_error',
    cp('result','r'),
    'execute store result score #keep tl run data get storage tinylisp:vm env.i','scoreboard players add #keep tl 1',
    setv('frames','[]'),sc('busy',0)])
put('run_loop',['function tinylisp:skip','execute if score #pos tl >= #length tl run return 1']+
    call('read')+[cp('expression','r')]+enderr()+call('eval',x='expression',e='env')+[cp('result','r')]+enderr()+
    ['execute if data storage tinylisp:vm output[0] run data modify storage tinylisp:vm output append value "\\n"']+
    call('print',x='result')+enderr()+[cp('r','result'),'function tinylisp:run_loop'])
put('run_error',[cp('r','err'),'data modify storage tinylisp:vm output append value "ERR (syntax, limit, numeric type or division by zero)"'])
put('show',['tellraw @s {"nbt":"output[]","storage":"tinylisp:vm","separator":""}'])
put('repl',['function tinylisp:run','function tinylisp:show'])
# Type failures must abort arithmetic, rather than silently keeping the accumulator.
for name,lines in funcs.items():
    if name.startswith('math/') or name=='prim/lt':
        funcs[name]=[line.replace('run return run function tinylisp:missing','run return run function tinylisp:error') if 'unless data' in line and '{t:0}' in line else line for line in lines]
# Entry initialization must recover the busy score even after interrupted execution.
funcs['reset'].append(sc('busy',0))
# Empty source returns nil.
funcs['run'].insert(funcs['run'].index('function tinylisp:gc'),cp('r','nil'))
put('demo/square',[setv('source_input','"(define square (lambda (x) (* x x))) (square 9)"'),'function tinylisp:repl'])
put('demo/closure',[setv('source_input','"(define make (lambda (x) (lambda (y) (+ x y)))) (define add7 (make 7)) (add7 3)"'),'function tinylisp:repl'])
put('demo/factorial',[setv('source_input','"(define fact (lambda (n) (if (< n 2) 1 (* n (fact (- n 1)))))) (fact 5)"'),'function tinylisp:repl'])
for name,lines in funcs.items():
    path=F/(name+'.mcfunction');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('# Generated by build.py; TinyLisp integer mcfunction port.\n'+'\n'.join(lines)+'\n')
(ROOT/'pack.mcmeta').write_text(json.dumps({'pack':{'pack_format':71,'description':'TinyLisp integer interpreter (Java 1.21.5)'}},ensure_ascii=False,indent=2)+'\n')
tag=ROOT/'data/minecraft/tags/function/load.json';tag.parent.mkdir(parents=True,exist_ok=True);tag.write_text('{"values":["tinylisp:load"]}\n')
print(f'Generated {len(funcs)} mcfunction files, {sum(map(len,funcs.values()))} commands')
