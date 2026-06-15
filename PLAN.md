# WeAt Web — 自研矩阵聊天客户端

## 一句话

**小团队沟通 + AI 副驾驶，打开浏览器就能用，无需安装任何东西。**

## 架构

```
用户浏览器
┌──────────────────────────────────────────────┐
│  React 前端                                  │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ 聊天界面  │  │ AI 起草  │  │ 本地 vault │ │
│  │ 房间列表  │  │ (JS Agent)│  │ (File API) │ │
│  │ 消息收发  │  │ 调 LLM   │  │            │ │
│  └─────┬────┘  └──────────┘  └────────────┘ │
└────────┼─────────────────────────────────────┘
         │ WebSocket / HTTP
         ▼
WeAt 后端 (Python FastAPI, 服务器上 ~50MB)
┌──────────────────────────────────────────────┐
│  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ Conduit  │  │ WebSocket│  │ 用户管理   │ │
│  │ API 封装  │  │ 消息推送  │  │ admin CLI  │ │
│  └─────┬────┘  └──────────┘  └────────────┘ │
└────────┼─────────────────────────────────────┘
         ▼
Conduit (Rust Matrix 服务端, 内存 ~30MB)
  — 消息路由 / 房间管理 / 消息存储
```

## 技术栈

| 层 | 选型 |
|---|---|
| 消息后端 | **Conduit**（Rust，docker 里跑单二进制） |
| Web 后端 | Python + **FastAPI** + aiohttp + uvicorn |
| 前端 | **React + TypeScript + Tailwind CSS**（Vite） |
| AI Agent | **浏览器端 TypeScript**（直接 fetch LLM API，tool calling） |
| 部署 | docker-compose（Conduit + WeAt + Nginx + HTTPS） |

## 用户模型

- 一个服务器 = 一个团队（不开放 Federation）
- 管理员 `weat-admin add-user` 创建账号
- 用户用用户名 + 密码登录（对 Matrix 完全透明）
- 每个用户自备 LLM API Key（存在浏览器 sessionStorage/IndexedDB）
- MVP 不做 E2EE（明文房间）

## 数据流（发消息）

```
Alice 浏览器: 输入消息 → WebSocket → WeAt 后端
  → WeAt 调用 Conduit REST: POST /rooms/{id}/send
  → 其他用户浏览器 sync 到新消息 → 显示
```

## 数据流（AI 起草）

```
Alice 看到 Bob 的消息 → 点 "AI 起草"
  → 浏览器 JS agent 启动：
     1. 调后端: GET /rooms/{id}/messages → 取群聊历史
     2. 调 LLM API (fetch, 带 tool calling)
     3. 如果需要读 vault → 浏览器 File API 读本地文件
     4. Agent 返回草稿文本
  → 显示草稿面板，Alice 修改
  → 满意 → 调后端: POST /rooms/{id}/send → (以 Alice 身份发出)
  → LLM Key 全程在浏览器，不经过服务器
```

## 分阶段实现

### Phase 1: MVP Web 客户端（纯聊天）

目标：登录 → 房间列表 → 收发消息，手机可用。

**后端** (`backend/`)：
- FastAPI + uvicorn
- `POST /api/login` — 通过 Conduit REST 登录 Matrix（用户名/密码 → access_token）
- `GET /api/rooms` — 已加入的房间列表
- `GET /api/rooms/{id}/messages?limit=N` — 历史消息
- `POST /api/rooms/{id}/messages` — 发送消息
- `WS /ws` — WebSocket 实时推送新消息
- 后台 sync 循环（aiohttp 调 Conduit /sync）
- `conduit_api.py` — Conduit REST 封装
- `admin_cli.py` — `weat-admin add-user / list-users / reset-password`

**前端** (`frontend/`)：
- 登录页（用户名 + 密码）
- 房间列表（侧栏/底部导航/响应式）
- 聊天页面（消息列表 + 输入框）
- 手机适配
- 消息渲染（支持简单 markdown）

### Phase 2: 浏览器 AI Agent

目标：浏览器端 JS agent，可调 LLM + 工具循环。

- `agent.ts` — Agent 循环（tools → LLM → parse → next turn）
- `tools/read_vault.ts` — 浏览器 File API 读用户选择的本地文件
- `tools/get_room_history.ts` — 调后端 API 获取群聊历史
- Agent 注册一个全局工具列表，附 JSON Schema

### Phase 3: AI 起草集成

目标：聊天界面里 AI 起草直达。

- 每条消息旁 "AI 起草" 按钮
- 点击后弹出草稿面板
- Agent 自动取群聊上下文 → LLM → 显示草稿
- 用户可编辑草稿、修改指令（"缩短到两句话"）
- 满意后一键发送（以用户身份）

### Phase 4: Vault 集成

目标：AI 起草时引用 vault 笔记。

- 用户通过浏览器选择 vault 目录（OPFS 或 File API）
- Agent 新增 tool: `search_vault(keyword)` → 读 .md 文件
- 草稿中标注 📚 来源引用

### Phase 5: 部署

目标：一键部署到云服务器或个人电脑 + 内网穿透。

- docker-compose.yml（Conduit + WeAt + Nginx）
- Nginx HTTPS（Let's Encrypt）/ HTTP 开发模式
- 安装脚本：git clone → docker-compose up → weat-admin init
- 内网穿透指南（Cloudflare Tunnel / Tailscale）

## 文件结构

```
/
├── PLAN.md
├── docker-compose.yml
├── Dockerfile
├── nginx.conf
│
├── backend/
│   ├── main.py              — FastAPI 入口 + uvicorn
│   ├── conduit_api.py       — Conduit REST API 封装
│   ├── sync_loop.py         — Matrix sync 后台循环
│   ├─- admin_cli.py         — weat-admin 命令行
│   ├── user_store.py        — SQLite 用户配置
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
│
└── conduit/
    └── config.toml           — Conduit 配置模板
```

## 关键设计原则

1. **用户 0 安装** — 只需要浏览器
2. **LLM Key 不出浏览器** — 服务器不碰用户 key，不做代付
3. **AI 以用户身份发送** — 群聊其他人看不到 AI 痕迹
4. **最少代码** — 后端只做消息代理，不做 AI
5. **手机可用** — 响应式设计，Phase 1 就适配

## 验证

1. `docker-compose up`
2. `weat-admin add-user alice pwd123`
3. 浏览器打开 http://localhost:8080
4. alice 登录 → 看到 empty room list
5. 创建房间 → 发消息 → 刷新能看到历史
6. 手机浏览器打开同样的地址 → 能用
7. Phase 3: AI 起草 → 编辑 → 发送
8. 内网穿透后外部设备也能访问
