import { useState, useEffect } from "react";
import { adminCreateUser, adminListUsers, adminDeleteUser, adminGetInviteCode } from "./api";

interface Props {
  onClose: () => void;
}

type Tab = "list" | "create" | "invite";

interface User {
  name: string;
  deactivated: boolean;
}

export default function AdminPanel({ onClose }: Props) {
  const [adminToken] = useState(
    sessionStorage.getItem("weat_admin_token") || ""
  );
  const [tab, setTab] = useState<Tab>("list");

  // list state
  const [users, setUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [listMsg, setListMsg] = useState("");

  // create state
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [createMsg, setCreateMsg] = useState("");

  // invite state
  const [inviteCode, setInviteCode] = useState<string | null>(null);
  const [inviteMsg, setInviteMsg] = useState("");

  const loadUsers = async () => {
    setLoadingUsers(true);
    setListMsg("");
    try {
      const list = await adminListUsers(adminToken);
      setUsers(list);
    } catch (err: any) {
      setListMsg(`❌ ${err.message}`);
    } finally {
      setLoadingUsers(false);
    }
  };

  useEffect(() => {
    if (tab === "list") loadUsers();
    if (tab === "invite") {
      adminGetInviteCode(adminToken)
        .then((r) => { setInviteCode(r.invite_code); setInviteMsg(r.message || ""); })
        .catch((e) => setInviteMsg(e.message));
    }
  }, [tab]);

  const handleDelete = async (userId: string) => {
    if (!confirm(`确定停用用户 ${userId}？此操作不可逆。`)) return;
    try {
      await adminDeleteUser(adminToken, userId);
      setUsers((prev) => prev.filter((u) => u.name !== userId));
    } catch (err: any) {
      setListMsg(`❌ ${err.message}`);
    }
  };

  const handleCreate = async () => {
    if (!username.trim() || !password.trim()) {
      setCreateMsg("请输入用户名和密码");
      return;
    }
    setBusy(true);
    setCreateMsg("");
    try {
      const uid = await adminCreateUser(adminToken, username.trim(), password);
      setCreateMsg(`✅ 用户 ${uid} 创建成功`);
      setUsername("");
      setPassword("");
    } catch (err: any) {
      setCreateMsg(`❌ ${err.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h2 className="text-lg font-semibold mb-4">用户管理</h2>

      {/* Tabs */}
      <div className="flex border-b mb-4">
        {(["list", "create", "invite"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-wechat text-wechat"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "list" ? "用户列表" : t === "create" ? "创建用户" : "邀请码"}
          </button>
        ))}
      </div>

      {tab === "list" && (
        <div>
          {listMsg && (
            <div className="text-sm rounded-lg px-3 py-2 mb-4 bg-red-50 text-red-600">
              {listMsg}
            </div>
          )}
          <div className="flex justify-end mb-3">
            <button
              onClick={loadUsers}
              disabled={loadingUsers}
              className="text-sm text-wechat hover:text-wechat-dark disabled:opacity-50"
            >
              {loadingUsers ? "加载中…" : "刷新"}
            </button>
          </div>
          {users.length === 0 && !loadingUsers && !listMsg && (
            <div className="text-gray-400 text-sm text-center py-8">暂无用户</div>
          )}
          <div className="space-y-1">
            {users.map((u) => (
              <div
                key={u.name}
                className="flex items-center justify-between px-3 py-2 rounded-lg border bg-white hover:bg-gray-50"
              >
                <div>
                  <span className="text-sm font-mono">{u.name}</span>
                  {u.deactivated && (
                    <span className="ml-2 text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                      已停用
                    </span>
                  )}
                </div>
                {!u.deactivated && (
                  <button
                    onClick={() => handleDelete(u.name)}
                    className="text-xs text-red-500 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50 transition-colors"
                  >
                    停用
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "create" && (
        <div>
          {createMsg && (
            <div
              className={`text-sm rounded-lg px-3 py-2 mb-4 ${
                createMsg.startsWith("✅")
                  ? "bg-green-50 text-green-700"
                  : "bg-red-50 text-red-600"
              }`}
            >
              {createMsg}
            </div>
          )}

          <label className="block text-sm text-gray-600 mb-1">用户名</label>
          <input
            className="w-full border rounded-lg px-3 py-2 mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-wechat"
            placeholder="新用户的用户名"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />

          <label className="block text-sm text-gray-600 mb-1">密码</label>
          <input
            className="w-full border rounded-lg px-3 py-2 mb-4 text-sm focus:outline-none focus:ring-2 focus:ring-wechat"
            type="password"
            placeholder="新用户的密码"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <button
            onClick={handleCreate}
            disabled={busy}
            className="w-full bg-wechat text-white rounded-lg py-2 text-sm hover:bg-wechat-dark disabled:opacity-50 transition-colors"
          >
            {busy ? "创建中…" : "创建用户"}
          </button>
        </div>
      )}

      {tab === "invite" && (
        <div className="p-4">
          <p className="text-sm text-gray-600 mb-3">当前邀请码（分享给需要注册的用户）：</p>
          {inviteCode ? (
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-gray-100 rounded-lg px-3 py-2 text-sm font-mono select-all">
                {inviteCode}
              </code>
              <button
                onClick={() => navigator.clipboard.writeText(inviteCode)}
                className="border rounded-lg px-3 py-2 text-sm hover:bg-gray-50"
              >
                复制
              </button>
            </div>
          ) : (
            <p className="text-sm text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
              {inviteMsg || "未设置 INVITE_CODE 环境变量，注册功能已禁用"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
