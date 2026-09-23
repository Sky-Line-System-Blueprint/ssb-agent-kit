"""Cấu hình chung cho cầu nối MCP và CLI REST: địa chỉ SSB + token kênh máy.

Thứ tự ưu tiên:
  host  : env SSB_URL  → dòng đầu (không phải #) của host.txt
  token : env SSB_MACHINE_TOKEN → dòng đầu (không phải #) của machine_token.txt
Token chỉ lấy đúng chuỗi ``ssbm_`` + 40 hex trong dòng (bỏ qua dấu #, nháy, chữ Bearer, khoảng trắng dính kèm).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent
DEFAULT_HOST = "http://192.168.10.182:8765"
_TOKEN_RE = re.compile(r"ssbm_[0-9a-f]{40}")


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


def token() -> str:
    """Token kênh máy hoặc "" nếu chưa dán. Dòng có ký tự thừa vẫn nhận nếu chứa đúng một token hợp lệ."""
    raw = (os.environ.get("SSB_MACHINE_TOKEN") or "").strip()
    if not raw:
        for line in (KIT_ROOT / "machine_token.txt").read_text(encoding="utf-8-sig").splitlines() if (KIT_ROOT / "machine_token.txt").is_file() else []:
            s = line.strip()
            if s and not s.startswith("#"):
                raw = s
                break
    m = _TOKEN_RE.search(raw)
    return m.group(0) if m else raw


def token_problem() -> str | None:
    """Mô tả lỗi token để in cho người dùng (None = ổn)."""
    t = token()
    if not t:
        return "chưa có token — dán token (ssbm_…) vào dòng trống cuối file machine_token.txt"
    if not _TOKEN_RE.fullmatch(t):
        return f"token sai định dạng ({len(t)} ký tự) — phải là ssbm_ + 40 ký tự 0-9a-f, chép bằng nút Copy ở tab Kênh máy"
    return None
