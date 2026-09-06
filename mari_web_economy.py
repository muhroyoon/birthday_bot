"""Virtual stock market and paid game passes, sharing Discord's balance table."""
from bisect import bisect_right
import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta, timezone

KST=timezone(timedelta(hours=9))
STOCKS=(('muro','머로증권','금융'),('jeumi','즈미테크','기술'),('samsung','삼성식품','식품'),('gimcheon','김천물류','물류'),('haerangsol','해랑솔에너지','에너지'),('harang','하랑건설','건설'),('hoon','훈이게임즈','게임'))
PAID={'aim','pubg','reaction','stopwatch','apple','snake','suika','2048','fortune'}

class Economy:
 def __init__(self,b,error):
  self.b=b;self.db=b.db;self.Error=error
  self.db.executescript('''
  CREATE TABLE IF NOT EXISTS mari_web_stocks(symbol TEXT PRIMARY KEY,price INTEGER NOT NULL,day TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS mari_web_stock_days(symbol TEXT,day TEXT,open INTEGER,close INTEGER,PRIMARY KEY(symbol,day));
  CREATE TABLE IF NOT EXISTS mari_web_stock_news(symbol TEXT,slot TEXT,headline TEXT,body TEXT,PRIMARY KEY(symbol,slot));
  CREATE TABLE IF NOT EXISTS mari_web_stock_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS mari_web_stock_updates(slot TEXT PRIMARY KEY);
  CREATE TABLE IF NOT EXISTS mari_web_holdings(user_id TEXT,symbol TEXT,qty INTEGER NOT NULL,cost INTEGER NOT NULL,PRIMARY KEY(user_id,symbol));
  CREATE TABLE IF NOT EXISTS mari_web_economy_requests(id TEXT PRIMARY KEY,user_id TEXT,fingerprint TEXT,result TEXT);
  CREATE TABLE IF NOT EXISTS mari_web_stock_trades(id TEXT PRIMARY KEY,user_id TEXT,symbol TEXT,side TEXT,qty INTEGER,price INTEGER,total INTEGER,profit INTEGER,at REAL);
  CREATE TABLE IF NOT EXISTS mari_web_passes(id TEXT PRIMARY KEY,user_id TEXT,guild_id TEXT,game TEXT,seed INTEGER,created REAL,submitted INTEGER DEFAULT 0,result TEXT);
  CREATE TABLE IF NOT EXISTS mari_web_fortune_days(user_id TEXT,day TEXT,pass_id TEXT,result TEXT,PRIMARY KEY(user_id,day));
  ''');self.db.commit()
 def today(self):return datetime.now(KST).date()
 def stock_slot(self):
  now=datetime.now(KST)
  return now.replace(minute=now.minute//30*30,second=0,microsecond=0)
 def balance(self,uid):
  row=self.db.execute('SELECT balance FROM balances WHERE user_id=?',(str(uid),)).fetchone();return row[0] if row else 0
 def receipt(self,member,data,kind):
  if data.get('expectedUser',str(member.id))!=str(member.id) or data.get('expectedGuild',str(member.guild.id))!=str(member.guild.id):raise self.Error('계정이나 서버가 바뀌었어요. 현재 계정으로 다시 시작해주세요.',409)
  request=data.get('requestId')
  if not isinstance(request,str) or not 16<=len(request)<=80:raise self.Error('요청 번호를 확인해주세요.')
  fp=hashlib.sha256(json.dumps([kind,{k:v for k,v in data.items() if k!='requestId'}],sort_keys=True).encode()).hexdigest()
  old=self.db.execute('SELECT user_id,fingerprint,result FROM mari_web_economy_requests WHERE id=?',(request,)).fetchone()
  if old and old[:2]!=(str(member.id),fp):raise self.Error('다른 작업에 사용한 요청 번호입니다.',409)
  return request,fp,json.loads(old[2]) if old else None
 def debit(self,uid,amount):
  if self.db.execute('UPDATE balances SET balance=balance-? WHERE user_id=? AND balance>=?',(amount,str(uid),amount)).rowcount!=1:raise self.Error('마리 잔액이 부족해요.',409)
 def remember(self,request,uid,fp,result):self.db.execute('INSERT INTO mari_web_economy_requests VALUES(?,?,?,?)',(request,str(uid),fp,json.dumps(result,ensure_ascii=False)))
 def settle(self):
  slot=self.stock_slot()
  with self.db:
   if not self.db.execute("SELECT 1 FROM mari_web_stock_settings WHERE key='half_hour_schedule'").fetchone():
    # Preserve existing prices when switching from the previous hourly schedule.
    self.db.execute('UPDATE mari_web_stocks SET day=? WHERE day<?',(slot.isoformat(),slot.isoformat()))
    self.db.execute("INSERT INTO mari_web_stock_settings VALUES('half_hour_schedule','1')")
   for symbol,_,_ in STOCKS:
    row=self.db.execute('SELECT price,day FROM mari_web_stocks WHERE symbol=?',(symbol,)).fetchone()
    if not row:
     self.db.execute('INSERT INTO mari_web_stocks VALUES(?,?,?)',(symbol,10000,slot.isoformat()))
     self.db.execute('INSERT INTO mari_web_stock_days VALUES(?,?,?,?)',(symbol,slot.isoformat(),10000,10000));continue
    price,day=row
    if len(day)==10:
     # Adopt the new schedule without retroactively rerolling existing prices.
     self.db.execute('UPDATE mari_web_stocks SET day=? WHERE symbol=?',(slot.isoformat(),symbol));continue
    date=datetime.fromisoformat(day)
    if date>=slot:continue
    while date<slot:
     date+=timedelta(minutes=30);old=price
     # No future prices are created or exposed. Each persisted scheduled move is -20%..+20%.
     price=max(100,(old*80+99)//100,min(10000000,old*120//100,(old*(10000+secrets.randbelow(4001)-2000)+5000)//10000))
     self.db.execute('INSERT INTO mari_web_stock_days VALUES(?,?,?,?)',(symbol,date.isoformat(),old,price))
     self.db.execute('INSERT OR IGNORE INTO mari_web_stock_updates VALUES(?)',(date.isoformat(),))
     from mari_stock_news import article
     name,sector=next((name,sector) for key,name,sector in STOCKS if key==symbol)
     previous=self.db.execute('SELECT headline FROM mari_web_stock_news WHERE symbol=? ORDER BY slot DESC LIMIT 1',(symbol,)).fetchone()
     headline,body=article(name,sector,old,price,previous[0] if previous else '')
     self.db.execute('INSERT OR IGNORE INTO mari_web_stock_news VALUES(?,?,?,?)',(symbol,date.isoformat(),headline,body))
    self.db.execute('UPDATE mari_web_stocks SET price=?,day=? WHERE symbol=?',(price,slot.isoformat(),symbol))
 def stock_notifications(self):
  notices=[]
  names={symbol:name for symbol,name,_ in STOCKS}
  for (slot,) in self.db.execute('SELECT slot FROM mari_web_stock_updates ORDER BY slot DESC LIMIT 9'):
   rows=self.db.execute('SELECT symbol,open,close FROM mari_web_stock_days WHERE day=? ORDER BY symbol',(slot,)).fetchall()
   body=' · '.join(f'{names.get(symbol,symbol)} {close:,} ({(close/open-1)*100:+.2f}%)' for symbol,open,close in rows)
   notices.append({'key':'stocks:'+slot,'category':'stocks','title':'주가가 갱신됐어요 · '+slot[11:16],'body':body,'at':slot,'tab':'games','url':'/games/stocks'})
  return notices
 def market(self,member):
  self.settle();items=[]
  for symbol,name,sector in STOCKS:
   rows=list(self.db.execute('SELECT day,open,close FROM mari_web_stock_days WHERE symbol=? ORDER BY day DESC LIMIT 90',(symbol,)))[::-1]
   starts=[datetime.fromisoformat(d).replace(tzinfo=KST).timestamp() for d,_,_ in rows]
   volumes=[0]*len(rows)
   for at,quantity in self.db.execute('SELECT at,qty FROM mari_web_stock_trades WHERE symbol=? AND at>=?',(symbol,starts[0])):
    index=bisect_right(starts,at)-1
    if index>=0:volumes[index]+=quantity
   holding=self.db.execute('SELECT qty,cost FROM mari_web_holdings WHERE user_id=? AND symbol=?',(str(member.id),symbol)).fetchone() or (0,0)
   items.append({'symbol':symbol,'name':name,'sector':sector,'price':rows[-1][2],'previous':rows[-1][1],'history':[{'day':d,'open':o,'close':c,'high':max(o,c),'low':min(o,c),'volume':volumes[i]} for i,(d,o,c) in enumerate(rows)],'quantity':holding[0],'cost':holding[1]})
  trades=[dict(zip(('id','symbol','side','quantity','price','total','profit','at'),row)) for row in self.db.execute('SELECT id,symbol,side,qty,price,total,profit,at FROM mari_web_stock_trades WHERE user_id=? ORDER BY at DESC LIMIT 30',(str(member.id),))]
  news=[{'symbol':symbol,'at':slot,'title':headline,'body':body} for symbol,slot,headline,body in self.db.execute('SELECT symbol,slot,headline,body FROM mari_web_stock_news ORDER BY slot DESC,symbol LIMIT 21')]
  return {'news':news,'stocks':items,'balance':self.balance(member.id),'day':self.today().isoformat(),'nextUpdate':(self.stock_slot()+timedelta(minutes=30)).isoformat(),'trades':trades}
 def trade(self,member,data):
  self.settle();request,fp,old=self.receipt(member,data,'trade')
  if old:return old
  symbol=data.get('symbol');side=data.get('side');qty=data.get('quantity');quoted=data.get('price')
  if symbol not in [s[0] for s in STOCKS] or side not in ('buy','sell') or type(qty) is not int or not 1<=qty<=1000000:raise self.Error('종목과 1주 이상의 정수 수량을 확인해주세요.')
  with self.db:
   price=self.db.execute('SELECT price FROM mari_web_stocks WHERE symbol=?',(symbol,)).fetchone()[0]
   if quoted!=price or type(quoted) is not int:raise self.Error('자정에 가격이 바뀌었어요. 새 가격을 확인하고 다시 주문해주세요.',409)
   uid=str(member.id);owned,cost=self.db.execute('SELECT qty,cost FROM mari_web_holdings WHERE user_id=? AND symbol=?',(uid,symbol)).fetchone() or (0,0);total=price*qty;profit=0
   if side=='buy':
    if owned+qty>100000000:raise self.Error('종목별 최대 보유 수량을 초과해요.')
    self.debit(uid,total);owned+=qty;cost+=total
   else:
    if qty>owned:raise self.Error('보유 수량보다 많이 매도할 수 없어요.',409)
    if self.balance(uid)+total>9000000000000000:raise self.Error('보유 가능한 마리 한도를 초과해요.')
    basis=cost*qty//owned;profit=total-basis;cost-=basis;owned-=qty
    self.db.execute('INSERT INTO balances VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance',(uid,total))
   self.db.execute('INSERT INTO mari_web_holdings VALUES(?,?,?,?) ON CONFLICT(user_id,symbol) DO UPDATE SET qty=excluded.qty,cost=excluded.cost',(uid,symbol,owned,cost))
   self.db.execute('INSERT INTO mari_web_stock_trades VALUES(?,?,?,?,?,?,?,?,?)',(request,uid,symbol,side,qty,price,total,profit,time.time()))
   result={'ok':True,'price':price,'quantity':qty,'total':total,'balance':self.balance(uid)};self.remember(request,uid,fp,result)
  return result
 def start(self,member,data,game=None,create=None):
  game=game or data.get('game')
  if game not in PAID:raise self.Error('지원하지 않는 티켓입니다.')
  request,fp,old=self.receipt(member,data,'pass:'+game)
  if old:return old
  if game=='fortune':
   oldday=self.db.execute('SELECT result FROM mari_web_fortune_days WHERE user_id=? AND day=?',(str(member.id),self.today().isoformat())).fetchone()
   if oldday:return json.loads(oldday[0])
   fortune=data.get('fortune')
   if not isinstance(fortune,dict) or fortune.get('date')!=self.today().isoformat():raise self.Error('오늘 날짜로 운세를 다시 확인해주세요.')
  price=1000000 if game=='fortune' else 150000
  with self.db:
   self.debit(member.id,price);rid=secrets.token_urlsafe(24);seed=secrets.randbits(32);now=time.time()
   self.db.execute('INSERT INTO mari_web_passes VALUES(?,?,?,?,?,?,0,NULL)',(rid,str(member.id),str(member.guild.id),game,seed,now))
   result={'id':rid,'seed':seed,'game':game,'price':price,'balance':self.balance(member.id),'created':now}
   if create:result.update(create(rid,seed,now))
   if game=='fortune':
    result['fortune']=data['fortune'];self.db.execute('INSERT INTO mari_web_fortune_days VALUES(?,?,?,?)',(str(member.id),self.today().isoformat(),rid,json.dumps(result,ensure_ascii=False)))
   self.remember(request,member.id,fp,result)
  return result
 def status(self,member):
  row=self.db.execute('SELECT result FROM mari_web_fortune_days WHERE user_id=? AND day=?',(str(member.id),self.today().isoformat())).fetchone()
  return {'balance':self.balance(member.id),'fortune':json.loads(row[0]) if row else None,'day':self.today().isoformat(),'price':150000,'dailyPrice':1000000}
 def ticket(self,member,data):
  row=self.db.execute('SELECT game,seed,created,submitted FROM mari_web_passes WHERE id=? AND user_id=? AND guild_id=?',(data.get('id'),str(member.id),str(member.guild.id))).fetchone()
  if not row or row[0] not in ('apple','snake') or time.time()-row[2]>900:raise self.Error('이 게임의 기록이 만료됐어요.',409)
  return {'id':data['id'],'game':row[0],'seed':row[1],'created':row[2]}
