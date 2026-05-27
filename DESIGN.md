# WeAt — 团队聊天 AI 副驾驶（Matrix + Obsidian）

> **状态**：design-locked（2026-05-27）
> **设计源头**：本文档由 `/Users/hhl/Documents/Ideas/spark/Ideas/团队聊天 AI 副驾驶（Matrix + Obsidian）.md` 镜像而来。如果想看一手讨论历史和归档的旧 idea，去 spark vault。

## For future Claude

这是一个**最大化复用开源组件**的小团队 AI 副驾驶产品。核心机制：用户在 Matrix 群聊里看到要回复的消息 → 私信自己的 AI bot 触发 → bot 调起本地 opencode agent → agent 读群聊历史（通过自研 Matrix MCP）+ **用自己的原生 Read/Grep 工具直接读 vault（一个普通 markdown 文件夹）** → **直接在私聊窗口里出草稿** → 用户在同一个私聊里**多轮微调**（"再短点"/"加上 X"/"换种语气"） → 满意后发 `/send` → bridge 用**用户自己的 Matrix 账户**发到群里（群里看不到 AI 痕迹）。

**唯一自研代码**：Matrix MCP server（让 agent 能"看见"群聊）+ 私聊对话编排器（约 900 行 Python）。**其他全部用现成开源**：Matrix / Element / opencode（自带文件工具）/ **[obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain)（MIT，提供 vault 操作 skill + AI-first 规范 + 33 个命令如 /obsidian-recap、/obsidian-log，已有 opencode 适配器生成 AGENTS.md）**。**没有独立 Web UI**——审核就是在和 bot 的私聊里；**没有 mcp-obsidian**——vault 就是文件夹，agent 自带工具直接读写。Obsidian 客户端是用户可选的人类查看器，系统不依赖。

**演化历史**：原始 idea [[_archived_local-first-ai-group-chat]] 想从零造一个"本地优先聊天软件"，经讨论后激进简化为"用现成聊天软件 + 用现成 agent + 我们只做胶水"。范围缩小 80%，价值密度反而上升。

---

## 一、产品定位

> **「让小团队每个成员在自己的电脑上，拥有一个能查阅个人知识库、读取群聊上下文、协助起草回复的 AI 副驾驶。」**

- **不是**"群里多了个 AI 机器人"
- **是**"每个人私下用 AI 帮自己起草回复，群里其他人感知不到"
- **目标用户**：5-20 人技术团队、远程协作组、独立工作室
- **核心哲学**：AI 是用户的私人副驾驶，**永远寄生在用户名下，永远经用户审核**（同 [[微信社恐回复助手]] 的"主动召唤"哲学）

---

## 二、核心工作流

### 工作流 A：AI 协助起草回复

```
1. Alice 在 Element 看到 #开发组 里 Bob 的技术问题
2. Alice 切到她和 @AliceAssistant（私人 bot）的私聊窗口
3. Alice：/draft #开发组 解释一下上周那个 P1 是怎么修的
4. bot 直接在私聊里出第一版草稿：
     > 上周的 P1 是因为 Redis 连接池配置错了……（草稿正文）
     > 📚 引用：[[2026-05-21 P1 调查日志]] / 群聊 Bob 2026-05-20 14:32
5. Alice 不满意 → 继续在私聊里直接说：
     "太长了，缩到三句，只讲根因和修复"
6. bot 重新出第二版（保留对话历史，知道是在改稿）
7. Alice 满意 → 发 `/send`（或 reaction 👍）
8. bridge 用 Alice 的 Matrix 凭据把最终版发到 #开发组
9. 群里其他成员看到：Alice 发的消息（无 AI 标识）
```

**核心**：审核就是在和 bot 的私聊里。没有浏览器窗口、没有第二个 UI 切换。如果 Alice 中途想放弃，发 `/cancel` 即可；30 分钟没动作自动失效。

### 工作流 B：群聊 → Obsidian 知识沉淀

```
1. Alice 在私信 bot 里发：/digest #开发组 本周
2. bot 调 opencode 读取本周聊天 + 当前 vault 已有相关笔记
3. bot 在私聊里出纪要草稿
4. Alice 多轮微调："标题换成 'P1 复盘周'" / "加一节人物清单"
5. Alice 满意 → 发 `/save`
6. bridge 写入 Alice 的 vault：Knowledge/2026-W21 开发组本周.md
```

**两个流程共享 ~90% 代码**——都是 "agent 在私聊出稿 → 多轮微调 → 落地（发群 / 写文件）"。

---

## 三、架构总览

### 部署模型

```
团队管理员部署一次：
  ┌────────────────────────────────────┐
  │  Matrix 服务器（Synapse, Docker）    │   ← 团队共享的唯一中心
  └────────────────────────────────────┘

每个团队成员在自己电脑上部署：
  ┌────────────────────────────────────┐
  │  Element 桌面客户端                  │   ← 现成（也是审核 UI）
  │  Vault 目录（普通 markdown 文件夹）   │   ← 用户的知识库，可选 Obsidian 浏览
  │  obsidian-second-brain skill        │   ← 现成 MIT 开源，opencode adapter 生成
  │  （AGENTS.md + .opencode/commands/） │     AGENTS.md 挂入 vault，命令进入 opencode
  │  Bridge（单 Docker 容器）            │   ← 我们做的
  │    ├─ Matrix bot 账号（@MyAssistant）│
  │    ├─ opencode 进程（自带文件工具）   │
  │    ├─ Matrix MCP server（自研）      │
  │    ├─ 编排器（私聊对话状态机）        │
  │    └─ 首次配置向导（一次性 Web 表单） │
  └────────────────────────────────────┘
```

**关键性质**：
- 只有 Matrix 服务器是共享的，其他**全部本地**
- 每个成员的 AI 草稿、vault、API key、token 完全私有
- 其他成员看不到你的草稿、vault、token 用量
- 这彻底绕开了"AI 数据政策"问题——agent 的输出经用户审过、用用户身份发，等同用户亲手发
- Vault 是普通文件夹，**用户也可以自己用任何编辑器（Obsidian / VS Code / vim）打开**，系统不锁定查看器

### 数据流（工作流 A）

```
Element ── 用户私信指令 ──▶ Matrix Server
                                  │
                                  ▼
                          Matrix Bot 账号
                                  │
                                  ▼
                          编排器（对话状态机）
                                  │
                          构造 prompt 上下文
                          （AGENTS.md / 命令路由由
                           obsidian-second-brain
                           skill 提供，opencode 自动加载）
                                  │
                                  ▼
                          opencode（subprocess）
                              ↕
                  ┌─────────────┼─────────────┐
                  ▼             ▼             ▼
          Matrix MCP server   opencode    opencode
          （读群聊历史）       自带 Read     自带 Grep
                              （读 vault    （搜 vault
                               markdown）    关键词）
                                  │
                          agent 输出草稿
                                  │
                                  ▼
                  bot 在私聊回复草稿（Markdown）
                                  │
                  ┌───────────────┼──────────────┐
                  ▼               ▼              ▼
            用户继续微调      用户 /send    用户 /cancel
            （回到编排器）         │              │
                                  ▼              ▼
                          Matrix Client API     丢弃
                          以用户身份发送
                                  ▼
                          群聊（其他人看到）
```

---

## 四、已锁定的设计决策

| ID | 决策 | 备注 |
|---|---|---|
| **D1** | 聊天底座 = Matrix + Synapse + Element | Matrix 是协议不是产品；Element 提供 UI |
| **D2** | Agent runtime = opencode（sst/opencode） | 开源、TUI、model-agnostic、支持 MCP |
| **D3** | 知识库 = 普通 markdown 文件夹 + agent 原生 Read/Grep + **[obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain) skill（MIT）** | 不需要 mcp-obsidian 抽象层；不自写 skill——直接复用现成的 33 个命令 + AI-first 规范 + opencode 适配器；Obsidian 客户端仅作可选人类查看器 |
| **D4** | LLM = 用户自带 API key | 用户对 token 成本负全责，平台不抽成 |
| **D5** | AI 触发 = 用户私信 @MyAssistant bot | 不在群里露面，最纯粹的"私人副驾驶" |
| **D6** | 草稿审核 = **私聊窗口里的多轮对话**，无独立 UI | bot 在私聊直接出稿，用户用自然语言或 `/send`/`/cancel`/`/retry` 微调；Matrix 本身即 UI |
| **D7** | 消息发送 = 以**用户身份**而非 bot 身份 | 群里看不到 AI 痕迹 |
| **D8** | AI 标签策略 = **审过 = 不打标** | 用户审核 = 用户对内容负全责（同 [[#AI 标签哲学]]） |
| **D9** | AI 代答（无人审）= **MVP 不做** | 用"AI 简报"（私聊推送）替代未来需求 |
| **D10** | 群聊 → Obsidian = 手动触发，不做定时 | 复杂度低，Phase 2 再加定时 |
| **D11** | 部署 = **单 Docker 容器**封装所有 bridge 组件 | MVP 简化，未来再拆 |
| **D12** | Matrix 凭据管理 = 首次 Web 登录引导 → token 加密存本地 | 用户必须信任 bridge 能以其身份发送 |
| **D13** | 目标受众 = 小团队（5-20 人）自部署，**不做 SaaS** | 维持"数据主权"承诺 |

### AI 标签哲学

经过多轮讨论锁定的核心原则：

- **用户审查过的消息 = 用户自己说的 = 不打标**（不区分有没有用过 AI）
- **AI 未经用户审查直接发出（"代答"）** = MVP **不支持**
- **辅助命令**（`/draft`、`/translate`、`/polish` 等）= 全部走"先生成 → 用户审核 → 用户发"流程，输出无标签

理由：和"用拼写检查/Grammarly/翻译软件"没本质区别，过度披露反而是表演式诚实。

---

## 五、技术栈

| 层 | 选型 | 备注 |
|---|---|---|
| 语言 | **Python** | 接的全是 Python 生态（MCP SDK、matrix-nio、opencode 可 subprocess） |
| Matrix SDK | matrix-nio | 最稳的 Python Matrix 库 |
| MCP SDK | Anthropic 官方 mcp Python | 实现 Matrix MCP server 用 |
| 配置向导 | FastAPI（仅首次启动，跑完即关）| 一次性收集 Matrix token、vault 路径、API key |
| Agent | opencode（subprocess 或可能的 SDK） | 用户配置 LLM、MCP 在 opencode 侧；自带 Read/Write/Grep/Glob 文件工具 |
| KB 访问 | opencode 原生文件工具 + **obsidian-second-brain skill** | 不依赖 mcp-obsidian；不自写 skill；安装 obsidian-second-brain 后运行其 opencode 适配器生成 AGENTS.md + .opencode/commands/，opencode 自动加载 |
| 数据持久化 | SQLite | 存当前草稿会话、token、配置 |
| 凭据加密 | cryptography（Fernet）+ OS keychain（可选）| 加密存 Matrix access token |
| 部署 | docker-compose（单容器） | Synapse 单独跑（团队级），bridge 单独跑（用户级） |
| 依赖管理 | uv | pip 的 100 倍快 |

**总代码量估计**：~900 行 Python（私聊审核去掉了 HTMX + 审核页面，缩水约 300 行）。**vault skill 完全不自写**——装 obsidian-second-brain 即可，跑它的 opencode 适配器生成 AGENTS.md。

---

## 六、自研的核心组件

### 组件 1：Matrix MCP Server（~300 行）

**作用**：让 agent 能以 MCP 工具的形式访问 Matrix。

**对外暴露的工具**：
- `list_rooms()` → 列出 bot 加入的所有房间
- `get_recent_messages(room_id, limit=50)` → 拉最近 N 条消息
- `search_messages(room_id, query)` → 关键词搜索房间内消息
- **不暴露 `send_message`**——发消息走私聊审核流程，绝不让 agent 直接发

**为什么不复用 send**：让 agent 调 `send_message` 工具就跳过审核步骤了。审核是产品的核心，不能让 agent 绕过。

### 组件 2：编排器 + 私聊对话状态机（~400 行）

**职责**：
1. 监听 Matrix 私信中的命令 `/draft <room> <topic>`、`/digest <room> <range>`、`/send`、`/save`、`/retry`、`/cancel`
2. 为每个用户维护"当前草稿会话"状态（SQLite）：目标房间、对话历史、最后一版草稿、过期时间（默认 30 分钟）
3. 收到 `/draft` 或微调指令时：构造 opencode 调用上下文（用户原始命令 + 房间历史 + 已有草稿 + 用户最新意见），subprocess 拉起 opencode、捕获输出
4. agent 输出渲染为 Markdown 消息发回私聊（草稿正文 + 📚 引用 + 🤖 步骤摘要）
5. `/send` → 用用户 Matrix token 发到目标房间；`/save` → 写入 Obsidian vault；`/cancel` → 丢弃会话
6. SQLite 留存所有已发送草稿的完整对话历史（审计 + 学习）

**私聊对话示例**：

```
Alice → bot:
  /draft #开发组 解释上周那个 P1 是怎么修的

bot → Alice:
  ─── 草稿 v1 ───
  上周的 P1 是因为 Redis 连接池配置错了。具体来说……
  （草稿正文）

  📚 引用：
   · [[2026-05-21 P1 调查日志]]
   · [[Redis 配置规范]]
   · 群聊：Bob @ 2026-05-20 14:32

  🤖 步骤：读 #开发组 最近 50 条 → 搜 vault "P1 Redis"（2 篇）→ 综合起草
  ────────────
  /send 发送 · /retry 重新生成 · /cancel 取消 · 或直接说怎么改

Alice → bot:
  太长了，缩到三句，只讲根因和修复

bot → Alice:
  ─── 草稿 v2 ───
  根因：Redis 连接池 max_connections 设成了 10，并发上来直接打满……
  （更短的版本）
  ────────────
  /send · /retry · /cancel · 或继续微调

Alice → bot:
  /send

bot → Alice:
  ✅ 已以你的身份发到 #开发组
```

**关键设计点**：
- bot 不是无状态命令处理器，而是**一个有上下文的小对话伙伴**——非命令消息默认解读为"在改当前草稿"
- 显式命令（`/send`、`/save`、`/cancel`、`/retry`）仅用于终态切换
- 会话默认 30 分钟无活动自动过期，避免遗忘的草稿堆积

### 组件 3：群聊 → Obsidian 同步（~80 行）

**复用编排器 ~95% 代码**，区别：
- 入口命令：`/digest <room> <时间范围>`
- 终态命令：`/save` 而非 `/send`
- 落地动作：把"群聊历史 + 用户额外指令"喂给 opencode，让 agent 通过 obsidian-second-brain 的 **`/obsidian-recap`**（或 `/obsidian-log`、`/obsidian-save`）写入 vault；agent 用原生 Write 工具落盘，遵循 skill 里的 AI-first 规范（preamble、frontmatter、wikilinks、recency markers）
- 多轮微调流程完全相同（私聊里来回改稿）

之所以这么短：底层机制已被组件 2 覆盖；vault 写入路径、文件命名、frontmatter 这些 obsidian-second-brain 已经处理好。我们只是把"群聊上下文"接到那套现成命令里。

### 组件 4：obsidian-second-brain 集成（~50 行 + 部署脚本）

**职责**：把 [obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain)（MIT）接入 bridge 容器。**不自写 vault skill**。

具体做法：
1. Bridge 容器构建时 `git clone` obsidian-second-brain 到镜像内
2. 首次启动时跑它的 `adapters/opencode/adapter.sh`，在用户 vault 根目录生成：
   - `AGENTS.md` — opencode 启动时自动读，作为 vault 操作手册
   - `.opencode/commands/*.md` — 33 个 vault 命令（/obsidian-save、/obsidian-recap、/obsidian-log…）
   - `.opencode/references/` — AI-first 规范、写入规则、vault schema
3. 同时执行 `/obsidian-init` 等价流程，给用户 vault 生成 `_CLAUDE.md`（若不存在）
4. opencode subprocess 启动时设 CWD = 用户 vault，opencode 自动找到 AGENTS.md

**我们因此免费拿到**：
- 33 个成熟的 vault 命令（含 `/obsidian-recap` 正好覆盖工作流 B）
- AI-first 7 条规范（preamble / frontmatter / wikilinks / 来源 / 置信度等）
- 标准的 _CLAUDE.md 模板和 vault 结构
- 4 个 scheduled agents（未来扩展时可用）
- 跨 CLI 兼容（如果未来要换 Claude Code / Codex CLI / Gemini CLI，都已适配）

**和上游的关系**：MIT 协议下 vendor + 跑适配器即可；版本钉死在某个 tag，升级时手动 bump。如果有需要的微调，先在上游提 PR，避免 fork 分叉。

### 组件 5：配置与部署（~100 行 + 文档）

- 首次启动引导：Web 表单收集 Matrix 服务器、账号、Obsidian vault 路径、opencode 位置、LLM API key
- 首次 Matrix 登录走浏览器 OAuth-like 流程，access token 加密存本地
- docker-compose.yml 一键启动
- 默认端口、默认路径合理化

---

## 七、MVP 时间表

| Sprint | 内容 | 时长 |
|---|---|---|
| Sprint 0 | 项目骨架 + 端到端最小连通：私信 bot 收到指令 → 调 opencode → bot 在私聊回复一条 "hello from agent" | 2-3 天 |
| Sprint 1 | Matrix MCP Server，让 agent 能"看见"群聊 | 2-3 天 |
| Sprint 2 | 编排器 + 私聊对话状态机（命令解析、会话状态、多轮微调、`/send` 用用户身份发送）| 5-6 天 |
| Sprint 3 | obsidian-second-brain 集成 + 群聊总结流程（vendor skill、跑 opencode 适配器、把 `/digest` 接到 `/obsidian-recap`）| 1-2 天 |
| Sprint 4 | 部署体验（docker-compose、首次配置 Web 向导、README、首启时自动跑 obsidian-second-brain 适配器）| 3-5 天 |
| **合计** | | **约 2 周** |

---

## 八、未来路线（Phase 2+）

按优先级排：

1. **AI 简报**：用户离线期间 AI 后台读群聊，回来时私信推送"你不在时发生了什么 + 建议优先回什么"（替代"AI 代答"需求）
2. **定时摘要**：每周自动跑 `/digest`，结果存草稿区等用户审核
3. **多 agent 切换**：可配置多套 CLAUDE.md（研究 agent / 运维 agent / 写作 agent），通过 `/draft @research-agent ...` 切换
4. **更多触发渠道**：Element 客户端插件、命令行 `assistant draft`、桌面菜单栏图标
5. **跨房间检索**：让 agent 跨多个房间分析共性话题（注意：会触发 [[#已抛弃的设计决策]] 里讨论过的隐私问题）

---

## 九、关键风险

| ID | 风险 | 缓解 | 置信度 |
|---|---|---|---|
| R1 | opencode CLI 接口可能变化，破坏 subprocess 集成 | adapter 抽象，未来支持多 runtime | medium |
| R2 | LLM API 成本累积（团队每天上千条消息）| 用户自付，可选本地模型（Ollama）作为低成本备选 | high |
| R3 | Matrix 凭据加密存本地仍有泄露风险（如 keyring 不安全的系统）| 使用 OS keychain 而非纯文件加密 | medium |
| R4 | 私聊里的多轮微调若 agent 响应慢（每轮 5-15s），节奏会拖累审核体验 | 流式输出（opencode 支持）、"agent 正在打字…" 状态消息、缓存上一版草稿便于增量改 | medium |
| R5 | 单容器封装多组件不利于调试 | Phase 2 拆分；MVP 接受这个代价换部署简单 | low |

---

## 十、已抛弃的设计决策

这些设计在讨论中考虑过然后放弃，记录在此供未来参考：

1. **从零造聊天软件 + P2P + CRDT 群 wiki**——见 [[_archived_local-first-ai-group-chat]]，被判定为"重造轮子"
2. **AI 作为独立 Matrix 用户**（@research-bot 等）——违反"AI 永远在用户名下"哲学
3. **AI 代答（无人审）**——团队场景下风险大于收益，用"AI 简报"替代
4. **AI 辅助打标签**——审过 = 用户负责 = 等同自己说，过度披露反而虚伪
5. **群 Wiki 共享**——冲突地狱，用"个人 Wiki + 群聊消息置顶"替代
6. **跨群 AI 检索分级隐私策略**（开放/仅本地/禁用）——MVP 阶段过度设计
7. **独立 Web 审核 UI（HTMX）**——切窗口太多次；Matrix 私聊本身就是聊天 UI，让 bot 在私聊里出稿、多轮微调，体验更连贯。FastAPI 缩减到只服务首次配置向导。
8. **mcp-obsidian / Obsidian 客户端依赖**——vault 是普通 markdown 文件夹，opencode 自带 Read/Write/Grep/Glob 已经够用，多加一层 MCP 是无谓抽象。Obsidian 降级为用户可选的人类查看器，系统不依赖。
9. **自写 vault skill 文档**——本来要写 ~200 行 markdown 教 agent vault 结构，发现 [obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain) MIT 已经做完且 spark vault 本身就是它生成的；直接 vendor 进 bridge 容器、跑它的 opencode 适配器即可，免费获得 33 个命令 + AI-first 规范 + 模板生成器。

---

## 十一、产品价值主张（一句话）

> **「群聊里有问题想答？私信你自己的 AI，让它读群聊、查你的笔记、起草回复，你审过就发。AI 帮你想，但你为每个字负责。」**

---

## 相关

- [[微信社恐回复助手]] — 1:1 微信场景的同源思路（消费场景、Tauri + macOS）
- [[_archived_local-first-ai-group-chat]] — 本 idea 的演化起点（已归档）
- [[Ideas/Context not Control — AI协作哲学]] — 反向应用：消费场景的 AI 必须比生产场景更克制
