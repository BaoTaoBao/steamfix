"""Test cho phần quản lý file hosts."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from steamfix import config
from steamfix.hostsfile import HostsError, HostsFile

SAMPLE = """\
# hosts mẫu
127.0.0.1   localhost

# mục của Tailscale
100.120.120.46 cengxunbao26242.tail7c795e.ts.net. cengxunbao26242

# --- steam-pin (ghi tay) ---
23.41.38.92     store.steampowered.com
23.41.37.9      steamcommunity.com
"""


class HostsFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "hosts"
        self.path.write_text(SAMPLE, encoding="utf-8")
        self.hosts = HostsFile(self.path)

    def test_managed_mapping_reads_manual_pins(self) -> None:
        mapping = self.hosts.managed_mapping()
        self.assertEqual(mapping["store.steampowered.com"], "23.41.38.92")
        self.assertEqual(mapping["steamcommunity.com"], "23.41.37.9")

    def test_apply_replaces_pins_and_keeps_other_lines(self) -> None:
        result = self.hosts.apply({"store.steampowered.com": "1.1.1.1", "steamcommunity.com": "2.2.2.2"})
        self.assertTrue(result.written)
        self.assertIsNotNone(result.backup)
        self.assertTrue(result.backup.exists())

        text = self.path.read_text(encoding="utf-8")
        self.assertIn("100.120.120.46 cengxunbao26242.tail7c795e.ts.net.", text)
        self.assertIn("127.0.0.1   localhost", text)
        self.assertNotIn("steam-pin", text)
        self.assertEqual(text.count(config.BLOCK_START_PREFIX), 1)

        mapping = self.hosts.managed_mapping()
        self.assertEqual(mapping["store.steampowered.com"], "1.1.1.1")
        self.assertEqual(mapping["steamcommunity.com"], "2.2.2.2")

    def test_apply_is_idempotent(self) -> None:
        mapping = {"store.steampowered.com": "1.1.1.1", "steamcommunity.com": "2.2.2.2"}
        self.hosts.apply(mapping)
        first = self.path.read_text(encoding="utf-8")
        self.hosts.apply(mapping)
        second = self.path.read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertEqual(second.count(config.BLOCK_START_PREFIX), 1)

    def test_dry_run_does_not_touch_file(self) -> None:
        before = self.path.read_text(encoding="utf-8")
        result = self.hosts.apply({"store.steampowered.com": "1.1.1.1"}, dry_run=True)
        self.assertFalse(result.written)
        self.assertTrue(result.changed)
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        self.assertTrue(any("1.1.1.1" in line for line in result.preview))

    def test_remove_restores_original_content(self) -> None:
        self.hosts.apply({"store.steampowered.com": "1.1.1.1", "steamcommunity.com": "2.2.2.2"})
        result = self.hosts.remove()
        self.assertTrue(result.changed)
        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn(config.BLOCK_START_PREFIX, text)
        self.assertIn("127.0.0.1   localhost", text)
        # các dòng ghim cũ đã bị dọn ở bước apply nên không quay lại
        self.assertNotIn("23.41.38.92", text)

    def test_remove_without_block_is_noop(self) -> None:
        self.path.write_text("127.0.0.1 localhost\n", encoding="utf-8")
        result = HostsFile(self.path).remove()
        self.assertFalse(result.changed)

    def test_preserves_crlf_newlines(self) -> None:
        self.path.write_bytes(SAMPLE.replace("\n", "\r\n").encode("utf-8"))
        hosts = HostsFile(self.path)
        hosts.apply({"store.steampowered.com": "1.1.1.1", "steamcommunity.com": "2.2.2.2"})
        raw = self.path.read_bytes().decode("utf-8")
        self.assertIn("\r\n", raw)
        self.assertNotIn("\n\n\n", raw.replace("\r\n", "\n"))

    def test_handles_file_without_trailing_newline(self) -> None:
        self.path.write_text("127.0.0.1 localhost", encoding="utf-8")
        hosts = HostsFile(self.path)
        hosts.apply({"store.steampowered.com": "1.1.1.1"})
        text = self.path.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertIn("1.1.1.1", text)

    def test_falls_back_to_in_place_write_when_replace_fails(self) -> None:
        """Windows đôi khi khoá hosts khiến os.replace trả WinError 5."""
        with mock.patch("os.replace", side_effect=PermissionError(13, "Access is denied")), mock.patch("time.sleep"):
            result = self.hosts.apply({"store.steampowered.com": "1.1.1.1"})
        self.assertTrue(result.written)
        self.assertIn("1.1.1.1", self.path.read_text(encoding="utf-8"))

    def test_backup_pruning(self) -> None:
        for index in range(config.MAX_BACKUPS + 3):
            self.hosts.apply({"store.steampowered.com": f"10.0.0.{index}", "steamcommunity.com": "10.0.0.1"})
        backups = list(self.path.parent.glob("hosts.steamfix-*.bak"))
        self.assertLessEqual(len(backups), config.MAX_BACKUPS)

    @unittest.skipIf(os.name == "nt", "quyền ghi trên Windows do ACL quyết định")
    def test_read_only_without_permission_raises(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root luôn ghi được")
        self.path.chmod(0o444)
        self.addCleanup(lambda: self.path.chmod(0o644))
        with self.assertRaises(HostsError):
            self.hosts.apply({"store.steampowered.com": "1.1.1.1"})


if __name__ == "__main__":
    unittest.main()
