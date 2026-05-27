# S4 — obsidian-second-brain × opencode

## 目标

验证 adapter 生成的 AGENTS.md + .opencode/commands/ 能被 opencode 识别，obsidian-second-brain 命令可用。

## 步骤

```bash
# 1. 构建 opencode dist
cd /path/to/obsidian-second-brain
bash scripts/build.sh --platform opencode
# → dist/opencode/ 生成 AGENTS.md + .opencode/{commands,references,scripts}/

# 2. 复制到 vault
cp -R dist/opencode/. /path/to/vault/

# 3. 验证 opencode 读取
opencode run --format json --dangerously-skip-permissions --dir /path/to/vault \
  "list available vault commands"
```

## 通过标准

- [x] `bash scripts/build.sh --platform opencode` 生成 33 个命令
- [x] opencode 在 vault 目录下自动读取 AGENTS.md
- [x] agent 能列举 /obsidian-recap、/obsidian-save 等命令

## 关键发现

- build.sh 输出到 `dist/opencode/`（而非 adapter.sh 直接写到 vault），需要手动 `cp -R dist/opencode/. vault/`
- `.opencode/commands/` 有 33 个 .md 文件
- AGENTS.md 包含完整命令路由表，opencode 自动将其作为 system context
- **integration path for WeAt**：Bridge 容器启动时 clone obsidian-second-brain，跑 build.sh，cp 到用户 vault

## 版本

obsidian-second-brain @ main (2026-05-27)
