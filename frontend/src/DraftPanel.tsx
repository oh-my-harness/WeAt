import { useState, useRef, useCallback } from "react";
import type { LLMConfig } from "./agent/types";
import { runAgent } from "./agent";
import { createGetRoomHistoryTool } from "./tools/getRoomHistory";

interface Props {
  roomId: string;
  llmConfig: LLMConfig;
  onClose: () => void;
  onSend: (text: string) => void;
}

export default function DraftPanel({ roomId, llmConfig, onClose, onSend }: Props) {
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<"idle" | "generating" | "editing">("idle");
  const [instruction, setInstruction] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const generate = useCallback(async (instruction: string) => {
    setStatus("generating");
    setDraft("");

    const ac = new AbortController();
    abortRef.current = ac;

    try {
      const text = await runAgent(
        {
          llm: llmConfig,
          systemPrompt: `你是一个团队聊天助手，帮助用户起草回复。

工具:
- get_room_history: 获取当前房间聊天历史

根据聊天历史和用户要求，起草一条合适的回复。
回复要简洁自然，符合对话上下文。
只用中文回复，除非原文是英文。`,
          tools: [createGetRoomHistoryTool(roomId)],
          maxTurns: 3,
        },
        instruction || "根据聊天历史，帮我起草一条回复",
        (event) => {
          if (event.type === "thinking" && event.text) {
            // 实时显示思考内容作为草稿
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
  }, [roomId, llmConfig]);

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

        {/* 修改指令 */}
        <div className="px-4 py-2 border-b">
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
              点击消息旁的"AI 起草"按钮开始
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
