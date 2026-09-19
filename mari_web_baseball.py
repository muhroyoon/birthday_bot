"""Fixed-entry number baseball; server-only answers and non-monetary best records."""
import json
import secrets
import time

COST=150000
LIMIT=120
BOARD='number_baseball_skill'

class Baseball:
 def __init__(self,b,error):
  self.b=b;self.db=b.db;self.Error=error
  self.db.executescript('''CREATE TABLE IF NOT EXISTS mari_web_baseball(id TEXT PRIMARY KEY,user_id TEXT,guild_id TEXT,answer TEXT,created REAL,guesses TEXT,done INTEGER DEFAULT 0,won INTEGER DEFAULT 0,elapsed REAL DEFAULT 0);
  CREATE UNIQUE INDEX IF NOT EXISTS baseball_active ON mari_web_baseball(user_id) WHERE done=0;
  CREATE INDEX IF NOT EXISTS baseball_user_time ON mari_web_baseball(user_id,created);''');self.db.commit()
 def public(self,row):
  if not row:return None
  return {'id':row[0],'created':row[4],'deadline':row[4]+LIMIT,'guesses':json.loads(row[5]),'done':bool(row[6]),'won':bool(row[7]),'elapsed':row[8],'answer':row[3] if row[6] else None}
 def expire(self,uid):
  with self.db:self.db.execute('UPDATE mari_web_baseball SET done=1,elapsed=? WHERE user_id=? AND done=0 AND created+?<=?',(LIMIT,str(uid),LIMIT,time.time()))
 def status(self,member):
  self.expire(member.id)
  row=self.db.execute('SELECT * FROM mari_web_baseball WHERE user_id=? ORDER BY created DESC LIMIT 1',(str(member.id),)).fetchone()
  return {'run':self.public(row),'balance':self.b.economy.balance(member.id)}
 def start(self,member,data):
  request,fp,old=self.b.economy.receipt(member,data,'baseball/start')
  self.expire(member.id)
  if old:
   row=self.db.execute('SELECT * FROM mari_web_baseball WHERE id=?',(old['id'],)).fetchone()
   return {'run':self.public(row),'balance':self.b.economy.balance(member.id)}
  row=self.db.execute('SELECT * FROM mari_web_baseball WHERE user_id=? AND done=0',(str(member.id),)).fetchone()
  with self.db:
   if not row:
    self.b.economy.consume_ticket(member.id)
    jid=secrets.token_urlsafe(24);answer=''.join(secrets.SystemRandom().sample('0123456789',4))
    self.db.execute('INSERT INTO mari_web_baseball(id,user_id,guild_id,answer,created,guesses) VALUES(?,?,?,?,?,?)',(jid,str(member.id),str(member.guild.id),answer,time.time(),'[]'))
    row=self.db.execute('SELECT * FROM mari_web_baseball WHERE id=?',(jid,)).fetchone()
   self.b.economy.remember(request,member.id,fp,{'id':row[0]})
  return {'run':self.public(row),'balance':self.b.economy.balance(member.id)}
 def guess(self,member,data):
  self.expire(member.id)
  row=self.db.execute('SELECT * FROM mari_web_baseball WHERE id=? AND user_id=?',(data.get('id'),str(member.id))).fetchone()
  if not row:raise self.Error('게임을 찾을 수 없어요.',404)
  guesses=json.loads(row[5]);seq=data.get('seq')
  if type(seq) is not int or seq<1:raise self.Error('입력 순서를 확인해주세요.')
  if row[6] or seq<=len(guesses):return {'run':self.public(row),'balance':self.b.economy.balance(member.id)}
  if seq!=len(guesses)+1:raise self.Error('게임 기록을 다시 불러와주세요.',409)
  value=data.get('guess')
  if not isinstance(value,str) or len(value)!=4 or any(c not in '0123456789' for c in value) or len(set(value))!=4:raise self.Error('서로 다른 숫자 4개를 입력해주세요.')
  if any(g['value']==value for g in guesses):raise self.Error('이미 입력한 숫자예요. 다른 조합으로 도전해주세요.')
  answer=row[3];strike=sum(a==b for a,b in zip(value,answer));ball=len(set(value)&set(answer))-strike
  guesses.append({'value':value,'strike':strike,'ball':ball});won=strike==4;done=won or len(guesses)>=8;elapsed=max(0,time.time()-row[4])
  if elapsed>=LIMIT:
   self.expire(member.id)
   return self.status(member)
  with self.db:
   self.db.execute('UPDATE mari_web_baseball SET guesses=?,done=?,won=?,elapsed=? WHERE id=?',(json.dumps(guesses),int(done),int(won),elapsed,row[0]))
   if won:self.b.weekly.record('baseball:'+row[0],BOARD,row[1],row[2],9-len(guesses),{'accuracy':100,'averageMs':round(elapsed*1000),'guesses':len(guesses)})
  return {'run':self.public(self.db.execute('SELECT * FROM mari_web_baseball WHERE id=?',(row[0],)).fetchone()),'balance':self.b.economy.balance(member.id)}
