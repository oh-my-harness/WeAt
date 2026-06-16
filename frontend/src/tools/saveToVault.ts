import type { Tool, ToolExecuteContext } from "../agent/types";
import { writeToVault, hasVault, readFromVault, listVaultFiles } from "../vault";

/**
 * 严格遵循 obsidian-save + write-rules + ai-first-rules 规范的保存工具：
 *
 * ## 写入前
 * - Search before write — 同名文件已存在时追加而非覆盖，除非明确要覆盖
 * - 按内容类型决定保存路径：
 *   - 项目相关 → wiki/projects/
 *   - 人物/公司/工具 → wiki/entities/
 *   - 概念/方法 → wiki/concepts/
 *   - 日常总结 → wiki/daily/ 或根目录
 *   - 决策记录 → wiki/decisions/（ADR 格式）
 *   - 无需目录的简单文件 → 根目录
 *
 * ## 写入内容必须遵循 AI-First 规范
 * 1. YAML frontmatter: date, type, tags, ai-first: true 等
 * 2. "## For future Claude" preamble（2-3 句摘要）
 * 3. 正文 Markdown，所有概念用 [[wikilinks]]
 * 4. 外部信息标注日期来源
 *
 * ## 写入后
 * - 传播：在相关笔记中链接此新文件
 * - 不要创建孤立笔记
 */

export function createSaveToVaultTool(): Tool<{
  filePath: string;
  content: string;
  overwrite?: boolean;
}> {
  return {
    definition: {
      name: "save_to_vault",
      description: `将内容保存到知识库的 .md 文件中。

## 文件路径规范

按 vault 目录结构存放：
- 项目相关 → wiki/projects/项目名
- 人物/公司 → wiki/entities/姓名
- 概念/方案 → wiki/concepts/标题
- 总结/日志 → 根目录用 YYYY-MM-DD-描述
- 决策 → wiki/decisions/ADR-YYYY-MM-DD-标题

系统自动补 .md 后缀和创建不存在的子目录。

## 编写规范（AI-First）

内容必须包含：
1. YAML frontmatter:
   ---
   date: 2026-06-16
   type: project | person | concept | daily | note
   tags: [type-tag, ...]
   ai-first: true
   status: active
   ---

2. "## For future Claude" 段落（第一段正文，2-3 句说明内容、日期、用途）

3. 正文用 [[Wikilink]] 链接相关人/项目/概念。外部信息标注日期和来源。

## 写入策略

- search_before_write: 自动检查同名文件是否存在
- 存在时默认追加（追加到「Recent Activity」或末尾），除非 overwrite=true
- 不存在时创建新文件

## 传播

保存后记得在相关笔记（如 daily note、project note）中添加 [[链接]] 引用。`,
      parameters: {
        type: "object",
        properties: {
          filePath: {
            type: "string",
            description: "文件路径，如 'wiki/projects/项目A' 或 '2026-06-16-周报'。不含 .md 后缀，按 vault 目录规范存放。",
          },
          content: {
            type: "string",
            description: `完整的 Markdown 内容，必须遵循 AI-First 规范：

---
date: 2026-06-16
type: note
tags: [chat-summary]
ai-first: true
---

## For future Claude
[2-3 句说明：这是什么、何时保存、为什么重要]

# 标题

正文。用 [[Wikilink]] 链接相关概念。`,
          },
          overwrite: {
            type: "boolean",
            description: "是否覆盖已有文件。默认 false = 追加。只有在明确需要替换已有内容时才设为 true。",
          },
        },
        required: ["filePath", "content"],
      },
    },
    async execute(params, context?: ToolExecuteContext) {
      const ok = await hasVault();
      if (!ok) return "错误：未选择知识库目录。请在设置中选择本地目录。";

      const fullPath = params.filePath.endsWith(".md") ? params.filePath : `${params.filePath}.md`;

      // ── Search before write ──────────────────────────────────
      const files = await listVaultFiles();
      const exists = files.includes(fullPath);

      if (exists && !params.overwrite) {
        // 追加：读取已有内容，在后面追加
        const existing = await readFromVault(fullPath);
        const updated = existing.trimEnd() + "\n\n---\n\n" + params.content.trimStart();
        await writeToVault(fullPath, updated);
        return `已追加到 vault: ${fullPath}（有同名文件，追加而非覆盖）`;
      }

      await writeToVault(fullPath, params.content);

      const action = exists ? "覆盖" : "新建";
      return `已${action} vault 文件: ${fullPath}`;
    },
  };
}
