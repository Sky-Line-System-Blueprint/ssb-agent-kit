#!/usr/bin/env python3
"""Cầu nối MCP stdio → SSB `/mcp` (ADR-069). Cursor / Claude Code khởi động file này theo
`.cursor/mcp.json` / `.mcp.json`; mỗi dòng JSON-RPC từ stdin được POST lên ``<host>/mcp`` kèm
``Authorization: Bearer <token>`` (machine_token.txt), phản hồi in ra stdout — mỗi dòng một JSON.

Thử tay:  echo {"jsonrpc":"2.0","id":1,"method":"tools/list"} | python ssb_mcp_bridge.py
Chẩn đoán in ra stderr (stdout dành riêng cho giao thức MCP). Chỉ dùng thư viện chuẩn Python.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ssb_config  # noqa: E402

TIMEOUT_SEC = 20.0


def _error(req_id, message: str, code: int = -32603) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def forward(line: str, base: str, token: str, *, opener=None) -> str | None:
    """Một dòng JSON-RPC → phản hồi (chuỗi JSON một dòng) hoặc None cho notification."""
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return json.dumps(_error(None, "JSON không hợp lệ", -32700), ensure_ascii=False)
    req_id = msg.get("id") if isinstance(msg, dict) else None
    is_notification = isinstance(msg, dict) and "id" not in msg
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{base}/mcp", data=line.encode("utf-8"), headers=headers, method="POST")
    try:
        with (opener or urllib.request.urlopen)(req, timeout=TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if is_notification:
            return None
        hint = " — token sai/thu hồi hoặc chưa dán token (machine_token.txt)" if e.code in (401, 403) else ""
        return json.dumps(_error(req_id, f"SSB {base} trả HTTP {e.code}{hint}"), ensure_ascii=False)
    except Exception as e:  # mất mạng / sai host
        if is_notification:
            return None
        return json.dumps(_error(req_id, f"Không kết nối được SSB {base} ({e.__class__.__name__}: {e}) — kiểm LAN / host.txt"), ensure_ascii=False)
    if is_notification or not raw.strip():
        return None
    return " ".join(raw.split("\n")).strip()


def main() -> int:
    for _s in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    base, tok = ssb_config.host(), ssb_config.token()
    problem = ssb_config.token_problem()
    print(f"ssb_mcp_bridge: {base}/mcp · " + (f"token {tok[:9]}…" if not problem else f"CẢNH BÁO: {problem}"), file=sys.stderr, flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        out = forward(line, base, tok)
        if out is not None:
            sys.stdout.write(out + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
