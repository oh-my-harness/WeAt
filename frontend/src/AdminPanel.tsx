import { useState } from "react";
import { adminCreateUser } from "./api";

interface Props {
  onClose: () => void;
}

export default function AdminPanel({ onClose }: Props) {
  const [adminToken, setAdminToken] = useState(
    sessionStorage.getItem("weat_admin_token") || ""
  );
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const handleCreate = async () => {
    if (!adminToken.trim()) { setMsg("请输入管理员令牌"); return; }
    if (!username.trim() || !password.trim()) { setMsg("请输入用户名和密码"); return; }
    setBusy(true);
    setMsg("");
    try {
      const uid = await adminCreateUser(adminToken.trim(), username.trim(), password);
      setMsg(`✅ 用户 ${uid} 创建成功`);
      setUsername("");
      setPassword("");
    } catch (err: any) {
      setMsg(`❌ ${err.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-6 max-w-md mx-auto">
      <h2 className="text-lg font-semibold mb-4">创建用户</h2>

      {msg && (
        <div className={`text-sm rounded-lg px-3 py-2 mb-4 ${msg.startsWith("✅") ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>
          {msg}
        </div>
      )}

      <label className="block text-sm text-gray-600 mb-1">管理员令牌</label>
      <input
        className="w-full border rounded-lg px-3 py-2 mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        type="password"
        placeholder="服务器的 ADMIN_TOKEN"
        value={adminToken}
        onChange={(e) => setAdminToken(e.target.value)}
      />

      <label className="block text-sm text-gray-600 mb-1">用户名</label>
      <input
        className="w-full border rounded-lg px-3 py-2 mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        placeholder="新用户的用户名"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
      />

      <label className="block text-sm text-gray-600 mb-1">密码</label>
      <input
        className="w-full border rounded-lg px-3 py-2 mb-4 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        type="password"
        placeholder="新用户的密码"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />

      <button
        onClick={handleCreate}
        disabled={busy}
        className="w-full bg-blue-600 text-white rounded-lg py-2 text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {busy ? "创建中…" : "创建用户"}
      </button>
    </div>
  );
}
