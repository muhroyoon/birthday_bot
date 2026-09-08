"""Server-authoritative small arcade games. Clients send controls, never scores."""
import json
import math
import secrets
import time

GAMES = {'fishing':'마리 낚시','runner':'장애물 달리기','memory':'기억력 게임',
         'tower':'타워 쌓기','territory':'땅따먹기','dodge':'탄막 피하기'}

def rand(s, n):
 s['rng'] = (s['rng'] * 1664525 + 1013904223) & 0xffffffff
 return s['rng'] % n

def initial(game, seed):
 s = dict(game=game,rng=seed,tick=0,score=0,done=False,lives=3,x=260,y=300,objects=[],message='시작!',seq=0)
 if game=='runner':s.update(y=300,vy=0)
 if game=='dodge':s.update(y=320,immune=0)
 if game=='tower':s.update(x=0,dir=1,width=190,blocks=[{'x':165,'w':190}],combo=0)
 if game=='memory':s.update(sequence=[rand(s,4)],level=1,index=0,phase='show',phaseAt=0)
 if game=='fishing':s.update(phase='wait',until=20+rand(s,25),tension=50,progress=0,needle=0,fish=[])
 if game=='territory':
  s.update(x=0,y=0,claimed=[i for i in range(280) if i%20 in (0,19) or i//20 in (0,13)],trail=[],enemy={'x':10,'y':7,'dx':1,'dy':1})
 return s

def step(s, x, y, tap):
 if s['done']:return
 s['tick']+=1;t=s['tick'];g=s['game']
 if t>=900:s['done']=True;s['message']='시간 종료';return
 if g=='runner':
  if tap and s['y']>=300:s['vy']=-27
  s['vy']+=3;s['y']=min(300,s['y']+s['vy'])
  if s['y']==300:s['vy']=0
  if t%max(10,22-t//100)==0:s['objects'].append({'id':t,'x':540,'y':310,'w':22+rand(s,20),'h':30+rand(s,30)})
  for o in s['objects']:o['x']-=10+t//160
  for o in s['objects']:
   if not o.get('hit') and o['x']<100 and o['x']+o['w']>76 and s['y']+24>334-o['h']:
    s['lives']-=1;o['hit']=True;s['message']='충돌!'
  s['objects']=[o for o in s['objects'] if o['x']>-50];s['score']=t
 elif g=='dodge':
  s['x']=max(12,min(508,s['x']+x*13));s['y']=max(12,min(348,s['y']+y*13))
  if t%max(3,10-t//140)==0:
   ox=rand(s,500)+10;dx=s['x']-ox;dy=s['y']+10;d=max(1,math.hypot(dx,dy))
   s['objects'].append({'id':t,'x':ox,'y':-10,'dx':dx/d*9,'dy':dy/d*9})
  for o in s['objects']:o['x']+=o['dx'];o['y']+=o['dy']
  if t>s['immune'] and any(math.hypot(o['x']-s['x'],o['y']-s['y'])<17 for o in s['objects']):s['lives']-=1;s['immune']=t+15;s['message']='피격!'
  s['objects']=[o for o in s['objects'] if -30<o['x']<550 and -30<o['y']<400];s['score']=t
 elif g=='tower':
  s['x']+=s['dir']*(7+len(s['blocks'])//3)
  if s['x']<0 or s['x']+s['width']>520:s['dir']*=-1;s['x']=max(0,min(520-s['width'],s['x']))
  if tap:
   last=s['blocks'][-1];left=max(last['x'],s['x']);right=min(last['x']+last['w'],s['x']+s['width'])
   if right-left<8:s['done']=True;s['message']='블록이 떨어졌어요';return
   perfect=abs(last['x']-s['x'])<=8
   if perfect:left=last['x'];right=left+last['w']
   s['combo']=s['combo']+1 if perfect else 0;s['width']=right-left;s['blocks'].append({'x':left,'w':right-left})
   s['score']+=100+(50 if perfect else 0);s['x']=0;s['dir']=1;s['message']='퍼펙트!' if perfect else f"{len(s['blocks'])-1}층 성공"
   if len(s['blocks'])>=26:s['done']=True;s['message']='25층 완성!'
 elif g=='memory':
  seq=s['sequence']
  if s['phase']=='show' and t-s['phaseAt']>=len(seq)*8+8:s['phase']='input';s['message']='순서대로 눌러주세요'
  elif s['phase']=='input' and tap:
   if tap-1!=seq[s['index']]:s['done']=True;s['message']='아쉬워요! 순서가 달랐어요';return
   s['index']+=1
   if s['index']==len(seq):
    s['score']+=len(seq)*100;s['level']+=1;s['index']=0;s['sequence'].append(rand(s,4));s['phase']='show';s['phaseAt']=t;s['message']='다음 순서를 기억하세요'
    if s['level']>12:s['done']=True;s['message']='12단계 완성!'
 elif g=='fishing':
  if s['phase']=='wait' and t>=s['until']:s['phase']='bite';s['until']=t+12;s['message']='입질! 지금 낚아채세요'
  elif s['phase']=='bite':
   if tap:s.update(phase='fight',progress=0,tension=50,message='초록 구간에서 누르고 버티세요')
   elif t>=s['until']:s['phase']='wait';s['until']=t+20+rand(s,25);s['message']='놓쳤어요. 다음 입질을 기다려요'
  elif s['phase']=='fight':
   s['needle']=(s.get('needle',0)+7)%200;position=s['needle'] if s['needle']<100 else 200-s['needle']
   good=35<=position<=70
   s['tension']+= (3 if good else -5) if x==1 else -1
   if x==1 and good:s['progress']+=4
   if s['progress']>=100:
    roll=rand(s,100);kind=0 if roll<55 else 1 if roll<85 else 2 if roll<97 else 3
    fish={'name':['붕어','무지개송어','푸른참치','황금용왕어'][kind],'size':15+rand(s,60)+kind*20,'rarity':kind}
    s['fish'].append(fish);s['score']+=(kind+1)*100+fish['size'];s['message']=fish['name']+' 포획!';s['phase']='wait';s['until']=t+20+rand(s,25)
   elif s['tension']<=0:s['phase']='wait';s['until']=t+20+rand(s,25);s['message']='물고기가 달아났어요'
   s['tension']=min(100,s['tension'])
 elif g=='territory' and t%2==0:
  claimed=set(s['claimed']);trail=s['trail'];e=s['enemy']
  if x or y:
   nx=max(0,min(19,s['x']+x));ny=max(0,min(13,s['y']+(y if not x else 0)));cell=ny*20+nx
   if (nx,ny)!=(s['x'],s['y']):
    if cell in trail:s['lives']-=1;s['x']=0;s['y']=0;trail.clear()
    else:
     s['x']=nx;s['y']=ny
     if cell not in claimed:trail.append(cell)
     elif trail:
      walls=claimed|set(trail);outside=set();todo=[e['y']*20+e['x']]
      while todo:
       v=todo.pop()
       if v in outside or v in walls:continue
       outside.add(v)
       for q in (v-20,v+20,v-1,v+1):
        if 0<=q<280 and abs(q%20-v%20)+abs(q//20-v//20)==1:todo.append(q)
      claimed=set(range(280))-outside;s['claimed']=sorted(claimed);trail.clear();s['message']='영역 확보!'
  for axis,delta,limit in [('x','dx',19),('y','dy',13)]:
   nx=e['x']+(e[delta] if axis=='x' else 0);ny=e['y']+(e[delta] if axis=='y' else 0)
   if not(0<=nx<20 and 0<=ny<14) or ny*20+nx in claimed:e[delta]*=-1
   else:e[axis]+=e[delta]
  if e['y']*20+e['x'] in trail:
   s['lives']-=1;trail.clear();s['x']=0;s['y']=0;s['message']='선이 끊겼어요'
  s['score']=max(0,len(claimed)-64)*10
  if len(claimed)>=210:s['done']=True;s['message']='75% 점령 성공!';s['score']+=900-t
 if s['lives']<=0:s['done']=True;s['message']='도전 종료'

class Adventure:
 def __init__(self,b,error):
  self.b=b;self.db=b.db;self.Error=error
  self.db.executescript('''CREATE TABLE IF NOT EXISTS mari_web_adventures(id TEXT PRIMARY KEY,user_id TEXT,guild_id TEXT,game TEXT,state TEXT,created REAL,last REAL,done INTEGER DEFAULT 0,score INTEGER DEFAULT 0);
  CREATE INDEX IF NOT EXISTS adventure_ranks ON mari_web_adventures(game,done,score);
  CREATE UNIQUE INDEX IF NOT EXISTS adventure_active ON mari_web_adventures(user_id) WHERE done=0;''');self.db.commit()
 def public(self,row):
  if not row:return {'job':None}
  s=json.loads(row[4]);s.pop('rng',None)
  if s['game']=='memory':
   seq=s.pop('sequence');elapsed=s['tick']-s['phaseAt'];i=elapsed//8
   s['lit']=seq[i] if s['phase']=='show' and i<len(seq) and elapsed%8<5 else -1
  return {'job':{'id':row[0],**s},'balance':self.b.economy.balance(row[1])}
 def status(self,member):
  row=self.db.execute('SELECT * FROM mari_web_adventures WHERE user_id=? ORDER BY created DESC LIMIT 1',(str(member.id),)).fetchone()
  if row and not row[7] and time.time()-row[5]>=90:
   s=json.loads(row[4]);s['done']=True;s['message']='시간 종료'
   self.db.execute('UPDATE mari_web_adventures SET state=?,done=1 WHERE id=?',(json.dumps(s),row[0]));self.db.commit()
   row=self.db.execute('SELECT * FROM mari_web_adventures WHERE id=?',(row[0],)).fetchone()
  return self.public(row)
 def start(self,member,data):
  game=data.get('game')
  if game not in GAMES:raise self.Error('게임을 확인해주세요.')
  request,fp,old=self.b.economy.receipt(member,data,'adventure/start')
  if old:return self.public(self.db.execute('SELECT * FROM mari_web_adventures WHERE id=?',(old['id'],)).fetchone())
  self.status(member)
  active=self.db.execute('SELECT * FROM mari_web_adventures WHERE user_id=? AND done=0',(str(member.id),)).fetchone()
  if active:return self.public(active)
  with self.db:
   self.b.economy.debit(member.id,150000);jid=secrets.token_urlsafe(24);now=time.time();s=initial(game,secrets.randbits(32))
   self.db.execute('INSERT INTO mari_web_adventures VALUES(?,?,?,?,?,?,?,0,0)',(jid,str(member.id),str(member.guild.id),game,json.dumps(s),now,now))
   self.b.economy.remember(request,member.id,fp,{'id':jid})
   self.b.log_history(member.id,member.guild.id,GAMES[game],'입장권 구매',-150000)
  return self.public(self.db.execute('SELECT * FROM mari_web_adventures WHERE id=?',(jid,)).fetchone())
 def control(self,member,data):
  row=self.db.execute('SELECT * FROM mari_web_adventures WHERE id=? AND user_id=? AND guild_id=?',(data.get('id'),str(member.id),str(member.guild.id))).fetchone()
  if not row:raise self.Error('진행 중인 게임을 찾을 수 없어요.',404)
  s=json.loads(row[4]);seq=data.get('seq');x=data.get('x',0);y=data.get('y',0);tap=data.get('tap',0)
  if type(seq) is not int or type(x) is not int or type(y) is not int or type(tap) is not int or x not in (-1,0,1) or y not in (-1,0,1) or not 0<=tap<=4:raise self.Error('입력 값을 확인해주세요.')
  if seq<=s['seq'] or s['done']:return self.public(row)
  if seq!=s['seq']+1:raise self.Error('연결 상태를 다시 확인해주세요.',409)
  now=time.time();ticks=min(10,int((now-row[6])*10))
  if now-row[5]>=90:s['done']=True;s['message']='시간 종료'
  for i in range(ticks):step(s,x,y,tap if i==0 else 0)
  # Do not acknowledge a tap until at least one authoritative tick can process it.
  if ticks==0 and not s['done']:return self.public(row)
  s['seq']=seq
  with self.db:self.db.execute('UPDATE mari_web_adventures SET state=?,last=?,done=?,score=? WHERE id=?',(json.dumps(s),now,int(s['done']),s['score'],row[0]))
  return self.public(self.db.execute('SELECT * FROM mari_web_adventures WHERE id=?',(row[0],)).fetchone())
