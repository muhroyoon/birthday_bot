"""Logic puzzle rules and bounded, uniqueness-checked generators.

Boards contain clues and player marks only. Solutions are local to generation.
All randomness is seeded; daily clients therefore receive identical problems.
"""
import copy
import random
from functools import lru_cache

GAMES = {'nurikabe': '섬 만들기', 'slitherlink': '고리 잇기', 'hashi': '다리 잇기'}

@lru_cache(maxsize=2048)
def adjacent(i,n):
 return [j for j in (i-n,i+n,i-1,i+1) if 0<=j<n*n and abs(j%n-i%n)+abs(j//n-i//n)==1]

def components(values,neighbors):
 left=set(values);out=[]
 while left:
  todo=[left.pop()];part=set(todo)
  while todo:
   for v in neighbors(todo.pop()):
    if v in left:left.remove(v);part.add(v);todo.append(v)
  out.append(part)
 return out

def connected(values,neighbors):return len(components(values,neighbors))==1

@lru_cache(maxsize=16)
def loop_edges(n):
 edges=[]
 for y in range(n+1):
  for x in range(n):edges.append((y*(n+1)+x,y*(n+1)+x+1))
 for y in range(n):
  for x in range(n+1):edges.append((y*(n+1)+x,(y+1)*(n+1)+x))
 return tuple(edges)

def cell_edges(n,i):
 x=i%n;y=i//n;off=n*(n+1)
 return [y*n+x,(y+1)*n+x,off+y*(n+1)+x,off+y*(n+1)+x+1]

def hashi_edges(islands):
 edges=[]
 for i,(x,y,_) in enumerate(islands):
  for axis in (0,1):
   candidates=[(p[axis],j) for j,p in enumerate(islands) if p[1-axis]==(y if axis==0 else x) and p[axis]>(x if axis==0 else y)]
   if candidates:edges.append((i,min(candidates)[1]))
 return edges

def bridge_cross(a,b,islands):
 p,q=[islands[i] for i in a];r,s=[islands[i] for i in b]
 if p[0]==q[0]:p,q,r,s=r,s,p,q
 return p[1]==q[1] and r[0]==s[0] and min(p[0],q[0])<r[0]<max(p[0],q[0]) and min(r[1],s[1])<p[1]<max(r[1],s[1])

def valid_land(n,clues,land):
 sea=set(range(n*n))-land
 if not connected(sea,lambda i:adjacent(i,n)):return False
 if any({i,i+1,i+n,i+n+1}<=sea for i in range(n*n) if i%n<n-1 and i//n<n-1):return False
 for group in components(land,lambda i:adjacent(i,n)):
  nums=[clues[i] for i in group if clues[i]]
  if len(nums)!=1 or nums[0]!=len(group):return False
 return all(not v or i in land for i,v in enumerate(clues))

def solved(b):
 g=b['game'];n=b['n'];marks=b['marks']
 if g=='nurikabe':
  return 0 not in marks and valid_land(n,b['clues'],{i for i,v in enumerate(marks) if v==1})
 edges=loop_edges(n) if g=='slitherlink' else hashi_edges(b['islands'])
 active=[e for e,v in zip(edges,marks) if v>0];graph={}
 for a,c in active:graph.setdefault(a,[]).append(c);graph.setdefault(c,[]).append(a)
 if not graph or not connected(graph,lambda i:graph[i]):return False
 if g=='slitherlink':
  return all(len(v)==2 for v in graph.values()) and all(v<0 or sum(marks[e]>0 for e in cell_edges(n,i))==v for i,v in enumerate(b['clues']))
 islands=b['islands']
 return len(graph)==len(islands) and all(sum(max(0,marks[e]) for e,p in enumerate(edges) if i in p)==v[2] for i,v in enumerate(islands)) and not any(bridge_cross(a,c,islands) for i,a in enumerate(active) for c in active[:i])

def move(b,e):
 if not isinstance(e,list) or len(e)!=2 or any(type(v) is not int for v in e):return False
 i,v=e;g=b['game']
 allowed=(0,1,2) if g in ('hashi','nurikabe') else (-1,0,1)
 if not 0<=i<len(b['marks']) or v not in allowed or b['marks'][i]==v:return False
 if g=='nurikabe' and b['clues'][i]:return False
 b['marks'][i]=v;return True

def analyze(b,limit=1600):
 """Return solver work and uniqueness, failing closed on exhausted search."""
 stats={'unique':False,'nodes':0,'branches':0,'depth':0,'forced':0,'limited':False};solutions=[]
 n=b['n'];g=b['game']
 if g=='nurikabe':
  nums=[i for i,v in enumerate(b['clues']) if v];domains=[]
  for root in nums:
   shapes={frozenset([root])}
   for _ in range(b['clues'][root]-1):
    shapes={shape|{v} for shape in shapes for i in shape for v in adjacent(i,n) if v not in shape and (not b['clues'][v] or v==root)}
    if len(shapes)>12000:stats['limited']=True;return stats
   domains.append([sum(1<<i for i in s) for s in sorted(shapes,key=lambda x:tuple(sorted(x)))])
  border={s:s|sum_mask(j for i in range(n*n) if s>>i&1 for j in adjacent(i,n)) for d in domains for s in d}
  squares=[sum(1<<j for j in (i,i+1,i+n,i+n+1)) for i in range(n*n) if i%n<n-1 and i//n<n-1]
  def propagate(ds):
   changed=True
   while changed:
    changed=False
    singles=[(i,d[0]) for i,d in enumerate(ds) if len(d)==1]
    for i,s in singles:
     for j,d in enumerate(ds):
      if i==j:continue
      q=[v for v in d if not v&border[s]]
      if not q:return None
      if len(q)!=len(d):stats['forced']+=len(d)-len(q);ds[j]=q;changed=True
    possible=0
    for d in ds:
     for s in d:possible|=s
    if any(not possible&s for s in squares):return None
    # Every 2x2 sea square must have at least one land cell.
    for square in squares:
     owners=[i for i,d in enumerate(ds) if any(s&square for s in d)]
     if len(owners)==1:
      i=owners[0];q=[s for s in ds[i] if s&square]
      if len(q)!=len(ds[i]):stats['forced']+=len(ds[i])-len(q);ds[i]=q;changed=True
   return ds
  def finish(ds):
   mask=0
   for d in ds:mask|=d[0]
   land={i for i in range(n*n) if mask>>i&1}
   return [1 if i in land else 2 for i in range(n*n)] if valid_land(n,b['clues'],land) else None
 else:
  edges=loop_edges(n) if g=='slitherlink' else hashi_edges(b['islands'])
  domains=[[0,1] if g=='slitherlink' else [0,1,2] for _ in edges];constraints=[];cross=[]
  if g=='slitherlink':
   constraints=[(cell_edges(n,i),{v}) for i,v in enumerate(b['clues']) if v>=0]
   constraints += [([i for i,p in enumerate(edges) if vertex in p],{0,2}) for vertex in range((n+1)**2)]
  else:
   constraints=[([i for i,p in enumerate(edges) if vertex in p],{v[2]}) for vertex,v in enumerate(b['islands'])]
   cross=[(i,j) for i,a in enumerate(edges) for j,c in enumerate(edges[:i]) if bridge_cross(a,c,b['islands'])]
  def propagate(ds):
   changed=True
   while changed:
    changed=False
    for ix,targets in constraints:
     lo=sum(min(ds[i]) for i in ix);hi=sum(max(ds[i]) for i in ix)
     if not any(lo<=t<=hi for t in targets):return None
     for i in ix:
      q=[v for v in ds[i] if any(lo-min(ds[i])+v<=t<=hi-max(ds[i])+v for t in targets)]
      if not q:return None
      if len(q)!=len(ds[i]):stats['forced']+=len(ds[i])-len(q);ds[i]=q;changed=True
    for i,j in cross:
     for a,c in ((i,j),(j,i)):
      if min(ds[a])>0:
       if 0 not in ds[c]:return None
       if ds[c]!=[0]:ds[c]=[0];changed=True
    if g=='hashi':
     graph={i:[] for i in range(len(b['islands']))}
     for i,(a,c) in enumerate(edges):
      if max(ds[i])>0:graph[a].append(c);graph[c].append(a)
     if not connected(graph,lambda i:graph[i]):return None
   return ds
  def finish(ds):
   marks=[d[0] for d in ds];candidate={**b,'marks':marks}
   return marks if solved(candidate) else None
 def search(ds,depth):
  if len(solutions)>1 or stats['limited']:return
  stats['nodes']+=1;stats['depth']=max(stats['depth'],depth)
  if stats['nodes']>limit:stats['limited']=True;return
  if any(not d for d in ds):return
  ds=propagate([d[:] for d in ds])
  if ds is None:return
  choices=[(len(d),i) for i,d in enumerate(ds) if len(d)>1]
  if not choices:
   answer=finish(ds)
   if answer is not None:solutions.append(answer)
   return
  _,i=min(choices);stats['branches']+=1
  for v in ds[i]:
   next_ds=ds[:];next_ds[i]=[v];search(next_ds,depth+1)
 search(domains,0)
 stats['unique']=len(solutions)==1 and not stats['limited']
 if solutions:stats['solution']=solutions[0]
 return stats

def sum_mask(values):
 out=0
 for i in values:out|=1<<i
 return out

def candidate(game,rng,n):
 if game=='nurikabe':
  land={i for i in range(n*n) if i%n%2==0 and i//n%2==0}
  for _ in range(n*n*3):
   i=rng.randrange(n*n);q=land^{i};sea=set(range(n*n))-q
   if not sea or not connected(sea,lambda j:adjacent(j,n)):continue
   if any({j,j+1,j+n,j+n+1}<=sea for j in range(n*n) if j%n<n-1 and j//n<n-1):continue
   if any(len(p)>5 for p in components(q,lambda j:adjacent(j,n))):continue
   land=q
  clues=[0]*(n*n)
  for group in components(land,lambda i:adjacent(i,n)):clues[rng.choice(sorted(group))]=len(group)
  return {'game':game,'n':n,'clues':clues,'marks':[1 if v else 0 for v in clues]}
 if game=='slitherlink':
  area={rng.randrange(n*n)}
  for _ in range(n*n*3):
   border=sorted({v for i in area for v in adjacent(i,n)}-area)
   if not border:break
   q=area|{rng.choice(border)}
   if len(q)>n*n*.65:break
   counts={}
   for i in q:
    for e in cell_edges(n,i):counts[e]=counts.get(e,0)+1
   graph={}
   for e,c in counts.items():
    if c==1:
     for v in loop_edges(n)[e]:graph[v]=graph.get(v,0)+1
   if all(v==2 for v in graph.values()):area=q
  counts={}
  for i in area:
   for e in cell_edges(n,i):counts[e]=counts.get(e,0)+1
  solution={e for e,v in counts.items() if v==1}
  clues=[sum(e in solution for e in cell_edges(n,i)) for i in range(n*n)]
  return {'game':game,'n':n,'clues':clues,'marks':[0]*len(loop_edges(n))}
 islands=[[x,y,0] for y in range(0,n,2) for x in range(0,n,2) if rng.random()<.82]
 if len(islands)<4:return None
 edges=hashi_edges(islands);order=list(range(len(edges)));rng.shuffle(order);chosen=[];groups=[{i} for i in range(len(islands))]
 for e in order:
  a,c=edges[e];ga=next(p for p in groups if a in p);gc=next(p for p in groups if c in p)
  if ga is gc or any(bridge_cross(edges[e],edges[j],islands) for j in chosen):continue
  ga.update(gc);groups.remove(gc);chosen.append(e)
 if len(groups)>1:return None
 for e in order:
  if e not in chosen and rng.random()<.2 and not any(bridge_cross(edges[e],edges[j],islands) for j in chosen):chosen.append(e)
 for e in chosen:
  v=rng.choice((1,1,2))
  for i in edges[e]:islands[i][2]+=v
 return {'game':game,'n':n,'islands':islands,'marks':[0]*len(edges)}

def make(game,seed,proof=None,level=1):
 if game not in GAMES:raise ValueError('Unknown puzzle')
 level=max(1,level or 1);rng=random.Random(seed)
 n=5+min(4,(level-1)//60);tries=12+min(52,(level-1)//6);best=None;best_stats=None
 if game in ('nurikabe','hashi'):tries*=3
 for _ in range(tries):
  b=candidate(game,rng,n)
  if b is None:continue
  a=analyze(b,700)
  if not a['unique']:continue
  key=(a['depth'],a['branches'],a['forced'])
  old_key=(best_stats['depth'],best_stats['branches'],best_stats['forced']) if best_stats else None
  if best is None or (key<old_key if level<=10 else key>old_key):best=b;best_stats=a
  target=0 if level<=10 else min(9,2+level//60)
  if _>=5 and (best_stats['depth']==0 if level<=10 else best_stats['depth']>=target):break
 if best is None:
  # Bounded retry with a separate seed, never issue an unverified board.
  raise ValueError('문제를 준비하지 못했어요. 잠시 후 다시 시도해주세요.')
 if game=='slitherlink':
  order=list(range(n*n));rng.shuffle(order)
  for i in order[:min(n*n//2,level//3)]:
   old=best['clues'][i];best['clues'][i]=-1;q=analyze(best,700)
   if q['unique']:best_stats=q
   else:best['clues'][i]=old
 if proof is not None:proof.extend([i,v] for i,v in enumerate(best_stats['solution']) if v!=best['marks'][i])
 return best
