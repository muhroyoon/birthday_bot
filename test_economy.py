import unittest
from datetime import date, datetime
from mari_web_economy import KST
from unittest.mock import patch
from test_bridge import Fixture
from mari_web_bridge import WebError

class EconomyTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):self.f=Fixture();self.token=await self.f.login();self.e=self.f.bridge.economy
 async def asyncTearDown(self):self.f.db.close()
 async def call(self,action,data):return await self.f.bridge.dispatch(action,self.token,data)
 async def test_add_buy_partial_sell_cost_basis_and_retry(self):
  await self.call('stocks',{})
  buy={'requestId':'buy-a-123456789012','symbol':'muro','side':'long','action':'open','quantity':10,'price':10000}
  await self.call('stocks/trade',buy);await self.call('stocks/trade',buy)
  self.assertEqual(self.f.balance(1),9900000)
  await self.call('stocks/trade',{**buy,'requestId':'buy-b-123456789012','quantity':5})
  await self.call('stocks/trade',{**buy,'requestId':'sell-a-12345678901','side':'long','action':'close','quantity':6})
  self.assertEqual(self.f.db.execute('SELECT qty,cost FROM mari_web_holdings').fetchone(),(9,90000));self.assertEqual(self.f.balance(1),9910000)
  candle=next(s for s in (await self.call('stocks',{}))['stocks'] if s['symbol']=='muro')['history'][-1]
  self.assertEqual((candle['buyVolume'],candle['sellVolume']),(15,6));self.assertEqual(candle['volume'],21);self.assertEqual((candle['high'],candle['low']),(10000,10000))
  with self.assertRaises(WebError):await self.call('stocks/trade',{**buy,'quantity':2})
 async def test_invalid_funds_and_quantity_roll_back(self):
  await self.call('stocks',{})
  for changes in [{'quantity':0},{'quantity':1.5},{'quantity':True},{'quantity':1001},{'side':'long','action':'close'},{'price':9999}]:
   with self.assertRaises(WebError):await self.call('stocks/trade',{'requestId':'invalid-1234567890','symbol':'muro','side':'long','action':'open','quantity':1,'price':10000,**changes})
  self.assertEqual(self.f.balance(1),10000000);self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_stock_trades').fetchone()[0],0)
 async def test_midnight_settles_once_and_rejects_stale_order(self):
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,6,0,tzinfo=KST)):await self.call('stocks',{})
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,6,0,10,tzinfo=KST)),patch('mari_web_economy.stock_move_bps',return_value=2000):
   market=await self.call('stocks',{});self.assertEqual(next(s for s in market['stocks'] if s['symbol']=='muro')['price'],14400);self.assertEqual(len(next(s for s in market['stocks'] if s['symbol']=='muro')['history']),3)
   self.assertEqual(next(s for s in (await self.call('stocks',{}))['stocks'] if s['symbol']=='muro')['price'],14400)
   with self.assertRaises(WebError):await self.call('stocks/trade',{'requestId':'stale-123456789012','symbol':'muro','side':'long','action':'open','quantity':1,'price':10000})
 async def test_daily_drop_and_price_floor(self):
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,6,0,tzinfo=KST)):await self.call('stocks',{})
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,6,0,5,tzinfo=KST)),patch('mari_web_economy.stock_move_bps',return_value=-2000):
   self.assertEqual(next(s for s in (await self.call('stocks',{}))['stocks'] if s['symbol']=='muro')['price'],8000)
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,10,7,0,tzinfo=KST)),patch('mari_web_economy.stock_move_bps',return_value=-2000):
   self.assertEqual(next(s for s in (await self.call('stocks',{}))['stocks'] if s['symbol']=='muro')['price'],100)
 async def test_legacy_migration_preserves_price_then_updates_at_next_slot(self):
  self.f.db.execute("INSERT INTO mari_web_stocks VALUES('muro',12345,'2026-09-06')")
  self.f.db.execute("INSERT INTO mari_web_stock_days VALUES('muro','2026-09-06',10000,12345)")
  self.f.db.commit()
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,7,23,55,tzinfo=KST)):
   m=await self.call('stocks',{});self.assertEqual(next(s for s in m['stocks'] if s['symbol']=='muro')['price'],12345)
   self.assertEqual(len(next(s for s in m['stocks'] if s['symbol']=='muro')['history']),1)
   self.assertEqual(m['nextUpdate'],'2026-09-08T00:00:00+09:00')
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,8,0,tzinfo=KST)),patch('mari_web_economy.stock_move_bps',return_value=2000):
   m=await self.call('stocks',{});self.assertEqual(next(s for s in m['stocks'] if s['symbol']=='muro')['price'],14814)
   self.assertEqual(m['nextUpdate'],'2026-09-08T00:05:00+09:00')
 async def test_half_hour_migration_does_not_reroll_old_slots(self):
  self.f.db.execute("INSERT INTO mari_web_stock_settings VALUES('half_hour_schedule','1')")
  self.f.db.execute("INSERT INTO mari_web_holdings VALUES('1','muro',5,50000)")
  self.f.db.execute("INSERT INTO mari_web_stocks VALUES('muro',12345,'2026-09-07T00:00:00+09:00')")
  self.f.db.execute("INSERT INTO mari_web_stock_days VALUES('muro','2026-09-07T00:00:00+09:00',10000,12345)")
  self.f.db.commit()
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,7,5,tzinfo=KST)):
   self.e.settle();self.assertEqual(self.e.stock_notifications(),[])
   self.assertEqual(self.f.balance(1),10000000)
   self.assertEqual(self.f.db.execute("SELECT qty,cost FROM mari_web_holdings WHERE user_id='1'").fetchone(),(5,50000))
   self.assertEqual(self.f.db.execute("SELECT price FROM mari_web_stocks WHERE symbol='muro'").fetchone()[0],12345)
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,7,5,5,tzinfo=KST)),patch('mari_web_economy.stock_move_bps',return_value=2000):
   self.e.settle();self.assertEqual(len(self.e.stock_notifications()),1)
   self.assertEqual(self.f.db.execute("SELECT price FROM mari_web_stocks WHERE symbol='muro'").fetchone()[0],14814)
 async def test_slot_boundaries(self):
  for hour,minute,expected in [(hour,minute,minute//5*5) for hour in (0,7,8,15,16,23) for minute in range(60)]:
   with patch('mari_web_economy.datetime') as clock:
    clock.now.return_value=datetime(2026,9,7,hour,minute,tzinfo=KST)
    self.assertEqual(self.e.stock_slot(),datetime(2026,9,7,hour,expected,tzinfo=KST))
 async def test_stock_notices_are_grouped_and_deduplicated(self):
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,6,0,tzinfo=KST)):
   self.e.settle();self.assertEqual(self.e.stock_notifications(),[])
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,6,0,10,tzinfo=KST)),patch('mari_web_economy.stock_move_bps',return_value=2000):
   self.e.settle();self.e.settle()
   notices=self.e.stock_notifications();self.assertEqual(len(notices),2)
   self.assertEqual(notices[0]['at'],'2026-09-06T00:10:00+09:00')
   self.assertEqual(notices[0]['url'],'/games/stocks')
   self.assertEqual(notices[0]['body'].count('%'),8)
   self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_stock_news').fetchone()[0],16)
   headlines=[r[0] for r in self.f.db.execute("SELECT headline FROM mari_web_stock_news WHERE symbol='muro' ORDER BY slot")]
   self.assertNotEqual(headlines[0],headlines[1])
   self.assertEqual(len((await self.call('stocks',{}))['news']),16)
 async def test_merge_games_charge_once_and_create_ranked_tickets(self):
  for game in ('suika','2048'):
   data={'requestId':'merge-game-test-'+game,'game':game}
   ticket=await self.call('tickets/start',data)
   self.assertEqual(ticket,await self.call('tickets/start',data))
   self.assertEqual(ticket['config'],{'mode':game,'difficulty':'normal','seconds':600})
   self.assertEqual(self.f.bridge.training.ticket(self.f.members[1],{'id':ticket['id']})[2],game)
  self.assertEqual(self.f.balance(1),9700000)
 async def test_paid_start_is_atomic_and_retries_charge_once(self):
  data={'requestId':'ticket-12345678901','mode':'flick','difficulty':'normal','seconds':15}
  t=await self.call('training/start',data);self.assertEqual(t,(await self.call('training/start',data)));self.assertEqual(self.f.balance(1),9850000)
  with self.assertRaises(WebError):await self.call('training/start',{**data,'seconds':30})
  self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_training_runs').fetchone()[0],1)
  self.f.db.execute("UPDATE balances SET balance=1 WHERE user_id='1'");self.f.db.commit()
  with self.assertRaises(WebError):await self.call('tickets/start',{'requestId':'empty-123456789012','game':'apple'})
  self.assertEqual(self.f.balance(1),1)
 async def test_fortune_once_per_day_shared_across_server_and_result_preserved(self):
  data={'requestId':'fortune-1234567890','fortune':{'date':self.e.today().isoformat(),'weapon':'test'}}
  one=await self.call('tickets/fortune',data);two=await self.call('tickets/fortune',{**data,'requestId':'fortune-abcdefghi','fortune':{**data['fortune'],'weapon':'changed'}})
  self.assertEqual(one,two);self.assertEqual(self.f.balance(1),9000000)
  self.assertEqual((await self.call('tickets/status',{}))['fortune'],one)
 async def test_ticket_cannot_be_reused_by_another_account(self):
  data={'requestId':'ticket-abcdefghi12','game':'snake'};await self.call('tickets/start',data);other=await self.f.login(2)
  with self.assertRaises(WebError):await self.f.bridge.dispatch('tickets/start',other,data)
  self.assertEqual(self.f.balance(2),10000000)
 async def test_creation_failure_restores_balance(self):
  def fail(*a):raise RuntimeError('failure')
  with self.assertRaises(RuntimeError):self.e.start(self.f.members[1],{'requestId':'rollback-123456789'},'aim',fail)
  self.assertEqual(self.f.balance(1),10000000);self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_passes').fetchone()[0],0)

 async def test_short_profit_add_partial_close_and_retry(self):
  await self.call('stocks',{})
  uid='1'
  order={'requestId':'short-first-123456','symbol':'muro','side':'short','action':'open','quantity':10,'price':10000}
  await self.call('stocks/trade',order);await self.call('stocks/trade',order)
  self.assertEqual(self.f.balance(1),9900000)
  self.f.db.execute("UPDATE mari_web_stocks SET price=8000 WHERE symbol='muro'")
  self.f.db.execute("UPDATE mari_web_stock_days SET close=8000 WHERE symbol='muro'");self.f.db.commit()
  await self.call('stocks/trade',{**order,'requestId':'short-add-12345678','quantity':5,'price':8000})
  pos=(await self.call('stocks',{}))['positions'][0]
  self.assertEqual((pos['quantity'],pos['cost'],pos['profit'],pos['equity']),(15,140000,20000,160000))
  result=await self.call('stocks/trade',{**order,'requestId':'short-close-123456','action':'close','quantity':6,'price':8000})
  self.assertEqual((result['total'],result['profit']),(64000,8000))
  self.assertEqual(self.f.db.execute('SELECT qty,cost FROM mari_web_shorts').fetchone(),(9,84000))
  result=await self.call('stocks/trade',{**order,'requestId':'short-rest-1234567','action':'close','quantity':9,'price':8000})
  self.assertEqual(result['total'],96000);self.assertEqual(self.f.balance(1),10020000)
 async def test_existing_holdings_remain_long_without_wallet_change(self):
  self.f.db.execute("INSERT INTO mari_web_holdings VALUES('1','muro',3,17001)");self.f.db.commit()
  m=await self.call('stocks',{});p=m['positions'][0]
  self.assertEqual((p['side'],p['quantity'],p['cost'],p['entry'],p['equity']),('long',3,17001,5667,30000))
  self.assertEqual(m['balance'],10000000)
  await self.call('stocks',{})
  self.assertEqual(len((await self.call('stocks',{}))['positions']),1)
 async def test_short_liquidation_on_intermediate_tick_is_once_and_isolated(self):
  base=datetime(2026,9,7,0,tzinfo=KST)
  with patch.object(self.e,'stock_slot',return_value=base):
   await self.call('stocks',{})
   for side in ('short','long'):
    await self.call('stocks/trade',{'requestId':'liquidation-open-'+side,'symbol':'muro','side':side,'action':'open','quantity':10,'price':10000})
  # Repeated 40% gains cross liquidation; a later 40% drop must not revive the position.
  class PriceRandom:
   def __init__(self):self.i=0
   def __call__(self,*args,**kwargs):
    self.i+=1
    return -4000 if self.i==5 else 4000
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,7,0,50,tzinfo=KST)),patch('mari_web_economy.stock_move_bps',side_effect=PriceRandom()):
   self.e.settle();self.e.settle()
  self.assertEqual(self.f.balance(1),9800000)
  self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_shorts').fetchone()[0],0)
  self.assertEqual(self.f.db.execute('SELECT qty FROM mari_web_holdings').fetchone()[0],10)
  trades=self.f.db.execute("SELECT total,profit FROM mari_web_stock_trades WHERE side='short_liquidate'").fetchall()
  self.assertEqual(trades,[(0,-100000)])
 async def test_position_ranking_counts_long_and_short_equity(self):
  await self.call('stocks',{})
  self.f.db.execute("INSERT INTO mari_web_holdings VALUES('1','muro',3,15000)")
  self.f.db.execute("INSERT INTO mari_web_shorts VALUES('1','muro',2,24000)")
  self.f.db.commit()
  result=self.f.bridge.leaderboard(1)['mine']
  self.assertEqual(result['stockValue'],58000)
  self.assertEqual(result['totalAssets'],result['balance']+result['savings']+58000)
 async def test_old_client_and_invalid_side_do_not_trade(self):
  await self.call('stocks',{})
  for side,action in [('buy',None),('sell',None),('wrong','open'),('short','wrong')]:
   with self.assertRaises(WebError):
    await self.call('stocks/trade',{'requestId':'invalid-old-client','symbol':'muro','side':side,'action':action,'quantity':1,'price':10000})
  self.assertEqual(self.f.balance(1),10000000)
 async def test_short_rounding_conserves_margin_and_prevents_overclose(self):
  await self.call('stocks',{})
  self.f.db.execute("INSERT INTO mari_web_shorts VALUES('1','muro',3,30001)");self.f.db.commit()
  before=self.f.balance(1)
  for i in range(3):
   await self.call('stocks/trade',{'requestId':'rounding-close-'+str(i)+'-test','symbol':'muro','side':'short','action':'close','quantity':1,'price':10000})
  self.assertEqual(self.f.balance(1)-before,30002)
  with self.assertRaises(WebError):
   await self.call('stocks/trade',{'requestId':'rounding-overclose','symbol':'muro','side':'short','action':'close','quantity':1,'price':10000})

 async def test_regime_weights_direction_and_exact_endpoints(self):
  from mari_web_economy import stock_move_bps
  from fractions import Fraction
  counts={80:0,401:0,1501:0}
  for bucket in range(1000):
   low,high=(80,400) if bucket<800 else (401,1500) if bucket<980 else (1501,3500)
   counts[low]+=1
   for magnitude in (0,high-low):
    moves=[]
    for direction in (0,1):
     with patch('mari_web_economy.secrets.randbelow',side_effect=[0 if direction else 99,bucket,magnitude]) as rng:
      move=stock_move_bps();moves.append(move)
      expected=low+magnitude if direction else Fraction(-10000*(low+magnitude),10000+low+magnitude)
      self.assertEqual(move,expected)
      self.assertEqual([c.args[0] for c in rng.call_args_list],[100,1000,high-low+1])
    self.assertEqual((1+Fraction(moves[0],10000))*(1+Fraction(moves[1],10000)),1)
  self.assertEqual(counts,{80:800,401:180,1501:20})
 async def test_new_shock_moves_and_caps(self):
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,7,0,tzinfo=KST)):self.e.settle()
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,7,0,5,tzinfo=KST)),patch('mari_web_economy.stock_move_bps',side_effect=[5500,__import__("fractions").Fraction(-55000000,15500),100,-100,2500,-2500,1000,500]):
   self.e.settle()
  prices=dict(self.f.db.execute('SELECT symbol,price FROM mari_web_stocks'))
  self.assertEqual(prices['muro'],15500);self.assertEqual(prices['jeumi_fb'],9677)
  self.assertEqual(prices['samsung'],10100);self.assertEqual(prices['gimcheon_bio'],4950)
  self.f.db.execute("UPDATE mari_web_stocks SET price=10000000 WHERE symbol='muro'")
  self.f.db.execute("UPDATE mari_web_stocks SET price=100 WHERE symbol='jeumi_fb'");self.f.db.commit()
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,7,0,10,tzinfo=KST)),patch('mari_web_economy.stock_move_bps',side_effect=[5500,__import__("fractions").Fraction(-55000000,15500),100,-100,2500,-2500,1000,500]):
   self.e.settle()
  prices=dict(self.f.db.execute('SELECT symbol,price FROM mari_web_stocks'))
  self.assertEqual(prices['muro'],10000000);self.assertEqual(prices['jeumi_fb'],150)
