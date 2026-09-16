import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from test_bridge import Fixture
from mari_web_economy import KST


class FiveMinuteMarketTests(unittest.TestCase):
 def setUp(self):
  self.f=Fixture();self.e=self.f.bridge.economy
  self.start=datetime(2026,9,16,12,tzinfo=KST)
 def tearDown(self):self.f.db.close()
 def test_clock_floors_to_five_minutes(self):
  with patch('mari_web_economy.datetime') as clock:
   clock.now.return_value=self.start+timedelta(minutes=9,seconds=59)
   self.assertEqual(self.e.stock_slot(),self.start+timedelta(minutes=5))
 def test_two_ticks_and_idempotence(self):
  with patch.object(self.e,'stock_slot',return_value=self.start):self.e.settle()
  before=list(self.f.db.execute('SELECT * FROM mari_web_stock_days'))
  with patch.object(self.e,'stock_slot',return_value=self.start+timedelta(minutes=10)),patch('mari_web_economy.stock_move_bps',return_value=100):
   public=self.e.market(self.f.members[1]);self.e.settle()
  self.assertEqual(public['nextUpdate'],(self.start+timedelta(minutes=15)).isoformat())
  self.assertEqual(self.f.db.execute("SELECT close FROM mari_web_stock_days WHERE symbol='muro' ORDER BY day").fetchall(),[(10000,),(10100,),(10201,)])
  for row in before:self.assertIn(row,list(self.f.db.execute('SELECT * FROM mari_web_stock_days')))
 def test_upgrade_does_not_backfill_old_five_minute_ticks(self):
  with patch.object(self.e,'stock_slot',return_value=self.start):self.e.settle()
  self.f.db.execute("DELETE FROM mari_web_stock_settings WHERE key='five_minute_start_v1'");self.f.db.commit()
  with patch.object(self.e,'stock_slot',return_value=self.start+timedelta(minutes=20)),patch('mari_web_economy.stock_move_bps',return_value=100):self.e.settle()
  stamps=[r[0] for r in self.f.db.execute("SELECT day FROM mari_web_stock_days WHERE symbol='muro' ORDER BY day")]
  self.assertEqual(stamps,[(self.start+timedelta(minutes=m)).isoformat() for m in (0,10,20)])
  with patch.object(self.e,'stock_slot',return_value=self.start+timedelta(minutes=25)),patch('mari_web_economy.stock_move_bps',return_value=100):self.e.settle()
  self.assertEqual(self.f.db.execute("SELECT COUNT(*) FROM mari_web_stock_days WHERE symbol='muro'").fetchone()[0],4)
