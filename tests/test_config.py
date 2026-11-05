"""Test cấu hình tĩnh."""

from __future__ import annotations

import ipaddress
import unittest

from steamfix import config


class ConfigTests(unittest.TestCase):
    def test_version_is_semver(self) -> None:
        parts = config.VERSION.split(".")
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(part.isdigit() for part in parts))

    def test_managed_hosts_are_lowercase_fqdn(self) -> None:
        for host in config.MANAGED_HOSTS:
            self.assertEqual(host, host.lower())
            self.assertNotIn(" ", host)
            self.assertTrue(host.endswith(".com"))

    def test_seed_ips_are_public_ipv4(self) -> None:
        for host, ips in config.SEED_IPS.items():
            for ip in ips:
                address = ipaddress.IPv4Address(ip)
                self.assertFalse(address.is_private, f"{host}: {ip}")
                self.assertFalse(address.is_loopback, f"{host}: {ip}")

    def test_seeds_cover_managed_hosts(self) -> None:
        for host in config.MANAGED_HOSTS:
            self.assertIn(host, config.SEED_IPS)

    def test_block_markers_are_comments(self) -> None:
        self.assertTrue(config.BLOCK_START_PREFIX.startswith("#"))
        self.assertTrue(config.BLOCK_END_PREFIX.startswith("#"))

    def test_exit_codes_are_distinct(self) -> None:
        codes = {
            config.EXIT_OK,
            config.EXIT_ERROR,
            config.EXIT_NO_ADMIN,
            config.EXIT_NO_WORKING_IP,
            config.EXIT_VERIFY_FAILED,
        }
        self.assertEqual(len(codes), 5)


if __name__ == "__main__":
    unittest.main()
