"""Test SSB Agent Kit — không cần server (giả lập HTTP). Chạy: python -m unittest discover -s tests"""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ssb  # noqa: E402
import ssb_config  # noqa: E402
import ssb_mcp_bridge as bridge  # noqa: E402

TOK = "ssbm_" + "a1" * 20


class FakeResp:
    def __init__(self, body: bytes):
        self._b = body

    def read(self) -> bytes:
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestConfig(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(self.id().replace(".", "_"))
        self.tmpdir = ROOT / "tests" / "_tmp"
        self.tmpdir.mkdir(exist_ok=True)
        self._p = mock.patch.object(ssb_config, "KIT_ROOT", self.tmpdir)
        self._p.start()
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop("SSB_MACHINE_TOKEN", None)
        os.environ.pop("SSB_URL", None)

    def tearDown(self) -> None:
        self._env.stop()
        self._p.stop()
        for f in self.tmpdir.iterdir():
            f.unlink()
        self.tmpdir.rmdir()

    def _tokfile(self, text: str) -> None:
        (self.tmpdir / "machine_token.txt").write_text(text, encoding="utf-8")

    def test_template_only_comments_means_no_token(self) -> None:
        tpl = (ROOT / "machine_token.txt").read_text(encoding="utf-8")
        self.assertNotRegex(tpl, r"ssbm_[0-9a-f]{40}")
        self._tokfile(tpl)
        self.assertEqual(ssb_config.token(), "")
        self.assertIn("chưa có token", ssb_config.token_problem())

    def test_token_extracted_from_noisy_line(self) -> None:
        for noisy in (TOK, f"  {TOK}  ", f"Bearer {TOK}", f'"{TOK}"', f"{TOK} # máy Thảo", f"{TOK}#"):
            self._tokfile("# chú thích\n\n" + noisy + "\n")
            self.assertEqual(ssb_config.token(), TOK, noisy)
            self.assertIsNone(ssb_config.token_problem())

    def test_bad_token_reported(self) -> None:
        self._tokfile("ssbm_0...2ff\n")
        self.assertIn("sai định dạng", ssb_config.token_problem())

    def test_env_overrides(self) -> None:
        self._tokfile("ssbm_" + "0" * 40 + "\n")
        (self.tmpdir / "host.txt").write_text("# x\nhttp://10.0.0.1:8765/\n", encoding="utf-8")
        self.assertEqual(ssb_config.host(), "http://10.0.0.1:8765")
        with mock.patch.dict(os.environ, {"SSB_MACHINE_TOKEN": TOK, "SSB_URL": "http://h:1"}):
            self.assertEqual((ssb_config.token(), ssb_config.host()), (TOK, "http://h:1"))

    def test_default_host(self) -> None:
        self.assertEqual(ssb_config.host(), ssb_config.DEFAULT_HOST)


class TestBridge(unittest.TestCase):
    def test_request_forwarded_with_bearer_single_line(self) -> None:
        seen: list = []

        def opener(req, timeout=None):
            seen.append(req)
            return FakeResp(b'{"jsonrpc":"2.0","id":7,' + bytes([10]) + b'"result":{}}')

        out = bridge.forward('{"jsonrpc":"2.0","id":7,"method":"tools/list"}', "http://h:8765", TOK, opener=opener)
        self.assertEqual(json.loads(out), {"jsonrpc": "2.0", "id": 7, "result": {}})
        self.assertNotIn(chr(10), out)
        self.assertEqual(seen[0].full_url, "http://h:8765/mcp")
        self.assertEqual(seen[0].get_header("Authorization"), f"Bearer {TOK}")

    def test_notification_silent_and_no_token_no_header(self) -> None:
        seen: list = []
        self.assertIsNone(bridge.forward('{"jsonrpc":"2.0","method":"notifications/initialized"}', "http://h", "", opener=lambda r, timeout=None: (seen.append(r), FakeResp(b""))[1]))
        self.assertIsNone(seen[0].get_header("Authorization"))

    def test_errors(self) -> None:
        def down(req, timeout=None):
            raise OSError("mất mạng")

        e = json.loads(bridge.forward('{"jsonrpc":"2.0","id":3,"method":"x"}', "http://h", TOK, opener=down))
        self.assertEqual((e["id"], e["error"]["code"]), (3, -32603))

        def forbid(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 403, "x", {}, io.BytesIO(b""))

        e = json.loads(bridge.forward('{"jsonrpc":"2.0","id":4,"method":"x"}', "http://h", TOK, opener=forbid))
        self.assertIn("machine_token.txt", e["error"]["message"])
        self.assertEqual(json.loads(bridge.forward("rác", "http://h", TOK))["error"]["code"], -32700)


class TestCli(unittest.TestCase):
    def _run(self, argv, body=b'{"ok": true}'):
        seen: list = []
        buf = io.StringIO()
        with mock.patch.object(ssb_config, "token", return_value=TOK), mock.patch.object(ssb_config, "host", return_value="http://h:8765"), \
             mock.patch("urllib.request.urlopen", side_effect=lambda req, timeout=None: (seen.append(req), FakeResp(body))[1]), \
             mock.patch("sys.stdout", buf):
            rc = ssb.main(argv)
        return rc, seen, buf.getvalue()

    def test_routes(self) -> None:
        cases = {
            ("role", "Giám đốc Ban TCNS"): "/api/v1/resolve/role?label=Gi%C3%A1m+%C4%91%E1%BB%91c+Ban+TCNS",
            ("owner", "Ban A"): "/api/v1/resolve/owner?label=Ban+A",
            ("combo", "GVBM"): "/api/v1/resolve/combo?token=GVBM",
            ("doc", "DOC.TCNS.01"): "/api/v1/docs/DOC.TCNS.01",
            ("form", "BM.TCNS.01"): "/api/v1/forms/BM.TCNS.01",
            ("unit", ""): "/api/v1/units",
            ("rolecat", "VT008"): "/api/v1/roles/VT008",
            ("status", ""): "/api/v1/status",
            ("get", "/api/v1/schema"): "/api/v1/schema",
        }
        for (cmd, val), path in cases.items():
            rc, seen, _ = self._run([cmd, val] if val else [cmd])
            self.assertEqual(rc, 0, cmd)
            self.assertEqual(seen[0].full_url, "http://h:8765" + path, cmd)
            self.assertEqual(seen[0].get_header("Authorization"), f"Bearer {TOK}")
        rc, seen, _ = self._run(["docs", "quy chế", "--limit", "5"])
        self.assertEqual(seen[0].full_url, "http://h:8765/api/v1/docs?q=quy+ch%E1%BA%BF&limit=5")

    def test_missing_value(self) -> None:
        with mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(ssb.main(["role"]), 2)


class TestConfigFiles(unittest.TestCase):
    def test_mcp_json_no_secret_points_to_bridge(self) -> None:
        for rel in (".cursor/mcp.json", ".mcp.json"):
            cfg = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            self.assertEqual(cfg["mcpServers"]["ssb"]["args"], ["ssb_mcp_bridge.py"], rel)
            self.assertNotIn("ssbm_", json.dumps(cfg))
        self.assertTrue((ROOT / ".claude/skills/ssb/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
