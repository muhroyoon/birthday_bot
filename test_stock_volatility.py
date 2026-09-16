import unittest
from datetime import datetime,timedelta
from unittest.mock import patch
from test_bridge import Fixture
from mari_web_economy import KST,Economy
import mari_stock_policy as policy

class VolatilityTests(unittest.TestCase):
 def setUp(self):
  self.f=Fixture();self.e=self.f.bridge.economy;self.start=datetime(2026,9,16,13,tzinfo=KST)
 def tearDown(self):self.f.db.close()
 def test_exact_state_weights(self):
  counts=[0]*5
  for n in range(100):
   with patch.object(policy.secrets,'randbelow',return_value=n):counts[policy.draw_volatility()]+=1
  self.assertEqual(counts,[10,20,40,20,10])
 def test_exact_band_weights_caps_and_reciprocal(self):
  for state,expected in enumerate([(950,45,5),(900,90,10),(800,180,20),(720,250,30),(650,300,50)]):
   counts=[0]*3
   for bucket in range(1000):
    with patch.object(policy.secrets,'randbelow',side_effect=[0,bucket,0]):move=policy.stock_move_bps(50,False,state)
    counts[0 if move==80 else 1 if move==401 else 2]+=1
   self.assertEqual(tuple(counts),expected)
   with patch.object(policy.secrets,'randbelow',side_effect=[0,999,1999]):up=policy.stock_move_bps(50,False,state)
   with patch.object(policy.secrets,'randbelow',side_effect=[99,999,1999]):down=policy.stock_move_bps(50,False,state)
   self.assertEqual(up,3500);self.assertEqual((1+up/10000)*(1+down/10000),1)
 def test_shared_schedule_restart_and_catchup(self):
  with patch('mari_web_economy.draw_volatility',side_effect=[0,4,2]),patch('mari_web_economy.draw_regime',side_effect=[1,3,0]),patch('mari_web_economy.draw_regime_duration',return_value=timedelta(hours=1)):
   self.assertEqual(self.e.private_volatility('muro',self.start),0)
   self.assertEqual(self.e.private_volatility('muro',self.start+timedelta(minutes=50)),0)
   self.assertEqual(self.e.private_volatility('muro',self.start+timedelta(hours=2)),2)
  regimes=self.f.db.execute('SELECT symbol,start,expires FROM mari_web_random_regimes ORDER BY start').fetchall()
  self.assertEqual(len(regimes),3)
  self.assertEqual(regimes,self.f.db.execute('SELECT symbol,start,expires FROM mari_web_volatility_states ORDER BY start').fetchall())
  self.f.db.commit();e=Economy(self.f.bridge,self.e.Error)
  with patch('mari_web_economy.draw_volatility',side_effect=AssertionError('reroll')):
   self.assertEqual(e.private_volatility('muro',self.start+timedelta(hours=1)),4)
 def test_direction_and_sideways_rule_are_unchanged(self):
  for state in range(5):
   positive=0
   for draw in range(100):
    with patch.object(policy.secrets,'randbelow',side_effect=[draw,0,0]):positive+=policy.stock_move_bps(55,False,state)>0
   self.assertEqual(positive,55)
   with patch.object(policy.secrets,'randbelow',side_effect=[0,999,1999]):
    self.assertEqual(policy.stock_move_bps(55,True,state),1225)
 def test_live_tick_uses_volatility_and_preserves_history(self):
  with patch.object(self.e,'stock_slot',return_value=self.start):self.e.settle()
  before=list(self.f.db.execute('SELECT * FROM mari_web_stock_days'))
  with patch.object(self.e,'stock_slot',return_value=self.start+timedelta(minutes=10)),patch('mari_web_economy.draw_volatility',return_value=4),patch('mari_web_economy.stock_move_bps',return_value=100) as move:
   public=self.e.market(self.f.members[1])
   self.assertTrue(all(c.kwargs=={'volatility':4} for c in move.call_args_list))
  import json
  self.assertNotIn('volatility',json.dumps(public))
  for row in before:self.assertIn(row,list(self.f.db.execute('SELECT * FROM mari_web_stock_days')))

 def test_existing_state_is_held_until_next_regime_then_replaced(self):
  for old_minutes in (20,360):
   symbol=str(old_minutes)
   end=self.start+timedelta(minutes=60)
   self.f.db.execute('INSERT INTO mari_web_random_regimes VALUES(?,?,?,?)',(symbol,self.start.isoformat(),end.isoformat(),1))
   self.f.db.execute('INSERT INTO mari_web_volatility_states VALUES(?,?,?,?)',(symbol,self.start.isoformat(),(self.start+timedelta(minutes=old_minutes)).isoformat(),0))
   with patch('mari_web_economy.draw_volatility',side_effect=AssertionError('early redraw')):
    self.assertEqual(self.e.private_volatility(symbol,self.start+timedelta(minutes=50)),0)
   with patch('mari_web_economy.draw_volatility',return_value=4),patch('mari_web_economy.draw_regime',return_value=3),patch('mari_web_economy.draw_regime_duration',return_value=timedelta(minutes=30)):
    self.assertEqual(self.e.private_volatility(symbol,end),4)
    self.assertEqual(self.e.random_regime(symbol,end),(45,False))
   self.assertEqual(self.f.db.execute('SELECT start,expires FROM mari_web_random_regimes WHERE symbol=? ORDER BY start DESC LIMIT 1',(symbol,)).fetchone(),self.f.db.execute('SELECT start,expires FROM mari_web_volatility_states WHERE symbol=? ORDER BY start DESC LIMIT 1',(symbol,)).fetchone())
 def test_symbols_have_independent_schedules_and_both_draws_roll_back(self):
  with patch('mari_web_economy.draw_regime_duration',side_effect=[timedelta(minutes=30),timedelta(minutes=120)]):
   with self.f.db:
    self.e.random_regime('muro',self.start);self.e.random_regime('hoon',self.start)
  self.assertNotEqual(*[r[0] for r in self.f.db.execute('SELECT expires FROM mari_web_random_regimes ORDER BY symbol')])
  before=list(self.f.db.execute('SELECT * FROM mari_web_random_regimes'))
  with self.assertRaises(RuntimeError),patch('mari_web_economy.draw_volatility',side_effect=RuntimeError('failed draw')):
   with self.f.db:self.e.random_regime('muro',self.start+timedelta(minutes=30))
  self.assertEqual(before,list(self.f.db.execute('SELECT * FROM mari_web_random_regimes')))
