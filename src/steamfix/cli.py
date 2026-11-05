"""Giao diện dòng lệnh của SteamFix."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from typing import List, Optional

from . import config, console, diagnose, platform_ops
from .hostsfile import HostsFile

DESCRIPTION = (
    "Sửa lỗi Steam Store / Steam Community bị nhà mạng chặn (DNS + lọc SNI) "
    "bằng cách ghim IP Akamai còn hoạt động vào file hosts."
)

EPILOG = """ví dụ:
  steamfix                     # kiểm tra + sửa
  steamfix check               # chỉ kiểm tra
  steamfix fix --dry-run       # xem trước, không ghi hosts
  steamfix fix -r -y           # sửa và tự khởi động lại Steam
  steamfix revert              # gỡ cấu hình, trả hosts như cũ
  steamfix fix --report out.json
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steamfix",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {config.VERSION}")

    def add_global_options(target: argparse.ArgumentParser, *, suppress: bool = False) -> None:
        """Thêm cờ toàn cục; bản trong subparser dùng SUPPRESS để không đè giá trị đã parse."""
        no_color_default = argparse.SUPPRESS if suppress else False
        debug_default = argparse.SUPPRESS if suppress else False
        log_default = argparse.SUPPRESS if suppress else None
        target.add_argument("--no-color", action="store_true", default=no_color_default, help="tắt màu ANSI")
        target.add_argument("--debug", action="store_true", default=debug_default, help="in traceback khi có lỗi")
        target.add_argument("--log", metavar="FILE", default=log_default, help="ghi toàn bộ output ra FILE")

    add_global_options(parser)

    sub = parser.add_subparsers(dest="command", metavar="{check,fix,revert}")

    def add_probe_options(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--timeout",
            type=float,
            default=config.DEFAULT_TIMEOUT,
            help="timeout mỗi lần kiểm tra, giây (mặc định: %(default)s)",
        )
        target.add_argument(
            "--workers",
            type=int,
            default=config.DEFAULT_WORKERS,
            help="số luồng kiểm tra song song (mặc định: %(default)s)",
        )
        target.add_argument("--hosts-path", default=None, help="dùng file hosts khác (chủ yếu để test)")
        target.add_argument("--json", action="store_true", help="in kết quả dạng JSON")

    check = sub.add_parser("check", help="kiểm tra trạng thái hiện tại")
    add_global_options(check, suppress=True)
    add_probe_options(check)

    fix = sub.add_parser("fix", help="tìm IP tốt và ghi vào hosts (mặc định)")
    add_global_options(fix, suppress=True)
    add_probe_options(fix)
    fix.add_argument("--dry-run", "-n", action="store_true", help="không ghi hosts")
    fix.add_argument("--restart-steam", "-r", action="store_true", help="khởi động lại Steam sau khi sửa")
    fix.add_argument("--yes", "-y", action="store_true", help="không hỏi lại")
    fix.add_argument("--no-elevate", action="store_true", help="không tự xin quyền admin")
    fix.add_argument("--report", metavar="FILE", default=None, help="xuất báo cáo JSON ra FILE")
    fix.add_argument("--pause", action="store_true", help=argparse.SUPPRESS)

    revert = sub.add_parser("revert", help="gỡ cấu hình, trả hosts về như cũ")
    add_global_options(revert, suppress=True)
    revert.add_argument("--hosts-path", default=None, help="dùng file hosts khác (chủ yếu để test)")
    revert.add_argument("--json", action="store_true", help="in kết quả dạng JSON")
    revert.add_argument("--no-elevate", action="store_true", help="không tự xin quyền admin")
    revert.add_argument("--pause", action="store_true", help=argparse.SUPPRESS)

    return parser


def _maybe_elevate(argv: List[str], args: argparse.Namespace) -> Optional[int]:
    """Tự mở lại với quyền admin (Windows). Trả mã thoát nếu đã xử lý xong."""
    if args.command not in {"fix", "revert"}:
        return None
    if getattr(args, "no_elevate", False) or platform_ops.is_admin():
        return None
    if not platform_ops.IS_WINDOWS:
        console.error("Cần quyền quản trị để sửa file hosts.")
        console.info(platform_ops.admin_hint())
        return config.EXIT_NO_ADMIN
    if "--pause" in argv:
        return None  # đã là tiến trình con được nâng quyền

    child = [*argv, "--pause"]
    console.warn("Cần quyền Administrator — đang mở cửa sổ mới...")
    code = platform_ops.elevate_and_wait(child)
    if code is None:
        console.error("Không nâng được quyền (bạn đã huỷ hộp thoại UAC?).")
        return config.EXIT_NO_ADMIN
    return code


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Phải đặt encoding UTF-8 TRƯỚC khi argparse in help/usage (nội dung tiếng Việt),
    # nếu không, khi stdout bị redirect trên Windows sẽ vỡ do code page cũ.
    console.setup()
    parser = build_parser()
    args = parser.parse_args(argv)

    console.setup(color=False if args.no_color else None)
    console.set_quiet(False)
    if args.log:
        console.set_logfile(args.log)

    if not args.command:
        parser.print_help()
        return config.EXIT_OK

    if getattr(args, "json", False):
        console.set_quiet(True)

    elevated_code = _maybe_elevate(argv, args)
    if elevated_code is not None:
        return elevated_code

    hosts_file = HostsFile(getattr(args, "hosts_path", None))
    payload: dict = {}
    code = config.EXIT_OK

    try:
        if args.command == "check":
            code, payload = diagnose.run_check(timeout=args.timeout, workers=args.workers, hosts_file=hosts_file)
        elif args.command == "fix":
            code, payload = diagnose.run_fix(
                timeout=args.timeout,
                workers=args.workers,
                dry_run=args.dry_run,
                restart_steam=args.restart_steam,
                yes=args.yes,
                hosts_file=hosts_file,
            )
            if args.report:
                try:
                    path = diagnose.write_report(args.report, payload)
                    if not getattr(args, "json", False):
                        console.info(f"Đã xuất báo cáo: {path}")
                except OSError as exc:
                    console.warn(f"Không ghi được báo cáo: {exc}")
        elif args.command == "revert":
            code, payload = diagnose.run_revert(hosts_file=hosts_file)
    except KeyboardInterrupt:
        console.blank()
        console.warn("Đã huỷ.")
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI phải không bao giờ văng traceback
        console.error(f"Lỗi không mong muốn: {exc}")
        if args.debug:
            traceback.print_exc()
        return config.EXIT_ERROR

    if getattr(args, "json", False) and payload:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    if getattr(args, "pause", False) and not getattr(args, "json", False):
        console.blank()
        try:
            input("  Nhấn Enter để đóng...")
        except (EOFError, KeyboardInterrupt):
            pass

    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
