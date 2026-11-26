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
        self.assertEqual(ssb_config._first_value(ROOT / "host.txt"), ssb_config.DEFAULT_HOST, "host.txt khớp mặc định (VM)")

    def test_local_file_first_legacy_still_read(self) -> None:
        tok2 = "ssbm_" + "1" * 40
        self._tokfile(f"{tok2}\n")
        self.assertEqual((ssb_config.token(), ssb_config.token_source()), (tok2, "machine_token.txt"))
        (self.tmpdir / "machine_token.local.txt").write_text(f"# riêng máy\n{TOK}\n", encoding="utf-8")
        self.assertEqual((ssb_config.token(), ssb_config.token_source()), (TOK, "machine_token.local.txt"))
        with mock.patch.dict(os.environ, {"SSB_MACHINE_TOKEN": tok2}):
            self.assertEqual(ssb_config.token_source(), "env")

    def test_local_token_file_ignored_by_git(self) -> None:
        self.assertIn("*.local.txt", (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())

    def test_check_and_bridge_never_print_token(self) -> None:
        with mock.patch.object(ssb_config, "token", return_value=TOK), \
                mock.patch.object(ssb_config, "token_source", return_value="env"), \
                mock.patch.object(ssb, "get", side_effect=OSError("offline")), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            ssb.main(["check"])
        with mock.patch.object(ssb_config, "token", return_value=TOK), \
                mock.patch.object(ssb_config, "token_source", return_value="env"), \
                mock.patch("sys.stdin", io.StringIO("")), \
                mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            bridge.main()
        for text in (out.getvalue(), err.getvalue()):
            self.assertIn("OK (env)", text)
            self.assertNotIn("ssbm_", text)


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
            ("duties", "VT008"): "/api/v1/f3/roles/VT008/duties",
            ("impact", "VT008"): "/api/v1/f3/roles/VT008/impact",
            ("steps", "QT_TCNS_01"): "/api/v1/f3/steps?f3_id=QT_TCNS_01",
            ("version", "QT_TCNS_01"): "/api/v1/f3/versions/QT_TCNS_01",
            ("functions", ""): "/api/v1/functions",
            ("functions", "DV12"): "/api/v1/functions?owner_unit=DV12",
            ("deferred", ""): "/api/v1/deferred-issues",
            ("flow", ""): "/api/v1/f3/flow",
            ("flow", "QT_TCNS_01"): "/api/v1/f3/flow?f3_id=QT_TCNS_01",
            ("flow-steps", ""): "/api/v1/f3/flow/steps",
            ("flow-steps", "QT_TCNS_01"): "/api/v1/f3/flow/steps?f3_id=QT_TCNS_01",
            ("x-log", ""): "/api/v1/f3/x-log",
            ("x-log", "QT_TCNS_01"): "/api/v1/f3/x-log?f3_id=QT_TCNS_01",
            ("p-sets", ""): "/api/v1/p/sets",
            ("p", "P2026T-001"): "/api/v1/p/items/P2026T-001",
            ("p-role", "VT008"): "/api/v1/p/roles/VT008",
            ("p-report", ""): "/api/v1/p/report",
        }
        for (cmd, val), path in cases.items():
            rc, seen, _ = self._run([cmd, val] if val else [cmd])
            self.assertEqual(rc, 0, cmd)
            self.assertEqual(seen[0].full_url, "http://h:8765" + path, cmd)
            self.assertEqual(seen[0].get_header("Authorization"), f"Bearer {TOK}")
        rc, seen, _ = self._run(["docs", "quy chế", "--limit", "5"])
        self.assertEqual(seen[0].full_url, "http://h:8765/api/v1/docs?q=quy+ch%E1%BA%BF&limit=5")
        rc, seen, _ = self._run(["steps", "QT_TCNS_01", "--step", "B1"])
        self.assertEqual(seen[0].full_url, "http://h:8765/api/v1/f3/steps?f3_id=QT_TCNS_01&step=B1")
        rc, seen, _ = self._run(["steps", "--form", "BM.TCNS.07"])
        self.assertEqual(seen[0].full_url, "http://h:8765/api/v1/f3/steps?form=BM.TCNS.07")
        rc, seen, _ = self._run(["version", "QT_KTĐBCL_01", "--seq", "1", "--flowchart"])
        self.assertEqual(seen[0].full_url,
                         "http://h:8765/api/v1/f3/versions/QT_KT%C4%90BCL_01?seq=1&flowchart=true")
        rc, seen, _ = self._run(["functions", "DV20", "--level", "f2"])
        self.assertEqual(seen[0].full_url, "http://h:8765/api/v1/functions?owner_unit=DV20&level=f2")
        rc, seen, _ = self._run(["p", "P2026T-001", "--build", "2"])
        self.assertEqual(seen[0].full_url, "http://h:8765/api/v1/p/items/P2026T-001?build=2")
        rc, seen, _ = self._run(["p-role", "VT008", "--ky", "2026T", "--build", "1"])
        self.assertEqual(seen[0].full_url, "http://h:8765/api/v1/p/roles/VT008?ky=2026T&build=1")
        rc, seen, _ = self._run(["p-report", "--ky", "2026T"])
        self.assertEqual(seen[0].full_url, "http://h:8765/api/v1/p/report?ky=2026T")
        rc, seen, _ = self._run(["x-log", "--from", "2026-11-01", "--to", "2026-11-30", "--e", "E2"])
        self.assertEqual(seen[0].full_url, "http://h:8765/api/v1/f3/x-log?from=2026-11-01&to=2026-11-30&e=E2")
        rc, seen, _ = self._run(["x-core", "QT_KTĐBCL_06", "--hash", "ab12"])
        self.assertEqual(seen[0].full_url, "http://h:8765/api/v1/f3/x-core?f3_id=QT_KT%C4%90BCL_06&content_hash=ab12")
        rc, seen, _ = self._run(["f3b-signals", "--from", "2026-11-01", "--to", "2026-11-30"])
        self.assertEqual(seen[0].full_url, "http://h:8765/api/v1/f3b/signals?from=2026-11-01&to=2026-11-30")

    def test_x_log_gom_du_trang(self) -> None:
        pages = iter([
            b'{"count": 2, "total": 3, "offset": 0, "truncated": true, "next_offset": 2, "rows": [{"e": "E0"}, {"e": "E2"}]}',
            b'{"count": 1, "total": 3, "offset": 2, "truncated": false, "next_offset": null, "rows": [{"e": "E3"}]}',
        ])
        seen: list = []
        buf = io.StringIO()
        with mock.patch.object(ssb_config, "token", return_value=TOK), mock.patch.object(ssb_config, "host", return_value="http://h:8765"), \
             mock.patch("urllib.request.urlopen", side_effect=lambda req, timeout=None: (seen.append(req), FakeResp(next(pages)))[1]), \
             mock.patch("sys.stdout", buf):
            rc = ssb.main(["x-log", "--e", "E2"])
        self.assertEqual(rc, 0)
        self.assertEqual([r.full_url for r in seen], ["http://h:8765/api/v1/f3/x-log?e=E2",
                                                      "http://h:8765/api/v1/f3/x-log?e=E2&offset=2"])
        data = json.loads(buf.getvalue())
        self.assertEqual((data["count"], data["total"], data["truncated"], data["next_offset"]), (3, 3, False, None))
        self.assertEqual([r["e"] for r in data["rows"]], ["E0", "E2", "E3"])

    def test_out_writes_utf8_file(self) -> None:
        out = ROOT / "tests" / "_out_flow_steps.json"
        try:
            with mock.patch("sys.stderr", io.StringIO()):
                rc, _, printed = self._run(["flow-steps", "--out", str(out)], body='{"items": [{"title": "Tuyển dụng"}]}'.encode("utf-8"))
            self.assertEqual((rc, printed), (0, ""))
            self.assertEqual(json.loads(out.read_text(encoding="utf-8")), {"items": [{"title": "Tuyển dụng"}]})
        finally:
            out.unlink(missing_ok=True)

    def test_missing_value(self) -> None:
        with mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(ssb.main(["role"]), 2)
            self.assertEqual(ssb.main(["f3b-signals"]), 2)
            self.assertEqual(ssb.main(["duties"]), 2)
            self.assertEqual(ssb.main(["steps"]), 2)
            self.assertEqual(ssb.main(["p"]), 2)
            self.assertEqual(ssb.main(["p-role"]), 2)
            self.assertEqual(ssb.main(["version"]), 2)
            self.assertEqual(ssb.main(["x-core", "QT_TCNS_01"]), 2)
            self.assertEqual(ssb.main(["x-core", "--hash", "ab12"]), 2)


class TestConfigFiles(unittest.TestCase):
    def test_mcp_json_no_secret_points_to_bridge(self) -> None:
        for rel in (".cursor/mcp.json", ".mcp.json"):
            cfg = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            self.assertEqual(cfg["mcpServers"]["ssb"]["args"], ["ssb_mcp_bridge.py"], rel)
            self.assertNotIn("ssbm_", json.dumps(cfg))
        self.assertTrue((ROOT / ".claude/skills/ssb/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
