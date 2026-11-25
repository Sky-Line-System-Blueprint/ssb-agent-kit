"""Cấu hình chung cho cầu nối MCP và CLI REST: địa chỉ SSB + token kênh máy.

Thứ tự ưu tiên:
  host  : env SSB_URL  → dòng đầu (không phải #) của host.txt
  token : env SSB_MACHINE_TOKEN → dòng đầu (không phải #) của machine_token.local.txt (riêng máy, git bỏ qua)
          → machine_token.txt (file mẫu git theo dõi — chỉ còn đọc cho máy đã dán từ trước)
Token chỉ lấy đúng chuỗi ``ssbm_`` + 40 hex trong dòng (bỏ qua dấu #, nháy, chữ Bearer, khoảng trắng dính kèm).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent
DEFAULT_HOST = "https://ssb-gov.skylineschool.edu.vn"  # SSB trên VM từ 16/10 — chỉ trong mạng công ty
_TOKEN_RE = re.compile(r"ssbm_[0-9a-f]{40}")
TOKEN_FILE = "machine_token.local.txt"  # nơi dán token — .gitignore bỏ qua, repo public không lộ
LEGACY_TOKEN_FILE = "machine_token.txt"  # file mẫu git theo dõi; dán vào đây thì dễ commit nhầm


def _first_value(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                return s
    except OSError:
        pass
    return ""


def host() -> str:
    return (os.environ.get("SSB_URL") or _first_value(KIT_ROOT / "host.txt") or DEFAULT_HOST).strip().rstrip("/")


def _token_raw() -> tuple[str, str]:
    """(chuỗi thô, nguồn) — nguồn là "env", tên file, hoặc "" khi chưa dán."""
    raw = (os.environ.get("SSB_MACHINE_TOKEN") or "").strip()
    if raw:
        return raw, "env"
    for name in (TOKEN_FILE, LEGACY_TOKEN_FILE):
        raw = _first_value(KIT_ROOT / name)
        if raw:
            return raw, name
    return "", ""


def token() -> str:
    """Token kênh máy hoặc "" nếu chưa dán. Dòng có ký tự thừa vẫn nhận nếu chứa đúng một token hợp lệ."""
    raw = _token_raw()[0]
    m = _TOKEN_RE.search(raw)
    return m.group(0) if m else raw


def token_source() -> str:
    return _token_raw()[1]


def token_problem() -> str | None:
    """Mô tả lỗi token để in cho người dùng (None = ổn)."""
    t = token()
    if not t:
        return f"chưa có token — tạo file {TOKEN_FILE} cạnh ssb.py, dán token (ssbm_…) vào một dòng"
    if not _TOKEN_RE.fullmatch(t):
        return f"token sai định dạng ({len(t)} ký tự) — phải là ssbm_ + 40 ký tự 0-9a-f, chép bằng nút Copy ở tab Kênh máy"
    return None
