"""Test cho DNS client tối giản."""

from __future__ import annotations

import struct
import unittest

from steamfix import dnsclient


def _question(name: str) -> bytes:
    out = bytearray()
    for label in name.split("."):
        out.append(len(label))
        out.extend(label.encode())
    out.append(0)
    out.extend(struct.pack(">HH", 1, 1))
    return bytes(out)


class BuildQueryTests(unittest.TestCase):
    def test_header_and_question(self) -> None:
        qid, packet = dnsclient.build_query("example.com", qid=0x1234)
        self.assertEqual(qid, 0x1234)
        header = struct.unpack(">HHHHHH", packet[:12])
        self.assertEqual(header[0], 0x1234)
        self.assertEqual(header[1], 0x0100)  # RD=1
        self.assertEqual(header[2], 1)  # QDCOUNT
        self.assertEqual(header[3], 0)  # ANCOUNT
        self.assertTrue(packet.endswith(b"\x00\x00\x01\x00\x01"))
        self.assertIn(b"\x07example\x03com", packet)

    def test_rejects_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            dnsclient.build_query("")

    def test_rejects_long_label(self) -> None:
        with self.assertRaises(ValueError):
            dnsclient.build_query("x" * 64 + ".com")


class ParseResponseTests(unittest.TestCase):
    def _response(self, answers: bytes, ancount: int, flags: int = 0x8180) -> bytes:
        header = struct.pack(">HHHHHH", 0x1234, flags, 1, ancount, 0, 0)
        return header + _question("example.com") + answers

    def test_parses_a_record_with_compression_pointer(self) -> None:
        answer = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 60, 4) + bytes([1, 2, 3, 4])
        packet = self._response(answer, 1)
        self.assertEqual(dnsclient.parse_response(packet), ["1.2.3.4"])

    def test_ignores_non_a_records(self) -> None:
        cname = b"\xc0\x0c" + struct.pack(">HHIH", 5, 1, 60, 4) + b"abcd"
        packet = self._response(cname, 1)
        self.assertEqual(dnsclient.parse_response(packet), [])

    def test_nxdomain_returns_empty(self) -> None:
        packet = self._response(b"", 0, flags=0x8183)
        self.assertEqual(dnsclient.parse_response(packet), [])

    def test_truncated_flag_raises(self) -> None:
        packet = self._response(b"", 0, flags=0x8380)
        with self.assertRaises(dnsclient.DnsError):
            dnsclient.parse_response(packet)

    def test_short_packet_raises(self) -> None:
        with self.assertRaises(dnsclient.DnsError):
            dnsclient.parse_response(b"\x00\x01")

    def test_pointer_loop_raises(self) -> None:
        # Tên bắt đầu bằng con trỏ trỏ về chính nó (offset 12).
        packet = struct.pack(">HHHHHH", 1, 0x8180, 1, 1, 0, 0) + b"\xc0\x0c"
        with self.assertRaises(dnsclient.DnsError):
            dnsclient.parse_response(packet)


if __name__ == "__main__":
    unittest.main()
