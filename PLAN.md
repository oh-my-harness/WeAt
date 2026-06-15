# WeAt Web — 自研 Matrix 聊天客户端（内嵌 AI 副驾驶）

## 为什么

现有 WeAt 依赖用户安装 Element 客户端和 Matrix 账号，团队普遍不愿意用。
核心问题是安装门槛太高，大家习惯打开浏览器就能聊天。

保持 Matrix 协议层不变（复用 Synapse 服务器），自研一个轻量 Web 聊天客户端，
把 AI 起草能力内嵌进去，手机+桌面都能用。

## 技术栈

```
前端: React + TypeScript + Tailwind CSS
后端: Python + FastAPI + aiohttp (Matrix REST API)
AI:   Rust sidecar (基于 llm-harness-core + llm-harness-runtime)
```

## 架构

```
┌──────────────────────────────────────────────────┐
│ Web 前端 (React SPA)                              │
│ 登录 / 房间列表 / 聊天 / AI 起草面板              │
└────────▲────────────▲─────────────────────────────┘
         │ WebSocket  │ HTTP/SSE
         ▼            ▼
┌──────────────────────────────────────────────────┐
│ Python 后端 (FastAPI)                             │
│ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │
│ │ Matrix sync  │ │ WebSocket    │ │ Agent      │ │
│ │ 消息推送     │ │ 消息路由     │ │ Bridge     │ │
│ │ (aiohttp)    │ │              │ │ (调 Rust)  │ │
│ └──────────────┘ └──────────────┘ └─────┬──────┘ │
└──────────────────────────────────────────────────┘
                                         │ subprocess
                                         ▼
┌──────────────────────────────────────────────────┐
│ Rust Agent Sidecar (llm-harness-core)            │
│ LLM 调用 / 工具调用 / Agent 循环                  │
│ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│ │ LLM Adpt │ │ Vault    │ │ MCP Client (读   │  │
│ │ (多provider) │工具(Read│ │ 群聊历史)        │  │
│ │            │ │ /Grep)  │ │                  │  │
│ └──────────┘ └──────────┘ └──────────────────┘  │
└──────────────────────────────────────────────────┘
```

## 分阶段实现

### Phase 1: MVP Web 客户端（纯聊天，不含 AI）

目标：能登录、看到群聊列表、收发消息，手机可用。

**后端 Python 模块** (新增 `weat_web/backend/`)：
- `app.py` — FastAPI + WebSocket 端点
  - `POST /api/login` — Matrix 登录（密码或 token）
  - `GET /api/rooms` — 已加入房间列表
  - `GET /api/rooms/{id}/messages?limit=N` — 历史消息
  - `POST /api/rooms/{id}/messages` — 发送消息
  - `WS /ws` — 实时消息推送
- `matrix_sync.py` — Matrix sync 循环
  - aiohttp 长轮询 Matrix /sync
  - 推送新消息到 WebSocket 连接

**前端 React 模块** (新增 `weat_web/frontend/`)：
- `LoginPage.tsx` — 登录页（服务器 + 用户名 + 密码/token）
- `RoomList.tsx` — 房间列表（侧栏）
- `ChatPage.tsx` — 聊天页面（消息列表 + 输入框）
- `websocket.ts` — WebSocket 客户端封装
- 移动端适配 (Tailwind CSS 响应式)

**依赖**：
- Python: `fastapi`, `uvicorn`, `websockets`, `aiohttp`
- JS: `react`, `react-router`, `tailwindcss`, `vite`

### Phase 2: Rust Agent Sidecar

目标：AI agent 可独立运行，Python 通过 HTTP 调它。

**Rust 项目** (新增 `agent-sidecar/`)：
- 基于 `llm-harness-core` 的 `Agent` 封装
- 自实现工具: `read_file`, `grep`, `list_dir` (vault 访问)
- MCP 客户端: 调现有 `matrix_mcp/server.py` 读群聊
- HTTP API: `POST /agent/run` → SSE 流式返回
- 可执行二进制，Python 子进程启动

### Phase 3: AI 起草集成

目标：聊天界面里 AI 起草直达。

- 前端 `AIAssistant.tsx` — 草稿面板
- 消息旁"AI 起草"按钮 → 弹出草稿区
- 草稿可编辑、可发修改指令多轮调整
- 满意度 → "以我身份发送"

### Phase 4: Vault 集成

目标：AI 起草时能查 vault 笔记。

- Rust sidecar 添加 vault 文件工具
- 复用 obsidian-second-brain 规范
- 前端 vault 搜索（可选）

## 关键文件

```
weat_web/
  backend/
    __init__.py
    app.py              — FastAPI + WebSocket
    matrix_sync.py      — Matrix sync 循环
    agent_bridge.py     — Rust sidecar 客户端
  frontend/
    package.json
    index.html
    src/
      main.tsx          — 入口
      App.tsx           — 路由
      LoginPage.tsx     — 登录
      RoomList.tsx      — 房间列表
      ChatPage.tsx      — 聊天页面
      AIAssistant.tsx   — AI 草稿面板
      websocket.ts      — WS 客户端

agent-sidecar/
  Cargo.toml
  src/
    main.rs             — HTTP 服务器
    agent.rs            — Agent 封装
    tools.rs            — 工具实现
```

## 验证

1. 启动本地 Synapse
2. `uv run weat-web` 启动后端
3. 浏览器打开前端
4. 用已有 Matrix 账号登录
5. ✅ 看到房间列表
6. ✅ 收发消息
7. Phase 3: AI 起草 → 编辑 → 发送
8. Phase 4: AI 引用 vault 笔记
