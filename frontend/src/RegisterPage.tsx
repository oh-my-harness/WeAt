import { useState, useCallback } from "react";
import { registerUser } from "./api";

interface Props {
  onSuccess: () => void;
  onBack: () => void;
}

export default function RegisterPage({ onSuccess, onBack }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim() || !inviteCode.trim()) return;
    setBusy(true);
    setError("");
    try {
      await registerUser(username.trim(), password.trim(), inviteCode.trim());
      onSuccess();
    } catch (err: any) {
      setError(err.message || "注册失败");
    } finally {
      setBusy(false);
    }
  }, [username, password, inviteCode, onSuccess]);

  return (
    <div className="min-h-full flex items-center justify-center bg-gradient-to-br from-wechat-light to-green-100 px-4">
      <div className="bg-white rounded-2xl shadow-sm border w-full max-w-sm p-8">
        <h1 className="text-2xl font-bold text-center mb-2 text-gray-800">注册 WeAt</h1>
        <p className="text-sm text-center text-gray-400 mb-6">需要管理员提供的邀请码</p>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-4 text-sm text-red-600">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">用户名</label>
            <input
              className="w-full border rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-wechat"
              placeholder="3-32 个字符"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              autoComplete="username"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">密码</label>
            <input
              type="password"
              className="w-full border rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-wechat"
              placeholder="至少 6 位"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">邀请码</label>
            <input
              className="w-full border rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-wechat"
              placeholder="向管理员获取"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={busy || !username.trim() || !password.trim() || !inviteCode.trim()}
            className="w-full bg-wechat text-white rounded-xl py-2.5 font-medium hover:bg-wechat-dark disabled:opacity-40 transition-colors"
          >
            {busy ? "注册中…" : "注册"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-400 mt-4">
          已有账号？{" "}
          <button onClick={onBack} className="text-wechat hover:underline">
            登录
          </button>
        </p>
      </div>
    </div>
  );
}
