# WeAt 开发路线

> **核心原则**：先验证开源依赖能做我们假设它做的事，再写代码。
> 任何 spike 失败 → 回 [[DESIGN.md]] 调整方案，而不是绕过验证继续做。

---

## Phase 0：开源依赖可用性验证（spike 周）

**目标**：用最小代码 / 手动操作验证 [DESIGN.md](DESIGN.md) 里 D1/D2/D3 等所有外部依赖**真的**能拼起来。
**产物**：每个 spike 留一份简短的 `spikes/SX-name/NOTES.md` 记录验证步骤、结论、踩坑、版本号。
**预算**：3-5 天。如果某个 spike 严重超时，就是信号——某个依赖比预期复杂，需要重新评估。

### 每个 spike 的标准格式

每条 spike 必须给出：

- **目标**：要验证哪个具体假设
- **步骤**：可重现的命令/脚本
- **通过标准**：什么算"过"，什么算"挂"
- **失败应对**：如果挂了，回退到什么方案

---

### S1 — Matrix + Synapse + matrix-nio（最关键）

**目标**：验证 D7（用用户身份发送，群里看不到 bot 痕迹）真的可行。

**步骤**：
1. `docker-compose` 起一个 Synapse 实例，开放 Element Web 访问
2. 创建 2 个测试账号：`@alice:localhost`、`@bob:localhost`
3. Element 桌面客户端登录 alice，新建房间，邀请 bob
4. 写一段 <100 行 Python（matrix-nio）：用 alice 的 access token 登录，读最近 50 条消息，发一条新消息
5. 在 Element 里观察这条消息——和 alice 用 GUI 发的能区分开吗？

**通过标准**：
- matrix-nio 发送的消息在 Element/bob 那边显示为 alice 的正常消息（无 bot 图标、无额外字段）
- 读历史消息能稳定拿到完整 timeline

**重点验证**：
- E2EE（加密房间）下还能读历史吗？matrix-nio 支持 Megolm，但需要 key share，**先测明文房间**，加密房间留到 Phase 1
- access token 怎么获取？passwordlogin / OAuth-like flow / SSO？挑一种最稳的固化到首次配置向导

**失败应对**：
- 如果 matrix-nio 不稳：换 `mautrix-python` 或 `nio` 的 fork
- 如果"用户身份发送"在 UI 上有可识别痕迹：D7 假设破产，整个 idea 要重新评估（这是项目最大单点风险）

---

### S2 — opencode 非交互调用

**目标**：验证 D2（opencode 可以被 subprocess 拉起、接受我们喂的上下文、输出可解析的结果）。

**步骤**：
1. 安装 opencode（按官方说明）
2. 找到非交互调用方式：是 `opencode --prompt "..."`？读 stdin？JSON IO？
3. 写一个最小 Python 脚本：subprocess 起 opencode，喂"用一句话解释什么是 Redis"，捕获输出
4. 测多轮：能不能把上一轮的对话历史作为上下文喂回去？（多轮微调需要）
5. 测输出结构：能否区分"最终答案"vs"中间思考"？

**通过标准**：
- Python 能稳定拿到 agent 的最终输出文本
- 多轮上下文能正确续接

**失败应对**：
- 如果 opencode 不支持非交互模式：要么用 PTY 假装是终端，要么换其他 agent（Claude Code CLI、Aider、Codex CLI）
- D2 一变，组件 2（编排器）的实现细节要重写——但产品形态不变

---

### S3 — opencode + MCP 服务

**目标**：验证 D2 的延伸——opencode 能加载自定义 MCP server，并且 agent 能用其中的工具。

**步骤**：
1. 用 Anthropic 官方 `mcp` Python SDK 写一个 hello world MCP server：暴露一个 `get_time()` 工具
2. 把它配进 opencode（opencode 配置文件里加 mcp 条目）
3. 在 opencode 里提问："现在几点？"
4. 观察 agent 是否调用了 `get_time` 工具

**通过标准**：
- agent 调用了我们的 MCP 工具
- 工具的返回值进了 agent 的回答

**重点验证**：
- opencode 用 stdio MCP 还是 HTTP MCP？两种都要确认能跑（自研的 Matrix MCP 走 stdio 最简单）
- MCP server 报错时 agent 的行为？

**失败应对**：
- 如果 opencode MCP 集成有限：自研 Matrix MCP 可能要降级成 "opencode tool"（如果 opencode 有插件机制），或者改成把群聊历史**直接拼进 prompt**（笨办法但能用）

---

### S4 — obsidian-second-brain × opencode

**目标**：验证 D3——`adapters/opencode/adapter.sh` 真的产出能让 opencode 用的 AGENTS.md + commands，且 `/obsidian-recap` 流程可跑。

**步骤**：
1. `mkdir test-vault && cd test-vault`
2. 跑 `bash /Users/hhl/Documents/projs/obsidian-second-brain/adapters/opencode/adapter.sh`（或它的 build 脚本）
3. 检查生成：AGENTS.md / .opencode/commands/ / .opencode/references/ 都在吗？
4. 在 test-vault 启动 opencode，看它是否自动读 AGENTS.md
5. 让 opencode 执行 `/obsidian-recap` 等价流程（喂一段假的"群聊内容"作为输入），看它能否按 AI-first 规范生成纪要

**通过标准**：
- AGENTS.md 被 opencode 识别和遵循
- 生成的纪要包含正确的 frontmatter、`## For future Claude` preamble、wikilinks
- 文件落在合理路径（如 `Knowledge/YYYY-Www xxx.md`）

**失败应对**：
- 如果 adapter 在 opencode 下生成的命令格式有错：上游提 PR 或 fork（MIT 协议允许）
- 如果某些命令重度依赖 Claude Code 特性：只用 opencode 适配过的子集，标注哪些命令不可用

---

### S5 — 端到端骨架烟测

**目标**：把 S1-S4 拼起来，跑通一个"假的但完整"的工作流，证明各组件接缝处没有意外。

**步骤**：
1. 一个最简 Python 脚本：
   - 用 matrix-nio 登录 alice 账号
   - 监听 alice 的私聊房间（一个固定的 DM with `@AliceBot:localhost`）
   - 收到 `/draft test-room hello` 时：
     - 调 opencode（subprocess）问"写一句招呼"
     - 把回答以 alice 身份发到 `test-room`
2. 在 Element 里实测一遍完整流程
3. **不接 MCP、不接 KB、不接 obsidian-second-brain**——这一步只验证骨架

**通过标准**：
- 全流程一次跑通
- 总代码 < 200 行
- 没有让人意外的接缝问题

**失败应对**：
- 任何意外接缝问题都记录到 NOTES.md，作为后续 Sprint 的输入

---

## Phase 0 退出标准（gate）

只有当 **S1、S2、S5 全部通过** 才进 Phase 1。S3 失败时降级为 "MCP 改成 prompt 拼接"；S4 失败时降级为 "用 obsidian-second-brain 子集 + 我们补一小段 vault skill"。

如果 S1 或 S2 失败 → **停**，回设计文档评估替代方案，不要硬上 Phase 1。

---

## Phase 1：MVP 实现（Sprint 0-4）

详细 sprint 表见 [DESIGN.md § 七](DESIGN.md)。这里只列概要：

| Sprint | 内容 | 时长 | 前置 |
|---|---|---|---|
| 0 | 项目骨架 + 端到端最小连通 | 2-3 天 | Phase 0 通过 |
| 1 | Matrix MCP Server（自研，让 agent 看见群聊） | 2-3 天 | S3 通过 |
| 2 | 编排器 + 私聊对话状态机 | 5-6 天 | Sprint 1 |
| 3 | 集成 obsidian-second-brain + 群聊总结 | 1-2 天 | S4 通过 + Sprint 2 |
| 4 | 部署体验（docker-compose、配置向导、README） | 3-5 天 | Sprint 3 |

**预算**：Phase 0 ~5 天 + Phase 1 ~2 周 = **约 3 周到 MVP**。

---

## Phase 2+：未来路线

见 [DESIGN.md § 八](DESIGN.md)。MVP 跑通后再展开。
