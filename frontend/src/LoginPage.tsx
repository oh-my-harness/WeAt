import { useState } from "react";
import { login, setUserId, adminLogin } from "./api";

interface Props {
  onLogin: () => void;
}

export default function LoginPage({ onLogin }: Props) {
  const [mode, setMode] = useState<"user" | "admin">("user");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [adminToken, setAdminToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleUserLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("请输入用户名和密码");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await login(username.trim(), password);
      onLogin();
    } catch (err: any) {
      setError(err.message || "登录失败");
    } finally {
      setBusy(false);
    }
  };

  const handleAdminLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminToken.trim()) {
      setError("请输入管理员令牌");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const token = await adminLogin(adminToken.trim());
      // Store admin token for later use
      sessionStorage.setItem("weat_admin_token", adminToken.trim());
      onLogin();
    } catch (err: any) {
      setError(err.message || "管理员登录失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-full bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm mx-4">
        <h1 className="text-2xl font-bold text-center mb-1">WeAt</h1>
        <p className="text-gray-500 text-sm text-center mb-6">
          {mode === "user" ? "团队聊天" : "管理员控制台"}
        </p>

        {/* 模式切换 */}
        <div className="flex mb-6 bg-gray-100 rounded-lg p-0.5">
          <button
            onClick={() => { setMode("user"); setError(""); }}
            className={`flex-1 py-2 text-sm rounded-md transition-colors ${mode === "user" ? "bg-white shadow-sm font-medium" : "text-gray-500 hover:text-gray-700"}`}
          >
            用户登录
          </button>
          <button
            onClick={() => { setMode("admin"); setError(""); }}
            className={`flex-1 py-2 text-sm rounded-md transition-colors ${mode === "admin" ? "bg-white shadow-sm font-medium" : "text-gray-500 hover:text-gray-700"}`}
          >
            管理员登录
          </button>
        </div>

        {error && (
          <div className="bg-red-50 text-red-600 text-sm rounded-lg px-3 py-2 mb-4">
            {error}
          </div>
        )}

        {mode === "user" ? (
          <form onSubmit={handleUserLogin}>
            <input
              className="w-full border rounded-lg px-3 py-2 mb-3 focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="用户名"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
            />
            <input
              className="w-full border rounded-lg px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-blue-400"
              type="password"
              placeholder="密码"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="submit"
              disabled={busy}
              className="w-full bg-blue-600 text-white rounded-lg py-2.5 font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {busy ? "登录中…" : "登录"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleAdminLogin}>
            <input
              className="w-full border rounded-lg px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-blue-400"
              type="password"
              placeholder="管理员令牌"
              value={adminToken}
              onChange={(e) => setAdminToken(e.target.value)}
              autoFocus
            />
            <button
              type="submit"
              disabled={busy}
              className="w-full bg-green-600 text-white rounded-lg py-2.5 font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {busy ? "验证中…" : "进入管理控制台"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
