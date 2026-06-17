import { useState, useCallback, useEffect, useRef } from "react";
import { getLLMConfig, setLLMConfig, clearLLMConfig } from "./api";
import { pickVault, hasVault, listVaultFiles, isVaultSupported, uploadFileToVault, deleteUploadedFile, downloadVaultFile } from "./vault";

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
  const [vaultError, setVaultError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 初始化检查 vault 状态
  useEffect(() => {
    hasVault().then((ok) => {
      setVaultReady(ok);
      if (ok) listVaultFiles().then(setVaultFiles);
    });
  }, []);

  const handlePickVault = useCallback(async () => {
    setVaultError("");
    try {
      const ok = await pickVault();
      setVaultReady(ok);
      if (ok) {
        const files = await listVaultFiles();
        setVaultFiles(files);
      }
    } catch (err: any) {
      setVaultError(err.message || "选择目录失败");
    }
  }, []);

  const handleUploadFiles = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setVaultError("");
    try {
      await uploadFileToVault(file);
      setVaultFiles(await listVaultFiles());
      setVaultReady(true);
    } catch (err: any) {
      setVaultError(err.message || "上传失败");
    }
    e.target.value = "";
  }, []);

  const handleDelete = useCallback(async (path: string) => {
    await deleteUploadedFile(path);
    const remaining = await listVaultFiles();
    setVaultFiles(remaining);
    if (remaining.length === 0) setVaultReady(false);
  }, []);

  const handleDownload = useCallback(async (path: string) => {
    try {
      await downloadVaultFile(path);
    } catch (err: any) {
      setVaultError(err.message || "下载失败");
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
          className="w-full border rounded-lg px-3 py-2 mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-wechat"
          placeholder="https://api.openai.com/v1"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
        />

        <label className="block text-sm text-gray-600 mb-1">模型</label>
        <input
          className="w-full border rounded-lg px-3 py-2 mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-wechat"
          placeholder="gpt-4o 或 deepseek-chat 等"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        />

        <label className="block text-sm text-gray-600 mb-1">API Key</label>
        <input
          className="w-full border rounded-lg px-3 py-2 mb-4 text-sm focus:outline-none focus:ring-2 focus:ring-wechat"
          type="password"
          placeholder="sk-..."
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />

        {/* Vault 区域 */}
        <div className="border-t pt-4 mt-2 mb-4">
          <p className="text-xs text-gray-400 mb-2">
            选择本地知识库目录，AI 可搜索其中的 .md 文件。
          </p>
          {isVaultSupported() ? (
            <>
              <button
                onClick={handlePickVault}
                className="w-full border border-dashed border-gray-300 rounded-lg px-3 py-3 text-sm text-gray-600 hover:bg-gray-50 hover:border-wechat transition-colors"
              >
                {vaultReady ? "📁 更换知识库目录" : "📁 选择知识库目录"}
              </button>
            </>
          ) : (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept=".md"
                className="hidden"
                onChange={handleUploadFiles}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full border border-dashed border-gray-300 rounded-lg px-3 py-3 text-sm text-gray-600 hover:bg-gray-50 hover:border-wechat transition-colors"
              >
                + 添加 .md 文件
              </button>
              <p className="text-xs text-gray-400 mt-1">
                文件仅存储在本设备浏览器中，不会上传到服务器。
              </p>
              {vaultFiles.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {vaultFiles.map((path) => (
                    <li key={path} className="flex items-center gap-1 text-xs bg-gray-50 rounded-lg px-3 py-2">
                      <span className="flex-1 truncate text-gray-700">{path}</span>
                      <button
                        onClick={() => handleDownload(path)}
                        className="shrink-0 text-gray-400 hover:text-wechat p-1"
                        title="下载"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                      </button>
                      <button
                        onClick={() => handleDelete(path)}
                        className="shrink-0 text-gray-400 hover:text-red-500 p-1"
                        title="删除"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
          {vaultReady && isVaultSupported() && (
            <p className="text-xs text-green-600 mt-1">
              已连接 ({vaultFiles.length} 个 .md 文件)
            </p>
          )}
          {vaultError && (
            <p className="text-xs text-red-500 mt-1">{vaultError}</p>
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
            className="flex-1 bg-wechat text-white rounded-lg py-2 text-sm hover:bg-wechat-dark disabled:opacity-40"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
