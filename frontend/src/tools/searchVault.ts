import type { Tool } from "../agent/types";
import { searchInVault, hasVault, listVaultTree, readFromVault } from "../vault";

/**
 * 严格遵循 obsidian-find 命令的搜索模式：
 *
 * 1. 先确认 vault 有目录结构
 * 2. 搜索 keyword
 * 3. 如果结果稀疏，自动试同义词 / 相关词再搜
 * 4. 返回结果含：note title, folder/path, excerpt, type（从 frontmatter 推断）
 * 5. 如果类型多样，按类型分组展示
 * 6. 返回足够的信息让 Agent 决定下一步动作
 */

// 常见同义词映射，当搜索结果稀疏时自动使用
const SYNONYM_GROUPS: Record<string, string[]> = {
  "architecture": ["架构", "design", "系统设计", "结构"],
  "部署": ["deploy", "release", "发布", "上线", "CD"],
};

function findSynonyms(keyword: string): string[] {
  const seen = new Set<string>();
  seen.add(keyword);
  for (const [key, values] of Object.entries(SYNONYM_GROUPS)) {
    if (key === keyword || values.includes(keyword)) {
      for (const v of [key, ...values]) {
        if (v !== keyword) seen.add(v);
      }
    }
  }
  return [...seen];
}

/** 从 frontmatter 中提取 type 标签 */
function detectType(text: string): string {
  const m = text.match(/^---\n([\s\S]*?)\n---/);
  if (!m) return "note";
  const fm = m[1];
  const typeMatch = fm.match(/^type:\s*(\S+)/m);
  if (typeMatch) return typeMatch[1];
  const tagsMatch = fm.match(/^tags:\s*\n([\s\S]*?)(?:\n\S|\n$)/m);
  if (tagsMatch) {
    const tagLine = tagsMatch[1].match(/-\s*(\S+)/);
    if (tagLine) return tagLine[1];
  }
  return "note";
}

export function createSearchVaultTool(): Tool<{ keyword: string; subDir?: string }> {
  return {
    definition: {
      name: "search_vault",
      description: `在本地知识库中搜索相关内容，用于起草回复或总结前查找相关笔记。

搜索范围覆盖所有子目录（递归）。subDir 参数可限定到某个子目录。

## 使用策略

1. 先用空 keyword 搜索，了解 vault 目录结构
2. 从用户问题中提取 1-3 个核心概念词搜索
3. 如果搜索结果为空或稀疏，工具会自动尝试同义词/相关词
4. 结果返回含：文件路径、文件名、上下文段落、类型（从 frontmatter 推断）
5. 如有不同类型的结果（project / person / concept 等），会按类型分组

## 适用于

- 起草回复前查找相关项目背景、历史决策、人物信息
- 总结对话前搜索之前相关的讨论或笔记
- 引用已有记录来支持回复`,
      parameters: {
        type: "object",
        properties: {
          keyword: {
            type: "string",
            description: "搜索关键词。传空字符串查看 vault 目录结构（了解有哪些子目录）。从用户问题中提取最核心的词，避免整句搜索。",
          },
          subDir: {
            type: "string",
            description: "可选。限定搜索的子目录，如 'wiki/projects' 或 'wiki/entities'。如果你知道 vault 结构，定向搜索更精准。",
          },
        },
        required: ["keyword"],
      },
    },
    async execute(params) {
      const ok = await hasVault();
      if (!ok) return "（知识库未连接，用户尚未选择本地目录）";

      // ── 空 keyword → 返回 vault 结构 ─────────────────────────
      if (!params.keyword.trim()) {
        const dirs = await listVaultTree();
        return [
          `vault 目录结构：${dirs.length} 个子目录`,
          ...dirs.map((d) => `  ${d}/`),
        ].join("\n");
      }

      // ── 尝试搜索，支持自动同义词重试 ─────────────────────────
      const keywords = findSynonyms(params.keyword);
      let allResults: Awaited<ReturnType<typeof searchInVault>> = [];

      for (const kw of keywords) {
        const r = await searchInVault(kw, params.subDir);
        allResults.push(...r);
      }

      // 去重（同路径只保留一次）
      const seen = new Set<string>();
      allResults = allResults.filter((r) => {
        const key = r.path;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });

      if (allResults.length === 0) {
        const suggestion = keywords.length > 1
          ? `已自动尝试同义词：${keywords.slice(1).join("、")}`
          : "可尝试不同的关键词或同义词";
        return `在 vault 中未找到与 "${params.keyword}" 相关的内容。\n${suggestion}`;
      }

      // ── 按类型分组展示 ─────────────────────────────────────────
      const byType = new Map<string, typeof allResults>();
      for (const r of allResults) {
        const type = detectType(r.snippet);
        if (!byType.has(type)) byType.set(type, []);
        byType.get(type)!.push(r);
      }

      const lines: string[] = [`共 ${allResults.length} 个匹配结果：`];
      for (const [type, items] of byType) {
        lines.push(`\n📂 ${type}：`);
        for (const r of items.slice(0, 5)) {
          lines.push(`  📄 ${r.path}`);
          lines.push(`    > ${r.snippet}`);
        }
        if (items.length > 5) {
          lines.push(`    …以及 ${items.length - 5} 个其它`);
        }
      }

      if (allResults.length > 10) {
        lines.push(`\n💡 提示：用 subDir 参数限定目录可缩小范围。`);
      }

      return lines.join("\n");
    },
  };
}
