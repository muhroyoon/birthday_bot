"""Virtual stock market and paid game passes, sharing Discord's balance table."""
from bisect import bisect_right
from fractions import Fraction
import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta, timezone

KST=timezone(timedelta(hours=9))
STOCKS=(('muro','머로증권','금융'),('jeumi','즈미테크','기술'),('samsung','삼성식품','식품'),('gimcheon','김천물류','물류'),('haerangsol','해랑솔에너지','에너지'),('harang','하랑건설','건설'),('hoon','훈이게임즈','게임'),('haneul','하늘반도체','반도체'))
PAID={'aim','pubg','reaction','stopwatch','apple','snake','suika','2048','fortune'}

def legacy_stock_move_bps(up_chance=50):
 """Daily private direction bias with unchanged reciprocal move magnitudes.

 Rise bands (bps) have 50/35/13/2 weights. A sampled +r pairs with
 -r/(1+r), not -r. Fraction keeps the inverse exact until price rounding.
 """
 rising=secrets.randbelow(100)<up_chance
 bucket=secrets.randbelow(1000)
 low,high=(300,1000) if bucket<500 else (1001,2500) if bucket<850 else (2501,4500) if bucket<980 else (4501,7000)
 magnitude=low+secrets.randbelow(high-low+1)
 return magnitude if rising else Fraction(-10000*magnitude,10000+magnitude)


def stock_move_bps(up_chance=50,sideways=False):
 """70/25/5 magnitude bands, with reciprocal down moves."""
 rising=secrets.randbelow(100)<up_chance
 bucket=secrets.randbelow(1000)
 low,high=(80,400) if bucket<700 else (401,1600) if bucket<950 else (1601,5500)
 magnitude=low+secrets.randbelow(high-low+1)
 if sideways:magnitude=round(Fraction(magnitude*35,100))
 return magnitude if rising else Fraction(-10000*magnitude,10000+magnitude)


class Economy:
 def __init__(self,b,error):
  self.b=b;self.db=b.db;self.Error=error
  from mari_stock_contracts import equity
  self.db.create_function("mari_log_equity",5,equity,deterministic=True)
  self.db.executescript('''
  CREATE TABLE IF NOT EXISTS mari_web_stocks(symbol TEXT PRIMARY KEY,price INTEGER NOT NULL,day TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS mari_web_stock_days(symbol TEXT,day TEXT,open INTEGER,close INTEGER,PRIMARY KEY(symbol,day));
  CREATE TABLE IF NOT EXISTS mari_web_stock_news(symbol TEXT,slot TEXT,headline TEXT,body TEXT,PRIMARY KEY(symbol,slot));
  CREATE TABLE IF NOT EXISTS mari_web_stock_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS mari_web_stock_updates(slot TEXT PRIMARY KEY);
  CREATE TABLE IF NOT EXISTS mari_web_private_regimes(symbol TEXT,day TEXT,bull INTEGER NOT NULL CHECK(bull IN (0,1)),PRIMARY KEY(symbol,day));
  CREATE TABLE IF NOT EXISTS mari_web_shorts(user_id TEXT,symbol TEXT,qty INTEGER NOT NULL,cost INTEGER NOT NULL,PRIMARY KEY(user_id,symbol));
  CREATE TABLE IF NOT EXISTS mari_web_holdings(user_id TEXT,symbol TEXT,qty INTEGER NOT NULL,cost INTEGER NOT NULL,PRIMARY KEY(user_id,symbol));
  CREATE TABLE IF NOT EXISTS mari_web_economy_requests(id TEXT PRIMARY KEY,user_id TEXT,fingerprint TEXT,result TEXT);
  CREATE TABLE IF NOT EXISTS mari_web_stock_trades(id TEXT PRIMARY KEY,user_id TEXT,symbol TEXT,side TEXT,qty INTEGER,price INTEGER,total INTEGER,profit INTEGER,at REAL);
  CREATE TABLE IF NOT EXISTS mari_web_passes(id TEXT PRIMARY KEY,user_id TEXT,guild_id TEXT,game TEXT,seed INTEGER,created REAL,submitted INTEGER DEFAULT 0,result TEXT);
  CREATE TABLE IF NOT EXISTS mari_web_fortune_days(user_id TEXT,day TEXT,pass_id TEXT,result TEXT,PRIMARY KEY(user_id,day));
  CREATE TABLE IF NOT EXISTS mari_web_leveraged(user_id TEXT,symbol TEXT,side TEXT,qty INTEGER,cost INTEGER,notional INTEGER,PRIMARY KEY(user_id,symbol,side));
  CREATE TABLE IF NOT EXISTS mari_web_trade_leverage(id TEXT PRIMARY KEY,leverage INTEGER);
  CREATE TABLE IF NOT EXISTS mari_web_six_hour_regimes(symbol TEXT,window TEXT,regime INTEGER NOT NULL CHECK(regime IN (0,1,2)),PRIMARY KEY(symbol,window));
  CREATE TABLE IF NOT EXISTS mari_web_five_state_regimes(symbol TEXT,window TEXT,regime INTEGER NOT NULL CHECK(regime IN (0,1,2,3,4)),PRIMARY KEY(symbol,window));
  CREATE TABLE IF NOT EXISTS mari_web_log_positions(user_id TEXT,symbol TEXT,side TEXT CHECK(side IN ('long','short')),leverage INTEGER CHECK(leverage IN (1,2)),qty INTEGER NOT NULL,cost INTEGER NOT NULL,notional INTEGER NOT NULL,log_basis TEXT NOT NULL,PRIMARY KEY(user_id,symbol,side,leverage));
  CREATE TABLE IF NOT EXISTS mari_web_delisted(symbol TEXT PRIMARY KEY,at TEXT NOT NULL,price INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS mari_web_trade_contract(id TEXT PRIMARY KEY,settlement TEXT NOT NULL);
  CREATE INDEX IF NOT EXISTS mari_web_stock_trade_symbol_time ON mari_web_stock_trades(symbol,at);
  ''');self.db.commit()
 def today(self):return datetime.now(KST).date()
 def stock_slot(self):
  now=datetime.now(KST)
  return now.replace(minute=now.minute//10*10,second=0,microsecond=0)
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
 def private_up_chance(self,symbol,slot):
  day=slot.astimezone(KST).date().isoformat()
  row=self.db.execute('SELECT bull FROM mari_web_private_regimes WHERE symbol=? AND day=?',(symbol,day)).fetchone()
  if row is None:
   self.db.execute('INSERT OR IGNORE INTO mari_web_private_regimes VALUES(?,?,?)',(symbol,day,secrets.randbelow(2)))
   row=self.db.execute('SELECT bull FROM mari_web_private_regimes WHERE symbol=? AND day=?',(symbol,day)).fetchone()
  return 55 if row[0] else 45
 def private_regime(self,symbol,slot):
  window=slot.astimezone(KST).replace(hour=slot.astimezone(KST).hour//6*6,minute=0,second=0,microsecond=0).isoformat()
  row=self.db.execute('SELECT regime FROM mari_web_five_state_regimes WHERE symbol=? AND window=?',(symbol,window)).fetchone()
  if row is None:
   draw=secrets.randbelow(100);regime=0 if draw<10 else 1 if draw<35 else 2 if draw<65 else 3 if draw<90 else 4
   self.db.execute('INSERT OR IGNORE INTO mari_web_five_state_regimes VALUES(?,?,?)',(symbol,window,regime))
   row=self.db.execute('SELECT regime FROM mari_web_five_state_regimes WHERE symbol=? AND window=?',(symbol,window)).fetchone()
  return ((70,False),(60,False),(50,True),(40,False),(30,False))[row[0]]
 def delist(self,symbol,slot):
  if self.db.execute('SELECT 1 FROM mari_web_delisted WHERE symbol=?',(symbol,)).fetchone():return
  # Called within settlement's transaction: archive, payouts, and removal commit together.
  self.db.execute('INSERT INTO mari_web_delisted VALUES(?,?,100)',(symbol,slot))
  rows=[]
  for side,table in [('long','mari_web_holdings'),('short','mari_web_shorts')]:
   rows.extend((uid,side,1,qty,cost,cost) for uid,qty,cost in self.db.execute(f'SELECT user_id,qty,cost FROM {table} WHERE symbol=? AND qty>0',(symbol,)))
  rows.extend((uid,side,2,qty,cost,notional) for uid,side,qty,cost,notional in self.db.execute('SELECT user_id,side,qty,cost,notional FROM mari_web_leveraged WHERE symbol=? AND qty>0',(symbol,)))
  for uid,side,lev,qty,cost,notional in rows:
   total=max(0,cost+(100*qty-notional)*(1 if side=='long' else -1));rid='delist:'+secrets.token_hex(16)
   self.db.execute('INSERT INTO balances VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance',(uid,total))
   self.db.execute('INSERT INTO mari_web_stock_trades VALUES(?,?,?,?,?,?,?,?,?)',(rid,uid,symbol,side+'_close',qty,100,total,total-cost,datetime.fromisoformat(slot).timestamp()))
   self.db.execute('INSERT INTO mari_web_trade_leverage VALUES(?,?)',(rid,lev))
  for table in ('mari_web_holdings','mari_web_shorts','mari_web_leveraged'):self.db.execute(f'DELETE FROM {table} WHERE symbol=?',(symbol,))
  self.db.execute('INSERT OR IGNORE INTO mari_web_stock_days VALUES(?,?,100,100)',(symbol,slot))
  self.db.execute('INSERT OR IGNORE INTO mari_web_stock_updates VALUES(?)',(slot,))
  name=next(name for key,name,_ in STOCKS if key==symbol)
  self.db.execute('INSERT OR REPLACE INTO mari_web_stock_news VALUES(?,?,?,?)',(symbol,slot,f'[{name}] 최저가 도달…상장폐지', '최저가 100마리에 도달해 거래가 종료됐습니다. 남은 롱·숏 포지션은 100마리 기준으로 정산되었습니다.'))
 def restore_linear_positions(self):
  # Archive the exact source rows; transfer original quantities and capital once.
  self.db.execute('CREATE TABLE IF NOT EXISTS mari_web_log_position_archive(user_id TEXT,symbol TEXT,side TEXT,leverage INTEGER,qty INTEGER,cost INTEGER,notional INTEGER,log_basis TEXT,restored_at REAL,PRIMARY KEY(user_id,symbol,side,leverage))')
  if self.db.execute("SELECT 1 FROM mari_web_stock_settings WHERE key='linear_restored_v1'").fetchone():return
  for uid,symbol,side,lev,qty,cost,notional,basis in list(self.db.execute('SELECT * FROM mari_web_log_positions')):
   self.db.execute('INSERT INTO mari_web_log_position_archive VALUES(?,?,?,?,?,?,?,?,?)',(uid,symbol,side,lev,qty,cost,notional,basis,time.time()))
   if lev==1:
    table='mari_web_holdings' if side=='long' else 'mari_web_shorts'
    self.db.execute(f'INSERT INTO {table} VALUES(?,?,?,?) ON CONFLICT(user_id,symbol) DO UPDATE SET qty=qty+excluded.qty,cost=cost+excluded.cost',(uid,symbol,qty,cost))
   else:
    self.db.execute('INSERT INTO mari_web_leveraged VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,symbol,side) DO UPDATE SET qty=qty+excluded.qty,cost=cost+excluded.cost,notional=notional+excluded.notional',(uid,symbol,side,qty,cost,notional))
  self.db.execute('DELETE FROM mari_web_log_positions')
  self.db.execute("INSERT INTO mari_web_stock_settings VALUES('linear_restored_v1',?)",(self.stock_slot().isoformat(),))
 def settle(self):
  slot=self.stock_slot()
  with self.db:
   self.restore_linear_positions()
   if not self.db.execute("SELECT 1 FROM mari_web_stock_settings WHERE key='ten_minute_schedule'").fetchone():
    # Preserve existing prices when switching to the ten-minute schedule.
    self.db.execute('UPDATE mari_web_stocks SET day=? WHERE day<?',(slot.isoformat(),slot.isoformat()))
    self.db.execute("INSERT INTO mari_web_stock_settings VALUES('ten_minute_schedule','1')")
   self.db.execute("INSERT OR IGNORE INTO mari_web_stock_settings VALUES('log_market_start',?)",((slot+timedelta(minutes=10)).isoformat(),))
   cutover=datetime.fromisoformat(self.db.execute("SELECT value FROM mari_web_stock_settings WHERE key='log_market_start'").fetchone()[0])
   for symbol,_,_ in STOCKS:
    if self.db.execute('SELECT 1 FROM mari_web_delisted WHERE symbol=?',(symbol,)).fetchone():continue
    self.private_regime(symbol,slot)
    row=self.db.execute('SELECT price,day FROM mari_web_stocks WHERE symbol=?',(symbol,)).fetchone()
    if not row:
     self.db.execute('INSERT INTO mari_web_stocks VALUES(?,?,?)',(symbol,10000,slot.isoformat()))
     self.db.execute('INSERT INTO mari_web_stock_days VALUES(?,?,?,?)',(symbol,slot.isoformat(),10000,10000));continue
    price,day=row
    if price<=100:
     self.delist(symbol,slot.isoformat());self.db.execute('UPDATE mari_web_stocks SET day=? WHERE symbol=?',(slot.isoformat(),symbol));continue
    self.liquidate(symbol,price,day)
    if len(day)==10:
     # Adopt the new schedule without retroactively rerolling existing prices.
     self.db.execute('UPDATE mari_web_stocks SET day=? WHERE symbol=?',(slot.isoformat(),symbol));continue
    date=datetime.fromisoformat(day)
    if date>=slot:continue
    while date<slot:
     date=date.replace(minute=date.minute//10*10,second=0,microsecond=0)+timedelta(minutes=10);old=price
     # Draw only when a scheduled slot is due; preserve all settled history.
     move=stock_move_bps(*self.private_regime(symbol,date)) if date>=cutover else legacy_stock_move_bps(self.private_up_chance(symbol,date))
     price=max(100,min(10000000,int((old*(10000+move)+5000)//10000)))
     if date<cutover:price=max((old*10+16)//17,min(old*170//100,price))
     self.liquidate(symbol,price,date.isoformat())
     self.db.execute('INSERT INTO mari_web_stock_days VALUES(?,?,?,?)',(symbol,date.isoformat(),old,price))
     self.db.execute('INSERT OR IGNORE INTO mari_web_stock_updates VALUES(?)',(date.isoformat(),))
     from mari_stock_news import article
     name,sector=next((name,sector) for key,name,sector in STOCKS if key==symbol)
     previous=self.db.execute('SELECT headline FROM mari_web_stock_news WHERE symbol=? ORDER BY slot DESC LIMIT 1',(symbol,)).fetchone()
     headline,body=article(name,sector,old,price,previous[0] if previous else '')
     self.db.execute('INSERT OR IGNORE INTO mari_web_stock_news VALUES(?,?,?,?)',(symbol,date.isoformat(),headline,body))
     if price<=100:
      self.delist(symbol,date.isoformat());break
    self.db.execute('UPDATE mari_web_stocks SET price=?,day=? WHERE symbol=?',(price,date.isoformat(),symbol))
 def liquidate(self,symbol,price,slot):
  from mari_stock_contracts import liquidate
  liquidate(self,symbol,price,datetime.fromisoformat(slot).replace(tzinfo=KST).timestamp())
  # Collateral is isolated per user/symbol/direction. Gap losses never debit the wallet.
  rows=list(self.db.execute('SELECT user_id,qty,cost FROM mari_web_shorts WHERE symbol=? AND qty>0 AND 2*cost<=qty*?',(symbol,price)))
  for uid,qty,cost in rows:
   rid='liquidate:'+secrets.token_hex(16)
   self.db.execute('INSERT INTO mari_web_stock_trades VALUES(?,?,?,?,?,?,?,?,?)',(rid,uid,symbol,'short_liquidate',qty,price,0,-cost,datetime.fromisoformat(slot).replace(tzinfo=KST).timestamp()))
   self.db.execute('DELETE FROM mari_web_shorts WHERE user_id=? AND symbol=?',(uid,symbol))
  for uid,side,qty,cost,notional in list(self.db.execute('SELECT user_id,side,qty,cost,notional FROM mari_web_leveraged WHERE symbol=? AND qty>0',(symbol,))):
   equity=cost+(price*qty-notional)*(1 if side=='long' else -1)
   if equity>0:continue
   rid='liquidate:'+secrets.token_hex(16)
   self.db.execute('INSERT INTO mari_web_stock_trades VALUES(?,?,?,?,?,?,?,?,?)',(rid,uid,symbol,side+'_liquidate',qty,price,0,-cost,datetime.fromisoformat(slot).replace(tzinfo=KST).timestamp()))
   self.db.execute('INSERT INTO mari_web_trade_leverage VALUES(?,2)',(rid,))
   self.db.execute('DELETE FROM mari_web_leveraged WHERE user_id=? AND symbol=? AND side=?',(uid,symbol,side))
 def positions(self,uid,stocks):
  prices={s['symbol']:s['price'] for s in stocks};result=[]
  for side,table in [('long','mari_web_holdings'),('short','mari_web_shorts')]:
   for symbol,qty,cost in self.db.execute(f'SELECT symbol,qty,cost FROM {table} WHERE user_id=? AND qty>0',(str(uid),)):
    raw=prices[symbol]*qty-cost
    profit=max(-cost,raw if side=='long' else -raw)
    result.append({'notional':cost,'leverage':1,'symbol':symbol,'side':side,'quantity':qty,'cost':cost,'entry':cost/qty,'profit':profit,'equity':cost+profit,'liquidation':2*cost/qty if side=='short' else 0})
  for symbol,side,qty,cost,notional in self.db.execute('SELECT symbol,side,qty,cost,notional FROM mari_web_leveraged WHERE user_id=? AND qty>0',(str(uid),)):
   raw=prices[symbol]*qty-notional;profit=max(-cost,raw if side=='long' else -raw)
   result.append({'symbol':symbol,'side':side,'leverage':2,'notional':notional,'quantity':qty,'cost':cost,'entry':notional/qty,'profit':profit,'equity':cost+profit,'liquidation':(notional-cost if side=='long' else notional+cost)/qty})
  from mari_stock_contracts import position
  for p in result:p['settlement']='linear'
  for symbol,side,lev,qty,cost,notional,basis in self.db.execute('SELECT symbol,side,leverage,qty,cost,notional,log_basis FROM mari_web_log_positions WHERE user_id=? AND qty>0',(str(uid),)):
   result.append(position(symbol,side,lev,qty,cost,notional,basis,prices[symbol]))
  return result
 def stock_notifications(self):
  notices=[]
  names={symbol:name for symbol,name,_ in STOCKS}
  for (slot,) in self.db.execute('SELECT slot FROM mari_web_stock_updates ORDER BY slot DESC LIMIT 9'):
   rows=self.db.execute('SELECT symbol,open,close FROM mari_web_stock_days WHERE day=? ORDER BY symbol',(slot,)).fetchall()
   body=' · '.join(f'{names.get(symbol,symbol)} {close:,} ({(close/open-1)*100:+.2f}%)' for symbol,open,close in rows)
   notices.append({'key':'stocks:'+slot,'category':'stocks','title':'주가가 갱신됐어요 · '+slot[11:16],'body':body,'at':slot,'tab':'games','url':'/games/stocks'})
  return notices
 def history(self,data):
  symbol=data.get('symbol');before=data.get('before','')
  if symbol not in [v[0] for v in STOCKS] or not isinstance(before,str) or len(before)>50:raise self.Error('차트 요청을 확인해주세요.')
  rows=list(self.db.execute('SELECT day,open,close FROM mari_web_stock_days WHERE symbol=? AND day<? ORDER BY day DESC LIMIT 601',(symbol,before or '9999')))
  more=len(rows)>600;rows=rows[:600][::-1]
  if not rows:return {'history':[],'hasMore':False}
  starts=[datetime.fromisoformat(d).replace(tzinfo=KST).timestamp() for d,_,_ in rows]
  following=self.db.execute('SELECT MIN(day) FROM mari_web_stock_days WHERE symbol=? AND day>?',(symbol,rows[-1][0])).fetchone()[0]
  end=datetime.fromisoformat(following).replace(tzinfo=KST).timestamp() if following else 1e15
  volumes=[0]*len(rows)
  for at,qty in self.db.execute('SELECT at,qty FROM mari_web_stock_trades WHERE symbol=? AND at>=? AND at<?',(symbol,starts[0],end)):
   index=bisect_right(starts,at)-1
   if index>=0:volumes[index]+=qty
  return {'history':[{'day':d,'open':o,'close':c,'high':max(o,c),'low':min(o,c),'volume':volumes[i]} for i,(d,o,c) in enumerate(rows)],'hasMore':more}
 def market(self,member):
  self.settle();items=[]
  for symbol,name,sector in STOCKS:
   page=self.history({'symbol':symbol});bars=page['history']
   holding=self.db.execute('SELECT qty,cost FROM mari_web_holdings WHERE user_id=? AND symbol=?',(str(member.id),symbol)).fetchone() or (0,0)
   delisted=self.db.execute('SELECT at FROM mari_web_delisted WHERE symbol=?',(symbol,)).fetchone()
   items.append({'delistedAt':delisted[0] if delisted else None,'symbol':symbol,'name':name,'sector':sector,'price':bars[-1]['close'],'previous':bars[-1]['open'],**page,'quantity':holding[0],'cost':holding[1]})
  trades=[dict(zip(('id','symbol','side','quantity','price','total','profit','at'),row)) for row in self.db.execute('SELECT id,symbol,side,qty,price,total,profit,at FROM mari_web_stock_trades WHERE user_id=? ORDER BY at DESC,id DESC LIMIT 10',(str(member.id),))]
  for t in trades:
   row=self.db.execute('SELECT leverage FROM mari_web_trade_leverage WHERE id=?',(t['id'],)).fetchone();t['leverage']=row[0] if row else 1
   row=self.db.execute('SELECT settlement FROM mari_web_trade_contract WHERE id=?',(t['id'],)).fetchone();t['settlement']=row[0] if row else 'linear';t['delisting']=t['id'].startswith('delist:')
  news=[{'symbol':symbol,'at':slot,'title':headline,'body':body,'sentiment':sentiment} for symbol,slot,headline,body,sentiment in self.db.execute("SELECT n.symbol,n.slot,n.headline,n.body,CASE WHEN d.close>d.open THEN 'positive' WHEN d.close<d.open THEN 'negative' WHEN d.close=d.open THEN 'neutral' ELSE 'unknown' END FROM mari_web_stock_news n LEFT JOIN mari_web_stock_days d ON d.symbol=n.symbol AND d.day=n.slot ORDER BY n.slot DESC,n.symbol LIMIT 24")]
  return {'positionVersion':4,'bulkClose':True,'positionClose':True,'positions':self.positions(member.id,items),'news':news,'stocks':items,'balance':self.balance(member.id),'day':self.today().isoformat(),'nextUpdate':(self.stock_slot()+timedelta(minutes=10)).isoformat(),'trades':trades}
 def trade(self,member,data):
  self.settle();request,fp,old=self.receipt(member,data,'trade')
  if old:return old
  if data.get('action')=='close_position':return self.close_all(member,data,request,fp,single=True)
  if data.get('action')=='close_all':return self.close_all(member,data,request,fp)
  if self.db.execute('SELECT 1 FROM mari_web_delisted WHERE symbol=?',(data.get('symbol'),)).fetchone():raise self.Error('상장폐지된 종목은 거래할 수 없어요.',409)
  if data.get('settlement','linear')!='linear':raise self.Error('기존 손익 방식으로 복원됐어요. 페이지를 새로고침해주세요.',409)
  return self.trade_legacy(member,data)
 def trade_legacy(self,member,data):
  self.settle();request,fp,old=self.receipt(member,data,'trade')
  if old:return old
  if data.get('action')=='close_all':return self.close_all(member,data,request,fp)
  symbol=data.get('symbol');side=data.get('side');action=data.get('action');qty=data.get('quantity');quoted=data.get('price')
  if side not in ('long','short') or action not in ('open','close'):raise self.Error('롱·숏 거래로 전환됐어요. 페이지를 새로고침해주세요.',409)
  if symbol not in [s[0] for s in STOCKS] or type(qty) is not int or not 1<=qty<=1000000:raise self.Error('종목과 1 이상의 정수 수량을 확인해주세요.')
  leverage=data.get('leverage',1)
  if type(leverage) is not int or leverage not in (1,2):raise self.Error('레버리지는 1배 또는 2배로 선택해주세요.')
  if leverage==2:return self.trade_leveraged(member,data,request,fp)
  table='mari_web_holdings' if side=='long' else 'mari_web_shorts'
  with self.db:
   price=self.db.execute('SELECT price FROM mari_web_stocks WHERE symbol=?',(symbol,)).fetchone()[0]
   if quoted!=price or type(quoted) is not int:raise self.Error('가격이 바뀌었어요. 새 가격을 확인하고 다시 주문해주세요.',409)
   uid=str(member.id);owned,cost=self.db.execute(f'SELECT qty,cost FROM {table} WHERE user_id=? AND symbol=?',(uid,symbol)).fetchone() or (0,0)
   total=price*qty;profit=0
   if action=='open':
    if owned+qty>100000000:raise self.Error('종목·방향별 최대 보유 수량을 초과해요.')
    self.debit(uid,total);owned+=qty;cost+=total
   else:
    if qty>owned:raise self.Error('보유 포지션 수량보다 많이 종료할 수 없어요.',409)
    # Allocate integer collateral once; the final close receives the exact remainder.
    basis=cost*qty//owned
    profit=(total-basis) if side=='long' else (basis-total)
    total=max(0,basis+profit);profit=total-basis
    if self.balance(uid)+total>9000000000000000:raise self.Error('보유 가능한 마리 한도를 초과해요.')
    cost-=basis;owned-=qty
    self.db.execute('INSERT INTO balances VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance',(uid,total))
   self.db.execute(f'INSERT INTO {table} VALUES(?,?,?,?) ON CONFLICT(user_id,symbol) DO UPDATE SET qty=excluded.qty,cost=excluded.cost',(uid,symbol,owned,cost))
   self.db.execute('INSERT INTO mari_web_stock_trades VALUES(?,?,?,?,?,?,?,?,?)',(request,uid,symbol,side+'_'+action,qty,price,total,profit,time.time()))
   result={'ok':True,'price':price,'quantity':qty,'total':total,'profit':profit,'balance':self.balance(uid)};self.remember(request,uid,fp,result)
  return result
 def close_all(self,member,data,request,fp,single=False):
  uid=str(member.id)
  with self.db:
   prices=dict(self.db.execute('SELECT symbol,price FROM mari_web_stocks'))
   positions=self.positions(uid,[{'symbol':s,'price':p} for s,p in prices.items()])
   fields=('symbol','side','leverage','quantity','cost','notional','settlement')
   quoted=data.get('positions')
   if isinstance(quoted,list):quoted=[{**p,'settlement':p.get('settlement','linear')} if isinstance(p,dict) else p for p in quoted]
   if not isinstance(quoted,list) or not 1<=len(quoted)<=64 or any(not isinstance(p,dict) or set(p)!=set(fields)|{'price'} or any(type(p[k]) is not int for k in ('leverage','quantity','cost','notional','price')) for p in quoted):raise self.Error('종료할 포지션을 다시 확인해주세요.',409)
   if single:
    if len(quoted)!=1:raise self.Error('종료할 포지션 하나를 선택해주세요.',409)
    identity=('symbol','side','leverage','settlement')
    positions=[p for p in positions if all(p[k]==quoted[0][k] for k in identity)]
   expected=[{**{k:p[k] for k in fields},'price':prices[p['symbol']]} for p in positions]
   canonical=lambda rows:sorted(json.dumps(p,sort_keys=True) for p in rows)
   if canonical(quoted)!=canonical(expected):raise self.Error('시세나 포지션이 바뀌었어요. 새 내역을 확인하고 다시 종료해주세요.',409)
   total=sum(p['equity'] for p in positions);profit=sum(p['profit'] for p in positions)
   if self.balance(uid)+total>9000000000000000:raise self.Error('보유 가능한 마리 한도를 초과해요.')
   at=time.time()
   for p in positions:
    rid='bulk:'+secrets.token_hex(16)
    self.db.execute('INSERT INTO mari_web_stock_trades VALUES(?,?,?,?,?,?,?,?,?)',(rid,uid,p['symbol'],p['side']+'_close',p['quantity'],prices[p['symbol']],p['equity'],p['profit'],at))
    if p['settlement']=='log':self.db.execute('INSERT INTO mari_web_trade_contract VALUES(?,?)',(rid,'log'))
    if p['leverage']==2:self.db.execute('INSERT INTO mari_web_trade_leverage VALUES(?,2)',(rid,))
   if single:
    p=positions[0]
    if p['settlement']=='log':self.db.execute('DELETE FROM mari_web_log_positions WHERE user_id=? AND symbol=? AND side=? AND leverage=?',(uid,p['symbol'],p['side'],p['leverage']))
    elif p['leverage']==2:self.db.execute('DELETE FROM mari_web_leveraged WHERE user_id=? AND symbol=? AND side=?',(uid,p['symbol'],p['side']))
    else:
     table='mari_web_holdings' if p['side']=='long' else 'mari_web_shorts'
     self.db.execute(f'DELETE FROM {table} WHERE user_id=? AND symbol=?',(uid,p['symbol']))
   else:
    for table in ('mari_web_holdings','mari_web_shorts','mari_web_leveraged','mari_web_log_positions'):
     self.db.execute(f'DELETE FROM {table} WHERE user_id=?',(uid,))
   self.db.execute('INSERT INTO balances VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance',(uid,total))
   result={'ok':True,'closed':len(positions),'total':total,'profit':profit,'balance':self.balance(uid)}
   self.remember(request,uid,fp,result)
  return result
 def trade_leveraged(self,member,data,request,fp):
  uid=str(member.id);symbol=data['symbol'];side=data['side'];qty=data['quantity'];action=data['action']
  with self.db:
   price=self.db.execute('SELECT price FROM mari_web_stocks WHERE symbol=?',(symbol,)).fetchone()[0]
   if type(data.get('price')) is not int or data['price']!=price:raise self.Error('가격이 바뀌었어요. 새 가격을 확인해주세요.',409)
   owned,cost,notional=self.db.execute('SELECT qty,cost,notional FROM mari_web_leveraged WHERE user_id=? AND symbol=? AND side=?',(uid,symbol,side)).fetchone() or (0,0,0)
   market=price*qty;profit=0
   if action=='open':
    if owned+qty>100000000:raise self.Error('종목·방향별 최대 보유 수량을 초과해요.')
    total=(market+1)//2;self.debit(uid,total);owned+=qty;cost+=total;notional+=market
   else:
    if qty>owned:raise self.Error('보유 포지션 수량보다 많이 종료할 수 없어요.',409)
    margin=cost*qty//owned;basis=notional*qty//owned
    total=max(0,margin+(market-basis)*(1 if side=='long' else -1));profit=total-margin
    if self.balance(uid)+total>9000000000000000:raise self.Error('보유 가능한 마리 한도를 초과해요.')
    self.db.execute('INSERT INTO balances VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance',(uid,total))
    owned-=qty;cost-=margin;notional-=basis
   self.db.execute('INSERT INTO mari_web_leveraged VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,symbol,side) DO UPDATE SET qty=excluded.qty,cost=excluded.cost,notional=excluded.notional',(uid,symbol,side,owned,cost,notional))
   self.db.execute('INSERT INTO mari_web_stock_trades VALUES(?,?,?,?,?,?,?,?,?)',(request,uid,symbol,side+'_'+action,qty,price,total,profit,time.time()))
   self.db.execute('INSERT INTO mari_web_trade_leverage VALUES(?,2)',(request,))
   result={'ok':True,'price':price,'quantity':qty,'total':total,'profit':profit,'balance':self.balance(uid),'leverage':2};self.remember(request,uid,fp,result)
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
