import unittest
from datetime import datetime,timedelta
from unittest.mock import patch
from test_bridge import Fixture
from mari_web_bridge import WebError
from mari_web_economy import KST
from mari_web_rankings import Rankings

class DelistingTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.f=Fixture();self.token=await self.f.login();self.e=self.f.bridge.economy
  self.base=datetime(2026,9,9,4,tzinfo=KST)
  self.clock=patch.object(self.e,'stock_slot',return_value=self.base);self.clock.start();self.e.settle()
 async def asyncTearDown(self):self.clock.stop();self.f.db.close()
 async def seed(self):
  for side in ('long','short'):
   for lev in (1,2):
    await self.f.bridge.dispatch('stocks/trade',self.token,dict(requestId='delist-open-'+side+str(lev),symbol='muro',side=side,leverage=lev,action='open',settlement='linear',quantity=10,price=10000))
  with self.f.db:self.f.db.execute("UPDATE mari_web_stocks SET price=120 WHERE symbol='muro'")
 async def test_floor_settles_all_positions_once_and_stops_history(self):
  await self.seed();before=self.f.balance(1)
  with patch.object(self.e,'stock_slot',return_value=self.base+timedelta(minutes=30)),patch('mari_web_economy.stock_move_bps',return_value=-3000):self.e.settle()
  self.assertEqual(self.f.balance(1)-before,349000)
  self.assertEqual(self.f.db.execute("SELECT price,day FROM mari_web_stocks WHERE symbol='muro'").fetchone(),(100,(self.base+timedelta(minutes=5)).isoformat()))
  trades=self.f.db.execute("SELECT SUM(total),SUM(profit),COUNT(*) FROM mari_web_stock_trades WHERE side LIKE '%_close' OR side LIKE '%_liquidate'").fetchone()
  self.assertEqual(trades,(349000,49000,4))
  self.assertEqual(Rankings(self.f.bridge,WebError).stocks(1)['mine']['realized'],49000)
  bars=list(self.f.db.execute("SELECT * FROM mari_web_stock_days WHERE symbol='muro'"));balance=self.f.balance(1)
  with patch.object(self.e,'stock_slot',return_value=self.base+timedelta(hours=6)),patch('mari_web_economy.stock_move_bps',return_value=100):self.e.settle()
  self.assertEqual(balance,self.f.balance(1));self.assertEqual(bars,list(self.f.db.execute("SELECT * FROM mari_web_stock_days WHERE symbol='muro'")))
  stock=self.e.market(self.f.members[1])['stocks'][0];self.assertTrue(stock['delistedAt']);self.assertEqual(stock['price'],100)
  with self.assertRaises(WebError):await self.f.bridge.dispatch('stocks/trade',self.token,dict(requestId='delisted-new-order-01',symbol='muro',side='long',leverage=1,action='open',quantity=1,price=100))
 async def test_current_floor_delists_but_old_floor_bar_does_not(self):
  with self.f.db:
   self.f.db.execute("INSERT INTO mari_web_stock_days VALUES('muro','2026-09-08T00:00:00+09:00',100,100)")
   self.f.db.execute("UPDATE mari_web_stocks SET price=100 WHERE symbol='haneul'")
   self.f.db.execute("UPDATE mari_web_stock_days SET close=100 WHERE symbol='haneul'")
  self.e.settle()
  self.assertEqual(self.f.db.execute('SELECT symbol FROM mari_web_delisted').fetchall(),[('haneul',)])
 async def test_failure_rolls_back_delisting_and_payouts(self):
  await self.seed()
  with self.f.db:
   self.f.db.execute("UPDATE mari_web_stocks SET price=100 WHERE symbol='muro'")
   self.f.db.execute("CREATE TRIGGER fail_delisting BEFORE INSERT ON mari_web_stock_trades WHEN NEW.id LIKE 'delist:%' BEGIN SELECT RAISE(ABORT,'disk failure'); END")
  before=self.f.balance(1)
  with self.assertRaises(Exception):self.e.settle()
  self.assertEqual(self.f.balance(1),before);self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_delisted').fetchone()[0],0)
  self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_holdings WHERE qty>0').fetchone()[0],1)

 async def test_bio_listing_is_separate_and_keeps_archived_records(self):
  with self.f.db:
   self.f.db.execute("INSERT INTO mari_web_delisted VALUES('gimcheon','2026-09-09T05:20:00+09:00',100)")
   self.f.db.execute("INSERT INTO mari_web_stocks VALUES('gimcheon',100,'2026-09-09T05:20:00+09:00')")
  market=self.e.market(self.f.members[1]);stocks={s['symbol']:s for s in market['stocks']}
  self.assertNotIn('gimcheon',stocks)
  bio=stocks['gimcheon_bio']
  self.assertEqual((bio['name'],bio['price'],bio['initialPrice'],bio['delistingPrice']),('김천바이오',5000,5000,50))
  self.assertEqual(self.f.db.execute("SELECT price FROM mari_web_delisted WHERE symbol='gimcheon'").fetchone(),(100,))
  self.e.settle();self.assertEqual(self.e.listing_price('gimcheon_bio'),5000)
  self.assertTrue(all(s['initialPrice']==10000 and s['delistingPrice']==100 for key,s in stocks.items() if key not in ('gimcheon_bio','jeumi_fb')))
 async def test_bio_survives_100_and_settles_at_50_only_once(self):
  for side in ('long','short'):
   for lev in (1,2):
    await self.f.bridge.dispatch('stocks/trade',self.token,dict(requestId='bio-open-order-'+side+str(lev),symbol='gimcheon_bio',side=side,leverage=lev,action='open',quantity=10,price=5000))
  with self.f.db:self.f.db.execute("UPDATE mari_web_stocks SET price=100 WHERE symbol='gimcheon_bio'")
  self.e.settle()
  self.assertIsNone(self.f.db.execute("SELECT * FROM mari_web_delisted WHERE symbol='gimcheon_bio'").fetchone())
  before=self.f.balance(1)
  with patch.object(self.e,'stock_slot',return_value=self.base+timedelta(minutes=5)),patch('mari_web_economy.stock_move_bps',return_value=-9000):self.e.settle()
  self.assertEqual(self.f.db.execute("SELECT price FROM mari_web_delisted WHERE symbol='gimcheon_bio'").fetchone(),(50,))
  self.assertEqual(self.f.balance(1)-before,174500)
  balance=self.f.balance(1)
  with patch.object(self.e,'stock_slot',return_value=self.base+timedelta(hours=12)):self.e.settle()
  self.assertEqual(self.f.balance(1),balance)
  self.assertEqual(self.e.listing_price('gimcheon_bio'),5000)
