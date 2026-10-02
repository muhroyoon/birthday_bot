"""Check retirement without importing the live bot or opening its database."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

SOURCE = Path(__file__).with_name('birthday_bot.py').read_text(encoding='utf-8-sig')
TREE = ast.parse(SOURCE)


class GuestRetirementTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_panel_only_reports_retirement(self):
        view = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'GuestRefreshView')
        callback = next(n for n in view.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'refresh')
        callback.decorator_list = []
        callback.returns = None
        for arg in callback.args.args:
            arg.annotation = None
        namespace = {}
        exec(compile(ast.Module(body=[callback], type_ignores=[]), '<old-panel>', 'exec'), namespace)
        response = SimpleNamespace(send_message=AsyncMock())
        # No guild/member/database is needed for a retired panel.
        await namespace['refresh'](None, SimpleNamespace(response=response), None)
        response.send_message.assert_awaited_once()
        self.assertIn('종료', response.send_message.call_args.args[0])
        self.assertTrue(response.send_message.call_args.kwargs['ephemeral'])

    def test_retired_commands_and_scheduler_are_not_registered(self):
        registered = set()
        for node in ast.walk(TREE):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'command':
                registered.update(k.value.value for k in node.keywords if k.arg == 'name' and isinstance(k.value, ast.Constant))
        self.assertFalse({'게스트갱신생성', '갱신점검', '게스트갱신초기화'} & registered)
        names = {n.id for n in ast.walk(TREE) if isinstance(n, ast.Name)}
        self.assertNotIn('run_guest_checks', names)
        self.assertNotIn('attendance_daily_loop', names)
        self.assertTrue({'출석생성', '게스트등업역할'} <= registered)
        self.assertIn('attendance_panel_loop', names)

    def test_attendance_settings_no_longer_offer_renewal_options(self):
        fn = next(n for n in TREE.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'set_attendance_feature')
        self.assertEqual([a.arg for a in fn.args.args], ['interaction', 'attendance_channel', 'midnight_channel', 'attendance_role'])


if __name__ == '__main__':
    unittest.main()
