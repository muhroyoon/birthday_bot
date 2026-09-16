import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from test_bridge import Fixture
from mari_web_bridge import WebError
from mari_web_economy import KST
from mari_web_rankings import Rankings

class StockUpgradeTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.f=Fixture();self.token=await self.f.login();self.e=self.f.bridge.economy
  self.slot=patch.object(self.e,'stock_slot',return_value=datetime(2026,9,8,0,tzinfo=KST));self.slot.start();self.e.settle();self.serial=0
 async def asyncTearDown(self):self.slot.stop();self.f.db.close()
 async def order(self,**changes):
  self.serial+=1
  data={'requestId':'leverage-order-test-'+str(self.serial),'symbol':'muro','side':'long','action':'open','leverage':2,'quantity':10,'price':10000,**changes}
  return await self.f.bridge.dispatch('stocks/trade',self.token,data)
 def price(self,p):
  self.f.db.execute("UPDATE mari_web_stocks SET price=? WHERE symbol='muro'",(p,))
  self.f.db.execute("UPDATE mari_web_stock_days SET close=? WHERE symbol='muro'",(p,));self.f.db.commit()
 async def test_news_sentiment_uses_its_own_price_bar(self):
  for i,(price,sentiment) in enumerate([(11000,'positive'),(9000,'negative'),(10000,'neutral')]):
   slot=f'2026-09-07T23:{i*10:02d}:00+09:00'
   self.f.db.execute('INSERT OR REPLACE INTO mari_web_stock_days VALUES(?,?,?,?)',('muro',slot,10000,price))
   self.f.db.execute('INSERT OR REPLACE INTO mari_web_stock_news VALUES(?,?,?,?)',('muro',slot,'news','body'))
  self.f.db.commit()
  news=self.e.market(self.f.members[1])['news']
  actual={n['at']:n['sentiment'] for n in news if n['title']=='news'}
  self.assertEqual(actual,{'2026-09-07T23:00:00+09:00':'positive','2026-09-07T23:10:00+09:00':'negative','2026-09-07T23:20:00+09:00':'neutral'})
 def bulk_payload(self,request='bulk-close-test-0001'):
  market=self.e.market(self.f.members[1]);prices={s['symbol']:s['price'] for s in market['stocks']}
  return {'action':'close_all','requestId':request,'positions':[{**{k:p[k] for k in ('symbol','side','leverage','quantity','cost','notional')},'price':prices[p['symbol']]} for p in market['positions']]}
 async def test_bulk_close_all_sides_leverages_and_retry(self):
  for symbol in ('muro','haneul'):
   for leverage in (1,2):
    for side in ('long','short'):await self.order(symbol=symbol,leverage=leverage,side=side,quantity=3)
  self.f.db.execute("INSERT INTO mari_web_holdings VALUES('2','muro',7,70000)");self.f.db.commit()
  self.price(11001);payload=self.bulk_payload();before=self.f.balance(1)
  expected=self.e.market(self.f.members[1])['positions'];total=sum(p['equity'] for p in expected)
  result=await self.f.bridge.dispatch('stocks/trade',self.token,payload)
  self.assertEqual((result['closed'],result['total'],self.f.balance(1)),(8,total,before+total))
  self.assertEqual(self.e.market(self.f.members[1])['positions'],[])
  self.assertEqual(self.f.db.execute("SELECT qty FROM mari_web_holdings WHERE user_id='2'").fetchone(),(7,))
  self.assertEqual(result,await self.f.bridge.dispatch('stocks/trade',self.token,payload))
  rows=self.f.db.execute("SELECT COUNT(*),SUM(total),SUM(profit) FROM mari_web_stock_trades WHERE side LIKE '%_close'").fetchone()
  self.assertEqual(rows,(8,total,sum(p['profit'] for p in expected)))
  self.assertEqual(self.f.db.execute("SELECT COUNT(*) FROM mari_web_trade_leverage WHERE id LIKE 'bulk:%'").fetchone()[0],4)
 async def test_bulk_close_rejects_stale_or_incomplete_quotes(self):
  await self.order();await self.order(side='short',leverage=1)
  good=self.bulk_payload();before=self.f.balance(1)
  for quote in ([],good['positions'][:1],[*good['positions'],good['positions'][0]], [{**p,'quantity':True} for p in good['positions']]):
   with self.assertRaises(WebError):await self.f.bridge.dispatch('stocks/trade',self.token,{**good,'positions':quote})
  self.price(11000)
  with self.assertRaises(WebError):await self.f.bridge.dispatch('stocks/trade',self.token,good)
  self.assertEqual(self.f.balance(1),before)
  self.assertEqual(len(self.e.market(self.f.members[1])['positions']),2)
 async def test_bulk_close_rolls_back_on_wallet_limit_and_storage_failure(self):
  await self.order();await self.order(side='short',leverage=1)
  payload=self.bulk_payload()
  self.f.db.execute("UPDATE balances SET balance=9000000000000000 WHERE user_id='1'");self.f.db.commit()
  with self.assertRaises(WebError):await self.f.bridge.dispatch('stocks/trade',self.token,payload)
  self.f.db.execute("UPDATE balances SET balance=10000000 WHERE user_id='1'");self.f.db.commit()
  with patch.object(self.e,'remember',side_effect=RuntimeError('storage failed')):
   with self.assertRaises(RuntimeError):await self.f.bridge.dispatch('stocks/trade',self.token,payload)
  self.assertEqual(self.f.balance(1),10000000)
  self.assertEqual(len(self.e.market(self.f.members[1])['positions']),2)
  self.assertEqual(self.f.db.execute("SELECT COUNT(*) FROM mari_web_stock_trades WHERE side LIKE '%_close'").fetchone()[0],0)
 async def test_separate_leverage_partial_close_retry_and_rankings(self):
  await self.order(leverage=1)
  first=await self.order(requestId='same-leverage-order-123');self.assertEqual(first,await self.order(requestId='same-leverage-order-123'))
  self.assertEqual(self.f.balance(1),9850000)
  self.price(12000)
  result=await self.order(action='close',quantity=4,price=12000)
  self.assertEqual((result['total'],result['profit']),(28000,8000))
  self.assertEqual(self.f.db.execute('SELECT qty,cost,notional FROM mari_web_leveraged').fetchone(),(6,30000,60000))
  self.assertEqual(self.f.bridge.leaderboard(1)['mine']['stockValue'],162000)
  rank=Rankings(self.f.bridge,WebError).stocks(1)['mine']
  self.assertEqual((rank['realized'],rank['unrealized'],rank['invested']),(8000,32000,150000))
  await self.order(action='close',quantity=6,price=12000)
  self.assertEqual(self.f.balance(1),9920000)
  self.assertEqual(self.f.db.execute('SELECT qty FROM mari_web_holdings').fetchone()[0],10)
 async def test_long_and_short_gap_liquidation_are_isolated_and_once(self):
  for side,p in [('long',4000),('short',17000)]:
   self.price(10000);await self.order(side=side)
   before=self.f.balance(1);self.price(p);self.e.settle();self.e.settle()
   self.assertEqual(self.f.balance(1),before)
   rows=self.f.db.execute('SELECT total,profit FROM mari_web_stock_trades WHERE side=?',(side+'_liquidate',)).fetchall()
   self.assertEqual(rows,[(0,-50000)])
  self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_leveraged').fetchone()[0],0)
  rank=Rankings(self.f.bridge,WebError).stocks(1)['mine'];self.assertEqual((rank['value'],rank['realized']),(-100,-100000))
 async def test_odd_price_split_closes_conserve_margin(self):
  self.price(10001)
  for side in ('long','short'):
   before=self.f.balance(1);await self.order(side=side,quantity=3,price=10001)
   self.assertEqual(before-self.f.balance(1),15002)
   for _ in range(3):await self.order(side=side,action='close',quantity=1,price=10001)
   self.assertEqual(self.f.balance(1),before)
 async def test_invalid_leverage_stale_quote_and_overclose_do_not_charge(self):
  for changes in [{'leverage':3},{'leverage':True},{'price':9999},{'action':'close'},{'quantity':1000000}]:
   with self.assertRaises(WebError):await self.order(**changes)
  self.assertEqual(self.f.balance(1),10000000)
  self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_stock_trades').fetchone()[0],0)
 async def test_history_pagination_reaches_listing_without_duplicates(self):
  self.f.db.execute("DELETE FROM mari_web_stock_days WHERE symbol='muro'")
  start=datetime(2026,8,1,tzinfo=KST)
  rows=[('muro',(start+timedelta(minutes=10*i)).isoformat(),10000+i,10001+i) for i in range(1250)]
  self.f.db.executemany('INSERT INTO mari_web_stock_days VALUES(?,?,?,?)',rows);self.f.db.commit()
  collected=[];before=''
  for expected,more in [(600,True),(600,True),(50,False)]:
   r=await self.f.bridge.dispatch('stocks/history',self.token,{'symbol':'muro','before':before})
   self.assertEqual((len(r['history']),r['hasMore']),(expected,more));collected=r['history']+collected;before=r['history'][0]['day']
  self.assertEqual([b['day'] for b in collected],[r[1] for r in rows])
  with self.assertRaises(WebError):await self.f.bridge.dispatch('stocks/history',None,{'symbol':'muro'})
 async def test_quarter_hour_migration_preserves_old_bars_and_positions(self):
  self.f.db.execute("DELETE FROM mari_web_stock_settings WHERE key='ten_minute_schedule'")
  self.f.db.execute("INSERT OR REPLACE INTO mari_web_stock_settings VALUES('quarter_hour_schedule','1')")
  self.f.db.execute("UPDATE mari_web_stocks SET day='2026-09-07T23:45:00+09:00'");self.f.db.commit()
  await self.order(leverage=1);before=list(self.f.db.execute('SELECT * FROM mari_web_stock_days'))
  self.assertEqual(self.f.balance(1),9900000);self.e.settle();self.assertEqual(before,list(self.f.db.execute('SELECT * FROM mari_web_stock_days')))
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,8,0,5,tzinfo=KST)),patch('mari_web_economy.stock_move_bps',return_value=1000):
   self.e.settle();self.e.settle();self.assertEqual(self.e.market(self.f.members[1])['stocks'][0]['price'],11000)
   self.assertEqual(self.f.db.execute("SELECT COUNT(*) FROM mari_web_stock_days WHERE symbol='muro'").fetchone()[0],2)

 async def test_haneul_listing_trade_news_and_board(self):
  from mari_stock_news import article
  from mari_web_social import Social
  market=self.e.market(self.f.members[1]);stock=next(v for v in market['stocks'] if v['symbol']=='haneul')
  self.assertEqual((stock['name'],stock['sector'],stock['price']),('하늘반도체','반도체',10000))
  before=list(self.f.db.execute("SELECT * FROM mari_web_stock_days WHERE symbol!='haneul'"))
  self.e.settle();self.assertEqual(before,list(self.f.db.execute("SELECT * FROM mari_web_stock_days WHERE symbol!='haneul'")))
  for leverage in (1,2):
   for side in ('long','short'):
    await self.order(symbol='haneul',leverage=leverage,side=side)
    await self.order(symbol='haneul',leverage=leverage,side=side,action='close')
  self.assertEqual(self.f.balance(1),10000000)
  for price in (5000,10000,15000):self.assertIn('하늘반도체',article('하늘반도체','반도체',10000,price)[0])
  board=Social(self.f.bridge,WebError).talk(self.f.members[1],{'symbol':'haneul'},'social/talk')
  self.assertEqual(board['total'],0)

 async def test_hundred_million_share_orders_and_five_recent_trades(self):
  with self.f.db:self.f.db.execute("UPDATE balances SET balance=5000000000000 WHERE user_id='1'")
  for side in ('long','short'):
   for lev in (1,2):
    before=self.f.balance(1)
    for bad in (100000001,True,1.5):
     with self.assertRaises(WebError):await self.order(side=side,leverage=lev,quantity=bad)
    self.assertEqual(before,self.f.balance(1))
    await self.order(side=side,leverage=lev,quantity=99999999)
    await self.order(side=side,leverage=lev,quantity=1)
    with self.assertRaises(WebError):await self.order(side=side,leverage=lev,quantity=1)
    await self.order(side=side,leverage=lev,action='close',quantity=100000000)
    self.assertEqual(before,self.f.balance(1))
    await self.order(side=side,leverage=lev,quantity=100000000)
    await self.order(side=side,leverage=lev,action='close',quantity=100000000)
    self.assertEqual(before,self.f.balance(1))
  market=self.e.market(self.f.members[1])
  self.assertEqual(len(market['trades']),5)
  self.assertEqual(len(market['positions']),0)
  self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_stock_trades').fetchone()[0],20)
