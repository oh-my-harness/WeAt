# WeAt

小团队 AI 副驾驶：在 Matrix 群聊里，打开「WeAt」房间发命令，让 AI 读群聊历史 + 查你的 Obsidian 知识库，起草回复，你审过再发——以你的身份。AI 帮你想，你为每个字负责。

---

## 快速上手（三步）

**前置条件：**
- Python 3.12+ + [uv](https://docs.astral.sh/uv/)
- [opencode](https://opencode.ai/) ≥ 1.15
- 一个 Matrix 账号（在 [matrix.org](https://app.element.io/#/register) 注册即可）
- Obsidian vault 或任意 markdown 文件夹

```bash
# 第一步：安装
git clone https://github.com/hhllhhyyds/weat
cd weat
uv sync

# 第二步：配置（交互式向导，约一分钟）
uv run weat-setup

# 第三步：启动
uv run weat-bridge
```

向导会询问：Matrix 用户名/密码、vault 路径、LLM API Key（DeepSeek / Anthropic / OpenAI）。配置完成后，打开 Element 找到「WeAt」房间，发 `/help` 开始。

---

## 使用

在「WeAt」房间里发命令：

```
/help                                    — 查看所有命令
/draft #开发组 解释上周那个 P1 是怎么修的   — 起草群聊回复
/digest #开发组 本周                      — 生成本周群聊纪要
```

AI 返回草稿后，直接说要怎么改：

```
太长了，缩到三句
换一个不那么正式的语气
再加上 Redis 连接池配置的具体数值
```

满意后：

```
/send    — 以你的身份发到目标频道（群里其他人看到的是你发的消息）
/save    — 保存纪要到 vault（仅 /digest 内容）
/retry   — 重新生成
/cancel  — 放弃当前草稿
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
                              /send ──► 你的 Matrix 账号发到群里
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
