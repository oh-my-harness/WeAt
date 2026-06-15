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

interface Props {
  room: Room;
  messages: ChatMessage[];
  onAddMessage: (msg: ChatMessage) => void;
  onBack: () => void;
}

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
  const listRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const userId = getUserId();
  const llmConfig = getLLMConfig();

  // 加载历史消息
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
        // 去重：用 ref 避免闭包滞后
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

  // 自动滚动到底部
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages.length]);

  // 发送消息（乐观更新）
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
    handleSend(input);
  }, [handleSend, input]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleInputSend();
    }
  };

  // AI 起草
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

  // 显示消息时间
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
        <h1 className="font-semibold truncate">
          {room.name || room.room_id}
        </h1>
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
                  {/* 对方名字 */}
                  {!isMe && (
                    <div className="text-xs text-gray-400 mb-0.5">
                      {displayName(msg.sender)}
                    </div>
                  )}

                  {/* Markdown */}
                  <div className={`text-sm prose-message ${isMe ? "text-white" : "text-gray-900"}`}>
                    <Markdown>{msg.body}</Markdown>
                  </div>

                  {/* 时间 */}
                  <div className={`text-xs mt-1 flex items-center gap-1 ${isMe ? "text-blue-200" : "text-gray-400"}`}>
                    <span>{formatTime(msg.ts)}</span>
                    {msg.pending && <span>发送中…</span>}
                    {msg.failed && <span className="text-red-400">发送失败</span>}
                  </div>
                </div>

                {/* AI 起草按钮（悬浮在对方消息上） */}
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
    </>
  );
}
