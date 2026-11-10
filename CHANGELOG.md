# Changelog

Mọi thay đổi đáng chú ý của dự án được ghi ở đây.
Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), phiên bản theo [SemVer](https://semver.org/lang/vi/).

## [2.1.0] — 2026-11-10

Bản dành cho người dùng cuối: tải file, double-click, xong.

### Thêm mới

- **`SteamFix.cmd`** ở thư mục gốc: tự xin quyền admin (UAC), tự tải bản mới nhất từ Releases,
  kiểm tra SHA-256, giải nén vào `%LOCALAPPDATA%\SteamFix`, chạy `fix` và giữ cửa sổ để đọc kết quả.
  Không cần Python, git hay pipx; không phải gõ lệnh nào.
- Truyền lệnh tuỳ chọn khi cần: `SteamFix.cmd check`, `SteamFix.cmd revert`, `SteamFix.cmd "fix -r"`.
- Thông báo lỗi rõ ràng cho từng mã thoát (2/3/4) và hướng dẫn khắc phục ngay trong cửa sổ.

### Thay đổi

- Số hiệu phiên bản 2.1.0 cho gói Python, bản `.exe` và các script bootstrap.

## [2.0.0] — 2026-11-05

Viết lại toàn bộ bằng Python, gộp các tính năng của bản PowerShell 1.x và mở rộng đa nền tảng.

### Thêm mới

- Gói `steamfix` cài qua `pip`/`pipx`, có entry point `steamfix`.
- Dò IP từ 4 nguồn: seed, DNS hệ thống, DNS UDP (1.1.1.1, 8.8.8.8, 9.9.9.9, 223.5.5.5), DoH (Cloudflare/Google/Quad9).
- Kiểm tra endpoint song song bằng `ThreadPoolExecutor` (mặc định 8 luồng), tự thử lại không xác thực chứng chỉ khi cần.
- `steamfix check` / `fix` / `revert`, cờ `--dry-run`, `--restart-steam`, `--yes`, `--json`, `--report`, `--log`.
- Tự nâng quyền trên Windows (`ShellExecuteEx` + chờ tiến trình con, trả đúng mã thoát).
- Flush DNS đa nền tảng: `ipconfig`, `dscacheutil`, `resolvectl`, `systemd-resolve`, `nscd`.
- Khởi động lại Steam trên Windows/macOS/Linux.
- Ghi `hosts` nguyên tử, giữ mode quyền, xử lý file read-only, giữ CRLF, backup tự dọn (5 bản).
- 51 unit test (không cần mạng), GitHub Actions CI cho 3 HĐH × 5 phiên bản Python, lint bằng Ruff.

### Thay đổi

- Block trong `hosts` dùng mốc `# >>> SteamFix managed block (auto-generated) >>>`; vẫn nhận diện và dọn block do bản 1.x tạo.
- Mã thoát thống nhất: `0` OK, `1` lỗi, `2` thiếu quyền, `3` không có IP, `4` kiểm chứng lỗi.

### Gỡ bỏ

- Script PowerShell 1.x (đã được thay bằng bản Python tương đương).

## [1.0.0] — 2026-11-05

- Script PowerShell cho Windows: chẩn đoán, dò IP Akamai, ghim `hosts`, backup/hoàn tác, flush DNS, khởi động lại Steam.
