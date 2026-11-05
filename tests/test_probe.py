"""Test cho phần kiểm tra endpoint (không cần mạng thật)."""

from __future__ import annotations

import socket
import ssl
import unittest
from unittest import mock

from steamfix import probe


class ParseTests(unittest.TestCase):
    def test_status_line(self) -> None:
        self.assertEqual(probe.parse_status_line(b"HTTP/1.1 200 OK\r\n"), 200)
        self.assertEqual(probe.parse_status_line(b"HTTP/1.0 302 Found\r\n"), 302)
        self.assertEqual(probe.parse_status_line(b"garbage"), 0)
        self.assertEqual(probe.parse_status_line(b""), 0)


class PickBestTests(unittest.TestCase):
    def test_picks_fastest_ok(self) -> None:
        results = [
            probe.ProbeResult("h", "1.1.1.1", ok=True, status=200, latency_ms=300),
            probe.ProbeResult("h", "2.2.2.2", ok=True, status=200, latency_ms=120),
            probe.ProbeResult("h", "3.3.3.3", ok=False, status=0, latency_ms=10, error="x"),
        ]
        best = probe.pick_best(results)
        self.assertIsNotNone(best)
        self.assertEqual(best.ip, "2.2.2.2")

    def test_returns_none_when_all_failed(self) -> None:
        results = [probe.ProbeResult("h", "1.1.1.1", ok=False, error="timeout")]
        self.assertIsNone(probe.pick_best(results))


class ProbeFailureTests(unittest.TestCase):
    def test_tcp_error_is_reported(self) -> None:
        with mock.patch("socket.create_connection", side_effect=OSError(10061, "refused")):
            result = probe.probe("store.steampowered.com", "1.1.1.1", timeout=0.5)
        self.assertFalse(result.ok)
        self.assertIn("TCP", result.error)
        self.assertEqual(result.status, 0)

    def test_timeout_is_reported(self) -> None:
        with mock.patch("socket.create_connection", side_effect=socket.timeout("timed out")):
            result = probe.probe("store.steampowered.com", "1.1.1.1", timeout=0.5)
        self.assertFalse(result.ok)
        self.assertIn("timeout", result.error)

    def test_tls_error_is_reported(self) -> None:
        fake_raw = mock.MagicMock()
        fake_raw.settimeout = mock.MagicMock()
        context = mock.MagicMock()
        context.wrap_socket.side_effect = ssl.SSLError("handshake failed")
        with (
            mock.patch("socket.create_connection", return_value=fake_raw),
            mock.patch.object(probe, "_make_context", return_value=context),
        ):
            result = probe.probe("store.steampowered.com", "1.1.1.1", timeout=0.5)
        self.assertFalse(result.ok)
        self.assertIn("TLS", result.error)


class ProbeManyTests(unittest.TestCase):
    def test_returns_one_result_per_ip(self) -> None:
        def fake_probe(host, ip, timeout=8.0, source=""):
            return probe.ProbeResult(host, ip, ok=ip.endswith(".1"), status=200, latency_ms=10, source=source)

        with mock.patch.object(probe, "probe", side_effect=fake_probe):
            results = probe.probe_many("h", ["1.1.1.1", "2.2.2.2"], sources={"1.1.1.1": "seed"})
        self.assertEqual(len(results), 2)
        self.assertEqual([item.ip for item in results], ["1.1.1.1", "2.2.2.2"])
        self.assertEqual(results[0].source, "seed")

    def test_empty_input(self) -> None:
        self.assertEqual(probe.probe_many("h", []), [])


if __name__ == "__main__":
    unittest.main()
