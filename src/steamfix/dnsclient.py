"""DNS client tối giản (UDP, chỉ bản ghi A) — không cần thư viện ngoài."""

from __future__ import annotations

import random
import socket
import struct
from typing import List, Tuple

MAX_NAME_LEN = 253
_QTYPE_A = 1
_QCLASS_IN = 1


class DnsError(Exception):
    """Lỗi định dạng/phản hồi DNS không hợp lệ."""


def build_query(name: str, qid: int | None = None) -> Tuple[int, bytes]:
    """Tạo packet DNS query cho bản ghi A. Trả về (query_id, packet)."""
    name = name.strip().rstrip(".")
    if not name:
        raise ValueError("Tên miền rỗng")
    if len(name) > MAX_NAME_LEN:
        raise ValueError("Tên miền quá dài")

    qid = random.randint(0, 0xFFFF) if qid is None else qid & 0xFFFF
    header = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)

    labels = name.split(".")
    qname = bytearray()
    for label in labels:
        raw = label.encode("idna") if any(ord(ch) > 127 for ch in label) else label.encode("ascii")
        if not raw or len(raw) > 63:
            raise ValueError(f"Nhãn DNS không hợp lệ: {label!r}")
        qname.append(len(raw))
        qname.extend(raw)
    qname.append(0)

    packet = header + bytes(qname) + struct.pack(">HH", _QTYPE_A, _QCLASS_IN)
    return qid, packet


def _read_name(data: bytes, offset: int, _depth: int = 0) -> Tuple[str, int]:
    if _depth > 8:
        raise DnsError("Con trỏ nén lồng quá sâu")
    labels: List[str] = []
    while True:
        if offset >= len(data):
            raise DnsError("Tên miền vượt quá kích thước gói")
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                raise DnsError("Con trỏ nén bị cắt")
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            suffix, _ = _read_name(data, pointer, _depth + 1)
            if suffix:
                labels.append(suffix)
            offset += 2
            break
        if length & 0xC0:
            raise DnsError("Nhãn DNS không hợp lệ")
        offset += 1
        if offset + length > len(data):
            raise DnsError("Nhãn DNS bị cắt")
        labels.append(data[offset : offset + length].decode("ascii", "replace"))
        offset += length
    return ".".join(labels), offset


def parse_response(data: bytes) -> List[str]:
    """Trả về danh sách IPv4 trong phần answer của gói DNS."""
    if len(data) < 12:
        raise DnsError("Gói DNS quá ngắn")

    _qid, flags, qdcount, ancount, _nscount, _arcount = struct.unpack(">HHHHHH", data[:12])
    if flags & 0x0200:
        raise DnsError("Phản hồi bị cắt (truncated)")
    if flags & 0x000F:
        return []  # NXDOMAIN / SERVFAIL... coi như không có bản ghi

    offset = 12
    for _ in range(qdcount):
        _, offset = _read_name(data, offset)
        offset += 4  # qtype + qclass
        if offset > len(data):
            raise DnsError("Phần question bị cắt")

    addresses: List[str] = []
    for _ in range(ancount):
        _, offset = _read_name(data, offset)
        if offset + 10 > len(data):
            raise DnsError("Bản ghi bị cắt")
        rtype, _rclass, _ttl, rdlength = struct.unpack(">HHIH", data[offset : offset + 10])
        offset += 10
        rdata = data[offset : offset + rdlength]
        offset += rdlength
        if rtype == _QTYPE_A and rdlength == 4:
            addresses.append(".".join(str(byte) for byte in rdata))
    return addresses


def query_a(server: str, name: str, timeout: float = 3.0) -> List[str]:
    """Hỏi bản ghi A qua UDP. Trả về [] nếu không có/không hợp lệ."""
    qid, packet = build_query(name)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(packet, (server, 53))
        data, _addr = sock.recvfrom(4096)

    if len(data) < 12:
        raise DnsError("Phản hồi quá ngắn")
    rid = struct.unpack(">H", data[:2])[0]
    if rid != qid:
        raise DnsError("Query ID không khớp")
    return parse_response(data)
