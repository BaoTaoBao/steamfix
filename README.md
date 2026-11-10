# SteamFix

[![CI](https://github.com/BaoTaoBao/steamfix/actions/workflows/ci.yml/badge.svg)](https://github.com/BaoTaoBao/steamfix/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](#)

**Sửa lỗi Steam Store / Steam Community không mở được** khi nhà mạng chặn bằng DNS + lọc SNI — tự dò IP Akamai còn sống, kiểm tra thật, rồi ghim vào file `hosts`.

Không VPN, không proxy, không cài service. Một lệnh, có backup, hoàn tác được.

## Cách nhanh nhất — tải file, double-click ✅

1. Mở **[SteamFix.cmd](https://github.com/BaoTaoBao/steamfix/blob/main/SteamFix.cmd)** → bấm **Download raw file**
   (hoặc chuột phải vào nút *Raw* → *Save link as...*).
2. **Double-click** file vừa tải → bấm **Yes** ở hộp thoại UAC.
3. Xong. Cửa sổ hiện tiến trình và kết quả, không phải gõ gì.

Script tự: xin quyền admin → tải bản mới nhất từ Releases → kiểm tra SHA-256 → giải nén vào
`%LOCALAPPDATA%\SteamFix` → chạy `steamfix fix` → giữ cửa sổ để bạn đọc kết quả.

Không cần Python, không cần git, không cần pipx. Muốn làm việc khác thì mở `cmd` tại thư mục đó:

```bat
SteamFix.cmd check      :: chỉ kiểm tra
SteamFix.cmd revert     :: gỡ cấu hình
SteamFix.cmd "fix -r"   :: sửa + mở lại Steam
```

```console
$ steamfix
==============================================================================
  SteamFix 2.1.0 — TỰ ĐỘNG SỬA
==============================================================================

[1] Kiểm tra hiện trạng
    [OK]   store.steampowered.com: đang OK (HTTP 200, 472 ms)
    [OK]   steamcommunity.com: đang OK (HTTP 200, 562 ms)

[2] Dò IP Akamai còn hoạt động
           store.steampowered.com: thử 6 IP song song ...
             IP              Nguồn       Kết quả  HTTP  Chi tiết
             23.41.38.92     seed        OK       200   509 ms
             104.83.198.104  seed        OK       200   446 ms
             42.119.186.138  seed        OK       200   419 ms
             184.24.24.16    seed        lỗi      403   HTTP 403
             23.44.130.48    seed        OK       200   1639 ms
             23.197.226.96   doh:google  lỗi      -     timeout 8s
    [OK]   Chọn 42.119.186.138 cho store.steampowered.com (HTTP 200, 419 ms)

[3] Cập nhật file hosts
           Đã sao lưu: C:\Windows\System32\drivers\etc\hosts.steamfix-20261105-181011.bak
    [OK]   Đã ghi block SteamFix vào hosts.
           Xoá cache DNS: Successfully flushed the DNS Resolver Cache.

[4] Kiểm chứng đầu-cuối
    [OK]   store.steampowered.com -> 42.119.186.138 | HTTP 200, 606 ms
    [OK]   steamcommunity.com -> 23.41.37.9 | HTTP 200, 460 ms

==============================================================================
  KẾT QUẢ
==============================================================================
  THÀNH CÔNG: Steam Store và Community đã truy cập được.
```

---

## Vấn đề này là gì?

Nhiều nhà mạng (điển hình là Viettel ở Việt Nam) chặn Steam Store/Community bằng hai lớp:

1. **DNS**: trả về IP bị "hố đen", có khi là `127.0.0.1`.
2. **Lọc SNI**: với các IP Akamai `23.15.x` phục vụ Steam, TCP vẫn bắt tay được nhưng TLS
   **không bao giờ hoàn tất** — kết nối treo ~19 giây rồi reset. Cùng IP đó, nếu đổi SNI sang
   `api.steampowered.com` thì mọi thứ lại bình thường.

Triệu chứng người dùng thấy:

- Steam client mở được, đăng nhập được, tải game được, nhưng **Store và Community trắng trang**.
- Trình duyệt vào `store.steampowered.com` quay vòng rồi báo *connection timed out*.
- `ping`/`telnet` tới IP vẫn "được" nên tưởng mạng không sao.

Vì chặn theo **cặp IP + SNI**, chữa được bằng cách trỏ tên miền sang một edge Akamai khác
còn sống — chính là việc công cụ này tự động hoá.

## Cách hoạt động

```
  nguồn IP                      kiểm tra thật                     hành động
┌───────────────────┐   ┌──────────────────────────────┐   ┌────────────────────┐
│ seed (đã kiểm)    │   │ TCP:443  →  TLS (SNI đúng)   │   │ chọn IP nhanh nhất │
│ DNS hệ thống      │──▶│          →  GET /            │──▶│ backup hosts       │
│ DNS UDP 1.1.1.1 … │   │          →  HTTP 2xx/3xx ?   │   │ ghi block có mốc   │
│ DoH CF/Google/Q9  │   │ (8 luồng song song, timeout) │   │ flush DNS          │
└───────────────────┘   └──────────────────────────────┘   │ kiểm chứng lại     │
                                                            │ (tuỳ chọn) restart │
                                                            └────────────────────┘
```

- **Song song**: mỗi tên miền thử tối đa 16 ứng viên bằng 8 luồng, nên toàn bộ quá trình
  thường dưới 3 giây kể cả khi phần lớn IP bị chặn.
- **Không tin DNS**: IP nào cũng phải tự chứng minh bằng một kết nối TLS thật với đúng SNI,
  và phải trả về HTTP 2xx/3xx. IP trả `403` (sai vhost) bị loại.
- **Chỉ sửa một block**: mọi thay đổi nằm giữa hai dòng mốc `# >>> SteamFix managed block`
  và `# <<< SteamFix managed block <<<`. Các dòng khác của `hosts` (kể cả mục MagicDNS của
  Tailscale) được giữ nguyên.

## Cài đặt

Yêu cầu: **Python 3.9+**, không cần thư viện ngoài.

```bash
# cách gọn nhất (khuyến nghị)
pipx install git+https://github.com/BaoTaoBao/steamfix

# hoặc pip
pip install git+https://github.com/BaoTaoBao/steamfix

# hoặc từ mã nguồn
git clone https://github.com/BaoTaoBao/steamfix
cd steamfix
python -m pip install -e .

# hoặc tải sẵn wheel/sdist ở trang Releases
# https://github.com/BaoTaoBao/steamfix/releases
```

Chạy không cần cài: `python -m steamfix` (sau khi thêm `src` vào `PYTHONPATH`).

> Trên Windows, app cần quyền Administrator để ghi `hosts`. SteamFix tự mở hộp thoại UAC
> và chờ tiến trình có quyền chạy xong, rồi trả đúng mã thoát.

### Windows — không cần cài Python

Tải `steamfix-windows-x64.zip` ở trang [**Releases**](https://github.com/BaoTaoBao/steamfix/releases),
giải nén ra một thư mục bất kỳ, rồi chạy:

```bat
steamfix\steamfix.exe            :: kiểm tra + sửa
steamfix\steamfix.exe check      :: chỉ kiểm tra
steamfix\steamfix.exe revert     :: gỡ cấu hình
steamfix\steamfix.exe fix -r     :: sửa + mở lại Steam
```

- Lần chạy đầu hiện hộp thoại **UAC** → bấm **Yes** (cần quyền admin để sửa `hosts`).
- File `.exe` chưa ký số nên SmartScreen/Defender có thể cảnh báo →
  **More info → Run anyway**.
- Bản này là *onedir*: giữ nguyên cả thư mục `steamfix\` (đừng copy lẻ file `.exe`).
- Muốn tự build: `powershell -ExecutionPolicy Bypass -File scripts/build-exe.ps1`
  (cần Python + PyInstaller trên máy build, máy đích thì không).

### Windows — một dòng lệnh kiểu `irm ... | iex` (nhanh nhất) ⚡

Mở **PowerShell** và dán:

```powershell
irm https://raw.githubusercontent.com/BaoTaoBao/steamfix/main/install.ps1 | iex
```

Hoặc từ **cmd**:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/BaoTaoBao/steamfix/main/install.ps1 | iex"
```

Script làm hết: tải bản mới nhất → **kiểm tra SHA-256** → giải nén vào `%LOCALAPPDATA%\SteamFix`
→ chạy `steamfix fix`. Muốn làm việc khác thì đặt biến môi trường trước khi chạy:

```powershell
$env:STEAMFIX_ARGS = 'check';  irm https://raw.githubusercontent.com/BaoTaoBao/steamfix/main/install.ps1 | iex
```

Script chỉ ~5 KB, đọc trước khi chạy được: [`install.ps1`](install.ps1).

### Windows — một dòng lệnh trong `cmd`, không cài gì

Dán vào `cmd` (máy chỉ cần Windows 10/11 x64 + mạng):

```bat
curl -fsSL -o "%TEMP%\steamfix.cmd" https://raw.githubusercontent.com/BaoTaoBao/steamfix/main/scripts/steamfix.cmd && "%TEMP%\steamfix.cmd" fix -r
```

Script tự tải bản mới nhất từ Releases, giải nén vào `%LOCALAPPDATA%\SteamFix` rồi chạy.
Các lần sau dùng lại lệnh trên (bản đã tải nên chạy ngay), hoặc gọi thẳng:

```bat
"%LOCALAPPDATA%\SteamFix\steamfix\steamfix.exe" check
"%LOCALAPPDATA%\SteamFix\steamfix\steamfix.exe" fix -r
```

### Windows — cài để gõ `steamfix` như một lệnh

```bat
curl -fsSL -o "%TEMP%\steamfix-install.cmd" https://raw.githubusercontent.com/BaoTaoBao/steamfix/main/scripts/install.cmd && "%TEMP%\steamfix-install.cmd"
```

Sau đó **mở `cmd` mới** và dùng:

```bat
steamfix check
steamfix fix -r
```

Cài vào `%LOCALAPPDATA%\SteamFix`, thêm launcher `steamfix.cmd` vào
`%LOCALAPPDATA%\Microsoft\WindowsApps` (đã có sẵn trong PATH) — **không cần quyền admin**.
Gỡ cài đặt: xoá 2 đường dẫn trên. Cập nhật: chạy lại lệnh `install` là xong.

## Sử dụng

| Lệnh | Việc làm |
|------|----------|
| `steamfix` | Kiểm tra rồi tự sửa (mặc định) |
| `steamfix check` | Chỉ chẩn đoán, không ghi gì |
| `steamfix fix` | Dò IP + ghi `hosts` |
| `steamfix fix -n` | Xem trước nội dung sẽ ghi (dry-run) |
| `steamfix fix -r` | Sửa rồi khởi động lại Steam |
| `steamfix revert` | Gỡ cấu hình, trả `hosts` về như cũ |
| `steamfix fix --json` | Xuất kết quả JSON (cho script/monitor) |
| `steamfix fix --report out.json` | Ghi báo cáo chi tiết ra file |

Tuỳ chọn hữu ích: `--timeout 8` (giây mỗi lần thử), `--workers 8` (số luồng),
`--log run.log` (ghi toàn bộ output ra file), `--no-color`, `--debug`,
`--hosts-path FILE` (dùng file hosts khác để thử nghiệm).

### Mã thoát

| Mã | Ý nghĩa |
|----|---------|
| `0` | Thành công (hoặc `check` thấy mọi thứ ổn) |
| `1` | Lỗi không mong muốn |
| `2` | Thiếu quyền Administrator |
| `3` | Không tìm được IP nào hoạt động → cần VPN |
| `4` | Đã ghi `hosts` nhưng kiểm chứng vẫn lỗi |
| `130` | Người dùng huỷ (Ctrl+C) |

## An toàn và hoàn tác

- Trước mỗi lần ghi, `hosts` được sao lưu thành `hosts.steamfix-<thời-gian>.bak` cùng thư mục
  (giữ 5 bản gần nhất).
- Ghi **nguyên tử**: tạo file tạm cùng thư mục rồi `os.replace`, giữ nguyên mode quyền.
- File read-only được tạm bỏ cờ, ghi xong khôi phục.
- `steamfix revert` chỉ xoá block của SteamFix, không đụng phần còn lại của `hosts`.
- Khôi phục nguyên trạng:

  ```bash
  # Linux/macOS
  sudo cp /etc/hosts.steamfix-<thời-gian>.bak /etc/hosts
  # Windows (PowerShell, Administrator)
  Copy-Item C:\Windows\System32\drivers\etc\hosts.steamfix-<thời-gian>.bak `
            C:\Windows\System32\drivers\etc\hosts -Force
  ipconfig /flushdns
  ```

Công cụ **không** gửi dữ liệu đi đâu, **không** cài service, **không** sửa registry/firewall.

## Không sửa được thì sao?

| Hiện tượng | Cách xử lý |
|------------|------------|
| `exit code 2` | Chạy lại bằng Administrator (Windows) hoặc `sudo` |
| `exit code 3` | Mọi edge thử được đều chết → dùng VPN/proxy |
| Sửa xong nhưng Steam vẫn trắng | Thoát hẳn Steam rồi mở lại (`steamfix fix -r`); Steam cache DNS trong tiến trình |
| Lại lỗi sau vài tuần | Chạy lại `steamfix` — Akamai đổi edge, IP cũ chết dần |
| `check` OK nhưng trình duyệt lỗi | Trình duyệt có thể đang bật DoH/Secure DNS riêng → tắt hoặc đổi sang "Off" |

> Nếu nhà mạng chặn ở mức độ sâu hơn (chặn cả SNI toàn tuyến, hoặc chặn IP Akamai diện rộng),
> `hosts` không còn tác dụng. Khi đó VPN là lựa chọn duy nhất.

## Phát triển

```bash
python -m pip install -e ".[dev]"

# test (không cần mạng, không chạm hosts thật)
python -m pytest -q
# hoặc chỉ với thư viện chuẩn
python -m unittest discover -s tests -t . -v

# lint + format
ruff check src tests
ruff format --check src tests
```

Bộ test phủ: dựng/đọc gói DNS (kể cả nén con trỏ và lỗi), lọc IP công khai, dựng block
`hosts` (giữ CRLF, file không có newline cuối, read-only), chọn IP tốt nhất, các nhánh
lỗi TCP/TLS/timeout, tham số CLI và mã thoát.

### Cấu trúc

```
src/steamfix/
├─ cli.py           # argparse, mã thoát, tự nâng quyền
├─ diagnose.py      # orchestration: check / fix / revert
├─ resolver.py      # gom IP ứng viên (seed, DNS hệ thống, UDP, DoH)
├─ dnsclient.py     # DNS client UDP tối giản (chỉ bản ghi A)
├─ probe.py         # TCP → TLS(SNI) → HTTP, chạy song song
├─ hostsfile.py     # block có mốc, backup, ghi nguyên tử
├─ platform_ops.py  # admin, flush DNS, khởi động lại Steam
├─ console.py       # màu ANSI, bảng, chế độ quiet
└─ config.py        # hằng số, seed IP, mã thoát
```

## Giới hạn đã biết

- Chỉ xử lý IPv4 (Steam Store/Community dùng A record; AAAA thường không có).
- IP được ghim là tĩnh: khi Akamai đổi edge, cần chạy lại (thường vài tuần/lần).
- Không tự chạy nền hay theo dõi liên tục — cố ý, để không can thiệp vào máy bạn.
- Chưa hỗ trợ DoH cho Steam client; chỉ ảnh hưởng tới DNS của hệ điều hành, không đổi cấu hình mạng.

## Ghi công

Phiên bản 1.0.0 là script PowerShell cho Windows; từ 2.0.0 toàn bộ được viết lại bằng Python,
gộp mọi tính năng và chạy được trên Windows, macOS, Linux.

## Giấy phép

[MIT](LICENSE). Dùng cho mục đích cá nhân, tự chịu trách nhiệm. Đây không phải sản phẩm của
Valve/Steam.

---

> Badge CI và link cài đặt trỏ tới `github.com/BaoTaoBao/steamfix`. Nếu đổi tên repo,
> nhớ cập nhật `README.md` và `pyproject.toml` cho khớp.
