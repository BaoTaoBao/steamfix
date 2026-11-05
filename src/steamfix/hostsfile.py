"""Đọc/ghi file hosts: block có đánh dấu, backup, ghi nguyên tử."""

from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import config

_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_LEGACY_PIN_RE = re.compile(r"^#\s*-{2,}\s*steam-pin")


class HostsError(Exception):
    """Không đọc/ghi được file hosts."""


def default_hosts_path() -> Path:
    if os.name == "nt":
        root = os.environ.get("SystemRoot") or os.environ.get("windir") or r"C:\Windows"  # noqa: SIM112
        return Path(root) / "System32" / "drivers" / "etc" / "hosts"
    return Path("/etc/hosts")


@dataclass
class ApplyResult:
    changed: bool = False
    written: bool = False
    backup: Optional[Path] = None
    removed: int = 0
    preview: List[str] = field(default_factory=list)


class HostsFile:
    """Quản lý một block mapping Steam trong file hosts.

    Không đụng tới các dòng khác (kể cả mục MagicDNS của Tailscale).
    """

    def __init__(self, path: Optional[Path | str] = None) -> None:
        self.path = Path(path) if path else default_hosts_path()
        self.newline = "\n"
        self.encoding = "utf-8"
        self.text = ""

    # ------------------------------------------------------------------ đọc
    def exists(self) -> bool:
        return self.path.exists()

    def read(self) -> List[str]:
        if not self.exists():
            self.text = ""
            self.newline = "\n"
            return []
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            raise HostsError(f"Không đọc được {self.path}: {exc}") from exc

        for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1"):
            try:
                text = raw.decode(encoding)
                self.encoding = encoding
                break
            except UnicodeDecodeError:
                continue
        else:  # pragma: no cover - latin-1 luôn giải mã được
            text = raw.decode("latin-1")
            self.encoding = "latin-1"

        self.text = text
        self.newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.split(self.newline)
        while lines and lines[-1] == "":
            lines.pop()
        return lines

    # ------------------------------------------------------------- phân tích
    @staticmethod
    def _is_block_start(line: str) -> bool:
        return line.strip().startswith(config.BLOCK_START_PREFIX)

    @staticmethod
    def _is_block_end(line: str) -> bool:
        return line.strip().startswith(config.BLOCK_END_PREFIX)

    @staticmethod
    def _split_mapping(line: str) -> Tuple[str, List[str]]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return "", []
        parts = stripped.split()
        if len(parts) < 2 or not _IPV4_RE.match(parts[0]):
            return "", []
        return parts[0], [part.lower() for part in parts[1:]]

    def managed_mapping(self) -> Dict[str, str]:
        """Host -> IP đang được ghim (kể cả block cũ của bản 1.x)."""
        mapping: Dict[str, str] = {}
        for line in self.read():
            ip, names = self._split_mapping(line)
            if not ip:
                continue
            for name in names:
                if name in config.MANAGED_HOSTS:
                    mapping[name] = ip
        return mapping

    def has_block(self) -> bool:
        return any(self._is_block_start(line) for line in self.read())

    # --------------------------------------------------------------- dựng nội dung
    def _strip(self, lines: Sequence[str]) -> Tuple[List[str], int]:
        kept: List[str] = []
        removed = 0
        inside = False
        for line in lines:
            if self._is_block_start(line):
                inside = True
                removed += 1
                continue
            if self._is_block_end(line):
                inside = False
                removed += 1
                continue
            if inside:
                removed += 1
                continue
            if _LEGACY_PIN_RE.match(line.strip()):
                removed += 1
                continue
            ip, names = self._split_mapping(line)
            if ip and any(name in config.MANAGED_HOSTS for name in names):
                removed += 1
                continue
            kept.append(line)
        return kept, removed

    def render(self, mapping: Dict[str, str]) -> Tuple[List[str], int]:
        lines, removed = self._strip(self.read())
        while lines and not lines[-1].strip():
            lines.pop()

        block = ["", f"{config.BLOCK_START_PREFIX} (auto-generated) >>>"]
        for host in config.MANAGED_HOSTS:
            ip = mapping.get(host)
            if ip:
                block.append(f"{ip:<16}{host}")
        block.append(f"{config.BLOCK_END_PREFIX} <<<")
        return lines + block, removed

    def render_without_block(self) -> Tuple[List[str], int]:
        lines, removed = self._strip(self.read())
        while lines and not lines[-1].strip():
            lines.pop()
        return lines, removed

    # ------------------------------------------------------------------ ghi
    def writable(self) -> bool:
        if not self.path.exists():
            return False
        return os.access(str(self.path), os.W_OK)

    def backup(self, tag: str = "") -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = f"-{tag}" if tag else ""
        target = self.path.with_name(f"hosts.steamfix-{stamp}{suffix}.bak")
        try:
            shutil.copy2(self.path, target)
        except OSError as exc:
            raise HostsError(f"Không tạo được backup: {exc}") from exc
        self._prune_backups()
        return target

    def _prune_backups(self) -> None:
        try:
            backups = sorted(
                self.path.parent.glob("hosts.steamfix-*.bak"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return
        for old in backups[config.MAX_BACKUPS :]:
            try:
                old.unlink()
            except OSError:
                pass

    def _write(self, lines: Sequence[str]) -> None:
        content = self.newline.join(lines) + self.newline
        parent = self.path.parent

        original_mode = None
        readonly = False
        try:
            original_mode = stat.S_IMODE(self.path.stat().st_mode)
            readonly = not (original_mode & stat.S_IWRITE)
        except OSError:
            pass

        if readonly:
            try:
                self.path.chmod(original_mode | stat.S_IWRITE)
            except OSError as exc:
                raise HostsError(f"File hosts đang read-only và không sửa được quyền: {exc}") from exc

        fd, tmp_name = tempfile.mkstemp(prefix="hosts.steamfix-", suffix=".tmp", dir=str(parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
            if original_mode is not None:
                try:
                    os.chmod(tmp_name, original_mode)
                except OSError:
                    pass
            self._replace_file(tmp_name)
        except OSError as exc:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise HostsError(f"Ghi hosts thất bại: {exc}") from exc
        finally:
            if readonly and original_mode is not None:  # pragma: no cover
                try:
                    self.path.chmod(original_mode)
                except OSError:
                    pass

    def _replace_file(self, tmp_name: str) -> None:
        """Thay file hosts một cách bền bỉ.

        Trên Windows, tiến trình khác (DNS Client, antivirus, Steam) có thể giữ
        `hosts` trong vài trăm ms khiến `os.replace` trả WinError 5. Thử lại vài
        lần rồi mới chuyển sang ghi đè tại chỗ.
        """
        last_error: Optional[OSError] = None
        for attempt in range(3):
            try:
                os.replace(tmp_name, self.path)
                return
            except OSError as exc:
                last_error = exc
                time.sleep(0.2 * (attempt + 1))

        try:
            shutil.copyfile(tmp_name, self.path)
        except OSError as exc:
            raise HostsError(
                f"Không thay được file hosts (có thể đang bị giữ bởi tiến trình khác): {last_error or exc}"
            ) from (last_error or exc)
        try:
            os.unlink(tmp_name)
        except OSError:
            pass

    # ------------------------------------------------------------------ API
    def apply(self, mapping: Dict[str, str], *, dry_run: bool = False) -> ApplyResult:
        lines, removed = self.render(mapping)
        if dry_run:
            return ApplyResult(changed=True, written=False, preview=lines, removed=removed)
        if not self.writable():
            raise HostsError(f"Không có quyền ghi {self.path}. Hãy chạy lại bằng Administrator/sudo.")
        backup = self.backup()
        self._write(lines)
        return ApplyResult(changed=True, written=True, backup=backup, preview=lines, removed=removed)

    def remove(self, *, dry_run: bool = False) -> ApplyResult:
        lines, removed = self.render_without_block()
        if removed == 0:
            return ApplyResult(changed=False)
        if dry_run:
            return ApplyResult(changed=True, written=False, preview=lines, removed=removed)
        if not self.writable():
            raise HostsError(f"Không có quyền ghi {self.path}. Hãy chạy lại bằng Administrator/sudo.")
        backup = self.backup()
        self._write(lines)
        return ApplyResult(changed=True, written=True, backup=backup, preview=lines, removed=removed)
