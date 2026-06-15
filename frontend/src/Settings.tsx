import { useState } from "react";
import { getLLMConfig, setLLMConfig, clearLLMConfig } from "./api";

interface Props {
  onClose: () => void;
}

export default function Settings({ onClose }: Props) {
  const existing = getLLMConfig();
  const [baseUrl, setBaseUrl] = useState(existing?.baseUrl || "");
  const [model, setModel] = useState(existing?.model || "");
  const [apiKey, setApiKey] = useState(existing?.apiKey || "");

  const handleSave = () => {
    if (baseUrl.trim() && model.trim() && apiKey.trim()) {
      setLLMConfig({ baseUrl: baseUrl.trim(), model: model.trim(), apiKey: apiKey.trim() });
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">设置</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

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
