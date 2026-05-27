# S2 — opencode 非交互调用

## 目标

验证 opencode 可被 subprocess 拉起、接受 prompt、输出可解析，多轮上下文通过 `--session` 续接。

## 通过标准

- [x] `opencode run --format json "message"` 返回 JSON 事件流
- [x] 事件类型：`step_start` / `text` / `step_finish`；文本在 `event.part.text`
- [x] `--session <id>` 续接后 agent 能记住上一轮内容（多轮微调核心需求）
- [x] `--dangerously-skip-permissions` 让 subprocess 无需交互确认

## 关键发现

- **JSON 事件格式**（非 `message.parts` 数组，直接是顶级 `type: "text"` 事件）：
  ```json
  {"type":"text","part":{"text":"Redis 是...","type":"text",...},...}
  ```
- **session_id** 从任意事件的 `sessionID` 字段提取
- **多轮**：下一轮 `--session <id>` 即可续接，无需额外操作
- **cost** 信息在 `step_finish` 事件中（可用于 token 监控）

## 版本

opencode 1.15.11
