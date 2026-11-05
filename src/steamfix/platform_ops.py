"""Thao tác đặc thù hệ điều hành: quyền admin, flush DNS, khởi động lại Steam."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Sequence, Tuple

IS_WINDOWS = os.name == "nt"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

STEAM_CANDIDATES: Sequence[str] = (
    r"C:\Program Files (x86)\Steam\steam.exe",
    r"C:\Program Files\Steam\steam.exe",
)


def is_admin() -> bool:
    """True nếu tiến trình có quyền Administrator/root."""
    if IS_WINDOWS:
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:  # pragma: no cover - rất hiếm
            return False
    try:
        return os.geteuid() == 0  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - Windows đã xử lý ở trên
        return False


def admin_hint() -> str:
    if IS_WINDOWS:
        return "Chuột phải Terminal/PowerShell → Run as administrator, rồi chạy lại."
    return "Chạy lại bằng: sudo -E steamfix ..."


def elevate(args: Sequence[str]) -> bool:
    """Mở lại chính app với quyền cao (chỉ Windows). Trả True nếu đã gửi lệnh."""
    if not IS_WINDOWS:
        return False
    try:
        import ctypes

        params = subprocess.list2cmdline([sys.executable, "-m", "steamfix", *args])
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        return int(result) > 32
    except Exception:
        return False


def elevate_and_wait(args: Sequence[str]) -> Optional[int]:
    """Mở app với quyền cao và chờ, trả về mã thoát của tiến trình con.

    Trả None nếu không nâng được quyền (người dùng bấm No / không phải Windows).
    """
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class SHELLEXECUTEINFOW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("fMask", wintypes.ULONG),
                ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR),
                ("lpFile", wintypes.LPCWSTR),
                ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR),
                ("nShow", ctypes.c_int),
                ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p),
                ("lpClass", wintypes.LPCWSTR),
                ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD),
                ("hIcon", wintypes.HANDLE),
                ("hProcess", wintypes.HANDLE),
            ]

        SEE_MASK_NOCLOSEPROCESS = 0x00000040
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
        shell32.ShellExecuteExW.restype = wintypes.BOOL
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        info = SHELLEXECUTEINFOW()
        info.cbSize = ctypes.sizeof(info)
        info.fMask = SEE_MASK_NOCLOSEPROCESS
        info.lpVerb = "runas"
        info.lpFile = sys.executable
        info.lpParameters = subprocess.list2cmdline(["-m", "steamfix", *args])
        info.nShow = 1

        if not shell32.ShellExecuteExW(ctypes.byref(info)):
            return None
        if not info.hProcess:
            return 0
        kernel32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
        code = wintypes.DWORD(0)
        kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        kernel32.CloseHandle(info.hProcess)
        return int(code.value)
    except Exception:
        return None


# --------------------------------------------------------------------- DNS cache
def flush_dns() -> Tuple[bool, str]:
    """Xoá cache DNS của hệ điều hành. Trả về (thành công, mô tả)."""
    if IS_WINDOWS:
        return _run_first([["ipconfig", "/flushdns"]])
    if IS_MACOS:
        return _run_first([["dscacheutil", "-flushcache"]], then=[["killall", "-HUP", "mDNSResponder"]])
    return _run_first(
        [
            ["resolvectl", "flush-caches"],
            ["systemd-resolve", "--flush-caches"],
            ["nscd", "-i", "hosts"],
        ]
    )


def _run_first(commands: Sequence[Sequence[str]], then: Sequence[Sequence[str]] = ()) -> Tuple[bool, str]:
    for command in commands:
        if not shutil.which(command[0]):
            continue
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode == 0:
            for extra in then:
                try:
                    subprocess.run(extra, capture_output=True, timeout=10, check=False)
                except (OSError, subprocess.SubprocessError):
                    pass
            output = (proc.stdout or proc.stderr or "").strip()
            return True, output or "OK"
    return False, "không có lệnh flush DNS phù hợp"


# ------------------------------------------------------------------ Steam client
def find_steam_exe() -> Optional[Path]:
    if IS_WINDOWS:
        for candidate in STEAM_CANDIDATES:
            path = Path(candidate)
            if path.exists():
                return path
        try:
            import winreg

            for root, key in (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
            ):
                try:
                    with winreg.OpenKey(root, key) as handle:
                        install, _ = winreg.QueryValueEx(handle, "SteamPath")
                        path = Path(install) / "steam.exe"
                        if path.exists():
                            return path
                except OSError:
                    continue
        except ImportError:  # pragma: no cover
            pass
        return None
    for name in ("steam", "steam.sh"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def steam_running() -> bool:
    if IS_WINDOWS:
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq steam.exe", "/NH"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            return "steam.exe" in (proc.stdout or "").lower()
        except (OSError, subprocess.SubprocessError):
            return False
    try:
        proc = subprocess.run(["pgrep", "-x", "steam"], capture_output=True, timeout=10, check=False)
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def restart_steam(timeout: float = 60.0, poll: float = 0.7) -> Tuple[bool, str]:
    """Thoát Steam rồi mở lại. Không làm gì nếu Steam đang không chạy."""
    if not steam_running():
        return False, "Steam không chạy"

    exe = find_steam_exe()
    if exe is None:
        return False, "không tìm thấy steam.exe"

    if IS_WINDOWS:
        try:
            subprocess.run([str(exe), "-shutdown"], timeout=20, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"không gửi được lệnh thoát: {exc}"
    elif IS_MACOS:
        try:
            subprocess.run(
                ["osascript", "-e", 'tell application "Steam" to quit'],
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            subprocess.run([str(exe), "-shutdown"], timeout=20, check=False)
        except (OSError, subprocess.SubprocessError):
            pass

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not steam_running():
            break
        time.sleep(poll)
    else:
        return False, "Steam chưa thoát hẳn sau thời gian chờ"

    time.sleep(1.0)
    try:
        if IS_MACOS:
            subprocess.Popen(["open", "-a", "Steam"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif IS_WINDOWS:
            subprocess.Popen(
                [str(exe)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
            )
        else:
            subprocess.Popen(
                [str(exe)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"thoát được nhưng không mở lại được Steam: {exc}"
    return True, "đã khởi động lại Steam"


def os_summary() -> str:
    if IS_WINDOWS:
        return f"Windows ({sys.getwindowsversion().major}.{sys.getwindowsversion().build})"
    if IS_MACOS:
        return f"macOS ({sys.platform})"
    return f"Linux ({sys.platform})"
