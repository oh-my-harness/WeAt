# WeAt

小团队 AI 副驾驶：在 Matrix 群聊里，私信你自己的 AI bot，让它读群聊历史 + 查你的 Obsidian 知识库，起草回复，你审过再发——以你的身份。AI 帮你想，你为每个字负责。

---

## 能用吗？

**能用。** MVP 已完成并经端到端测试验证：

- `/draft` → bot 调 opencode 读取真实 Matrix 群聊 → DeepSeek 生成草稿 → 私信回给你
- 多轮改稿（直接在私聊里说要怎么改）
- `/send` → 以你的 Matrix 账号身份发到目标频道（群里看不到 AI 痕迹）
- `/digest` → 生成群聊纪要草稿 → `/save` 写入 Obsidian vault

已知限制：DeepSeek 等思维链模型有时会把推理步骤混入草稿正文，需要手动删除或用提示词约束。

---

## 前置条件

| 依赖 | 说明 |
|---|---|
| Python 3.12+ + [uv](https://docs.astral.sh/uv/) | 包管理 |
| [opencode](https://opencode.ai/) ≥ 1.15 | Agent 运行时 |
| LLM API Key | DeepSeek / Anthropic / 任意 opencode 支持的模型 |
| Matrix 账号 × 2 | 一个你自己的、一个 bot 专用的 |
| Obsidian vault | 任意一个 markdown 文件夹即可 |

---

## 安装

```bash
git clone https://github.com/hhllhhyyds/weat
cd weat
uv sync
```

---

## 配置

### 第一步：准备两个 Matrix 账号

你需要：
- **用户账号**（如 `@alice:matrix.org`）：你平时发消息用的账号
- **Bot 账号**（如 `@alicebot:matrix.org`）：专门接收你私信、代表你运行 AI 的账号

用任意 Matrix 服务器注册（推荐 [matrix.org](https://app.element.io/#/register)）。

**获取 access token（两个账号都要）：**

```bash
# 替换成你的服务器、用户名、密码
curl -s -X POST https://matrix.org/_matrix/client/v3/login \
  -H "Content-Type: application/json" \
  -d '{"type":"m.login.password","user":"alice","password":"你的密码"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['access_token'])"
```

对两个账号各执行一次，记录两个 token。

### 第二步：配置 opencode LLM

```bash
opencode providers login deepseek
# 或
opencode providers login anthropic
```

### 第三步：写配置文件

```bash
cp weat.json.example weat.json
```

编辑 `weat.json`：

```json
{
  "homeserver": "https://matrix.org",
  "user_id": "@alice:matrix.org",
  "access_token": "syt_alice_实际token",
  "bot_user_id": "@alicebot:matrix.org",
  "bot_access_token": "syt_bot_实际token",
  "vault_path": "/Users/alice/Documents/Notes",
  "db_path": "/Users/alice/.local/share/weat/weat.db",
  "opencode_model": "deepseek/deepseek-chat",
  "session_timeout_minutes": 30
}
```

| 字段 | 说明 |
|---|---|
| `homeserver` | Matrix 服务器地址 |
| `user_id` | 你的账号 Matrix ID |
| `access_token` | 你的账号 token |
| `bot_user_id` | Bot 账号 Matrix ID |
| `bot_access_token` | Bot 账号 token |
| `vault_path` | Obsidian vault（或任意 markdown 文件夹）绝对路径 |
| `db_path` | SQLite 数据库路径（自动创建） |
| `opencode_model` | opencode 模型 ID，格式见 `opencode models` |

---

## 启动

```bash
uv run weat-bridge --config weat.json
```

日志正常后，去 Element（或任意 Matrix 客户端）找你的 bot 账号，开一个私聊。

---

## 使用

在和 bot 的私聊里发消息：

```
/help                                    — 查看所有命令
/draft #开发组 解释上周那个 P1 是怎么修的   — 起草群聊回复
/digest #开发组 本周                      — 生成本周群聊纪要
```

bot 返回草稿后，直接说要怎么改：

```
太长了，缩到三句
换一个不那么正式的语气
再加上 Redis 连接池配置的具体数值
```

满意后：

```
/send    — 以你的身份发到目标频道
/save    — 保存纪要到 vault（仅 /digest 生成的内容）
/retry   — 重新生成
/cancel  — 放弃当前草稿
```

群里其他人看到的是你发的消息，没有 AI 标识。

---

## 技术架构

```
你的 Element ──私聊──► WeAt Bridge (Python)
                              │
                        检测到命令
                              │
                        opencode run ──► MCP ──► Matrix 群聊历史
                              │               └─► Obsidian vault (直接读文件)
                              │
                        DeepSeek / Claude
                              │
                        草稿回到私聊
                              │
                        /send ──► 你的 Matrix token 发送
                                        │
                              群里所有人看到你发的消息
```

自研代码约 900 行，其余全部复用开源：
- [matrix-nio](https://github.com/poljar/matrix-nio) — Matrix Python SDK
- [opencode](https://opencode.ai/) — Agent 运行时（自带文件读写工具）
- [obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain) — vault 操作 skill（33 个命令 + AI-first 规范）
- [mcp](https://github.com/modelcontextprotocol/python-sdk) — MCP stdio server

---

## 项目结构

```
src/weat/
  main.py                      — 入口 (weat-bridge)
  config/
    settings.py                — Config dataclass
    wizard.py                  — 首次配置向导 (weat-setup，可选)
  matrix_mcp/
    server.py                  — Matrix MCP Server
                                 (list_rooms / get_recent_messages / search_messages)
  orchestrator/
    orchestrator.py            — 私聊对话状态机 + 命令路由
    session_store.py           — SQLite 草稿会话存储
    opencode_runner.py         — opencode subprocess 封装
  vault/
    setup.py                   — obsidian-second-brain 集成安装器
```

---

## 文档

- [DESIGN.md](DESIGN.md) — 完整设计文档：13 条锁定决策、架构、风险分析
- [ROADMAP.md](ROADMAP.md) — 开发路线图
