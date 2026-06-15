import { useEffect, useRef, useState, useCallback } from "react";
import Markdown from "react-markdown";
import {
  Room,
  ChatMessage,
  fetchMessages,
  sendMessage,
  getUserId,
} from "./api";

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
  const listRef = useRef<HTMLDivElement>(null);
  const userId = getUserId();

  // 加载历史消息
  useEffect(() => {
    setLoading(true);
    fetchMessages(room.room_id, 50)
      .then((mxMsgs) => {
        const msgs: ChatMessage[] = mxMsgs.map((m) => ({
          id: m.event_id,
          room_id: room.room_id,
          sender: m.sender,
          body: m.content?.body || "",
          ts: m.origin_server_ts,
          pending: false,
        }));
        // 去重：保留已有的（包括乐观更新的）
        const existingIds = new Set(messages.map((m) => m.id));
        const newMsgs = msgs.filter((m) => !existingIds.has(m.id));
        // 按时间排序后全部塞入
        const merged = [...messages.filter((m) => m.room_id === room.room_id), ...newMsgs];
        merged.sort((a, b) => a.ts - b.ts);
        // 用 onAddMessage 批量添加新消息
        newMsgs.forEach((m) => onAddMessage(m));
        setLoading(false);
      })
      .catch((e) => {
        console.error("Failed to load messages", e);
        setLoading(false);
      });
  }, [room.room_id]);

  // 自动滚动到底部
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages.length]);

  // 发送消息（乐观更新）
  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;

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
      // 替换临时 ID
      onAddMessage({ ...optimistic, id: result.event_id, pending: false });
    } catch (e) {
      console.error("Send failed", e);
      // 标记为发送失败
      onAddMessage({ ...optimistic, pending: false });
    } finally {
      setSending(false);
    }
  }, [input, sending, room.room_id, userId, onAddMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 显示消息时间
  const formatTime = (ts: number) => {
    const d = new Date(ts);
    const pad = (n: number) => n.toString().padStart(2, "0");
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  // 提取简单显示名
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
              className={`flex ${isMe ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] sm:max-w-[70%] rounded-2xl px-3 py-2 ${
                  isMe
                    ? "bg-blue-600 text-white rounded-br-md"
                    : "bg-white border rounded-bl-md"
                } ${msg.pending ? "opacity-60" : ""}`}
              >
                {/* 发送者名字 */}
                {!isMe && (
                  <div className="text-xs text-gray-400 mb-0.5">
                    {displayName(msg.sender)}
                  </div>
                )}

                {/* Markdown 内容 */}
                <div className={`text-sm prose-message ${isMe ? "text-white" : "text-gray-900"}`}>
                  <Markdown>{msg.body}</Markdown>
                </div>

                {/* 时间戳 + 状态 */}
                <div
                  className={`text-xs mt-1 flex items-center gap-1 ${
                    isMe ? "text-blue-200" : "text-gray-400"
                  }`}
                >
                  <span>{formatTime(msg.ts)}</span>
                  {msg.pending && <span>发送中…</span>}
                </div>
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
            onClick={handleSend}
            disabled={!input.trim() || sending}
            className="bg-blue-600 text-white rounded-xl px-4 py-2 hover:bg-blue-700 disabled:opacity-40 transition-colors shrink-0"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19V5m0 0l-7 7m7-7l7 7" />
            </svg>
          </button>
        </div>
      </div>
    </>
  );
}
