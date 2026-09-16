import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from fractions import Fraction
from test_bridge import Fixture
from mari_web_economy import KST, Economy
from mari_stock_policy import draw_regime_duration, stock_move_bps


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
   self.assertEqual(self.e.random_regime('muro',self.start),(60,False))
   self.assertEqual(self.e.random_regime('muro',self.start+timedelta(hours=2)),(60,False))
   self.assertEqual(self.e.random_regime('muro',self.start+timedelta(hours=6)),(55,False))
  self.f.db.commit();restarted=Economy(self.f.bridge,self.e.Error)
  with patch('mari_web_economy.draw_regime',side_effect=AssertionError('reroll')):
   self.assertEqual(restarted.random_regime('muro',self.start+timedelta(hours=6)),(55,False))
   self.assertEqual(restarted.random_regime('muro',self.start),(60,False))
 def test_one_vote_netting_and_window_excludes_forced_and_future(self):
  for _ in range(20):self.trade(1,'long_open')
  self.assertEqual(self.e.account_pressure('muro',self.start),Fraction(1,5))
  self.trade(1,'long_close',20)
  self.trade(2,'short_open')
  self.trade(3,'short_close',rid='delist:forced')
  self.trade(4,'short_liquidate')
  self.trade(5,'long_open',minutes=0)
  self.trade(6,'long_open',minutes=-31)
  self.trade(7,'long_open',symbol='samsung')
  self.assertEqual(self.e.account_pressure('muro',self.start),Fraction(-1,5))
 def test_maximum_two_points_and_balanced_zero(self):
  for uid in range(20):self.trade(uid,'short_close')
  self.assertEqual(self.e.account_pressure('muro',self.start),2)
  for uid in range(20,40):self.trade(uid,'short_open',1000000)
  self.assertEqual(self.e.account_pressure('muro',self.start),0)
 def test_duration_endpoints_and_fractional_probability(self):
  for draw,minutes in [(0,60),(30,360)]:
   with patch('mari_stock_policy.secrets.randbelow',return_value=draw):
    self.assertEqual(draw_regime_duration(),timedelta(minutes=minutes))
  for draw,positive in [(5519,True),(5520,False)]:
   with patch('mari_stock_policy.secrets.randbelow',side_effect=[draw,0,0]):
    self.assertEqual(stock_move_bps(Fraction(276,5))>0,positive)
 def test_migration_pressure_reaches_price_draw_without_public_leak(self):
  with patch.object(self.e,'stock_slot',return_value=self.start-timedelta(minutes=10)):self.e.settle()
  before=list(self.f.db.execute('SELECT * FROM mari_web_stock_days'))
  self.trade(1,'long_open');self.f.db.commit()
  with patch.object(self.e,'stock_slot',return_value=self.start),patch('mari_web_economy.draw_regime',return_value=1),patch('mari_web_economy.stock_move_bps',return_value=100) as move:
   public=self.e.market(self.f.members[1])
   self.assertEqual(move.call_args_list[0].args,(Fraction(276,5),False))
  self.assertEqual(self.f.db.execute('SELECT COUNT(*) FROM mari_web_random_regimes').fetchone()[0],8)
  import json
  for key in ('random_regimes','expires','account_pressure','up_chance'):
   self.assertNotIn('"'+key+'"',json.dumps(public))
  for row in before:self.assertIn(row,list(self.f.db.execute('SELECT * FROM mari_web_stock_days')))
  with patch.object(self.e,'stock_slot',return_value=self.start),patch('mari_web_economy.stock_move_bps',side_effect=AssertionError('duplicate tick')):self.e.settle()
