# WeAt

小团队 AI 副驾驶：在 Matrix 群聊里，私信你自己的 AI bot，让它读群聊 + 查你的 Obsidian 知识库、起草回复，你审过就发——以你的身份。AI 帮你想，你为每个字负责。

## 文档

- **[DESIGN.md](DESIGN.md)** — 完整设计文档：13 条锁定决策、架构、组件分工、风险
- **[ROADMAP.md](ROADMAP.md)** — 开发路线：Phase 0（开源依赖 spike）→ Phase 1（5 个 Sprint MVP）

## 当前状态

`design-locked`，准备进 **Phase 0**：验证 Matrix / matrix-nio / opencode / obsidian-second-brain 真的能拼起来。**还没开始写产品代码**。

## 技术栈

- 聊天底座：[Matrix](https://matrix.org) + Synapse + Element
- Agent runtime：[opencode](https://github.com/sst/opencode)
- 知识库 skill：[obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain)（MIT，提供 vault 操作命令 + AI-first 规范）
- 语言：Python 3（matrix-nio + 官方 mcp SDK + FastAPI 仅做首次配置向导）
- 预计自研代码：~900 行

## 一句话价值主张

> 群聊里有问题想答？私信你自己的 AI，让它读群聊、查你的笔记、起草回复，你审过就发。AI 帮你想，但你为每个字负责。
