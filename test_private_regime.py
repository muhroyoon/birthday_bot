import json
import unittest
from datetime import datetime
from unittest.mock import patch
from test_bridge import Fixture
from mari_web_economy import Economy,KST,stock_move_bps
from mari_web_bridge import WebError

class PrivateRegimeTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):self.f=Fixture();self.token=await self.f.login();self.e=self.f.bridge.economy
 async def asyncTearDown(self):self.f.db.close()
 def test_exact_direction_probabilities(self):
  for chance in (48,49,50,51,52):
   positive=0
   for draw in range(100):
    with patch('mari_web_economy.secrets.randbelow',side_effect=[draw,0,0]):positive+=stock_move_bps(chance)>0
   self.assertEqual(positive,chance)
 def test_day_symbol_independence_restart_and_midnight(self):
  before=datetime(2026,9,9,23,50,tzinfo=KST);after=datetime(2026,9,10,0,tzinfo=KST)
  with self.f.db,patch('mari_web_economy.secrets.randbelow',side_effect=[1,0,0]) as rng:
   self.assertEqual(self.e.private_up_chance('muro',before),55)
   self.assertEqual(self.e.private_up_chance('haneul',before),45)
   self.assertEqual(self.e.private_up_chance('muro',before),55)
   self.assertEqual(self.e.private_up_chance('muro',after),45)
   self.assertEqual(rng.call_count,3)
  restarted=Economy(self.f.bridge,WebError)
  with patch('mari_web_economy.secrets.randbelow',side_effect=AssertionError('must not reroll')):
   self.assertEqual(restarted.private_up_chance('muro',before),55)
 def test_catchup_uses_each_dates_bias_and_does_not_expose_it(self):
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,9,23,50,tzinfo=KST)):self.e.settle()
  self.f.db.execute("INSERT OR REPLACE INTO mari_web_five_state_regimes VALUES('muro','2026-09-10T00:00:00+09:00',3)");self.f.db.commit()
  self.f.db.execute("UPDATE mari_web_stock_settings SET value='2026-09-11T00:00:00+09:00' WHERE key='random_regime_start_v1'");self.f.db.commit()
  with patch.object(self.e,'stock_slot',return_value=datetime(2026,9,10,0,10,tzinfo=KST)),patch('mari_web_economy.stock_move_bps',return_value=100) as moves:
   market=self.e.market(self.f.members[1]);self.assertEqual([c.args for c in moves.call_args_list[1:3]],[(49,False),(49,False)])
  def keys(v):
   if isinstance(v,dict):return set(v).union(*(keys(x) for x in v.values()))
   if isinstance(v,list):return set().union(*(keys(x) for x in v))
   return set()
  public=[market,self.e.history({'symbol':'muro'}),self.e.stock_notifications()]
  self.assertFalse(keys(public)&{'bull','regime','up_chance','private_regimes','sideways','window','six_hour_regimes','five_state_regimes'})
  self.assertEqual(len(self.f.db.execute('SELECT * FROM mari_web_five_state_regimes').fetchall()),16)

 def test_five_states_exact_weights_and_independent_symbols(self):
  counts={52:0,51:0,50:0,49:0,48:0}
  slot=datetime(2026,9,9,3,tzinfo=KST)
  with self.f.db:
   for draw in range(100):
    with patch('mari_web_economy.secrets.randbelow',return_value=draw):
     chance,sideways=self.e.private_regime('symbol-'+str(draw),slot)
    expected=52 if draw<10 else 51 if draw<35 else 50 if draw<65 else 49 if draw<90 else 48
    self.assertEqual((chance,sideways),(expected,expected==50));counts[chance]+=1
  self.assertEqual(counts,{52:10,51:25,50:30,49:25,48:10})

 def test_six_hour_boundaries_and_restart_preserve_draws(self):
  with self.f.db:
   for hour in (0,6,12,18):
    with patch('mari_web_economy.secrets.randbelow',return_value=0) as rng:
     self.assertEqual(self.e.private_regime('muro',datetime(2026,9,9,hour,tzinfo=KST)),(52,False))
     self.assertEqual(self.e.private_regime('muro',datetime(2026,9,9,hour+5,59,tzinfo=KST)),(52,False))
     self.assertEqual(rng.call_count,1)
  restarted=Economy(self.f.bridge,WebError)
  with patch('mari_web_economy.secrets.randbelow',side_effect=AssertionError('must not reroll')):
   self.assertEqual(restarted.private_regime('muro',datetime(2026,9,9,15,tzinfo=KST)),(52,False))
  with self.f.db,patch('mari_web_economy.secrets.randbelow',return_value=99):
   self.assertEqual(restarted.private_regime('muro',datetime(2026,9,10,0,tzinfo=KST)),(48,False))

 def test_upgrade_preserves_old_regimes_prices_and_positions(self):
  slot=datetime(2026,9,9,3,tzinfo=KST)
  with patch.object(self.e,'stock_slot',return_value=slot):
   self.e.settle()
   with self.f.db:
    self.f.db.execute("INSERT INTO mari_web_six_hour_regimes VALUES('muro','2026-09-09T00:00:00+09:00',2)")
    self.f.db.execute('DELETE FROM mari_web_five_state_regimes')
    self.f.db.execute("INSERT INTO mari_web_holdings VALUES('1','muro',10,100000)")
   before=list(self.f.db.execute('SELECT * FROM mari_web_stock_days'))
   self.e.settle();self.e.settle()
  self.assertEqual(before,list(self.f.db.execute('SELECT * FROM mari_web_stock_days')))
  self.assertEqual(self.f.db.execute('SELECT qty,cost FROM mari_web_holdings').fetchone(),(10,100000))
  self.assertEqual(self.f.db.execute('SELECT regime FROM mari_web_six_hour_regimes').fetchone(),(2,))
  self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_five_state_regimes').fetchone()[0],8)
