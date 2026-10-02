import sqlite3
import unittest
import ast
import copy
from pathlib import Path
from mari_attendance_rewards import pay_reward, reward_amount


class AttendanceRewardsTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE balances(user_id TEXT PRIMARY KEY, balance INTEGER NOT NULL)')

    def test_amounts_and_non_winners(self):
        self.assertEqual([reward_amount(i) for i in range(1, 6)], [5000000, 3000000, 1000000, 0, 0])

    def test_replay_and_rank_collision_do_not_pay_twice(self):
        self.assertEqual(pay_reward(self.db, 'g', '2026-10-02', 'u', 1), 5000000)
        self.assertEqual(pay_reward(self.db, 'g', '2026-10-02', 'u', 1), 0)
        self.assertEqual(pay_reward(self.db, 'g', '2026-10-02', 'v', 1), 0)
        self.assertEqual(pay_reward(self.db, 'g', '2026-10-02', 'u', 2), 0)
        self.assertEqual(self.db.execute('SELECT SUM(balance) FROM balances').fetchone()[0], 5000000)

    def test_days_and_guilds_are_independent(self):
        for guild, day in [('g', '2026-10-02'), ('g', '2026-10-03'), ('h', '2026-10-02')]:
            pay_reward(self.db, guild, day, 'u', 2)
        self.assertEqual(self.db.execute('SELECT balance FROM balances').fetchone()[0], 9000000)

    def test_failed_wallet_update_rolls_back_ledger(self):
        self.db.execute("CREATE TRIGGER fail BEFORE UPDATE ON balances BEGIN SELECT RAISE(ABORT, 'failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            pay_reward(self.db, 'g', '2026-10-02', 'u', 3)
        self.db.execute('DROP TRIGGER fail')
        self.assertEqual(pay_reward(self.db, 'g', '2026-10-02', 'u', 3), 1000000)

    def test_does_not_commit_unrelated_transaction(self):
        self.db.execute("INSERT INTO balances VALUES ('other', 10)")
        with self.assertRaises(RuntimeError):
            pay_reward(self.db, 'g', '2026-10-02', 'u', 1)
        self.db.rollback()
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM balances').fetchone()[0], 0)

    def test_pending_recovery_and_historical_exclusion(self):
        tree = ast.parse(Path(__file__).with_name('birthday_bot.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'settle_pending_attendance_rewards')
        data = {'guilds': {'g': {'today_order': {'2026-10-01': ['old']}, 'pending_rewards': [
            {'day': '2026-10-02', 'user_id': 'u', 'rank': 1}]}}}
        saved = copy.deepcopy(data)
        def crash():
            raise OSError('crash after wallet commit before outbox removal persisted')
        env = {'attendance_data': data, 'conn': self.db, 'pay_reward': pay_reward, 'save_attendance_data': crash}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<attendance>', 'exec'), env)
        with self.assertRaises(OSError):
            env['settle_pending_attendance_rewards']()
        env['attendance_data'] = saved
        env['save_attendance_data'] = lambda: None
        env['settle_pending_attendance_rewards']()
        self.assertEqual(self.db.execute('SELECT user_id, balance FROM balances').fetchall(), [('u', 5000000)])
        self.assertEqual(saved['guilds']['g']['pending_rewards'], [])


if __name__ == '__main__':
    unittest.main()
