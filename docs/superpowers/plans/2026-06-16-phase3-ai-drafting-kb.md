# Phase 3: AI 起草集成 + 知识库 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在聊天界面中通过按钮触发 AI 总结，支持保存到本地 vault；AI 起草回复时用户可选是否搜索知识库（默认关，省 token）。

**Architecture:** 新增 vault.ts 模块基于 File System Access API 管理本地目录；新增 SummaryPanel 组件展示 AI 生成摘要；ChatPage 头部新增"总结"按钮触发 Agent 总结；DraftPanel 新增"搜索知识库"开关控制 searchVault 工具是否注入 Agent。

**Tech Stack:** TypeScript, React 19, File System Access API (showDirectoryPicker), IndexedDB (handle 持久化)

---

### Task 1: Vault 基础设施模块

**Files:**
- Create: `frontend/src/vault.ts`

Vault 模块负责：用户选择本地目录 → 持久化 FileSystemDirectoryHandle 到 IndexedDB → 提供读/写/搜索 .md 文件的能力。File System Access API 的 handle 可存入 IndexedDB（Chrome/Edge 支持，Firefox 需内存降级）。

- [ ] **Step 1: 编写 vault.ts 完整模块**

```typescript
/**
 * Vault 模块 — 管理本地知识库目录
 *
 * 基于 File System Access API (showDirectoryPicker)。
 * DirectoryHandle 持久化到 IndexedDB（Chrome/Edge），Firefox 降级为内存持有。
 */

const DB_NAME = "weat_vault";
const DB_VERSION = 1;
const STORE_NAME = "handles";
const HANDLE_KEY = "vaultDir";

// ── IndexedDB helpers ───────────────────────────────────────────────────────

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE_NAME)) {
        req.result.createObjectStore(STORE_NAME);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function txDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function storeHandle(handle: FileSystemDirectoryHandle): Promise<void> {
  try {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).put(handle, HANDLE_KEY);
    await txDone(tx);
  } catch {
    // Firefox 不支持 IndexedDB 存储 FileSystemHandle，降级为内存
    memoryHandle = handle;
  }
}

async function loadHandle(): Promise<FileSystemDirectoryHandle | null> {
  try {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, "readonly");
    const handle = await new Promise<any>((resolve) => {
      const req = tx.objectStore(STORE_NAME).get(HANDLE_KEY);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    });
    await txDone(tx);
    if (handle?.kind === "directory") return handle as FileSystemDirectoryHandle;
    return null;
  } catch {
    return memoryHandle;
  }
}

// Firefox 降级：内存持有 handle
let memoryHandle: FileSystemDirectoryHandle | null = null;

// ── Public API ──────────────────────────────────────────────────────────────

/** 让用户选择一个本地目录作为 vault，返回是否成功 */
export async function pickVault(): Promise<boolean> {
  try {
    const handle = await window.showDirectoryPicker({ mode: "readwrite" });
    await storeHandle(handle);
    return true;
  } catch (err: any) {
    if (err.name === "AbortError") return false;
    console.error("pickVault failed:", err);
    return false;
  }
}

/** 获取已存储的 vault 目录 handle（无则返回 null） */
export async function getVaultHandle(): Promise<FileSystemDirectoryHandle | null> {
  return memoryHandle ?? (await loadHandle());
}

/** 是否已选择 vault */
export async function hasVault(): Promise<boolean> {
  return (await getVaultHandle()) !== null;
}

/** 将内容写入 vault 中的 .md 文件（覆盖或创建） */
export async function writeToVault(filename: string, content: string): Promise<void> {
  const dirHandle = await getVaultHandle();
  if (!dirHandle) throw new Error("未选择 vault 目录。请先在设置中选择本地知识库目录。");

  // 确保 .md 后缀
  const safeName = filename.endsWith(".md") ? filename : `${filename}.md`;
  const fileHandle = await dirHandle.getFileHandle(safeName, { create: true });
  const writable = await fileHandle.createWritable();
  await writable.write(content);
  await writable.close();
}

/** 搜索 vault 中所有 .md 文件，返回匹配结果 */
export async function searchInVault(
  keyword: string
): Promise<Array<{ fileName: string; snippet: string }>> {
  const dirHandle = await getVaultHandle();
  if (!dirHandle) throw new Error("未选择 vault 目录。请先在设置中选择本地知识库目录。");

  const results: Array<{ fileName: string; snippet: string }> = [];
  const lowerKeyword = keyword.toLowerCase();

  for await (const [name, handle] of (dirHandle as any).entries()) {
    if (!name.endsWith(".md")) continue;
    const fileHandle = handle as FileSystemFileHandle;
    const file = await fileHandle.getFile();
    const text = await file.text();
    const idx = text.toLowerCase().indexOf(lowerKeyword);
    if (idx >= 0) {
      const start = Math.max(0, idx - 60);
      const end = Math.min(text.length, idx + keyword.length + 60);
      const snippet =
        (start > 0 ? "…" : "") +
        text.slice(start, end).replace(/\n+/g, " ") +
        (end < text.length ? "…" : "");
      results.push({ fileName: name, snippet });
    }
  }
  return results;
}

/** 读取 vault 中某个 .md 文件的内容 */
export async function readFromVault(filename: string): Promise<string> {
  const dirHandle = await getVaultHandle();
  if (!dirHandle) throw new Error("未选择 vault 目录。");

  const fileHandle = await dirHandle.getFileHandle(filename);
  const file = await fileHandle.getFile();
  return file.text();
}

/** 列出 vault 中所有 .md 文件名 */
export async function listVaultFiles(): Promise<string[]> {
  const dirHandle = await getVaultHandle();
  if (!dirHandle) return [];

  const files: string[] = [];
  for await (const [name] of (dirHandle as any).entries()) {
    if (name.endsWith(".md")) files.push(name);
  }
  return files;
}
```

- [ ] **Step 2: 验证 TypeScript 类型**

```bash
cd frontend && npx tsc --noEmit src/vault.ts
```

Expected: 可能有 IndexedDB 相关类型警告，不影响运行。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/vault.ts
git commit -m "feat: add vault module — File System Access API + IndexedDB persistence"
```

---

### Task 2: Vault 选择入口（Settings 扩展）

**Files:**
- Modify: `frontend/src/Settings.tsx:1-80`

在 Settings 弹窗中添加"选择知识库目录"按钮，让用户可以 pick vault 目录。

- [ ] **Step 1: 修改 Settings.tsx 添加 vault picker**

完整替换 `frontend/src/Settings.tsx`：

```tsx
import { useState, useCallback } from "react";
import { getLLMConfig, setLLMConfig, clearLLMConfig } from "./api";
import { pickVault, hasVault, listVaultFiles } from "./vault";

interface Props {
  onClose: () => void;
}

export default function Settings({ onClose }: Props) {
  const existing = getLLMConfig();
  const [baseUrl, setBaseUrl] = useState(existing?.baseUrl || "");
  const [model, setModel] = useState(existing?.model || "");
  const [apiKey, setApiKey] = useState(existing?.apiKey || "");
  const [vaultReady, setVaultReady] = useState(false);
  const [vaultFiles, setVaultFiles] = useState<string[]>([]);

  // 初始化检查 vault 状态
  useState(() => {
    hasVault().then((ok) => {
      setVaultReady(ok);
      if (ok) listVaultFiles().then(setVaultFiles);
    });
  });

  const handlePickVault = useCallback(async () => {
    const ok = await pickVault();
    setVaultReady(ok);
    if (ok) {
      const files = await listVaultFiles();
      setVaultFiles(files);
    }
  }, []);

  const handleSave = () => {
    if (baseUrl.trim() && model.trim() && apiKey.trim()) {
      setLLMConfig({ baseUrl: baseUrl.trim(), model: model.trim(), apiKey: apiKey.trim() });
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">设置</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* LLM 配置区域 */}
        <p className="text-xs text-gray-400 mb-4">
          LLM API Key 仅存储在浏览器中，不会发送到服务器。
        </p>

        <label className="block text-sm text-gray-600 mb-1">API 地址</label>
        <input
          className="w-full border rounded-lg px-3 py-2 mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          placeholder="https://api.openai.com/v1"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
        />

        <label className="block text-sm text-gray-600 mb-1">模型</label>
        <input
          className="w-full border rounded-lg px-3 py-2 mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          placeholder="gpt-4o 或 deepseek-chat 等"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        />

        <label className="block text-sm text-gray-600 mb-1">API Key</label>
        <input
          className="w-full border rounded-lg px-3 py-2 mb-4 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          type="password"
          placeholder="sk-..."
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />

        {/* Vault 区域 */}
        <div className="border-t pt-4 mt-2 mb-4">
          <p className="text-xs text-gray-400 mb-2">
            选择本地知识库目录（浏览器 File API），AI 可搜索其中的 .md 文件。
          </p>
          <button
            onClick={handlePickVault}
            className="w-full border border-dashed border-gray-300 rounded-lg px-3 py-3 text-sm text-gray-600 hover:bg-gray-50 hover:border-blue-400 transition-colors"
          >
            {vaultReady ? "📁 更换知识库目录" : "📁 选择知识库目录"}
          </button>
          {vaultReady && (
            <p className="text-xs text-green-600 mt-1">
              已连接 ({vaultFiles.length} 个 .md 文件)
            </p>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => { clearLLMConfig(); onClose(); }}
            className="flex-1 border border-gray-300 rounded-lg py-2 text-sm hover:bg-gray-50"
          >
            清除
          </button>
          <button
            onClick={handleSave}
            disabled={!baseUrl.trim() || !model.trim() || !apiKey.trim()}
            className="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm hover:bg-blue-700 disabled:opacity-40"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 类型检查**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/Settings.tsx
git commit -m "feat: add vault directory picker in Settings"
```

---

### Task 3: saveToVault Agent 工具

**Files:**
- Create: `frontend/src/tools/saveToVault.ts`

Agent 工具：将 LLM 生成的文本内容保存为 vault 中的 .md 文件。

- [ ] **Step 1: 编写 saveToVault 工具**

```typescript
import type { Tool } from "../agent/types";
import { writeToVault, hasVault } from "../vault";

export function createSaveToVaultTool(): Tool<{ filename: string; content: string }> {
  return {
    definition: {
      name: "save_to_vault",
      description:
        "将文本内容保存到本地知识库目录的 .md 文件中。文件名应简洁描述内容（如 '项目架构讨论摘要'）。",
      parameters: {
        type: "object",
        properties: {
          filename: {
            type: "string",
            description: "文件名（不含 .md 后缀），如 '2026-06-16-项目讨论'",
          },
          content: {
            type: "string",
            description: "要保存的 Markdown 内容",
          },
        },
        required: ["filename", "content"],
      },
    },
    async execute(params) {
      const ok = await hasVault();
      if (!ok) return "错误：未选择知识库目录。请在设置中选择本地目录。";

      await writeToVault(params.filename, params.content);
      return `已保存到 vault: ${params.filename}.md`;
    },
  };
}
```

- [ ] **Step 2: 类型检查**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/tools/saveToVault.ts
git commit -m "feat: add saveToVault agent tool"
```

---

### Task 4: searchVault Agent 工具

**Files:**
- Create: `frontend/src/tools/searchVault.ts`

Agent 工具：在用户本地 vault 中搜索关键词，返回匹配的 .md 文件片段。

- [ ] **Step 1: 编写 searchVault 工具**

```typescript
import type { Tool } from "../agent/types";
import { searchInVault, hasVault } from "../vault";

export function createSearchVaultTool(): Tool<{ keyword: string }> {
  return {
    definition: {
      name: "search_vault",
      description:
        "在本地知识库的 .md 文件中搜索关键词。返回匹配的文件名和上下文片段。用于查找之前保存的讨论摘要、笔记等。",
      parameters: {
        type: "object",
        properties: {
          keyword: {
            type: "string",
            description: "搜索关键词，如 '架构设计' 或 '部署方案'",
          },
        },
        required: ["keyword"],
      },
    },
    async execute(params) {
      const ok = await hasVault();
      if (!ok) return "（知识库未连接，用户尚未选择本地目录）";

      const results = await searchInVault(params.keyword);
      if (results.length === 0) return `在 vault 中未找到与 "${params.keyword}" 相关的内容。`;

      const lines = results.map(
        (r) => `### ${r.fileName}\n> ${r.snippet}`
      );
      return lines.join("\n\n");
    },
  };
}
```

- [ ] **Step 2: 类型检查**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/tools/searchVault.ts
git commit -m "feat: add searchVault agent tool"
```

---

### Task 5: SummaryPanel 组件

**Files:**
- Create: `frontend/src/SummaryPanel.tsx`

类似 DraftPanel 的弹窗，但用于展示 AI 生成的摘要。提供：摘要预览、编辑、保存到 vault、发送到聊天。

- [ ] **Step 1: 编写 SummaryPanel 组件**

```tsx
import { useState, useCallback } from "react";

interface Props {
  summary: string;
  onClose: () => void;
  onSaveToVault: (content: string) => void;
  onSendToChat: (text: string) => void;
  savingVault: boolean;
}

export default function SummaryPanel({
  summary,
  onClose,
  onSaveToVault,
  onSendToChat,
  savingVault,
}: Props) {
  const [text, setText] = useState(summary);

  const handleSaveVault = useCallback(() => {
    onSaveToVault(text);
  }, [text, onSaveToVault]);

  const handleSend = useCallback(() => {
    if (text.trim()) {
      onSendToChat(text.trim());
      onClose();
    }
  }, [text, onSendToChat, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/30">
      <div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-xl w-full sm:max-w-lg max-h-[80vh] flex flex-col mx-0 sm:mx-4">
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h3 className="font-semibold text-sm">AI 总结</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 内容编辑 */}
        <div className="flex-1 overflow-y-auto px-4 py-3 min-h-[120px]">
          <textarea
            className="w-full h-60 resize-none border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>

        {/* 底部操作 */}
        <div className="flex gap-2 px-4 py-3 border-t">
          <button
            onClick={handleSaveVault}
            disabled={savingVault}
            className="flex-1 border border-gray-300 rounded-xl py-2 text-sm hover:bg-gray-50 disabled:opacity-40 transition-colors"
          >
            {savingVault ? "保存中…" : "保存到知识库"}
          </button>
          <button
            onClick={handleSend}
            disabled={!text.trim()}
            className="flex-1 bg-blue-600 text-white rounded-xl py-2 text-sm hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            发送到聊天
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 类型检查**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/SummaryPanel.tsx
git commit -m "feat: add SummaryPanel component"
```

---

### Task 6: ChatPage 头部"总结"按钮 + Summary 集成

**Files:**
- Modify: `frontend/src/ChatPage.tsx:1-257`

用按钮替代斜杠命令触发总结：
- 聊天头部新增"总结"按钮 — 点击后 Agent 获取最近 N 条消息 → LLM 生成摘要 → SummaryPanel 展示
- 移除斜杠命令提示和解析逻辑
- Agent 总结时始终包含 searchVault 工具（总结场景需要查历史笔记）

- [ ] **Step 1: 重写 ChatPage.tsx**

```tsx
import { useEffect, useRef, useState, useCallback } from "react";
import Markdown from "react-markdown";
import {
  Room,
  ChatMessage,
  fetchMessages,
  sendMessage,
  getUserId,
  getLLMConfig,
} from "./api";
import DraftPanel from "./DraftPanel";
import SummaryPanel from "./SummaryPanel";
import { runAgent } from "./agent";
import { createGetRoomHistoryTool } from "./tools/getRoomHistory";
import { createSaveToVaultTool } from "./tools/saveToVault";
import { createSearchVaultTool } from "./tools/searchVault";

interface Props {
  room: Room;
  messages: ChatMessage[];
  onAddMessage: (msg: ChatMessage) => void;
  onBack: () => void;
}

const SUMMARY_MESSAGE_COUNT = 30;

export default function ChatPage({
  room,
  messages,
  onAddMessage,
  onBack,
}: Props) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [draftTarget, setDraftTarget] = useState<string | null>(null);
  const [summaryState, setSummaryState] = useState<{
    text: string;
    busy: boolean;
  } | null>(null);
  const [savingVault, setSavingVault] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const userId = getUserId();
  const llmConfig = getLLMConfig();

  // ── 加载历史消息 ─────────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchMessages(room.room_id, 50, controller.signal)
      .then((mxMsgs) => {
        if (controller.signal.aborted) return;
        const msgs: ChatMessage[] = mxMsgs.map((m) => ({
          id: m.event_id,
          room_id: room.room_id,
          sender: m.sender,
          body: m.content?.body || "",
          ts: m.origin_server_ts,
          pending: false,
        }));
        const existingIds = new Set(messagesRef.current.map((m) => m.id));
        const newMsgs = msgs.filter((m) => !existingIds.has(m.id));
        newMsgs.forEach((m) => onAddMessage(m));
        setLoading(false);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        console.error("Failed to load messages", e);
        setLoading(false);
      });
    return () => controller.abort();
  }, [room.room_id]);

  // ── 自动滚动 ──────────────────────────────────────────────────
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages.length]);

  // ── 发送消息（乐观更新）───────────────────────────────────────
  const handleSend = useCallback(async (text: string) => {
    if (!text.trim() || sending) return;

    const tempId = `temp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const optimistic: ChatMessage = {
      id: tempId,
      room_id: room.room_id,
      sender: userId || "",
      body: text,
      ts: Date.now(),
      pending: true,
    };

    onAddMessage(optimistic);
    setInput("");
    setSending(true);

    try {
      const result = await sendMessage(room.room_id, text);
      onAddMessage({ ...optimistic, id: result.event_id, pending: false, _tempId: tempId });
    } catch (e) {
      console.error("Send failed", e);
      onAddMessage({ ...optimistic, pending: false, failed: true });
    } finally {
      setSending(false);
    }
  }, [sending, room.room_id, userId, onAddMessage]);

  const handleInputSend = useCallback(() => {
    if (input.trim()) {
      handleSend(input.trim());
    }
  }, [input, handleSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleInputSend();
    }
  };

  // ── "总结"按钮 ────────────────────────────────────────────────
  const handleSummarize = useCallback(async () => {
    if (!llmConfig) {
      alert("请先在设置中配置 LLM API");
      return;
    }

    setSummaryState({ text: "", busy: true });

    try {
      const result = await runAgent(
        {
          llm: llmConfig,
          systemPrompt: `你是一个团队聊天助手，帮助用户总结对话。

工具:
- get_room_history: 获取当前房间聊天历史（参数 limit 控制条数）
- search_vault: 搜索本地知识库中的相关笔记
- save_to_vault: 将总结保存到本地知识库

工作流程：
1. 用 get_room_history 获取最近 ${SUMMARY_MESSAGE_COUNT} 条消息
2. 用 search_vault 搜索是否有与当前讨论相关的历史笔记
3. 生成摘要：要点列表 + 待办事项 + 关键决策
4. 用 save_to_vault 保存摘要到 vault

摘要格式用 Markdown，标题以 "# 聊天总结" 开头。`,
          tools: [
            createGetRoomHistoryTool(room.room_id),
            createSearchVaultTool(),
            createSaveToVaultTool(),
          ],
          maxTurns: 6,
        },
        `请总结本房间最近 ${SUMMARY_MESSAGE_COUNT} 条聊天消息，并搜索知识库找相关历史。生成摘要后保存到 vault。`,
        () => {}, // onEvent — 总结过程不实时展示思考
      );

      setSummaryState({ text: result, busy: false });
    } catch (err: any) {
      setSummaryState({ text: `Error: ${err.message}`, busy: false });
    }
  }, [llmConfig, room.room_id]);

  // ── SummaryPanel 回调 ────────────────────────────────────────
  const handleSaveToVault = useCallback(async (content: string) => {
    setSavingVault(true);
    try {
      const { writeToVault } = await import("./vault");
      const dateStr = new Date().toISOString().slice(0, 10);
      await writeToVault(`${dateStr}-${room.name || room.room_id.slice(0,8)}-总结`, content);
      alert("已保存到知识库");
    } catch (err: any) {
      alert(`保存失败: ${err.message}`);
    } finally {
      setSavingVault(false);
    }
  }, [room.name, room.room_id]);

  const handleSummarySend = useCallback((text: string) => {
    handleSend(text);
  }, [handleSend]);

  // ── AI 起草 ───────────────────────────────────────────────────
  const handleAIDraft = useCallback((msgBody: string) => {
    if (!llmConfig) {
      alert("请先在设置中配置 LLM API");
      return;
    }
    setDraftTarget(msgBody);
  }, [llmConfig]);

  const handleDraftSend = useCallback((text: string) => {
    handleSend(text);
  }, [handleSend]);

  // ── 辅助函数 ──────────────────────────────────────────────────
  const formatTime = (ts: number) => {
    const d = new Date(ts);
    const pad = (n: number) => n.toString().padStart(2, "0");
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  const displayName = (sender: string) => {
    const parts = sender.split(":");
    if (parts.length >= 2) return parts[0].replace("@", "");
    return sender;
  };

  // ── 渲染 ──────────────────────────────────────────────────────
  return (
    <>
      {/* 聊天头部 */}
      <header className="flex items-center gap-2 px-4 py-3 border-b bg-white shrink-0">
        <button
          onClick={onBack}
          className="md:hidden text-gray-500 hover:text-gray-700"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 className="font-semibold truncate flex-1">
          {room.name || room.room_id}
        </h1>
        {/* "总结"按钮 */}
        {llmConfig && (
          <button
            onClick={handleSummarize}
            disabled={summaryState?.busy}
            className="shrink-0 border border-gray-300 rounded-lg px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 hover:border-blue-400 disabled:opacity-40 transition-colors"
            title="AI 总结最近消息"
          >
            {summaryState?.busy ? "总结中…" : "📋 总结"}
          </button>
        )}
      </header>

      {/* 消息列表 */}
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {loading && (
          <div className="text-center text-gray-400 text-sm py-8">
            加载中…
          </div>
        )}

        {!loading && messages.length === 0 && (
          <div className="text-center text-gray-400 text-sm py-8">
            暂无消息，发送第一条消息吧
          </div>
        )}

        {messages.map((msg) => {
          const isMe = msg.sender === userId;
          return (
            <div
              key={msg.id}
              className={`group flex ${isMe ? "justify-end" : "justify-start"}`}
            >
              <div className="relative max-w-[80%] sm:max-w-[70%]">
                <div
                  className={`rounded-2xl px-3 py-2 ${
                    isMe
                      ? "bg-blue-600 text-white rounded-br-md"
                      : "bg-white border rounded-bl-md"
                  } ${msg.pending ? "opacity-60" : ""} ${msg.failed ? "border-red-400" : ""}`}
                >
                  {!isMe && (
                    <div className="text-xs text-gray-400 mb-0.5">
                      {displayName(msg.sender)}
                    </div>
                  )}

                  <div className={`text-sm prose-message ${isMe ? "text-white" : "text-gray-900"}`}>
                    <Markdown>{msg.body}</Markdown>
                  </div>

                  <div className={`text-xs mt-1 flex items-center gap-1 ${isMe ? "text-blue-200" : "text-gray-400"}`}>
                    <span>{formatTime(msg.ts)}</span>
                    {msg.pending && <span>发送中…</span>}
                    {msg.failed && <span className="text-red-400">发送失败</span>}
                  </div>
                </div>

                {/* AI 起草按钮 */}
                {!isMe && !msg.pending && (
                  <button
                    onClick={() => handleAIDraft(msg.body)}
                    className="absolute -top-2 -right-2 opacity-0 group-hover:opacity-100 bg-white border rounded-full p-1 shadow hover:bg-blue-50 transition-opacity"
                    title="AI 起草回复"
                  >
                    <svg className="w-3.5 h-3.5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 输入区 */}
      <div className="px-4 py-3 border-t bg-white shrink-0">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息…"
            rows={1}
            className="flex-1 border rounded-xl px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 text-sm max-h-32"
          />
          <button
            onClick={handleInputSend}
            disabled={!input.trim() || sending}
            className="bg-blue-600 text-white rounded-xl px-4 py-2 hover:bg-blue-700 disabled:opacity-40 transition-colors shrink-0"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19V5m0 0l-7 7m7-7l7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Draft Panel */}
      {draftTarget !== null && llmConfig && (
        <DraftPanel
          roomId={room.room_id}
          llmConfig={llmConfig}
          targetMessage={draftTarget}
          onClose={() => setDraftTarget(null)}
          onSend={handleDraftSend}
        />
      )}

      {/* Summary Panel */}
      {summaryState && (
        <SummaryPanel
          summary={summaryState.text}
          onClose={() => setSummaryState(null)}
          onSaveToVault={handleSaveToVault}
          onSendToChat={handleSummarySend}
          savingVault={savingVault}
        />
      )}
    </>
  );
}
```

- [ ] **Step 2: 类型检查**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/ChatPage.tsx
git commit -m "feat: add summarize button in chat header + SummaryPanel integration"
```

---

### Task 7: DraftPanel 添加"搜索知识库"开关

**Files:**
- Modify: `frontend/src/DraftPanel.tsx:1-168`

在 DraftPanel 顶部指令输入区新增一个复选框，默认关闭。用户可勾选"搜索知识库"来让 Agent 携带 searchVault 工具（耗 token、慢），不勾选则只用 getRoomHistory。

- [ ] **Step 1: 重写 DraftPanel.tsx**

```tsx
import { useState, useRef, useCallback, useEffect } from "react";
import type { LLMConfig } from "./agent/types";
import type { Tool } from "./agent/types";
import { runAgent } from "./agent";
import { createGetRoomHistoryTool } from "./tools/getRoomHistory";
import { createSearchVaultTool } from "./tools/searchVault";

interface Props {
  roomId: string;
  llmConfig: LLMConfig;
  targetMessage?: string;
  onClose: () => void;
  onSend: (text: string) => void;
}

export default function DraftPanel({ roomId, llmConfig, targetMessage, onClose, onSend }: Props) {
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<"idle" | "generating" | "editing">("idle");
  const [instruction, setInstruction] = useState("");
  const [searchVault, setSearchVault] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const generate = useCallback(async (userInstruction: string) => {
    setStatus("generating");
    setDraft("");

    const ac = new AbortController();
    abortRef.current = ac;

    const contextHint = targetMessage
      ? `用户想回复这条消息：「${targetMessage}」\n\n`
      : "";

    // 按开关决定是否注入 searchVault
    const tools: Tool[] = [createGetRoomHistoryTool(roomId)];
    let toolListDesc = "- get_room_history: 获取当前房间聊天历史";
    if (searchVault) {
      tools.push(createSearchVaultTool());
      toolListDesc += "\n- search_vault: 搜索本地知识库中的相关笔记（如果有的话）";
    }

    try {
      const text = await runAgent(
        {
          llm: llmConfig,
          systemPrompt: `你是一个团队聊天助手，帮助用户起草回复。

工具:
${toolListDesc}

根据聊天历史和用户要求，起草一条合适的回复。
${searchVault ? "如果知识库中有相关信息，可以作为参考。" : ""}
回复要简洁自然，符合对话上下文。
只用中文回复，除非原文是英文。`,
          tools,
          maxTurns: searchVault ? 4 : 3,
        },
        `${contextHint}${userInstruction || "根据聊天历史，帮我起草一条回复"}`,
        (event) => {
          // 实时显示思考内容
          if (event.type === "thinking" && event.text) {
            // 不自动覆盖 draft，保持用户编辑内容
          }
        },
        ac.signal,
      );

      setDraft(text);
      setStatus(text ? "editing" : "idle");
    } catch (err: any) {
      if (err.name !== "AbortError") {
        setDraft(`Error: ${err.message}`);
        setStatus("editing");
      }
    } finally {
      abortRef.current = null;
    }
  }, [roomId, llmConfig, targetMessage, searchVault]);

  // 打开面板时自动触发生成
  useEffect(() => {
    generate("");
  }, []);

  const handleRegenerate = useCallback(() => {
    generate(instruction);
  }, [generate, instruction]);

  const handleModify = useCallback(() => {
    if (instruction.trim()) {
      generate(instruction);
    }
  }, [generate, instruction]);

  const handleSend = useCallback(() => {
    if (draft.trim()) {
      onSend(draft.trim());
      onClose();
    }
  }, [draft, onSend, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/30">
      <div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-xl w-full sm:max-w-lg max-h-[80vh] flex flex-col mx-0 sm:mx-4">
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h3 className="font-semibold text-sm">AI 起草</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 指令 + 开关 */}
        <div className="px-4 py-2 border-b space-y-2">
          {/* 修改指令 */}
          <div className="flex gap-2">
            <input
              className="flex-1 border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="修改指令（如：缩短到一句话）"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleModify();
              }}
            />
            <button
              onClick={handleModify}
              disabled={!instruction.trim() || status === "generating"}
              className="bg-gray-100 text-gray-600 rounded-lg px-3 py-1.5 text-sm hover:bg-gray-200 disabled:opacity-40"
            >
              修改
            </button>
          </div>

          {/* 搜索知识库开关 */}
          <label className="flex items-center gap-2 cursor-pointer text-xs text-gray-500">
            <input
              type="checkbox"
              checked={searchVault}
              onChange={(e) => setSearchVault(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-400"
            />
            搜索知识库
            <span className="text-gray-400">（较慢，消耗更多 token）</span>
          </label>
        </div>

        {/* 草稿内容 */}
        <div className="flex-1 overflow-y-auto px-4 py-3 min-h-[120px]">
          {status === "generating" && !draft && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin h-6 w-6 border-2 border-blue-600 border-t-transparent rounded-full" />
              <span className="ml-2 text-sm text-gray-400">生成中…</span>
            </div>
          )}

          {draft && (
            <textarea
              className="w-full h-40 resize-none border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
          )}

          {status === "idle" && !draft && (
            <div className="text-center text-gray-400 text-sm py-8">
              点击"重新生成"开始
            </div>
          )}
        </div>

        {/* 底部按钮 */}
        <div className="flex gap-2 px-4 py-3 border-t">
          <button
            onClick={handleRegenerate}
            disabled={status === "generating"}
            className="flex-1 border border-gray-300 rounded-xl py-2 text-sm hover:bg-gray-50 disabled:opacity-40 transition-colors"
          >
            {status === "generating" ? "生成中…" : "重新生成"}
          </button>
          <button
            onClick={handleSend}
            disabled={!draft.trim()}
            className="flex-1 bg-blue-600 text-white rounded-xl py-2 text-sm hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 类型检查**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/DraftPanel.tsx
git commit -m "feat: add vault search toggle in DraftPanel (off by default to save tokens)"
```

---

### Task 8: 端到端验证 Phase 3

- [ ] **Step 1: 启动开发环境**

```bash
./dev.sh
```

- [ ] **Step 2: 浏览器验证 checklist**

1. 打开 http://localhost:5173 → 登录 alice
2. 进入房间 → 聊天头部出现"📋 总结"按钮（需先配置 LLM）
3. 点击"📋 总结" → Agent 获取消息 → 生成摘要 → SummaryPanel 弹出
4. SummaryPanel 中编辑摘要 → 点击"保存到知识库" → vault 目录中多一个 .md 文件
5. 点击"发送到聊天" → 摘要发送为聊天消息
6. 将鼠标悬停在他人消息上 → AI 起草按钮出现 → 点击
7. DraftPanel 弹出 → 自动生成草稿 → 默认"搜索知识库"未勾选（省 token）
8. 勾选"搜索知识库" → 点击"重新生成" → Agent 携带 searchVault 工具（验证响应中可能引用 vault 内容）
9. 编辑修改指令 → 点击"修改" → Agent 按新指令重新生成
10. 编辑草稿 → 点击"发送" → 消息发到聊天
11. 在设置中选择 vault 目录 → 显示已连接及 .md 文件数量

- [ ] **Step 3: Commit (如有 fix)**

```bash
git add -A
git commit -m "fix: Phase 3 integration fixes"
```

---

## Self-Review

**1. Spec coverage:**

| 需求 | 任务 | 说明 |
|------|------|------|
| F10 斜杠命令触发 AI | Task 6 | 改为聊天头部"📋 总结"按钮触发 |
| F11 AI 总结→保存到本地 File API | Task 3 + Task 5 + Task 6 | saveToVault + SummaryPanel + "总结"按钮 |
| F12 从本地 vault 搜索.md | Task 1 + Task 4 + Task 7 | vault 模块 + searchVault 工具 + DraftPanel 开关 |
| F13 草稿编辑面板 | Task 7 | DraftPanel 完善：修改指令 + 搜索知识库开关 |

**2. Placeholder scan:** 无 TBD/TODO，所有步骤均有完整代码。

**3. Type consistency:**
- `Tool<TParams>` from `agent/types.ts` — saveToVault, searchVault, getRoomHistory 都符合该泛型
- `LLMConfig` from `agent/types.ts` — 在 DraftPanel、ChatPage 中使用一致
- `ChatMessage` from `api.ts` — 未改
- Vault API: `pickVault()`, `hasVault()`, `writeToVault()`, `searchInVault()`, `listVaultFiles()` — 在 vault.ts 定义，Settings.tsx、saveToVault.ts、searchVault.ts、ChatPage.tsx 中使用一致
- DraftPanel Props: 新增 `searchVault` 内部状态（不暴露到 Props），对调用方 ChatPage 无影响
- SummaryPanel Props: `summary`, `onClose`, `onSaveToVault`, `onSendToChat`, `savingVault` — ChatPage 传参全部匹配
