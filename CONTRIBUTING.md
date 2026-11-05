# Đóng góp cho SteamFix

Cảm ơn bạn đã quan tâm! Dự án nhỏ, quy ước cũng gọn.

## Môi trường

```bash
git clone https://github.com/BaoTaoBao/steamfix
cd steamfix
python -m pip install -e ".[dev]"
```

Yêu cầu Python 3.9+. Không thêm dependency runtime nếu có thể — mục tiêu là **chỉ thư viện chuẩn**.

## Trước khi mở PR

```bash
python -m pytest -q          # hoặc: python -m unittest discover -s tests -t . -v
ruff check src tests
ruff format src tests
```

- Test phải **không cần mạng** và **không chạm `hosts` thật** (dùng `tmp_path`/`tempfile`).
- Hành vi mới phải kèm test; sửa lỗi phải kèm test tái hiện lỗi.
- Giữ tương thích Python 3.9 (không dùng cú pháp chỉ có ở 3.10+).

## Quy ước code

- Type hint đầy đủ, `from __future__ import annotations`.
- Hàm thuần (dựng/đọc dữ liệu) tách khỏi phần I/O để dễ test.
- Thông báo cho người dùng bằng tiếng Việt, ngắn gọn, có tiền tố `[OK] / [!] / [X]` qua `console`.
- Không log IP người dùng ra ngoài máy; không thêm telemetry.

## Báo lỗi

Kèm thông tin:

1. Hệ điều hành + phiên bản Python.
2. Kết quả `steamfix check --json` (đã che thông tin nhạy cảm nếu cần).
3. Nhà mạng/quốc gia, và việc `store.steampowered.com` có bị chặn ở trình duyệt không.

## Giấy phép đóng góp

Khi gửi PR, bạn đồng ý phần đóng góp được phát hành theo giấy phép MIT của dự án.
