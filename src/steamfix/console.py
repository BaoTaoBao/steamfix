"""In ra console: màu ANSI, tiêu đề, bảng — không phụ thuộc thư viện ngoài."""

from __future__ import annotations

import os
import re
import sys
from typing import Iterable, Sequence

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

_COLORS = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "gray": "\033[90m",
    "white": "\033[97m",
    "magenta": "\033[35m",
}

_state = {"color": None, "width": 78, "quiet": False, "log": None}


def _supports_color(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    if not getattr(stream, "isatty", lambda: False)():
        return False
    if os.name == "nt":
        _enable_windows_ansi()
    return True


def _enable_windows_ansi() -> None:
    """Bật Virtual Terminal Processing cho console Windows (best-effort)."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def setup(*, color: bool | None = None, width: int | None = None) -> None:
    """Khởi tạo console: UTF-8 trên Windows, bật/tắt màu, đặt độ rộng bảng."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if color is None:
        color = _supports_color(sys.stdout)
    _state["color"] = bool(color)
    if width:
        _state["width"] = max(40, int(width))


def width() -> int:
    return int(_state["width"])


def set_quiet(value: bool = True) -> None:
    """Tắt toàn bộ output (dùng khi in JSON máy đọc)."""
    _state["quiet"] = bool(value)


def is_quiet() -> bool:
    return bool(_state["quiet"])


def set_logfile(path: str | None) -> None:
    """Ghi mọi dòng in ra vào file log (bỏ mã màu). None để tắt."""
    _state["log"] = str(path) if path else None


def styled(text: str, *styles: str) -> str:
    if not _state["color"]:
        return text
    prefix = "".join(_COLORS.get(s, "") for s in styles)
    return f"{prefix}{text}{_COLORS['reset']}" if prefix else text


def _emit(text: str = "") -> None:
    if _state["quiet"]:
        return
    print(text, flush=True)
    log_path = _state["log"]
    if log_path:
        try:
            from datetime import datetime

            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(f"[{stamp}] {_ANSI_RE.sub('', text)}\n")
        except OSError:
            pass


def blank() -> None:
    _emit()


def head(text: str) -> None:
    rule = "=" * width()
    _emit()
    _emit(styled(rule, "dim", "cyan"))
    _emit(styled(f"  {text}", "bold", "cyan"))
    _emit(styled(rule, "dim", "cyan"))


def step(number: int, text: str) -> None:
    _emit()
    _emit(styled(f"[{number}] {text}", "bold", "white"))


def info(text: str) -> None:
    _emit(styled(f"           {text}", "gray"))


def ok(text: str) -> None:
    _emit("    " + styled("[OK]", "green") + f"   {text}")


def warn(text: str) -> None:
    _emit("    " + styled("[!]", "yellow") + f"    {text}")


def error(text: str) -> None:
    _emit("    " + styled("[X]", "red") + f"    {text}")


def plain(text: str, *styles: str) -> None:
    _emit(styled(text, *styles))


def banner(title: str, subtitle: str = "") -> None:
    head(title)
    if subtitle:
        info(subtitle)


def kv_table(rows: Sequence[tuple[str, str]], indent: int = 11) -> None:
    if not rows:
        return
    pad = max(len(k) for k, _ in rows)
    for key, value in rows:
        _emit(" " * indent + styled(key.ljust(pad), "dim") + "  " + value)


def columns(headers: Sequence[str], rows: Iterable[Sequence[str]], indent: int = 13) -> None:
    """In bảng cột đơn giản, canh trái theo độ dài tối đa."""
    data = [[str(c) for c in row] for row in rows]
    if not data:
        return
    widths = [len(str(h)) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))
    line = " " * indent + "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    _emit(styled(line, "dim"))
    for row in data:
        cells = []
        for i, cell in enumerate(row):
            pad = widths[i] if i < len(widths) else 0
            cells.append(cell.ljust(pad))
        _emit(" " * indent + "  ".join(cells))
