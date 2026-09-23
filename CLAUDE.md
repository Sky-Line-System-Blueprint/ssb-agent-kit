# SSB Agent Kit — Claude Code

Repo này nối Claude Code với **SSB** qua MCP server `ssb` (`.mcp.json` → `ssb_mcp_bridge.py`), chỉ đọc.

- Skill: `.claude/skills/ssb/SKILL.md` — dùng khi hỏi về chức danh (VT###), đơn vị (DV###), văn bản DOC, biểu mẫu BM, trạng thái hệ thống.
- Không có MCP → `python ssb.py <lệnh>` (xem `python ssb.py -h`).
- Mã phải lấy từ tool, không đoán. Ambiguous → hỏi người dùng. Trả lời bằng tiếng Việt, ghi mã kèm tên.
- Lỗi token → `machine_token.txt` + `python ssb.py check`.
