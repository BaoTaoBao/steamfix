"""Test cho phần thu thập IP ứng viên."""

from __future__ import annotations

import unittest
from unittest import mock

from steamfix import config, resolver


class IpFilterTests(unittest.TestCase):
    def test_accepts_public_ipv4(self) -> None:
        for ip in ("23.41.38.92", "104.83.198.104", "1.1.1.1"):
            self.assertTrue(resolver.is_usable_ipv4(ip), ip)

    def test_rejects_private_and_special(self) -> None:
        for ip in (
            "127.0.0.1",
            "10.1.2.3",
            "192.168.1.1",
            "172.16.0.1",
            "169.254.10.10",
            "100.64.0.1",
            "0.0.0.0",
            "224.0.0.1",
            "999.1.1.1",
            "not-an-ip",
            "",
        ):
            self.assertFalse(resolver.is_usable_ipv4(ip), ip)


class CollectCandidatesTests(unittest.TestCase):
    def test_seeds_only(self) -> None:
        candidates = resolver.collect_candidates("store.steampowered.com", system=False, udp=False, doh=False)
        self.assertEqual(
            [item.ip for item in candidates],
            list(config.SEED_IPS["store.steampowered.com"]),
        )
        self.assertTrue(all(item.source == "seed" for item in candidates))

    def test_deduplicates_sources(self) -> None:
        with mock.patch.object(resolver, "system_resolve", return_value=["23.41.38.92", "8.8.8.8"]):
            candidates = resolver.collect_candidates("store.steampowered.com", udp=False, doh=False)
        ips = [item.ip for item in candidates]
        self.assertEqual(ips.count("23.41.38.92"), 1)
        self.assertIn("8.8.8.8", ips)
        self.assertEqual(len(ips), len(set(ips)))

    def test_skips_private_answers(self) -> None:
        with mock.patch.object(resolver, "system_resolve", return_value=["127.0.0.1", "10.0.0.5", "5.5.5.5"]):
            candidates = resolver.collect_candidates("steamcommunity.com", seeds=False, udp=False, doh=False)
        self.assertEqual([item.ip for item in candidates], ["5.5.5.5"])

    def test_limit(self) -> None:
        many = [f"8.8.{index}.{index}" for index in range(1, 30)]
        with mock.patch.object(resolver, "system_resolve", return_value=many):
            candidates = resolver.collect_candidates(
                "store.steampowered.com", seeds=False, udp=False, doh=False, limit=5
            )
        self.assertEqual(len(candidates), 5)

    def test_doh_parsing_ignores_non_a(self) -> None:
        payload = b'{"Answer":[{"type":1,"data":"1.2.3.4"},{"type":5,"data":"x"}]}'
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = payload
        with mock.patch("urllib.request.urlopen", return_value=fake):
            self.assertEqual(resolver.doh_resolve("cloudflare", "example.com"), ["1.2.3.4"])

    def test_doh_failure_returns_empty(self) -> None:
        with mock.patch("urllib.request.urlopen", side_effect=OSError("blocked")):
            self.assertEqual(resolver.doh_resolve("cloudflare", "example.com"), [])


if __name__ == "__main__":
    unittest.main()
