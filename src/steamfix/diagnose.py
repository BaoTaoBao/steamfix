"""Điều phối: chẩn đoán, sửa, hoàn tác."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from . import config, console, platform_ops, resolver
from .hostsfile import ApplyResult, HostsError, HostsFile
from .probe import ProbeResult, pick_best, probe_many


@dataclass
class HostReport:
    host: str
    resolved: List[str] = field(default_factory=list)
    probes: List[ProbeResult] = field(default_factory=list)
    best: Optional[ProbeResult] = None

    @property
    def ok(self) -> bool:
        return self.best is not None and self.best.ok

    def as_dict(self) -> dict:
        return {
            "host": self.host,
            "resolved": self.resolved,
            "ok": self.ok,
            "best": self.best.as_dict() if self.best else None,
            "probes": [item.as_dict() for item in self.probes],
        }


def diagnose(
    hosts: Sequence[str] = config.MANAGED_HOSTS,
    *,
    timeout: float = config.DEFAULT_TIMEOUT,
    workers: int = config.DEFAULT_WORKERS,
    prefer_pinned: bool = True,
) -> List[HostReport]:
    """Kiểm tra từng tên miền theo phân giải hiện tại (hosts/DNS)."""
    reports: List[HostReport] = []
    for host in hosts:
        resolved = resolver.system_resolve(host)
        report = HostReport(host=host, resolved=list(resolved))
        if not resolved:
            report.best = ProbeResult(host=host, ip="", error="không phân giải được DNS")
            reports.append(report)
            continue
        ips = resolved[:4] if prefer_pinned else resolved
        probes = probe_many(
            host,
            ips,
            timeout=timeout,
            workers=workers,
            sources=dict.fromkeys(ips, "hosts/DNS"),
        )
        report.probes = probes
        report.best = pick_best(probes) or (probes[0] if probes else None)
        reports.append(report)
    return reports


def _print_probe_rows(report: HostReport) -> None:
    rows = []
    for item in report.probes:
        state = "OK" if item.ok else "lỗi"
        rows.append(
            (
                item.ip or "-",
                item.source or "-",
                state,
                f"{item.status}" if item.status else "-",
                f"{item.latency_ms} ms" if item.ok else item.error,
            )
        )
    console.columns(("IP", "Nguồn", "Kết quả", "HTTP", "Chi tiết"), rows)


def run_check(
    *,
    timeout: float = config.DEFAULT_TIMEOUT,
    workers: int = config.DEFAULT_WORKERS,
    hosts_file: Optional[HostsFile] = None,
) -> tuple[int, dict]:
    hosts_file = hosts_file or HostsFile()
    console.head(f"{config.APP_NAME} {config.VERSION} — KIỂM TRA TRẠNG THÁI")

    admin = platform_ops.is_admin()
    console.ok("Đang chạy với quyền Administrator." if admin else "Không có quyền Administrator (chỉ đọc được).")
    console.info(f"Hệ điều hành: {platform_ops.os_summary()}   |   hosts: {hosts_file.path}")

    try:
        mapping = hosts_file.managed_mapping()
    except HostsError as exc:
        console.error(str(exc))
        return config.EXIT_ERROR, {"error": str(exc)}

    if mapping:
        console.ok("Đang có ghim của SteamFix trong hosts:")
        for host, ip in mapping.items():
            console.info(f"{host:<26} -> {ip}")
    else:
        console.warn("Chưa có ghim nào của SteamFix trong hosts.")

    console.step(1, "Phân giải hiện tại và kết nối thật")
    reports = diagnose(timeout=timeout, workers=workers)
    for report in reports:
        console.info(f"{report.host} -> {', '.join(report.resolved) or '(không có A record)'}")
        if report.probes:
            _print_probe_rows(report)
        if report.ok and report.best:
            console.ok(f"{report.host}: OK — {report.best.summary()} qua {report.best.ip}")
        else:
            reason = report.best.error if report.best else "không rõ"
            console.error(f"{report.host}: LỖI — {reason}")

    console.step(2, "Dịch vụ Steam khác (đối chiếu)")
    for host in config.HEALTH_HOSTS:
        item = diagnose((host,), timeout=timeout, workers=1)[0]
        if item.best and item.best.status:
            console.ok(f"{host}: có phản hồi HTTP {item.best.status} ({item.best.latency_ms} ms)")
        else:
            console.warn(f"{host}: {item.best.error if item.best else 'không phản hồi'}")

    console.step(3, "Steam client")
    console.ok("Steam đang chạy.") if platform_ops.steam_running() else console.warn("Steam không chạy.")

    bad = [report for report in reports if not report.ok]
    report_dict = {
        "version": config.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "os": platform_ops.os_summary(),
        "admin": admin,
        "hosts_path": str(hosts_file.path),
        "managed": mapping,
        "hosts": [report.as_dict() for report in reports],
        "ok": not bad,
    }

    console.head("KẾT LUẬN")
    if not bad:
        console.plain("  Steam Store + Community đang hoạt động bình thường.", "green")
        return config.EXIT_OK, report_dict

    console.plain("  Steam Store/Community đang bị lỗi kết nối.", "red")
    console.plain("  Chạy:  steamfix fix     (tự động sửa)", "yellow")
    return config.EXIT_VERIFY_FAILED, report_dict


def run_fix(
    *,
    timeout: float = config.DEFAULT_TIMEOUT,
    workers: int = config.DEFAULT_WORKERS,
    dry_run: bool = False,
    restart_steam: bool = False,
    yes: bool = False,
    hosts_file: Optional[HostsFile] = None,
) -> tuple[int, dict]:
    hosts_file = hosts_file or HostsFile()
    console.head(f"{config.APP_NAME} {config.VERSION} — TỰ ĐỘNG SỬA")
    if dry_run:
        console.warn("Chế độ dry-run: sẽ không ghi vào file hosts.")
    if not platform_ops.is_admin():
        console.error("Cần quyền Administrator để sửa file hosts.")
        console.info(platform_ops.admin_hint())
        return config.EXIT_NO_ADMIN, {"error": "no-admin"}

    console.step(1, "Kiểm tra hiện trạng")
    before = diagnose(timeout=timeout, workers=workers)
    for report in before:
        if report.ok and report.best:
            console.ok(f"{report.host}: đang OK ({report.best.summary()})")
        else:
            console.warn(f"{report.host}: đang lỗi — {report.best.error if report.best else 'không rõ'}")

    console.step(2, "Dò IP Akamai còn hoạt động")
    chosen: Dict[str, str] = {}
    detail: Dict[str, dict] = {}
    for host in config.MANAGED_HOSTS:
        candidates = resolver.collect_candidates(host, timeout=min(timeout, 4.0))
        if not candidates:
            console.error(f"{host}: không thu thập được IP ứng viên nào.")
            continue
        console.info(f"{host}: thử {len(candidates)} IP song song ...")
        sources = {item.ip: item.source for item in candidates}
        probes = probe_many(
            host,
            [item.ip for item in candidates],
            timeout=timeout,
            workers=workers,
            sources=sources,
        )
        report = HostReport(host=host, resolved=report_ips(host), probes=probes, best=pick_best(probes))
        _print_probe_rows(report)
        if report.best:
            chosen[host] = report.best.ip
            detail[host] = report.as_dict()
            console.ok(f"Chọn {report.best.ip} cho {host} ({report.best.summary()})")
        else:
            console.error(f"Không có IP nào hoạt động cho {host}.")

    missing = [host for host in config.MANAGED_HOSTS if host not in chosen]
    if missing:
        console.error("Thiếu IP khả dụng cho: " + ", ".join(missing))
        console.info("Không ghi hosts để tránh làm hỏng cấu hình đang có.")
        if len(missing) == len(config.MANAGED_HOSTS):
            console.info("Nhà mạng có thể đã chặn sâu hơn — cân nhắc dùng VPN/proxy.")
        return config.EXIT_NO_WORKING_IP, {"error": "no-working-ip", "missing": missing}

    console.step(3, "Cập nhật file hosts")
    if dry_run:
        console.info("Nội dung sẽ ghi:")
        for line in hosts_file.render(chosen)[0]:
            console.plain("           | " + line, "gray")
        console.head("KẾT QUẢ")
        console.plain("  Dry-run xong — chưa thay đổi gì trên hệ thống.", "yellow")
        return config.EXIT_OK, {"result": "dry-run", "chosen": chosen}

    try:
        applied: ApplyResult = hosts_file.apply(chosen)
    except HostsError as exc:
        console.error(str(exc))
        return config.EXIT_ERROR, {"error": str(exc)}

    if applied.removed:
        console.info(f"Đã dọn {applied.removed} dòng mapping Steam cũ.")
    if applied.backup:
        console.info(f"Đã sao lưu: {applied.backup}")
    console.ok("Đã ghi block SteamFix vào hosts.")

    ok_flush, flush_message = platform_ops.flush_dns()
    if ok_flush:
        console.info(f"Xoá cache DNS: {flush_message}")
    else:
        console.warn(f"Không xoá được cache DNS: {flush_message}")

    console.step(4, "Kiểm chứng đầu-cuối")
    after: List[HostReport] = []
    failed = 0
    for _attempt in range(3):
        after = diagnose(timeout=timeout, workers=workers)
        failed = sum(1 for report in after if not report.ok)
        if failed == 0:
            break
        time.sleep(0.6)

    for report in after:
        if report.ok and report.best:
            console.ok(f"{report.host} -> {report.best.ip} | {report.best.summary()}")
        else:
            console.error(
                f"{report.host} -> {report.best.ip if report.best else '-'} | "
                f"{report.best.error if report.best else 'lỗi'}"
            )

    steam_info = {"running": platform_ops.steam_running(), "restarted": False, "message": ""}
    console.step(5, "Steam client")
    if not steam_info["running"]:
        console.info("Steam không chạy — mở Steam là cấu hình có hiệu lực.")
    elif restart_steam:
        ok_restart, message = platform_ops.restart_steam()
        steam_info["restarted"] = ok_restart
        steam_info["message"] = message
        console.ok(message) if ok_restart else console.warn(message)
    elif yes:
        console.info("Cần thoát và mở lại Steam để áp dụng cấu hình mới (hoặc dùng -r).")
    elif _confirm("Khởi động lại Steam để áp dụng ngay?", default=True):
        ok_restart, message = platform_ops.restart_steam()
        steam_info["restarted"] = ok_restart
        steam_info["message"] = message
        console.ok(message) if ok_restart else console.warn(message)
    else:
        console.info("Cần thoát và mở lại Steam để áp dụng cấu hình mới.")

    report_dict = {
        "version": config.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "os": platform_ops.os_summary(),
        "admin": True,
        "hosts_path": str(hosts_file.path),
        "chosen": chosen,
        "backup": str(applied.backup) if applied.backup else None,
        "before": [report.as_dict() for report in before],
        "after": [report.as_dict() for report in after],
        "steam": steam_info,
        "candidates": detail,
    }

    console.head("KẾT QUẢ")
    if failed == 0:
        console.plain("  THÀNH CÔNG: Steam Store và Community đã truy cập được.", "green")
        if applied.backup:
            console.plain(f"  Hoàn tác: steamfix revert   (backup: {applied.backup})", "gray")
        return config.EXIT_OK, report_dict

    console.plain(f"  CÒN {failed} mục lỗi — xem chi tiết phía trên.", "red")
    return config.EXIT_VERIFY_FAILED, report_dict


def run_revert(*, hosts_file: Optional[HostsFile] = None) -> tuple[int, dict]:
    hosts_file = hosts_file or HostsFile()
    console.head(f"{config.APP_NAME} {config.VERSION} — HOÀN TÁC")
    if not platform_ops.is_admin():
        console.error("Cần quyền Administrator để sửa file hosts.")
        console.info(platform_ops.admin_hint())
        return config.EXIT_NO_ADMIN, {"error": "no-admin"}

    try:
        result = hosts_file.remove()
    except HostsError as exc:
        console.error(str(exc))
        return config.EXIT_ERROR, {"error": str(exc)}

    if not result.changed:
        console.info("Không có block SteamFix nào trong hosts — không cần làm gì.")
    else:
        console.ok("Đã gỡ block SteamFix khỏi hosts.")
        if result.backup:
            console.info(f"Backup: {result.backup}")

    ok_flush, message = platform_ops.flush_dns()
    if ok_flush:
        console.info(f"Xoá cache DNS: {message}")

    console.step(1, "Kiểm tra lại phân giải")
    reports = diagnose()
    for report in reports:
        console.info(f"{report.host} -> {', '.join(report.resolved) or '(không có)'}")
        if report.ok:
            console.ok(f"{report.host}: vẫn OK ({report.best.summary()})")
        else:
            console.warn(f"{report.host}: {report.best.error if report.best else 'lỗi'}")

    return config.EXIT_OK, {"result": "reverted", "backup": str(result.backup) if result.backup else None}


def report_ips(host: str) -> List[str]:
    return resolver.system_resolve(host)


def _confirm(prompt: str, *, default: bool = True, yes: bool = False) -> bool:
    if yes:
        return default
    if not _interactive():
        return False
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(f"    {prompt} {suffix} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if not answer:
        return default
    return answer in {"y", "yes", "c", "co", "có"}


def _interactive() -> bool:
    import sys

    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def write_report(path: str, payload: dict) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path
