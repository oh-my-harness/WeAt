# WeAt

小团队 AI 副驾驶：在 Matrix 群聊里，私信你自己的 AI bot，让它读群聊 + 查你的 Obsidian 知识库、起草回复，你审过就发——以你的身份。AI 帮你想，你为每个字负责。

## 文档

- **[DESIGN.md](DESIGN.md)** — 完整设计文档：13 条锁定决策、架构、组件分工、风险
- **[ROADMAP.md](ROADMAP.md)** — 开发路线：Phase 0（开源依赖 spike）→ Phase 1（5 个 Sprint MVP）

## 当前状态

**MVP 完成** ✅

| 组件 | 状态 |
|---|---|
| Matrix MCP Server | ✅ `src/weat/matrix_mcp/server.py` |
| 编排器 + 私聊状态机 | ✅ `src/weat/orchestrator/orchestrator.py` |
| Session Store (SQLite) | ✅ `src/weat/orchestrator/session_store.py` |
| opencode Runner | ✅ `src/weat/orchestrator/opencode_runner.py` |
| obsidian-second-brain 集成 | ✅ `src/weat/vault/setup.py` |
| 首次配置向导 (FastAPI) | ✅ `src/weat/config/wizard.py` |
| Docker Compose | ✅ `docker-compose.yml` |
| Phase 0 Spikes | ✅ S2/S3/S4/S5 通过；S1 待 Matrix 账号验证 D7 |

## 快速上手

### 前置条件

- Matrix 账号两个：一个作为你的账号（发消息），一个作为 bot（接收私信）
- 两个账号都在同一个 Matrix 服务器（或互联邦服务器）
- opencode 已安装并配置了 LLM API key
- Python 3.12+ + uv

### 安装

```bash
git clone https://github.com/yourname/weat
cd weat
uv sync
```

### 首次配置（交互式向导）

```bash
uv run weat-setup
# 浏览器自动打开 http://localhost:8080
# 填写两个 Matrix 账号和 vault 路径
```

或手动复制配置文件：

```bash
cp weat.json.example weat.json
# 编辑 weat.json，填入真实 token 和路径
```

### 启动

```bash
uv run weat-bridge
```

或用 Docker：

```bash
cp weat.json.example weat.json  # 填入真实值
export VAULT_PATH=/path/to/your/vault
docker-compose up -d
```

### 使用

在 Element（或任意 Matrix 客户端）打开你和 bot 的私聊，发送：

```
/help                          — 查看所有命令
/draft #开发组 解释上周的 P1 修复  — 起草回复
/digest #开发组 本周             — 生成本周纪要
/send                          — 以你的身份发到频道
/save                          — 保存纪要到 vault
```

非命令消息默认作为"改稿指令"（"太长了"/"换种语气"/"加上 X"）。

## 技术栈

- 聊天底座：[Matrix](https://matrix.org) + Synapse + Element
- Agent runtime：[opencode](https://github.com/sst/opencode) 1.15+
- Matrix Python SDK：[matrix-nio](https://github.com/poljar/matrix-nio)
- 知识库 skill：[obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain)（MIT，33 个 vault 命令）
- 语言：Python 3.12（matrix-nio + 官方 mcp SDK + FastAPI 配置向导）
- 依赖管理：uv

## 项目结构

```
src/weat/
  main.py                      — 主入口 (weat-bridge)
  config/
    settings.py                — Config dataclass
    wizard.py                  — 首次配置向导 (weat-setup)
  matrix_mcp/
    server.py                  — Matrix MCP Server (list_rooms / get_recent_messages / search_messages)
  orchestrator/
    orchestrator.py            — 私聊对话状态机 + 命令路由
    session_store.py           — SQLite 草稿会话存储
    opencode_runner.py         — opencode subprocess 封装
  vault/
    setup.py                   — obsidian-second-brain 集成安装器
spikes/
  S1-matrix/                   — matrix-nio 验证脚本（需要 Matrix 账号）
  S2-opencode/                 — opencode 非交互调用验证 ✅
  S3-mcp/                      — MCP hello world ✅
  S4-obsidian/                 — obsidian-second-brain adapter ✅
  S5-e2e/                      — 端到端骨架烟测 ✅
```

## 一句话价值主张

> 群聊里有问题想答？私信你自己的 AI，让它读群聊、查你的笔记、起草回复，你审过就发。AI 帮你想，但你为每个字负责。
