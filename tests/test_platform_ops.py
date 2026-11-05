"""Test cho các hàm đặc thù nền tảng (không chạm hệ thống)."""

from __future__ import annotations

import sys
import unittest

from steamfix import platform_ops


class SelfArgumentsTests(unittest.TestCase):
    def test_python_mode_uses_module_invocation(self) -> None:
        exe, params = platform_ops.self_arguments(["fix", "--dry-run"])
        self.assertEqual(exe, sys.executable)
        self.assertIn("-m steamfix", params)
        self.assertIn("fix", params)
        self.assertIn("--dry-run", params)

    def test_frozen_mode_calls_exe_directly(self) -> None:
        had = hasattr(sys, "frozen")
        old = getattr(sys, "frozen", None)
        sys.frozen = True  # type: ignore[attr-defined]
        try:
            exe, params = platform_ops.self_arguments(["check"])
            self.assertEqual(exe, sys.executable)
            self.assertNotIn("-m steamfix", params)
            self.assertIn("check", params)
        finally:
            if had:
                sys.frozen = old  # type: ignore[attr-defined]
            else:
                del sys.frozen  # type: ignore[attr-defined]


class AdminTests(unittest.TestCase):
    def test_is_admin_returns_bool(self) -> None:
        self.assertIsInstance(platform_ops.is_admin(), bool)

    def test_admin_hint_mentions_platform(self) -> None:
        hint = platform_ops.admin_hint()
        self.assertTrue(hint)
        if platform_ops.IS_WINDOWS:
            self.assertIn("administrator", hint.lower())


if __name__ == "__main__":
    unittest.main()
