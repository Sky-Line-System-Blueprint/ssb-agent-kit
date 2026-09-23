# SSB Agent Kit

Cho **agent AI** (Cursor, Claude Code) hỏi thẳng **SSB** — cơ cấu tổ chức (đơn vị DV###, chức danh VT###, cấp bậc), sổ văn bản DOC, biểu mẫu BM, trạng thái hệ thống — mà **không cần f3_builder**. Chỉ đọc. Chỉ dùng Python chuẩn (≥ 3.10), không cài thêm gì.

## Cài (3 bước, một lần)

1. `git clone https://github.com/Sky-Line-System-Blueprint/ssb-agent-kit.git` (repo private — xin quyền read).
2. Xin sysadmin **token kênh máy**: SSB Governance `http://192.168.10.182:8765` → tab **Kênh máy** → «Token kênh máy — theo người» → bấm **Copy**. Mở `machine_token.txt`, dán vào **dòng trống cuối file**, lưu. Kiểm:
   ```
   python ssb.py check
   ```
   Phải thấy `quyền : OK — đọc được bằng token`.
3. Mở thư mục repo bằng agent:
   - **Cursor**: File → Open Folder → thư mục này → **Settings → MCP**: server `ssb` xanh (đọc `.cursor/mcp.json`). Khởi động lại Cursor nếu vừa dán token.
   - **Claude Code**: `claude` trong thư mục này → chấp nhận server `ssb` từ `.mcp.json` (hoặc `claude mcp add ssb -- python ssb_mcp_bridge.py`).

Xong — hỏi agent tự nhiên: «mã chức danh giám đốc ban tổ chức nhân sự?», «có quy chế lương không, còn hiệu lực không?». Agent làm theo skill `.claude/skills/ssb/SKILL.md` (Cursor: rule `.cursor/rules/ssb.mdc`).

## Thành phần

| File | Vai trò |
|---|---|
| `machine_token.txt` | Token của bạn (dán 1 lần; **không commit** sau khi dán) |
| `host.txt` | Địa chỉ SSB (mặc định `http://192.168.10.182:8765`; env `SSB_URL` ghi đè) |
| `ssb_mcp_bridge.py` | Cầu nối MCP stdio → `<host>/mcp` kèm token — Cursor/Claude Code tự khởi động |
| `.cursor/mcp.json`, `.mcp.json` | Khai báo MCP server `ssb` cho Cursor / Claude Code (không chứa bí mật) |
| `ssb.py` | CLI REST (`/api/v1/*`) — cho người hoặc agent chưa bật MCP |
| `.claude/skills/ssb/SKILL.md`, `.cursor/rules/ssb.mdc`, `CLAUDE.md` | Hướng dẫn agent dùng đúng tool |

## CLI nhanh

```
python ssb.py role  "Giám đốc Ban Tổ chức nhân sự"   # → VT###
python ssb.py owner "Ban Tổ chức - Nhân sự"          # → DV### + trưởng ban
python ssb.py combo "GVBM"                           # → nhãn gộp RACI
python ssb.py docs  "quy chế"                        # tìm văn bản
python ssb.py doc   DOC.TCNS.01                      # một văn bản đủ trường
python ssb.py forms "phiếu"                          # tìm biểu mẫu
python ssb.py status                                 # tình trạng hệ thống
python ssb.py get /api/v1                            # danh sách mọi đường REST
```

## Dùng chung f3_builder?

Không cần. Nếu máy đã có f3_builder thì agent trong f3_builder đã có sẵn MCP `ssb` (cùng cơ chế). Kit này dành cho người **không** soạn quy trình F3 nhưng cần agent tra tổ chức / văn bản.

## Sự cố

| Triệu chứng | Xử lý |
|---|---|
| `python ssb.py check` báo `chưa có token` / `sai định dạng` | Dán lại bằng nút **Copy** (một dòng, `ssbm_` + 40 ký tự, không thêm gì) |
| `HTTP 403` | Token sai/thu hồi/đang ngủ (90 ngày không dùng) → báo sysadmin (tab Kênh máy: Kích hoạt lại hoặc cấp mới) |
| `Không kết nối được SSB` | Máy chưa vào mạng công ty / Tailscale; kiểm `host.txt` |
| Cursor: server `ssb` đỏ | Mở đúng thư mục repo làm workspace (không phải thư mục cha). Còn đỏ → sửa `args` trong `.cursor/mcp.json` thành đường dẫn tuyệt đối tới `ssb_mcp_bridge.py` |
| `python` không chạy | Cài Python ≥ 3.10; Windows có thể thay `python` bằng `py` trong `.cursor/mcp.json` |

Tài liệu API đầy đủ (máy chủ SSB): `docs/API.md` trong repo SSB. Thiết kế: ADR-069.
