#!/usr/bin/env python3
"""CLI REST cho SSB (`/api/v1/*`, ADR-069) — cho người hoặc agent chưa bật được MCP. Chỉ đọc.

  python ssb.py check                         # kiểm kết nối + token
  python ssb.py role  "Giám đốc Ban TCNS"     # nhãn chức danh → VT###
  python ssb.py owner "Ban Tổ chức - Nhân sự" # tên ban → DV### + trưởng ban
  python ssb.py combo "GVBM"                  # nhãn gộp RACI
  python ssb.py docs  "quy chế" [--limit 20]  # tìm DOC
  python ssb.py forms "phiếu"   [--limit 20]  # tìm BM
  python ssb.py doc   DOC.TCNS.01             # một DOC đủ trường
  python ssb.py form  BM.TCNS.01              # một BM
  python ssb.py unit  [DV12]                  # đơn vị (bỏ id = tất cả)
  python ssb.py rolecat [VT008]               # chức danh (bỏ id = tất cả)
  python ssb.py status                        # tình trạng hệ thống
  python ssb.py get /api/v1/...               # gọi thẳng đường bất kỳ (xem: python ssb.py get /api/v1)

In JSON ra stdout. Mã thoát: 0 ổn · 2 lỗi tham số · 3 lỗi mạng/HTTP.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ssb_config  # noqa: E402

TIMEOUT_SEC = 20.0


def get(path: str, params: dict | None = None, *, opener=None) -> dict:
    base, tok = ssb_config.host(), ssb_config.token()
    q = ("?" + urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})) if params else ""
    headers = {"Accept": "application/json"}
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(f"{base}{path}{q}", headers=headers, method="GET")
    with (opener or urllib.request.urlopen)(req, timeout=TIMEOUT_SEC) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _q(s: str) -> str:
    return urllib.parse.quote(str(s), safe="")


ROUTES = {
    "role": lambda a: ("/api/v1/resolve/role", {"label": a.value}),
    "owner": lambda a: ("/api/v1/resolve/owner", {"label": a.value}),
    "combo": lambda a: ("/api/v1/resolve/combo", {"token": a.value}),
    "docs": lambda a: ("/api/v1/docs", {"q": a.value, "limit": a.limit}),
    "forms": lambda a: ("/api/v1/forms", {"q": a.value, "limit": a.limit}),
    "doc": lambda a: (f"/api/v1/docs/{_q(a.value)}", None),
    "form": lambda a: (f"/api/v1/forms/{_q(a.value)}", None),
    "unit": lambda a: (f"/api/v1/units/{_q(a.value)}" if a.value else "/api/v1/units", None),
    "rolecat": lambda a: (f"/api/v1/roles/{_q(a.value)}" if a.value else "/api/v1/roles", None),
    "status": lambda a: ("/api/v1/status", None),
    "get": lambda a: (a.value or "/api/v1", None),
}


def main(argv: list[str] | None = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n", 1)[1])
    ap.add_argument("cmd", choices=["check", *ROUTES])
    ap.add_argument("value", nargs="?", default="")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        problem = ssb_config.token_problem()
        print(f"host  : {ssb_config.host()}")
        print(f"token : {'OK ' + ssb_config.token()[:9] + '…' if not problem else problem}")
        try:
            idx = get("/api/v1")
            print(f"server: OK — {len(idx.get('routes') or [])} đường REST")
            get("/api/v1/catalog")
            print("quyền : OK — đọc được bằng " + ("token" if not problem else "IP (legacy) — nên dán token"))
            return 0
        except urllib.error.HTTPError as e:
            print(f"quyền : HTTP {e.code} — {'token sai/thu hồi hoặc chưa dán' if e.code in (401, 403) else 'lỗi server'}")
            return 3
        except Exception as e:
            print(f"server: không kết nối được ({e}) — kiểm LAN / host.txt")
            return 3
    if a.cmd in ("role", "owner", "combo", "docs", "forms", "doc", "form") and not a.value:
        print(f"thiếu tham số: python ssb.py {a.cmd} \"<giá trị>\"", file=sys.stderr)
        return 2
    path, params = ROUTES[a.cmd](a)
    try:
        data = get(path, params)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"Không kết nối được SSB {ssb_config.host()} ({e})", file=sys.stderr)
        return 3
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
