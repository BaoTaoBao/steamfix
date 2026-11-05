"""Cấu hình và hằng số dùng chung cho SteamFix."""

from __future__ import annotations

from typing import Dict, Tuple

APP_NAME = "SteamFix"
VERSION = "2.0.0"
__version__ = VERSION

#: Tên miền được quản lý (viết thường, không có dấu chấm cuối).
MANAGED_HOSTS: Tuple[str, ...] = (
    "store.steampowered.com",
    "steamcommunity.com",
)

#: Mốc bắt đầu/kết thúc block do SteamFix ghi vào file hosts.
#: Dùng tiền tố để nhận diện được cả block do bản PowerShell 1.x tạo ra.
BLOCK_START_PREFIX = "# >>> SteamFix managed block"
BLOCK_END_PREFIX = "# <<< SteamFix managed block"

#: Dịch vụ Steam không bị chặn — dùng để đối chiếu khi chẩn đoán.
HEALTH_HOSTS: Tuple[str, ...] = (
    "login.steampowered.com",
    "api.steampowered.com",
)

#: IP Akamai từng hoạt động tốt. Chỉ là "hạt giống": mọi IP đều được kiểm tra
#: lại trước khi dùng, IP chết sẽ bị loại tự động.
SEED_IPS: Dict[str, Tuple[str, ...]] = {
    "store.steampowered.com": (
        "23.41.38.92",
        "104.83.198.104",
        "42.119.186.138",
        "184.24.24.16",
        "23.44.130.48",
    ),
    "steamcommunity.com": (
        "23.41.37.9",
        "104.83.197.9",
        "23.41.38.92",
    ),
}

#: Resolver UDP dùng để dò thêm IP (ngoài DNS hệ thống).
DNS_SERVERS: Tuple[str, ...] = ("1.1.1.1", "8.8.8.8", "9.9.9.9", "223.5.5.5")

#: Resolver DNS-over-HTTPS (JSON API).
DOH_ENDPOINTS: Dict[str, str] = {
    "cloudflare": "https://cloudflare-dns.com/dns-query?name={name}&type=A",
    "google": "https://dns.google/resolve?name={name}&type=A",
    "quad9": "https://dns.quad9.net:5053/dns-query?name={name}&type=A",
}

DEFAULT_TIMEOUT = 8.0
DEFAULT_WORKERS = 8
MAX_CANDIDATES = 16
MAX_BACKUPS = 5

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NO_ADMIN = 2
EXIT_NO_WORKING_IP = 3
EXIT_VERIFY_FAILED = 4
