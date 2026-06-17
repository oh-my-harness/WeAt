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
  const summaryClosedRef = useRef(false);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const userId = getUserId();
  const llmConfig = getLLMConfig();
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const onResize = () => {
      const diff = window.innerHeight - vv.height - vv.offsetTop;
      setKeyboardHeight(diff > 0 ? diff : 0);
    };
    vv.addEventListener("resize", onResize);
    vv.addEventListener("scroll", onResize);
    return () => {
      vv.removeEventListener("resize", onResize);
      vv.removeEventListener("scroll", onResize);
    };
  }, []);

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
        const newMsgs = msgs
          .filter((m) => !existingIds.has(m.id))
          .sort((a, b) => a.ts - b.ts);
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

    summaryClosedRef.current = false;
    setSummaryState({ text: "", busy: true });

    try {
      const result = await runAgent(
        {
          llm: llmConfig,
          systemPrompt: `你是一个团队聊天助手，帮助用户总结群聊对话。

## 工具

- get_room_history: 获取当前房间聊天历史（参数 limit 控制条数）
- search_vault: 搜索本地知识库中的相关笔记（自动试同义词 / 按类型分组 / 支持子目录）

## 工作流程

1. **扫描对话**：get_room_history 获取最近 ${SUMMARY_MESSAGE_COUNT} 条消息
2. **搜索知识库**：search_vault 查找相关背景
   - 先 search_vault("") 了解目录结构
   - 提取消息中的核心实体/概念，逐个搜索
3. **输出摘要**：直接返回 Markdown 正文，不要保存，不要输出 YAML frontmatter

## 输出格式

## For future Claude
<2-3 句话：这段对话的核心内容、关键决策、后续行动>

## 要点
- ...

## 待办
- [ ] ...

## 关键决策
- ...

## 涉及人员与项目
- ...

用 [[Wikilink]] 链接知识库中已有的人、项目、概念。只返回上述 Markdown 正文，不调用 save_to_vault。`,
          tools: [
            createGetRoomHistoryTool(room.room_id),
            createSearchVaultTool(),
          ],
          maxTurns: 8,
        },
        `请总结本房间最近 ${SUMMARY_MESSAGE_COUNT} 条聊天消息，并搜索知识库补充相关背景。只返回摘要文本，不要保存。`,
        () => {},
      );

      if (!summaryClosedRef.current) {
        setSummaryState({ text: result, busy: false });
      }
    } catch (err: any) {
      if (!summaryClosedRef.current) {
        setSummaryState({ text: `Error: ${err.message}`, busy: false });
      }
    }
  }, [llmConfig, room.room_id]);

  // ── SummaryPanel 回调 ────────────────────────────────────────
  const handleSaveToVault = useCallback(async (content: string) => {
    setSavingVault(true);
    try {
      const { writeToVault } = await import("./vault");
      const now = new Date();
      const dateStr = now.toISOString().slice(0, 10);
      const pad = (n: number) => n.toString().padStart(2, "0");
      const timeStr = `${pad(now.getHours())}${pad(now.getMinutes())}`;
      const frontmatter = `---\ndate: ${dateStr}\ntype: chat-summary\ntags: []\nai-first: true\n---\n\n`;
      await writeToVault(`${dateStr}-${timeStr}-${room.name || room.room_id.slice(0, 8)}-总结`, frontmatter + content);
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
            className="shrink-0 border border-gray-300 rounded-lg px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 hover:border-wechat disabled:opacity-40 transition-colors"
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
          const senderName = displayName(msg.sender);
          const avatarColors = ["bg-red-400","bg-orange-400","bg-amber-400","bg-green-500","bg-teal-500","bg-wechat-light0","bg-violet-500","bg-pink-500"];
          const avatarColor = avatarColors[senderName.charCodeAt(0) % avatarColors.length];
          return (
            <div
              key={msg.id}
              className={`group flex items-end gap-2 ${isMe ? "justify-end" : "justify-start"}`}
            >
              {/* 对方头像 */}
              {!isMe && (
                <div className={`shrink-0 w-8 h-8 rounded-full ${avatarColor} flex items-center justify-center text-white text-xs font-semibold mb-1`}>
                  {senderName.charAt(0).toUpperCase()}
                </div>
              )}

              <div className="relative max-w-[75%] sm:max-w-[65%]">
                <div
                  className={`rounded-2xl px-3 py-2 ${
                    isMe
                      ? "bg-wechat text-white rounded-br-md"
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

                  <div className={`text-xs mt-1 flex items-center gap-1 ${isMe ? "text-wechat-light" : "text-gray-400"}`}>
                    <span>{formatTime(msg.ts)}</span>
                    {msg.pending && <span>发送中…</span>}
                    {msg.failed && <span className="text-red-400">发送失败</span>}
                  </div>
                </div>

                {/* AI 起草按钮 */}
                {!isMe && !msg.pending && (
                  <button
                    onClick={() => handleAIDraft(msg.body)}
                    className="absolute -top-2 -right-2 opacity-0 group-hover:opacity-100 bg-white border rounded-full p-1 shadow hover:bg-wechat-light transition-opacity"
                    title="AI 起草回复"
                  >
                    <svg className="w-3.5 h-3.5 text-wechat" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </button>
                )}
              </div>

              {/* 自己占位（保持对齐） */}
              {isMe && <div className="w-8 shrink-0" />}
            </div>
          );
        })}
      </div>

      {/* 输入区 */}
      <div
        className="px-4 py-3 border-t bg-white shrink-0"
        style={{ paddingBottom: `calc(0.75rem + ${keyboardHeight}px)` }}
      >
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息…"
            rows={1}
            className="flex-1 border rounded-xl px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-wechat text-sm max-h-32"
          />
          <button
            onClick={handleInputSend}
            disabled={!input.trim() || sending}
            className="bg-wechat text-white rounded-xl px-4 py-2 hover:bg-wechat-dark disabled:opacity-40 transition-colors shrink-0"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19V5m0 0l-7 7m7-7l7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* FAB：AI 起草 */}
      {llmConfig && draftTarget === null && (
        <button
          onClick={() => handleAIDraft("")}
          className="fixed bottom-20 right-4 md:absolute md:bottom-20 md:right-6 z-20 w-12 h-12 bg-wechat hover:bg-wechat-dark text-white rounded-full shadow-lg flex items-center justify-center transition-colors active:scale-95"
          title="AI 起草回复"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </button>
      )}

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
          onClose={() => {
            summaryClosedRef.current = true;
            setSummaryState(null);
          }}
          onSaveToVault={handleSaveToVault}
          onSendToChat={handleSummarySend}
          savingVault={savingVault}
        />
      )}
    </>
  );
}
