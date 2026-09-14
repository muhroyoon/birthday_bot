"""Five deterministic logic puzzles, authoritative moves and KST daily boards."""
import copy
import hashlib
import json
import random
import secrets
import time
from datetime import datetime, timezone, timedelta

GAMES={'parking':'마리 주차장 탈출','power':'전력 연결','warehouse':'보석 창고','untangle':'엉킨 실 풀기','light':'빛의 미로'}
KST=timezone(timedelta(hours=9))
DIRS=((0,-1),(1,0),(0,1),(-1,0))

def rotate(mask):return ((mask<<1)&15)|(mask>>3)
def cells(car,n):return [car['y']*n+car['x']+i*(1 if car['axis']=='h' else n) for i in range(car['length'])]
def car_move(b,i,d):
 if not 0<=i<len(b['cars']) or d not in (-1,1):return False
 c=b['cars'][i];q={**c,'x':c['x']+(d if c['axis']=='h' else 0),'y':c['y']+(d if c['axis']=='v' else 0)};n=b['n']
 if q['x']<0 or q['y']<0 or q['x']+(q['length'] if q['axis']=='h' else 1)>n or q['y']+(q['length'] if q['axis']=='v' else 1)>n:return False
 occupied={v for j,a in enumerate(b['cars']) if i!=j for v in cells(a,n)}
 if occupied.intersection(cells(q,n)):return False
 b['cars'][i]=q;return True

def make(game,seed,proof=None):
 r=random.Random(seed)
 if game=='parking':
  cars=[(4,2,2,'h'),(0,0,3,'v'),(1,0,2,'h'),(3,0,2,'v'),(4,0,2,'h'),(1,3,3,'h'),(4,3,2,'v'),(0,5,3,'h'),(5,3,3,'v'),(1,1,2,'v')]
  b={'game':game,'n':6,'cars':[dict(x=x,y=y,length=l,axis=a) for x,y,l,a in cars]}
  backwards=[]
  for _ in range(600):
   i=r.randrange(len(cars));d=r.choice((-1,1))
   if car_move(b,i,d):backwards.append([i,-d])
  while b['cars'][0]['x']>0:
   if not car_move(b,0,-1):break
   backwards.append([0,1])
  if solved(b):return make(game,seed+1,proof)
  if proof is not None:proof.extend(reversed(backwards))
  return b
 if game=='power':
  n=5;m=[0]*(n*n);seen={0};todo=[0]
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
  n=7;walls=[i for i in range(n*n) if i%n in (0,n-1) or i//n in (0,n-1)]+[10,38];goals=[16,18,32];boxes=goals[:];p=24;backwards=[]
  for _ in range(800):
   d=r.randrange(4);dx,dy=DIRS[d];q=p+dx+dy*n
   if q in walls or q in boxes:continue
   behind=p-dx-dy*n
   if behind in boxes and r.random()<.75:boxes[boxes.index(behind)]=p
   p=q;backwards.append([(d+2)%4])
  if set(boxes)==set(goals):return make(game,seed+1,proof)
  if proof is not None:proof.extend(reversed(backwards))
  return {'game':game,'n':n,'walls':walls,'goals':goals,'boxes':boxes,'player':p}
 if game=='untangle':
  import math
  nodes=[[int(500+380*math.cos(i*2*math.pi/9)),int(500+380*math.sin(i*2*math.pi/9))] for i in range(9)];r.shuffle(nodes)
  edges=[]
  for y in range(3):
   for x in range(3):
    a=y*3+x
    if x<2:edges.append([a,a+1])
    if y<2:edges.append([a,a+3])
    if x<2 and y<2 and r.random()<.6:edges.append([a,a+4])
  if proof is not None:proof.extend([[i,100+(i%3)*400,100+(i//3)*400] for i in range(9)])
  return {'game':game,'n':9,'nodes':nodes,'edges':edges}
 n=9;y=4;mirrors={};path={y*n+x for x in range(n)}
 for x in (1,3,5,7):
  ny=r.choice([a for a in range(1,8) if a!=y]);down=ny>y
  mirrors[y*n+x]=1 if down else 0;mirrors[ny*n+x]=1 if down else 0
  path.update(a*n+x for a in range(min(y,ny),max(y,ny)+1));path.update(ny*n+a for a in range(x,n));y=ny
 target=y*n+8
 for i in r.sample([i for i in range(n*n) if i not in path],4):mirrors[i]=r.randrange(2)
 walls=r.sample([i for i in range(n*n) if i not in path and i not in mirrors],8)
 b={'game':game,'n':n,'source':36,'target':target,'walls':walls,'mirrors':{str(i):r.randrange(2) for i in mirrors}}
 if solved(b):b['mirrors']['37']=1-b['mirrors']['37']
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
 n=b['n'];x=0;y=4;dx=1;dy=0;seen=set();path=[]
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
 if g=='parking':return b['cars'][0]['x']==b['n']-2
 if g=='warehouse':return set(b['boxes'])==set(b['goals'])
 if g=='power':return len(powered(b))==b['n']**2
 if g=='light':return beam(b)[-1]==b['target']
 p=b['nodes']
 return not crossed(b) and all((a[0]-c[0])**2+(a[1]-c[1])**2>=1600 for i,a in enumerate(p) for c in p[:i])

def move(b,e):
 if not isinstance(e,list) or not e or any(type(v) is not int for v in e):return False
 g=b['game'];n=b['n']
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

class Puzzles:
 def __init__(self,b,error):
  self.b=b;self.db=b.db;self.Error=error
  self.db.executescript('''CREATE TABLE IF NOT EXISTS mari_web_puzzles(id TEXT PRIMARY KEY,user_id TEXT,guild_id TEXT,game TEXT,mode TEXT,day TEXT,created REAL,last REAL,state TEXT,seq INTEGER DEFAULT 0,done INTEGER DEFAULT 0,moves INTEGER DEFAULT 0,elapsed REAL DEFAULT 0);
  CREATE UNIQUE INDEX IF NOT EXISTS puzzle_daily_user ON mari_web_puzzles(user_id,game,day) WHERE mode='daily';
  CREATE INDEX IF NOT EXISTS puzzle_ranking ON mari_web_puzzles(game,day,mode,done,moves,elapsed);
  CREATE INDEX IF NOT EXISTS puzzle_resume ON mari_web_puzzles(user_id,game,mode,created);''');self.db.commit()
 def day(self):return datetime.now(KST).date().isoformat()
 def public(self,row):return {'id':row[0],'game':row[3],'mode':row[4],'day':row[5],'created':row[6],'elapsed':row[12],'seq':row[9],**json.loads(row[8])}
 def start(self,member,data):
  game=data.get('game');mode=data.get('mode','daily');day=self.day()
  if game not in GAMES or mode not in ('daily','free'):raise self.Error('게임 모드를 확인해주세요.')
  request,fp,old=self.b.economy.receipt(member,data,'puzzles/start')
  if old:return self.public(self.db.execute('SELECT * FROM mari_web_puzzles WHERE id=?',(old['id'],)).fetchone())
  row=self.db.execute('SELECT * FROM mari_web_puzzles WHERE user_id=? AND game=? AND mode=? AND (day=? OR mode=\'free\') ORDER BY created DESC LIMIT 1',(str(member.id),game,mode,day)).fetchone()
  with self.db:
   if not row or mode=='free' and row[10]:
    seed=int(hashlib.sha256(('puzzles-v1:'+game+':'+day).encode()).hexdigest()[:16],16) if mode=='daily' else secrets.randbits(32)
    board=make(game,seed);state={'board':board,'initial':copy.deepcopy(board),'history':[],'moves':0,'done':False};jid=secrets.token_urlsafe(24);now=time.time()
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
 def ranking(self,uid,game):
  from mari_web_rankings import Rankings
  rows=self.db.execute("SELECT user_id,moves,elapsed FROM mari_web_puzzles WHERE game=? AND day=? AND mode='daily' AND done=1 ORDER BY moves,elapsed,last,user_id",(game,self.day())).fetchall()
  result=Rankings(self.b,self.Error).result([{'userId':u,'value':m,'score':m,'averageMs':round(t*1000)} for u,m,t in rows],uid,'moves','오늘의 공통 퍼즐 · 적은 이동 횟수 → 짧은 소요 시간 → 먼저 완료한 순서. 되돌리기·처음부터도 이동에 포함돼요. 오늘의 도전은 최초 완료 기록으로 확정돼요.')
  result['day']=self.day();return result
