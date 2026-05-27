# S3 — opencode + MCP 集成

## 目标

验证 opencode 能加载自定义 MCP server，agent 能调用其中的工具。

## 通过标准

- [x] MCP server（`mcp_server_spike.py`）以 stdio transport 运行
- [x] opencode 在 `opencode.jsonc` 里识别 MCP server 配置
- [x] agent 调用 `get_time()` 工具，结果出现在最终回答里

## 关键发现

**opencode.jsonc MCP 配置格式**（command 必须是数组，且需要 `enabled: true`）：
```json
{
  "mcp": {
    "server-name": {
      "type": "local",
      "enabled": true,
      "command": ["uv", "run", "--project", "/path/to/project", "python", "server.py"]
    }
  }
}
```

- `type: "local"` = stdio transport（最简单，Matrix MCP Server 就用这个）
- opencode.jsonc 放在 working directory 即可被自动加载（项目级配置）
- `--dir` 标志指定工作目录，会影响 opencode.jsonc 的搜索路径

## 版本

opencode 1.15.11 / mcp Python SDK 1.27.1
