"""Kiểm tra một endpoint thật: TCP → TLS (SNI đúng tên miền) → HTTP."""

from __future__ import annotations

import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Optional, Sequence

from . import config

_STATUS_RE = re.compile(rb"^HTTP/\d(?:\.\d)?\s+(\d{3})")
_MAX_HEADER_BYTES = 64 * 1024


@dataclass
class ProbeResult:
    host: str
    ip: str
    ok: bool = False
    status: int = 0
    latency_ms: int = 0
    error: str = ""
    engine: str = "python"
    source: str = ""

    def as_dict(self) -> dict:
        return {
            "host": self.host,
            "ip": self.ip,
            "ok": self.ok,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "engine": self.engine,
            "source": self.source,
        }

    def summary(self) -> str:
        if self.ok:
            return f"HTTP {self.status}, {self.latency_ms} ms"
        return self.error or "lỗi không rõ"


def _make_context(verify: bool) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    if verify:
        context.verify_mode = ssl.CERT_REQUIRED
    else:
        context.verify_mode = ssl.CERT_NONE
    try:
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    except (AttributeError, ValueError):  # pragma: no cover - Python < 3.7
        pass
    return context


def parse_status_line(data: bytes) -> int:
    """Lấy mã trạng thái từ dữ liệu HTTP thô. Trả 0 nếu không đọc được."""
    match = _STATUS_RE.match(data)
    return int(match.group(1)) if match else 0


def _read_headers(sock: ssl.SSLSocket) -> bytes:
    buffer = bytearray()
    while len(buffer) < _MAX_HEADER_BYTES:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buffer.extend(chunk)
        if b"\r\n\r\n" in buffer:
            break
    return bytes(buffer)


def _attempt(host: str, ip: str, timeout: float, verify: bool) -> tuple:
    """Một lần thử. Trả về (status, error)."""
    started = time.perf_counter()
    raw = socket.create_connection((ip, 443), timeout=timeout)
    try:
        raw.settimeout(timeout)
        context = _make_context(verify)
        with context.wrap_socket(raw, server_hostname=host) as tls:
            request = (
                f"GET / HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"User-Agent: {config.APP_NAME}/{config.VERSION}\r\n"
                f"Accept: */*\r\n"
                f"Connection: close\r\n\r\n"
            ).encode("ascii", "ignore")
            tls.settimeout(max(1.0, timeout - (time.perf_counter() - started)))
            tls.sendall(request)
            data = _read_headers(tls)
    finally:
        raw.close()
    return parse_status_line(data), ""


def probe(host: str, ip: str, timeout: float = config.DEFAULT_TIMEOUT, *, source: str = "") -> ProbeResult:
    """Kiểm tra (host, ip). Tự thử lại không xác thực chứng chỉ nếu cần."""
    started = time.perf_counter()
    result = ProbeResult(host=host, ip=ip, source=source)

    last_error = ""
    for verify in (True, False):
        try:
            status, _ = _attempt(host, ip, timeout, verify)
        except (socket.timeout, TimeoutError):
            last_error = f"timeout {timeout:g}s"
            break
        except ssl.SSLCertVerificationError as exc:
            last_error = f"chứng chỉ: {exc.verify_message or exc}"
            continue
        except ssl.SSLError as exc:
            last_error = f"TLS: {getattr(exc, 'reason', '') or exc}"
            break
        except ConnectionResetError:
            last_error = "kết nối bị reset"
            break
        except OSError as exc:
            last_error = f"TCP: {exc.strerror or exc}"
            break

        result.status = status
        result.ok = 200 <= status < 400
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        if not result.ok:
            result.error = f"HTTP {status}" if status else "không có phản hồi HTTP"
        return result

    result.latency_ms = int((time.perf_counter() - started) * 1000)
    result.error = last_error or "không kết nối được"
    return result


def probe_many(
    host: str,
    ips: Sequence[str],
    timeout: float = config.DEFAULT_TIMEOUT,
    workers: int = config.DEFAULT_WORKERS,
    sources: Optional[dict] = None,
) -> List[ProbeResult]:
    """Kiểm tra song song nhiều IP, trả về theo thứ tự truyền vào."""
    if not ips:
        return []
    sources = sources or {}
    results: List[ProbeResult] = [None] * len(ips)  # type: ignore[list-item]

    def task(index: int, ip: str) -> None:
        results[index] = probe(host, ip, timeout=timeout, source=sources.get(ip, ""))

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(ips)))) as pool:
        futures = [pool.submit(task, i, ip) for i, ip in enumerate(ips)]
        for future in futures:
            future.result()
    return results


def pick_best(results: Sequence[ProbeResult]) -> Optional[ProbeResult]:
    """Chọn kết quả OK có độ trễ thấp nhất."""
    usable = [item for item in results if item and item.ok]
    if not usable:
        return None
    return min(usable, key=lambda item: (item.latency_ms, item.ip))
