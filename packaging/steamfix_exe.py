"""Entry point cho bản đóng gói bằng PyInstaller (tạo steamfix.exe)."""

from __future__ import annotations

from steamfix.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
