"""Five deterministic logic puzzles, authoritative moves and KST daily boards."""
from collections import deque
from functools import lru_cache
import copy
import hashlib
import json
import random
import secrets
import time
from datetime import datetime, timezone, timedelta

GAMES={'parking':'마리 주차장 탈출','power':'전력 연결','warehouse':'보석 창고','untangle':'엉킨 실 풀기','light':'빛의 미로','shikaku':'마리 사각 퍼즐'}
KST=timezone(timedelta(hours=9))
DIRS=((0,-1),(1,0),(0,1),(-1,0))

# Switch at a KST day boundary so every entrant receives the same daily board.
DAILY_EXPERT_FROM='2026-09-24'
DAILY_EXPERT_LEVEL=40

def daily_level(day):return DAILY_EXPERT_LEVEL if day>=DAILY_EXPERT_FROM else None

def rotate(mask):return ((mask<<1)&15)|(mask>>3)
def cells(car,n):return [car['y']*n+car['x']+i*(1 if car['axis']=='h' else n) for i in range(car['length'])]
def car_move(b,i,d):
 if not 0<=i<len(b['cars']) or d not in (-1,1):return False
 c=b['cars'][i];q={**c,'x':c['x']+(d if c['axis']=='h' else 0),'y':c['y']+(d if c['axis']=='v' else 0)};n=b['n']
 if q['x']<0 or q['y']<0 or q['x']+(q['length'] if q['axis']=='h' else 1)>n or q['y']+(q['length'] if q['axis']=='v' else 1)>n:return False
 occupied={v for j,a in enumerate(b['cars']) if i!=j for v in cells(a,n)}
 if occupied.intersection(cells(q,n)):return False
 b['cars'][i]=q;return True

def parking_neighbors(state,cars):
 occupied=set()
 for i,c in enumerate(cars):
  for k in range(c['length']):occupied.add((state[i]+k,c['y']) if c['axis']=='h' else (c['x'],state[i]+k))
 for i,c in enumerate(cars):
  for d in (-1,1):
   z=state[i]-1 if d<0 else state[i]+c['length'];p=(z,c['y']) if c['axis']=='h' else (c['x'],z)
   if 0<=z<6 and p not in occupied:
    q=list(state);q[i]+=d;yield tuple(q),[i,d]

@lru_cache(maxsize=1)
def parking_difficulties():
 # Enumerate this compact lane layout once, then measure minimum legal moves to any exit.
 cars=make('parking',12)['cars'];start=tuple(c['x'] if c['axis']=='h' else c['y'] for c in cars)
 seen={start};todo=deque([start])
 while todo:
  for q,_ in parking_neighbors(todo.popleft(),cars):
   if q not in seen:seen.add(q);todo.append(q)
 distance={q:0 for q in seen if q[0]==4};todo=deque(sorted(distance))
 while todo:
  state=todo.popleft()
  for q,_ in parking_neighbors(state,cars):
   if q not in distance:distance[q]=distance[state]+1;todo.append(q)
 return cars,distance

def free_parking(seed,level,proof):
 r=random.Random(seed);cars,dist=parking_difficulties();target=min(max(dist.values()),2+level)
 state=r.choice(sorted(q for q,d in dist.items() if d==target));result=copy.deepcopy(cars)
 for i,c in enumerate(result):c['x' if c['axis']=='h' else 'y']=state[i]
 if proof is not None:
  while dist[state]:
   state,event=next((q,e) for q,e in parking_neighbors(state,cars) if dist[q]==dist[state]-1);proof.append(event)
 return {'game':'parking','n':6,'cars':result}

def make(game,seed,proof=None,level=None):
 r=random.Random(seed)
 if game=='shikaku':return make_shikaku(seed,proof,level)
 if game=='parking':
  if level is not None:return free_parking(seed,level,proof)
  cars=[(4,2,2,'h'),(0,0,3,'v'),(1,0,2,'h'),(3,0,2,'v'),(4,0,2,'h'),(1,3,3,'h'),(4,3,2,'v'),(0,5,3,'h'),(5,3,3,'v'),(1,1,2,'v')]
  b={'game':game,'n':6,'cars':[dict(x=x,y=y,length=l,axis=a) for x,y,l,a in cars]}
  backwards=[]
  for _ in range(600):
   i=r.randrange(len(cars));d=r.choice((-1,1))
   if car_move(b,i,d):backwards.append([i,-d])
  while b['cars'][0]['x']>0:
   if not car_move(b,0,-1):break
   backwards.append([0,1])
  if solved(b):return make(game,seed+1,proof,level)
  if proof is not None:proof.extend(reversed(backwards))
  return b
 if game=='power':
  n=5 if level is None else min(8,3+(level-1)//3);m=[0]*(n*n);seen={0};todo=[0]
  while todo:
   a=todo[-1];neighbors=[(k,(a//n+dy)*n+a%n+dx) for k,(dx,dy) in enumerate(DIRS) if 0<=a%n+dx<n and 0<=a//n+dy<n and (a//n+dy)*n+a%n+dx not in seen]
   if not neighbors:todo.pop();continue
   k,c=r.choice(neighbors);m[a]|=1<<k;m[c]|=1<<((k+2)%4);seen.add(c);todo.append(c)
  correct=m[:]
  for i in range(len(m)):
   for _ in range(r.randrange(4)):m[i]=rotate(m[i])
  b={'game':game,'n':n,'tiles':m};
  if solved(b):m[0]=rotate(m[0])
  if proof is not None:
   for i,mask in enumerate(m):
    while mask!=correct[i]:proof.append([i]);mask=rotate(mask)
  return b
 if game=='warehouse':
  n=7 if level is None else min(9,6+(level-1)//4)
  walls=[i for i in range(n*n) if i%n in (0,n-1) or i//n in (0,n-1)]
  if level is None:walls += [10,38];goals=[16,18,32];p=24
  else:
   candidates=[y*n+x for y in range(2,n-2) for x in range(2,n-2)];goals=r.sample(candidates,min(8,len(candidates),2+(level-1)//3));p=n+1
  boxes=goals[:];backwards=[]
  for _ in range(800 if level is None else min(2500,150+level*100)):
   d=r.randrange(4);dx,dy=DIRS[d];q=p+dx+dy*n
   if q in walls or q in boxes:continue
   behind=p-dx-dy*n
   if behind in boxes and r.random()<.75:boxes[boxes.index(behind)]=p
   p=q;backwards.append([(d+2)%4])
  if set(boxes)==set(goals):return make(game,seed+1,proof,level)
  if proof is not None:proof.extend(reversed(backwards))
  return {'game':game,'n':n,'walls':walls,'goals':goals,'boxes':boxes,'player':p}
 if game=='untangle':
  import math
  side=3 if level is None else min(5,2+(level-1)//4);count=side*side
  nodes=[[int(500+380*math.cos(i*2*math.pi/count)),int(500+380*math.sin(i*2*math.pi/count))] for i in range(count)];r.shuffle(nodes)
  edges=[]
  for y in range(side):
   for x in range(side):
    a=y*side+x
    if x<side-1:edges.append([a,a+1])
    if y<side-1:edges.append([a,a+side])
    if x<side-1 and y<side-1 and r.random()<(.6 if level is None else min(.9,.2+level*.05)):edges.append([a,a+side+1])
  b={'game':game,'n':count,'nodes':nodes,'edges':edges}
  if solved(b):return make(game,seed+1,proof,level)
  if proof is not None:proof.extend([[i,100+round((i%side)*800/(side-1)),100+round((i//side)*800/(side-1))] for i in range(count)])
  return b
 n=9 if level is None else min(11,5+2*((level-1)//4));y=n//2;source=y*n;mirrors={};path={y*n+x for x in range(n)}
 for x in range(1,n-1,2):
  ny=r.choice([a for a in range(1,n-1) if a!=y]);down=ny>y
  mirrors[y*n+x]=1 if down else 0;mirrors[ny*n+x]=1 if down else 0
  path.update(a*n+x for a in range(min(y,ny),max(y,ny)+1));path.update(ny*n+a for a in range(x,n));y=ny
 target=y*n+n-1
 for i in r.sample([i for i in range(n*n) if i not in path],min(4 if level is None else 1+level//2,sum(i not in path for i in range(n*n)))):mirrors[i]=r.randrange(2)
 available=[i for i in range(n*n) if i not in path and i not in mirrors];walls=r.sample(available,min(len(available),8 if level is None else 2+level))
 b={'game':game,'n':n,'source':source,'target':target,'walls':walls,'mirrors':{str(i):r.randrange(2) for i in mirrors}}
 if solved(b):b['mirrors'][str(source+1)]=1-b['mirrors'][str(source+1)]
 if proof is not None:proof.extend([[i] for i,v in mirrors.items() if b['mirrors'][str(i)]!=v])
 return b

def powered(b):
 seen={0};todo=[0];n=b['n']
 while todo:
  a=todo.pop()
  for k,(dx,dy) in enumerate(DIRS):
   x=a%n+dx;y=a//n+dy;c=y*n+x
   if b['tiles'][a]&(1<<k) and 0<=x<n and 0<=y<n and b['tiles'][c]&(1<<((k+2)%4)) and c not in seen:seen.add(c);todo.append(c)
 return seen

def beam(b):
 n=b['n'];x=b['source']%n;y=b['source']//n;dx=1;dy=0;seen=set();path=[]
 for _ in range(n*n*4):
  if not(0<=x<n and 0<=y<n):break
  a=y*n+x;key=(a,dx,dy)
  if key in seen:break
  seen.add(key);path.append(a)
  if a in b['walls'] or a==b['target']:break
  if str(a) in b['mirrors']:
   dx,dy=(-dy,-dx) if b['mirrors'][str(a)]==0 else (dy,dx)
  x+=dx;y+=dy
 return path

def crossed(b):
 def orient(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 def on(a,b,c):return min(a[0],b[0])<=c[0]<=max(a[0],b[0]) and min(a[1],b[1])<=c[1]<=max(a[1],b[1])
 bad=set();edges=b['edges'];p=b['nodes']
 for i,(a,c) in enumerate(edges):
  for j in range(i):
   u,v=edges[j]
   if len({a,c,u,v})<4:
    shared=next(iter({a,c}&{u,v}));other=c if a==shared else a;last=v if u==shared else u
    if orient(p[shared],p[other],p[last])==0 and sum((p[other][k]-p[shared][k])*(p[last][k]-p[shared][k]) for k in (0,1))>0:bad.update((i,j))
    continue
   q=[orient(p[a],p[c],p[u]),orient(p[a],p[c],p[v]),orient(p[u],p[v],p[a]),orient(p[u],p[v],p[c])]
   if q[0]*q[1]<0 and q[2]*q[3]<0 or q[0]==0 and on(p[a],p[c],p[u]) or q[1]==0 and on(p[a],p[c],p[v]) or q[2]==0 and on(p[u],p[v],p[a]) or q[3]==0 and on(p[u],p[v],p[c]):bad.update((i,j))
 return bad

def solved(b):
 g=b['game']
 if g=='shikaku':
  covered=set()
  for rect in b['rects']:
   cells=shikaku_cells(b,rect)
   if cells is None or covered.intersection(cells):return False
   covered.update(cells)
  return len(covered)==b['n']**2
 if g=='parking':return b['cars'][0]['x']==b['n']-2
 if g=='warehouse':return set(b['boxes'])==set(b['goals'])
 if g=='power':return len(powered(b))==b['n']**2
 if g=='light':return beam(b)[-1]==b['target']
 p=b['nodes']
 return not crossed(b) and all((a[0]-c[0])**2+(a[1]-c[1])**2>=1600 for i,a in enumerate(p) for c in p[:i])

def move(b,e):
 if not isinstance(e,list) or not e or any(type(v) is not int for v in e):return False
 g=b['game'];n=b['n']
 if g=='shikaku':
  if len(e)==2 and e[0]==-1 and 0<=e[1]<len(b['rects']):
   b['rects'].pop(e[1]);return True
  cells=shikaku_cells(b,e)
  if cells is None:return False
  if any(cells.intersection(shikaku_cells(b,rect)) for rect in b['rects']):return False
  b['rects'].append(e[:]);return True
 if g=='parking':return len(e)==2 and car_move(b,*e)
 if g=='power' and len(e)==1 and 0<=e[0]<n*n:b['tiles'][e[0]]=rotate(b['tiles'][e[0]]);return True
 if g=='light' and len(e)==1 and str(e[0]) in b['mirrors']:b['mirrors'][str(e[0])]=1-b['mirrors'][str(e[0])];return True
 if g=='untangle' and len(e)==3 and 0<=e[0]<len(b['nodes']) and all(30<=v<=970 for v in e[1:]) and b['nodes'][e[0]]!=e[1:]:b['nodes'][e[0]]=e[1:];return True
 if g=='warehouse' and len(e)==1 and 0<=e[0]<4:
  dx,dy=DIRS[e[0]];p=b['player'];x=p%n+dx;y=p//n+dy;q=y*n+x
  if not(0<=x<n and 0<=y<n) or q in b['walls']:return False
  if q in b['boxes']:
   z=q+dx+dy*n
   if not(0<=x+dx<n and 0<=y+dy<n) or z in b['walls'] or z in b['boxes']:return False
   b['boxes'][b['boxes'].index(q)]=z
  b['player']=q;return True
 return False

def apply(state,event):
 if state['done']:raise ValueError('이미 완료한 퍼즐이에요.')
 if event=='reset':state['board']=copy.deepcopy(state['initial']);state['history']=[]
 elif event=='undo':
  if not state['history']:raise ValueError('되돌릴 이동이 없어요.')
  state['board']=state['history'].pop()
 else:
  board=copy.deepcopy(state['board'])
  if not move(board,event):raise ValueError('이동할 수 없는 위치예요.')
  state['history']=(state['history']+[state['board']])[-50:];state['board']=board
 state['moves']+=1;state['done']=solved(state['board'])

def shikaku_cells(b,rect):
 if len(rect)!=4 or any(type(v) is not int for v in rect):return None
 x1,y1,x2,y2=rect;n=b['n']
 if not(0<=x1<=x2<n and 0<=y1<=y2<n):return None
 cells={y*n+x for y in range(y1,y2+1) for x in range(x1,x2+1)}
 clues=[b['clues'][i] for i in cells if b['clues'][i]]
 return cells if len(clues)==1 and clues[0]==len(cells) else None

def shikaku_unique(b):
 n=b['n'];groups=[]
 for i,area in enumerate(b['clues']):
  if not area:continue
  masks=[]
  for w in range(1,n+1):
   if area%w:continue
   h=area//w
   if h>n:continue
   for x in range(max(0,i%n-w+1),min(i%n,n-w)+1):
    for y in range(max(0,i//n-h+1),min(i//n,n-h)+1):
     cells=shikaku_cells(b,[x,y,x+w-1,y+h-1])
     if cells is not None:masks.append(sum(1<<c for c in cells))
  groups.append(masks)
 nodes=0
 def search(left,occupied):
  nonlocal nodes
  nodes+=1
  if nodes>10000:return 2
  if not left:return 1
  options=[(i,[m for m in group if not m&occupied]) for i,group in enumerate(left)]
  index,choices=min(options,key=lambda item:len(item[1]))
  rest=left[:index]+left[index+1:];count=0
  for mask in choices:
   count+=search(rest,occupied|mask)
   if count>=2:return 2
  return count
 return search(groups,0)==1

def make_shikaku(seed,proof=None,level=None):
 r=random.Random(seed);n=8 if level is None else min(10,5+(level-1)//4)
 for attempt in range(100):
  rects=[]
  def split(x,y,w,h):
   if w*h<=3 or w*h<=10 and r.random()<.3:
    rects.append([x,y,x+w-1,y+h-1]);return
   vertical=w>1 and (h==1 or r.random()<w/(w+h))
   if vertical:
    cut=r.randrange(1,w);split(x,y,cut,h);split(x+cut,y,w-cut,h)
   else:
    cut=r.randrange(1,h);split(x,y,w,cut);split(x,y+cut,w,h-cut)
  split(0,0,n,n)
  clues=[0]*(n*n)
  for x,y,x2,y2 in rects:clues[r.randint(y,y2)*n+r.randint(x,x2)]=(x2-x+1)*(y2-y+1)
  b={'game':'shikaku','n':n,'clues':clues,'rects':[]}
  if shikaku_unique(b):break
 else:
  # Guaranteed unique fallback: each row has one clue in the same column.
  column=r.randrange(n);b={'game':'shikaku','n':n,'clues':[n if i%n==column else 0 for i in range(n*n)],'rects':[]}
  rects=[[0,y,n-1,y] for y in range(n)]
 if proof is not None:proof.extend(rects)
 return b

def make_shikaku_challenge(seed,proof=None,level=1):
 # Prefer ambiguous rectangle shapes over single cells and obvious full-row strips.
 r=random.Random(seed);n=min(12,7+(level-1)//4);best=None;best_score=-1;unique=0
 for attempt in range(160):
  rects=[]
  def split(x,y,w,h):
   axes=([True] if w>=4 else [])+([False] if h>=4 else [])
   if not axes or w*h<=12 and r.random()<.65:
    rects.append([x,y,x+w-1,y+h-1]);return
   if r.choice(axes):
    cut=r.randint(2,w-2);split(x,y,cut,h);split(x+cut,y,w-cut,h)
   else:
    cut=r.randint(2,h-2);split(x,y,w,cut);split(x,y+cut,w,h-cut)
  split(0,0,n,n)
  if len(rects)<4:continue
  clues=[0]*(n*n)
  for x,y,x2,y2 in rects:clues[r.randint(y,y2)*n+r.randint(x,x2)]=(x2-x+1)*(y2-y+1)
  b={'game':'shikaku','n':n,'clues':clues,'rects':[]}
  if not shikaku_unique(b):continue
  score=0
  for i,area in enumerate(clues):
   if not area:continue
   choices=0
   for w in range(1,n+1):
    if area%w or area//w>n:continue
    h=area//w
    for x in range(max(0,i%n-w+1),min(i%n,n-w)+1):
     for y in range(max(0,i//n-h+1),min(i//n,n-h)+1):
      choices+=shikaku_cells(b,[x,y,x+w-1,y+h-1]) is not None
   score+=min(choices-1,8)
  if score>best_score:best=(b,rects);best_score=score
  unique+=1
  if unique>=12:break
 if best is None:return make_shikaku(seed,proof,level)
 if proof is not None:proof.extend(best[1])
 return best[0]

class Puzzles:
 def __init__(self,b,error):
  self.b=b;self.db=b.db;self.Error=error
  self.db.executescript('''CREATE TABLE IF NOT EXISTS mari_web_puzzles(id TEXT PRIMARY KEY,user_id TEXT,guild_id TEXT,game TEXT,mode TEXT,day TEXT,created REAL,last REAL,state TEXT,seq INTEGER DEFAULT 0,done INTEGER DEFAULT 0,moves INTEGER DEFAULT 0,elapsed REAL DEFAULT 0);
  CREATE UNIQUE INDEX IF NOT EXISTS puzzle_daily_user ON mari_web_puzzles(user_id,game,day) WHERE mode='daily';
  CREATE INDEX IF NOT EXISTS puzzle_ranking ON mari_web_puzzles(game,day,mode,done,moves,elapsed);
  CREATE INDEX IF NOT EXISTS puzzle_resume ON mari_web_puzzles(user_id,game,mode,created);''');self.db.commit()
 def day(self):return datetime.now(KST).date().isoformat()
 def public(self,row):
  state=json.loads(row[8])
  if row[4]=='free' and state.get('level') is None:state['level']=1+self.db.execute("SELECT COUNT(*) FROM mari_web_puzzles WHERE user_id=? AND game=? AND mode='free' AND done=1 AND created<?",(row[1],row[3],row[6])).fetchone()[0]
  return {'id':row[0],'game':row[3],'mode':row[4],'day':row[5],'created':row[6],'elapsed':row[12],'seq':row[9],**state}
 def start(self,member,data):
  game=data.get('game');mode=data.get('mode','daily');day=self.day()
  if game not in GAMES or mode not in ('daily','free'):raise self.Error('게임 모드를 확인해주세요.')
  request,fp,old=self.b.economy.receipt(member,data,'puzzles/start')
  if old:return self.public(self.db.execute('SELECT * FROM mari_web_puzzles WHERE id=?',(old['id'],)).fetchone())
  row=self.db.execute('SELECT * FROM mari_web_puzzles WHERE user_id=? AND game=? AND mode=? AND (day=? OR mode=\'free\') ORDER BY created DESC LIMIT 1',(str(member.id),game,mode,day)).fetchone()
  with self.db:
   if not row or mode=='free' and row[10]:
    if mode=='daily':self.b.economy.consume_ticket(member.id)
    seed=int(hashlib.sha256(('puzzles-v1:'+game+':'+day).encode()).hexdigest()[:16],16) if mode=='daily' else secrets.randbits(32)
    level=1+self.db.execute("SELECT COUNT(*) FROM mari_web_puzzles WHERE user_id=? AND game=? AND mode='free' AND done=1",(str(member.id),game)).fetchone()[0] if mode=='free' else None
    board=make_shikaku_challenge(seed,level=level if mode=='free' else DAILY_EXPERT_LEVEL) if game=='shikaku' and (mode=='free' or day>='2026-09-25') else make(game,seed,level=daily_level(day) if mode=='daily' else level)
    state={'board':board,'initial':copy.deepcopy(board),'history':[],'moves':0,'done':False,'level':level};jid=secrets.token_urlsafe(24);now=time.time()
    self.db.execute('INSERT INTO mari_web_puzzles(id,user_id,guild_id,game,mode,day,created,last,state) VALUES(?,?,?,?,?,?,?,?,?)',(jid,str(member.id),str(member.guild.id),game,mode,day,now,now,json.dumps(state)))
    row=self.db.execute('SELECT * FROM mari_web_puzzles WHERE id=?',(jid,)).fetchone()
   self.b.economy.remember(request,member.id,fp,{'id':row[0]})
  return self.public(row)
 def control(self,member,data):
  row=self.db.execute('SELECT * FROM mari_web_puzzles WHERE id=? AND user_id=?',(data.get('id'),str(member.id))).fetchone()
  if not row:raise self.Error('퍼즐을 찾을 수 없어요.',404)
  seq=data.get('seq');events=data.get('events')
  if type(seq) is not int or not isinstance(events,list) or not 1<=len(events)<=30:raise self.Error('이동 기록을 확인해주세요.')
  if seq<=row[9] or row[10]:return self.public(row)
  if seq!=row[9]+1:raise self.Error('연결 상태를 다시 확인해주세요.',409)
  state=json.loads(row[8])
  try:
   for event in events:apply(state,event)
  except ValueError as e:raise self.Error(str(e),400)
  now=time.time();elapsed=max(0,now-row[6])
  with self.db:self.db.execute('UPDATE mari_web_puzzles SET state=?,seq=?,last=?,done=?,moves=?,elapsed=? WHERE id=?',(json.dumps(state),seq,now,int(state['done']),state['moves'],elapsed,row[0]))
  return self.public(self.db.execute('SELECT * FROM mari_web_puzzles WHERE id=?',(row[0],)).fetchone())
 def ranking(self,uid,game,mode='daily'):
  from mari_web_rankings import Rankings
  if mode=='free':
   rows=self.db.execute("SELECT user_id,state,moves,elapsed,last,ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created,id) FROM mari_web_puzzles WHERE game=? AND mode='free' AND done=1",(game,)).fetchall()
   best={}
   for user,state,moves,elapsed,last,completed in rows:
    level=json.loads(state).get('level') or completed
    key=(-level,moves,elapsed,last,user)
    if user not in best or key<best[user][0]:best[user]=(key,{'userId':user,'value':level,'score':level,'moves':moves,'averageMs':round(elapsed*1000)})
   result=Rankings(self.b,self.Error).result([entry for _,entry in sorted(best.values(),key=lambda item:item[0])],uid,'level','누적 최고 클리어 단계 → 해당 단계의 적은 이동 횟수 → 짧은 소요 시간 → 먼저 완료한 순서. 진행 중인 단계는 제외해요.')
   result['todayStarted']=bool(self.db.execute("SELECT 1 FROM mari_web_puzzles WHERE user_id=? AND game=? AND mode='daily' AND day=?",(str(uid),game,self.day())).fetchone())
   return result
  order='elapsed,moves,last,user_id' if game=='shikaku' else 'moves,elapsed,last,user_id'
  rows=self.db.execute("SELECT user_id,moves,elapsed FROM mari_web_puzzles WHERE game=? AND day=? AND mode='daily' AND done=1 ORDER BY "+order,(game,self.day())).fetchall()
  result=Rankings(self.b,self.Error).result([{'userId':u,'value':m,'score':m,'averageMs':round(t*1000)} for u,m,t in rows],uid,'moves','오늘의 공통 퍼즐 · 적은 이동 횟수 → 짧은 소요 시간 → 먼저 완료한 순서. 되돌리기·처음부터도 이동에 포함돼요. 오늘의 도전은 최초 완료 기록으로 확정돼요.')
  if game=='shikaku':
   for entry in result['entries']:entry['value']=entry['averageMs']/1000;entry['score']=entry['value']
   if result.get('mine'):result['mine']['value']=result['mine']['averageMs']/1000;result['mine']['score']=result['mine']['value']
   result['metric']='seconds';result['note']='오늘의 공통 퍼즐 · 짧은 소요 시간 → 적은 이동 횟수 → 먼저 완료한 순서. 최초 시작부터 시간을 재며 첫 완료 기록으로 확정해요.'
  result['todayStarted']=bool(self.db.execute("SELECT 1 FROM mari_web_puzzles WHERE user_id=? AND game=? AND mode='daily' AND day=?",(str(uid),game,self.day())).fetchone())
  result['day']=self.day();return result
