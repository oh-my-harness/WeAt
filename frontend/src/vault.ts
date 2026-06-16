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
    const handle = await (window as any).showDirectoryPicker({ mode: "readwrite" });
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

/** 将内容写入 vault 的 .md 文件（覆盖或创建）。
 *  filePath 支持子目录路径，如 "wiki/projects/项目名.md" 或 "2026-06-16-周报"。
 *  子目录会自动创建（如果不存在）。 */
export async function writeToVault(filePath: string, content: string): Promise<void> {
  const dirHandle = await getVaultHandle();
  if (!dirHandle) throw new Error("未选择 vault 目录。请先在设置中选择本地知识库目录。");

  const fullPath = filePath.endsWith(".md") ? filePath : `${filePath}.md`;
  const parts = fullPath.split("/").filter(Boolean);
  const fileName = parts.pop()!;

  // 逐层获取/创建子目录
  let current = dirHandle;
  for (const part of parts) {
    current = await current.getDirectoryHandle(part, { create: true });
  }

  const fileHandle = await current.getFileHandle(fileName, { create: true });
  const writable = await fileHandle.createWritable();
  await writable.write(content);
  await writable.close();
}

/**
 * 递归搜索 vault 中所有 .md 文件，返回匹配结果。
 * 可指定 subDir 限定搜索子目录（如 "wiki/entities"），不传则全量递归。
 */
/** 从 Markdown 文本中提取 YAML frontmatter 的 type 字段，默认返回 "note" */
function extractFrontmatterType(text: string): string {
  const fmMatch = text.match(/^---\n([\s\S]*?)\n---/);
  if (!fmMatch) return "note";
  const typeMatch = fmMatch[1].match(/^type:\s*(\S+)/m);
  return typeMatch ? typeMatch[1] : "note";
}

export async function searchInVault(
  keyword: string,
  subDir?: string,
): Promise<Array<{ fileName: string; snippet: string; path: string; noteType: string }>> {
  const dirHandle = await getVaultHandle();
  if (!dirHandle) throw new Error("未选择 vault 目录。请先在设置中选择本地知识库目录。");

  let searchRoot: FileSystemDirectoryHandle = dirHandle;
  if (subDir) {
    const parts = subDir.split("/").filter(Boolean);
    for (const part of parts) {
      searchRoot = await searchRoot.getDirectoryHandle(part);
    }
  }

  const results: Array<{ fileName: string; snippet: string; path: string; noteType: string }> = [];
  const lowerKeyword = keyword.toLowerCase();

  async function walk(dir: FileSystemDirectoryHandle, prefix: string): Promise<void> {
    for await (const [name, handle] of (dir as any).entries()) {
      if (handle.kind === "directory") {
        await walk(handle as FileSystemDirectoryHandle, prefix ? `${prefix}/${name}` : name);
      } else if (name.endsWith(".md")) {
        const file = await (handle as FileSystemFileHandle).getFile();
        const text = await file.text();
        const idx = text.toLowerCase().indexOf(lowerKeyword);
        if (idx >= 0) {
          const start = Math.max(0, idx - 60);
          const end = Math.min(text.length, idx + keyword.length + 60);
          const snippet =
            (start > 0 ? "…" : "") +
            text.slice(start, end).replace(/\n+/g, " ") +
            (end < text.length ? "…" : "");
          results.push({ fileName: name, snippet, path: prefix ? `${prefix}/${name}` : name, noteType: extractFrontmatterType(text) });
        }
      }
    }
  }

  await walk(searchRoot, subDir || "");
  return results;
}

/** 读取 vault 中某个路径的 .md 文件内容（支持子目录路径如 "wiki/entities/某人.md"） */
export async function readFromVault(filePath: string): Promise<string> {
  const dirHandle = await getVaultHandle();
  if (!dirHandle) throw new Error("未选择 vault 目录。");

  const parts = filePath.split("/").filter(Boolean);
  const fileName = parts.pop()!;
  let current = dirHandle;
  for (const part of parts) {
    current = await current.getDirectoryHandle(part);
  }
  const fileHandle = await current.getFileHandle(fileName);
  const file = await fileHandle.getFile();
  return file.text();
}

/** 递归列出 vault 中所有 .md 文件的相对路径 */
export async function listVaultFiles(): Promise<string[]> {
  const dirHandle = await getVaultHandle();
  if (!dirHandle) return [];

  const files: string[] = [];

  async function walk(dir: FileSystemDirectoryHandle, prefix: string): Promise<void> {
    for await (const [name, handle] of (dir as any).entries()) {
      if (handle.kind === "directory") {
        await walk(handle as FileSystemDirectoryHandle, prefix ? `${prefix}/${name}` : name);
      } else if (name.endsWith(".md")) {
        files.push(prefix ? `${prefix}/${name}` : name);
      }
    }
  }

  await walk(dirHandle, "");
  return files;
}

/** 返回 vault 目录结构树（仅目录名，用于 Agent 了解 vault 布局） */
export async function listVaultTree(): Promise<string[]> {
  const dirHandle = await getVaultHandle();
  if (!dirHandle) return [];

  const dirs: string[] = [];

  async function walk(dir: FileSystemDirectoryHandle, prefix: string): Promise<void> {
    for await (const [name, handle] of (dir as any).entries()) {
      if (handle.kind === "directory") {
        const fullPath = prefix ? `${prefix}/${name}` : name;
        dirs.push(fullPath);
        await walk(handle as FileSystemDirectoryHandle, fullPath);
      }
    }
  }

  await walk(dirHandle, "");
  return dirs;
}
