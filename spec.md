# WeAt Web — 自研矩阵聊天客户端

## 1. 背景

现有的 WeAt MVP 是一个 CLI-Python 应用，需要用户安装 Python/opencode/Element 等本地工具。为了让使用门槛降低到"打开浏览器就能用"，需要提供一个纯 Web 的聊天客户端。

同时，团队需要在聊天中集成 AI 副驾驶能力：起草回复、总结对话保存到个人知识库、从知识库检索信息——全部在浏览器端运行，不经过服务器。

## 2. 目标 & 非目标

### 目标

- 用户 0 安装——只需要浏览器
- 登录 → 房间列表 → 收发消息（Phase 1 纯聊天）
- 每条消息旁 "AI 起草" 按钮（按消息上下文的回复）
- 聊天框里斜杠命令（如 `/summarize`）触发 AI 操作
- 基于房间聊天历史手动触发总结/保存到知识库
- 从本地知识库搜索信息作为 AI 上下文
- 手机可用（响应式设计）
- 后端只做消息代理，不做 AI，不碰 LLM Key

### 非目标

- E2EE（MVP 用明文房间）
- Matrix Federation（单服务器 = 单团队）
- 自动 AI 总结（只做手动触发）
- 服务端知识库（知识存在浏览器本地）
- 多人实时协作编辑

## 3. 需求

### 3.1 功能性需求

| # | 需求 | 优先级 | 阶段 |
|---|------|--------|------|
| F1 | 用户名+密码登录 | P0 | Phase 1 |
| F2 | 已加入的房间列表（侧栏/底部导航） | P0 | Phase 1 |
| F3 | 房间消息流展示 | P0 | Phase 1 |
| F4 | 发送消息 | P0 | Phase 1 |
| F5 | WebSocket 实时新消息推送 | P0 | Phase 1 |
| F6 | 消息支持简单 Markdown 渲染 | P0 | Phase 1 |
| F7 | 手机响应式适配 | P0 | Phase 1 |
| F8 | 每条消息旁 "AI 起草" 按钮 | P1 | Phase 2 |
| F9 | 浏览器端 Agent 循环（LLM + tool calling） | P1 | Phase 2 |
| F10 | 斜杠命令触发 AI（/summarize 等） | P1 | Phase 3 |
| F11 | AI 总结对话 → 保存到本地 File API | P1 | Phase 3 |
| F12 | 从本地 vault 搜索.md 文件作为 AI 上下文 | P1 | Phase 3 |
| F13 | 草稿编辑面板（编辑、修改指令、一键发送） | P1 | Phase 3 |
| F14 | 管理 Tuwunel 用户的 admin CLI | P1 | Phase 1 |

### 3.2 非功能性需求

| # | 需求 | 说明 |
|---|------|------|
| NF1 | 零安装 | 用户只需要浏览器 |
| NF2 | LLM Key 不出服务器 | API Key 仅存在浏览器 sessionStorage/IndexedDB |
| NF3 | AI 以用户身份发送 | 群聊其他人看不到 AI 痕迹 |
| NF4 | 消息发送延迟 < 1s（乐观更新） | POST 后本地立即显示，不等 sync |
| NF5 | 后端不持久化消息 | 消息全走 Tuwunel 存储，后端只做代理 |
| NF6 | 后端无状态 | 除用户 token 缓存外，不存会话状态 |

## 4. 系统设计

### 4.1 方案概览

#### 整体思路

用户浏览器（React SPA）通过 WebSocket / HTTP 与 FastAPI 后端通信，后端作为 Tuwunel（Rust Matrix 服务端）的 REST API 代理，不做 AI、不存储消息。AI Agent 全程运行在浏览器端，直接调 LLM API，通过后端 API 获取群聊历史，通过浏览器 File API 操作本地知识库。

#### 模块划分

**前端（React SPA）**：

| 模块 | 职责 |
|------|------|
| Auth | 登录页、token 管理（sessionStorage）、自动重连 |
| RoomList | 已加入房间列表、响应式导航（桌面侧栏/手机底部 Tab） |
| Chat | 消息流渲染（Markdown）、输入框、发送消息、乐观更新 |
| WebSocket | WS 长连接维护、自动重连、事件分发 |
| API Client | 后端 HTTP 客户端封装 |
| Agent | 浏览器端 LLM 工具循环、意图解析、多轮对话调度 |
| Tools | 起草回复、总结保存、知识库搜索等 Agent 工具 |
| DraftPanel | 草稿编辑面板（编辑、修改指令、一键发送） |

**后端（FastAPI）**：

| 模块 | 职责 |
|------|------|
| Auth API | `POST /api/login` — 用户名/密码 → Tuwunel 验证 → access_token |
| Room API | `GET /api/rooms` — 已加入房间列表 |
| Message API | `GET /api/rooms/{id}/messages` — 历史消息；`POST /api/rooms/{id}/messages` — 发送消息 |
| WebSocket Handler | `WS /ws` — 管理每个用户的连接、验证 token、收发事件 |
| Matrix API 封装 | `matrix_api.py` — Tuwunel 的 Matrix Client-Server REST API 封装 |
| Sync Loop | 每用户独立后台任务：long-polling Tuwunel `/sync` → 通过 WS 推送给前端 |
| Admin CLI | `weat-admin add-user / list-users / reset-password` |

#### 依赖方向

```
前端 Auth / RoomList / Chat → API Client / WebSocket 模块
前端 Agent / Tools         → API Client / WebSocket 模块

后端 Auth API / Room API / Message API     → Matrix API 封装
后端 WebSocket Handler / Sync Loop          → Matrix API 封装
后端 Matrix API 封装                        → HTTP → Tuwunel (Rust, Docker)
```

#### 数据流

**发送消息（乐观更新）**：
```
Alice 输入消息 → Chat 模块
  → 乐观更新: 插入消息到本地列表（临时 ID）
  → POST /api/rooms/{id}/messages
  → 后端 → Tuwunel REST: POST /_matrix/client/v3/rooms/{id}/send
  → 成功返回 event_id → 前端替换临时 ID
  → Sync Loop 轮询到消息 → 通过 WS 推送给房间内其他用户
```

**WebSocket + Sync 循环**：
```
Alice 打开页面 → WS /ws?token=xxx 连接建立
  → 后端创建 Alice 的 sync 后台任务
  → 循环:
      1. aiohttp GET Tuwunel /sync?since={next_batch}&timeout=30000
      2. 有事件 → 通过 WS 推送给 Alice
      3. 继续下一轮 sync
  → Alice 关闭页面 → WS 断开 → 取消 sync 任务
```

**AI 起草回复**：
```
Alice 点击消息旁的 "AI 起草"
  → 浏览器 Agent 启动
  → Tool: get_room_history → GET /api/rooms/{id}/messages?limit=50
  → Agent 构建 prompt（消息上下文 + 用户指令）
  → fetch LLM API（Key 在浏览器 sessionStorage）
  → 返回草稿文本 → 显示 DraftPanel
  → Alice 编辑 / 修改指令 → 满意 → POST /api/rooms/{id}/messages（以 Alice 身份发送）
```

**AI 总结保存到知识库**：
```
Alice 输入 "/summarize" 或点击 "总结"
  → 浏览器 Agent 取最近 N 条消息
  → 调 LLM 生成摘要
  → 显示摘要预览，Alice 确认
  → Agent 通过 File API 写为本地 .md 文件
```

**AI 从知识库搜索**：
```
Alice 输入 "@AI 查一下上次讨论的架构设计"
  → Agent 解析意图
  → Tool: search_vault("架构设计") → 浏览器 File API 遍历本地 .md 文件
  → 匹配内容 → 作为 context 加入 LLM 调用
  → 生成回答
```

#### 关键 Trade-off

| 决策 | 权衡 |
|------|------|
| 每用户独立 sync 循环 | 简单但每个在线用户都产生 Tuwunel sync 请求 |
| 乐观更新 | 即时 UX 但需要处理 event_id 替换和去重 |
| LLM Key 在浏览器 | 安全（不经过服务器）但浏览器端无法用流式响应以外的复杂 LLM 框架 |
| 知识库在浏览器本地 | 用户隐私好但 Agent 只能访问用户选择的目录 |
| 后端无状态（不存消息） | 运维简单但每次 sync 都需要 Tuwunel 作为正常 Matrix 客户端 |

### 4.2 组件设计

N/A - 当前为 Phase 1 纯聊天阶段，组件设计将在编码过程中确定。

### 4.3 核心逻辑

N/A - 核心逻辑将在编码过程中实现。

## 5. 接口设计

### 5.1 后端 API

| 方法 | 路径 | 说明 | Headers |
|------|------|------|---------|
| POST | `/api/login` | 登录获取 access_token | - |
| GET | `/api/rooms` | 已加入房间列表 | `Authorization: Bearer <token>` |
| GET | `/api/rooms/{id}/messages?limit=N` | 历史消息 | 同上 |
| POST | `/api/rooms/{id}/messages` | 发送消息 | 同上 |
| WS | `/ws?token=<token>` | WebSocket 实时推送 | Query param |

### 5.2 Matrix API 封装

`matrix_api.py` 封装 Tuwunel 的 Matrix Client-Server API：

- `login(username, password) → access_token, user_id`
- `get_rooms(token) → room[]`
- `get_messages(room_id, token, limit=50) → message[]`
- `send_message(room_id, token, body) → event_id`
- `sync(token, since=None, timeout=30000) → sync_response`

## 6. 文件结构

```
/
├── PLAN.md
├── spec.md
├── docker-compose.yml        — Tuwunel (Matrix server) Docker 配置
│
├── backend/
│   ├── main.py              — FastAPI 入口 + uvicorn
│   ├── matrix_api.py        — Tuwunel Matrix Client-Server REST API 封装
│   ├── sync_loop.py         — Matrix sync 后台循环
│   ├── admin_cli.py         — weat-admin 命令行（调用 Matrix API 管理用户）
│   └── requirements.txt
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── tailwind.config.js
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── LoginPage.tsx
│       ├── RoomList.tsx
│       ├── ChatPage.tsx
│       ├── AIAssistant.tsx   — AI 起草面板
│       ├── agent.ts          — 浏览器端 Agent 循环
│       ├── tools/            — Agent 工具
│       ├── websocket.ts
│       └── api.ts            — 后端 HTTP 客户端
```

## 7. 分阶段实现

### Phase 1: MVP Web 客户端（纯聊天）

目标：登录 → 房间列表 → 收发消息，手机可用。

**后端**：
- FastAPI + uvicorn
- 5 个 HTTP 端点 + 1 个 WS 端点
- Tuwunel Matrix REST API 封装（`matrix_api.py`）
- 每用户独立 sync 循环
- admin_cli.py（Tuwunel 用户管理）
- 乐观更新的消息发送

**前端**：
- 登录页（用户名+密码）
- 房间列表（响应式：桌面侧栏/手机底部导航）
- 聊天页面（消息列表 + 输入框 + Markdown 渲染）
- WebSocket 连接 + 自动重连
- 乐观更新 + event_id 替换

**验证**：
1. `docker compose up matrix -d` — 启动 Tuwunel
2. `weat-admin add-user alice pwd123` — 创建测试用户
3. `uv run uvicorn backend.main:app --reload` — 启动后端
4. `cd frontend && npm run dev` — 启动前端
5. 浏览器打开 http://localhost:5173 → alice 登录 → 看到房间列表
6. 选择房间 → 发消息 → 刷新能看到历史
7. 手机浏览器同样地址 → 能用

### Phase 2: 浏览器端 AI Agent

目标：浏览器端 JS agent，可调 LLM + 起草回复。

- `agent.ts` — Agent 循环
- `tools/get_room_history.ts` — 取群聊历史
- `tools/write_reply.ts` — 生成草稿
- DraftPanel 组件

### Phase 3: AI 起草集成 + 知识库

目标：完整 AI 起草流程，本地知识库支持。

- 斜杠命令处理（/summarize 等）
- AI 总结 → 保存到本地 File API
- 知识库搜索工具
- 草稿编辑面板（修改指令、一键发送）

### Phase 4: 部署

- docker-compose.yml（Tuwunel + WeAt + Nginx）
- Nginx HTTPS（Let's Encrypt）/ HTTP 开发模式
- 安装脚本
