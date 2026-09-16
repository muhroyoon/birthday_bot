import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from test_bridge import Fixture
from mari_web_economy import KST, Economy
from mari_stock_policy import draw_regime_duration


class RandomMarketTests(unittest.TestCase):
 def setUp(self):
  self.f=Fixture();self.e=self.f.bridge.economy
  self.start=datetime(2026,9,16,12,tzinfo=KST)
 def tearDown(self):self.f.db.close()
 def trade(self,uid,side,qty=1,minutes=-1,rid=None,symbol='muro'):
  rid=rid or str(self.f.db.execute('SELECT COUNT(*) FROM mari_web_stock_trades').fetchone()[0])
  self.f.db.execute('INSERT INTO mari_web_stock_trades VALUES(?,?,?,?,?,?,?,?,?)',(rid,str(uid),symbol,side,qty,10000,10000,0,(self.start+timedelta(minutes=minutes)).timestamp()))
 def test_schedule_persists_and_catches_up_at_expiry(self):
  with patch('mari_web_economy.draw_regime',side_effect=[0,4,1]),patch('mari_web_economy.draw_regime_duration',return_value=timedelta(hours=3)):
   self.assertEqual(self.e.random_regime('muro',self.start),(52,False))
   self.assertEqual(self.e.random_regime('muro',self.start+timedelta(hours=2)),(52,False))
   self.assertEqual(self.e.random_regime('muro',self.start+timedelta(hours=6)),(51,False))
  self.f.db.commit();restarted=Economy(self.f.bridge,self.e.Error)
  with patch('mari_web_economy.draw_regime',side_effect=AssertionError('reroll')):
   self.assertEqual(restarted.random_regime('muro',self.start+timedelta(hours=6)),(51,False))
   self.assertEqual(restarted.random_regime('muro',self.start),(52,False))
 def test_duration_endpoints(self):
  for draw,minutes in [(0,30),(9,120)]:
   with patch('mari_stock_policy.secrets.randbelow',return_value=draw):
    self.assertEqual(draw_regime_duration(),timedelta(minutes=minutes))
 def test_trades_do_not_change_direction_probability_or_schedule(self):
  with patch.object(self.e,'stock_slot',return_value=self.start-timedelta(minutes=10)):self.e.settle()
  with patch('mari_web_economy.draw_regime',return_value=1):
   self.assertEqual(self.e.market_parameters('muro',self.start),(51,False))
  schedule=list(self.f.db.execute('SELECT * FROM mari_web_random_regimes'))
  for side in ('long_open','short_close','short_open','long_close'):
   for uid in range(20):self.trade(uid,side,qty=1000000)
   self.assertEqual(self.e.market_parameters('muro',self.start),(51,False))
   self.assertEqual(list(self.f.db.execute('SELECT * FROM mari_web_random_regimes')),schedule)
 def test_migration_ignores_trades_without_public_leak(self):
  with patch.object(self.e,'stock_slot',return_value=self.start-timedelta(minutes=10)):self.e.settle()
  before=list(self.f.db.execute('SELECT * FROM mari_web_stock_days'))
  self.trade(1,'long_open');self.f.db.commit()
  with patch.object(self.e,'stock_slot',return_value=self.start),patch('mari_web_economy.draw_regime',return_value=1),patch('mari_web_economy.stock_move_bps',return_value=100) as move:
   public=self.e.market(self.f.members[1])
   self.assertEqual(move.call_args_list[0].args,(51,False))
  self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_random_regimes').fetchone()[0],8)
  import json
  for key in ('random_regimes','expires','account_pressure','up_chance'):
   self.assertNotIn('"'+key+'"',json.dumps(public))
  for row in before:self.assertIn(row,list(self.f.db.execute('SELECT * FROM mari_web_stock_days')))
  with patch.object(self.e,'stock_slot',return_value=self.start),patch('mari_web_economy.stock_move_bps',side_effect=AssertionError('duplicate tick')):self.e.settle()
