# WeAt

小团队 AI 副驾驶：在 Matrix 群聊里，打开「WeAt」房间发命令，让 AI 读群聊历史 + 查你的 Obsidian 知识库，起草回复，你审过再发——以你的身份。AI 帮你想，你为每个字负责。

---

## 第零步：安装前置工具

### 1. Element（Matrix 客户端）

Element 是最主流的 Matrix 客户端，WeAt 需要配合它使用。

| 平台 | 安装方式 |
|---|---|
| macOS | `brew install --cask element` 或[下载 .dmg](https://element.io/download) |
| Windows | [下载安装包](https://element.io/download) 或 `scoop install element` |
| iOS | App Store 搜「Element」 |
| Android | Google Play 搜「Element」 |
| 网页版 | [app.element.io](https://app.element.io)（无需安装） |

**注册 Matrix 账号：**
1. 打开 Element → 点「Create account」
2. 服务器选默认的 `matrix.org`（国内可能需要代理）
3. 填用户名 + 密码完成注册

> 如果用 Google / Apple 等 SSO 登录（没有密码），配置向导会提示你粘贴 Access Token：
> Element → **Settings → Help & About → 滚到最底部 → Access Token → 点复制**

**创建群聊 & 邀请朋友：**
1. Element 左侧点「+」→「New room」创建群聊
2. 进群 → 右侧「People」→「Invite」→ 输入朋友的 Matrix ID（格式：`@username:matrix.org`）
3. 朋友在 Element 注册后接受邀请即可加入

---

### 2. uv（Python 包管理器）

uv 会自动管理 Python 版本，不需要单独安装 Python。

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows（PowerShell）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS（Homebrew）
brew install uv
```

安装后重新打开终端，运行 `uv --version` 确认。

---

### 3. opencode（AI Agent 运行时）

```bash
# macOS（推荐）
brew install opencode

# 任意平台（curl）
curl -fsSL https://opencode.ai/install | bash

# npm
npm install -g opencode-ai@latest

# Windows
scoop install opencode
```

安装后运行 `opencode --version` 确认（需要 ≥ 1.15）。

---

### 4. LLM API Key

配置向导会询问 API Key，提前准备好其中一个：

| 提供商 | 注册地址 | 备注 |
|---|---|---|
| DeepSeek | [platform.deepseek.com](https://platform.deepseek.com) | 推荐，价格便宜 |
| Anthropic | [console.anthropic.com](https://console.anthropic.com) | Claude 系列 |
| OpenAI | [platform.openai.com](https://platform.openai.com) | GPT 系列 |

---

## 安装 & 启动（三步）

```bash
# 第一步：下载并安装依赖
git clone https://github.com/hhllhhyyds/weat
cd weat
uv sync

# 第二步：运行配置向导（约一分钟）
uv run weat-setup

# 第三步：启动
uv run weat-bridge
```

向导会依次询问：Matrix 用户名/密码（或 Token）、vault 路径、LLM API Key，并自动创建「WeAt」指令房间。完成后在 Element 找到「WeAt」房间，发 `/weat-help` 开始。

---

## 使用

在「WeAt」房间里发命令：

```
/weat-help                                    — 查看所有命令
/weat-draft #开发组 解释上周那个 P1 是怎么修的   — 起草群聊回复
/weat-digest #开发组 本周                      — 生成本周群聊纪要
```

AI 返回草稿后，直接说要怎么改：

```
太长了，缩到三句
换一个不那么正式的语气
再加上 Redis 连接池配置的具体数值
```

满意后：

```
/weat-send    — 以你的身份发到目标频道（群里其他人看到的是你发的消息）
/weat-save    — 保存纪要到 vault（仅 /weat-digest 内容）
/weat-retry   — 重新生成
/weat-cancel  — 放弃当前草稿
```

---

## 已知限制

DeepSeek 等思维链模型有时会把推理步骤混入草稿正文，需要手动删除。

---

## 技术架构

```
你的 Element ──「WeAt」房间──► WeAt Bridge (Python)
                                      │
                                检测到命令
                                      │
                              opencode run ──► MCP ──► Matrix 群聊历史
                                      │           └──► Obsidian vault (直接读文件)
                                      │
                              DeepSeek / Claude
                                      │
                              草稿回到「WeAt」房间
                                      │
                              /weat-send ──► 你的 Matrix 账号发到群里
```

只需**一个** Matrix 账号。WeAt 房间是首次配置时自动创建的私密房间，所有命令和草稿都在这里。群里其他人看不到 AI 痕迹。

自研代码约 700 行，其余全部复用开源：
- [matrix-nio](https://github.com/poljar/matrix-nio) — Matrix Python SDK
- [opencode](https://opencode.ai/) — Agent 运行时（自带文件读写工具）
- [obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain) — vault 操作 skill
- [mcp](https://github.com/modelcontextprotocol/python-sdk) — MCP stdio server

---

## 项目结构

```
src/weat/
  main.py                      — 入口 (weat-bridge，首次运行自动启动向导)
  config/
    settings.py                — Config dataclass
    wizard.py                  — 配置向导 (weat-setup)
  matrix_mcp/
    server.py                  — Matrix MCP Server
  orchestrator/
    orchestrator.py            — 命令房间状态机 + 命令路由
    session_store.py           — SQLite 草稿会话存储
    opencode_runner.py         — opencode subprocess 封装
  vault/
    setup.py                   — obsidian-second-brain 集成安装器
```

---

## 文档

- [DESIGN.md](DESIGN.md) — 完整设计文档：架构决策、组件分工、风险分析
- [ROADMAP.md](ROADMAP.md) — 开发路线图
