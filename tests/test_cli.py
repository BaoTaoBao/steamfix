"""Test cho CLI (không chạm mạng, không chạm hosts thật)."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest import mock

from steamfix import cli, config


def run_main(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, out.getvalue()


class ParserTests(unittest.TestCase):
    def test_defaults(self) -> None:
        args = cli.build_parser().parse_args(["check"])
        self.assertEqual(args.command, "check")
        self.assertEqual(args.timeout, config.DEFAULT_TIMEOUT)
        self.assertEqual(args.workers, config.DEFAULT_WORKERS)
        self.assertFalse(args.json)

    def test_fix_flags(self) -> None:
        args = cli.build_parser().parse_args(["fix", "--dry-run", "-r", "-y", "--report", "out.json"])
        self.assertTrue(args.dry_run)
        self.assertTrue(args.restart_steam)
        self.assertTrue(args.yes)
        self.assertEqual(args.report, "out.json")

    def test_no_command(self) -> None:
        args = cli.build_parser().parse_args([])
        self.assertIsNone(args.command)

    def test_log_flag_position_does_not_matter(self) -> None:
        before = cli.build_parser().parse_args(["--log", "a.log", "check"])
        after = cli.build_parser().parse_args(["check", "--log", "b.log"])
        self.assertEqual(before.log, "a.log")
        self.assertEqual(after.log, "b.log")

    def test_global_flags_survive_subcommand(self) -> None:
        args = cli.build_parser().parse_args(["--no-color", "check"])
        self.assertTrue(args.no_color)


class MainTests(unittest.TestCase):
    def test_help_exits_zero(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            cli.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_no_command_prints_help(self) -> None:
        code, output = run_main([])
        self.assertEqual(code, config.EXIT_OK)
        self.assertIn("usage:", output)

    def test_check_success(self) -> None:
        with mock.patch.object(cli.diagnose, "run_check", return_value=(config.EXIT_OK, {"ok": True})):
            code, output = run_main(["check", "--json"])
        self.assertEqual(code, config.EXIT_OK)
        self.assertEqual(json.loads(output)["ok"], True)

    def test_check_failure_code(self) -> None:
        with mock.patch.object(cli.diagnose, "run_check", return_value=(config.EXIT_VERIFY_FAILED, {"ok": False})):
            code, _ = run_main(["check"])
        self.assertEqual(code, config.EXIT_VERIFY_FAILED)

    def test_fix_dry_run(self) -> None:
        with (
            mock.patch.object(cli.platform_ops, "is_admin", return_value=True),
            mock.patch.object(cli.diagnose, "run_fix", return_value=(config.EXIT_OK, {"result": "dry-run"})) as run_fix,
        ):
            code, _ = run_main(["fix", "--dry-run", "--json"])
        self.assertEqual(code, config.EXIT_OK)
        self.assertTrue(run_fix.call_args.kwargs["dry_run"])

    def test_fix_writes_report(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.json"
            with (
                mock.patch.object(cli.platform_ops, "is_admin", return_value=True),
                mock.patch.object(cli.diagnose, "run_fix", return_value=(config.EXIT_OK, {"ok": True})),
            ):
                code, _ = run_main(["fix", "--report", str(target)])
            self.assertEqual(code, config.EXIT_OK)
            self.assertTrue(target.exists())
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["ok"], True)

    def test_revert_requires_admin_on_windows_without_elevate(self) -> None:
        with (
            mock.patch.object(cli.platform_ops, "is_admin", return_value=False),
            mock.patch.object(cli.platform_ops, "IS_WINDOWS", True),
            mock.patch.object(cli.platform_ops, "elevate_and_wait", return_value=None),
        ):
            code, _ = run_main(["revert"])
        self.assertEqual(code, config.EXIT_NO_ADMIN)

    def test_unexpected_error_returns_error_code(self) -> None:
        with mock.patch.object(cli.diagnose, "run_check", side_effect=RuntimeError("boom")):
            code, output = run_main(["check"])
        self.assertEqual(code, config.EXIT_ERROR)
        self.assertIn("boom", output)


if __name__ == "__main__":
    unittest.main()
