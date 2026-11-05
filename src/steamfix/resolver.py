"""Thu thập IP ứng viên từ nhiều nguồn: seed, DNS hệ thống, DNS UDP, DoH."""

from __future__ import annotations

import ipaddress
import json
import socket
import urllib.request
from dataclasses import dataclass
from typing import Iterable, List, Sequence
from urllib.parse import quote

from . import config, dnsclient

USER_AGENT = f"{config.APP_NAME}/{config.VERSION}"


@dataclass(frozen=True)
class Candidate:
    ip: str
    source: str


def is_usable_ipv4(value: str) -> bool:
    """Chỉ nhận IPv4 công khai, loại bỏ private/loopback/CGNAT/..."""
    try:
        address = ipaddress.IPv4Address(value)
    except (ipaddress.AddressValueError, ValueError):
        return False
    blocked = (
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
    return not blocked


def system_resolve(host: str, timeout: float = 3.0) -> List[str]:
    """Phân giải bằng resolver của hệ điều hành."""
    try:
        infos = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        return []
    result: List[str] = []
    for info in infos:
        ip = info[4][0]
        if ip not in result:
            result.append(ip)
    return result


def doh_resolve(provider: str, host: str, timeout: float = 5.0) -> List[str]:
    """Hỏi Cloudflare/Google/Quad9 qua DNS-over-HTTPS (JSON)."""
    template = config.DOH_ENDPOINTS.get(provider)
    if not template:
        return []
    url = template.format(name=quote(host, safe=""))
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/dns-json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    answers = payload.get("Answer") or []
    result = [item["data"] for item in answers if item.get("type") == 1 and "data" in item]
    return result


def udp_resolve(server: str, host: str, timeout: float = 3.0) -> List[str]:
    """Hỏi trực tiếp resolver bằng UDP."""
    try:
        return dnsclient.query_a(server, host, timeout=timeout)
    except (OSError, dnsclient.DnsError, ValueError):
        return []


def collect_candidates(
    host: str,
    *,
    seeds: bool = True,
    system: bool = True,
    udp: bool = True,
    doh: bool = True,
    timeout: float = 3.0,
    limit: int = config.MAX_CANDIDATES,
) -> List[Candidate]:
    """Gom IP ứng viên theo thứ tự ưu tiên: seed → hệ thống → UDP → DoH."""
    ordered: List[Candidate] = []
    seen = set()

    def add(values: Iterable[str], source: str) -> None:
        for value in values:
            value = str(value).strip()
            if not is_usable_ipv4(value) or value in seen:
                continue
            seen.add(value)
            ordered.append(Candidate(value, source))

    if seeds:
        add(config.SEED_IPS.get(host, ()), "seed")
    if system:
        add(system_resolve(host, timeout=timeout), "system")
    if udp:
        for server in config.DNS_SERVERS:
            add(udp_resolve(server, host, timeout=timeout), f"dns:{server}")
    if doh:
        for provider in config.DOH_ENDPOINTS:
            add(doh_resolve(provider, host, timeout=timeout), f"doh:{provider}")

    return ordered[:limit]


def candidates_to_dicts(candidates: Sequence[Candidate]) -> List[dict]:
    return [{"ip": item.ip, "source": item.source} for item in candidates]
