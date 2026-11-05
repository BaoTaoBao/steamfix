"""Test cho lớp console (màu, quiet, log file)."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from steamfix import console


class ConsoleTests(unittest.TestCase):
    def tearDown(self) -> None:
        console.set_quiet(False)
        console.set_logfile(None)
        console.setup(color=False)

    def test_no_color_style_is_plain(self) -> None:
        console.setup(color=False)
        self.assertEqual(console.styled("xin chào", "green"), "xin chào")

    def test_color_style_wraps_ansi(self) -> None:
        console.setup(color=True)
        styled = console.styled("ok", "green")
        self.assertTrue(styled.startswith("\033["))
        self.assertTrue(styled.endswith("\033[0m"))

    def test_quiet_suppresses_output(self) -> None:
        console.setup(color=False)
        buffer = io.StringIO()
        console.set_quiet(True)
        with contextlib.redirect_stdout(buffer):
            console.info("không được in")
        self.assertEqual(buffer.getvalue(), "")

    def test_logfile_receives_lines_without_ansi(self) -> None:
        console.setup(color=True)
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "run.log"
            console.set_logfile(log)
            with contextlib.redirect_stdout(io.StringIO()):
                console.ok("đã sửa xong")
            content = log.read_text(encoding="utf-8")
        self.assertIn("đã sửa xong", content)
        self.assertNotIn("\033[", content)


if __name__ == "__main__":
    unittest.main()
