import { useState, useCallback, useEffect } from "react";

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

  useEffect(() => {
    setText(summary);
  }, [summary]);

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
            className="w-full h-60 resize-none border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-wechat"
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
            className="flex-1 bg-wechat text-white rounded-xl py-2 text-sm hover:bg-wechat-dark disabled:opacity-40 transition-colors"
          >
            发送到聊天
          </button>
        </div>
      </div>
    </div>
  );
}
