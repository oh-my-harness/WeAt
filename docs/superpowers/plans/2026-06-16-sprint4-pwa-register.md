# Sprint 4: PWA + 自助注册（邀请码）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 WeAt 可以安装到手机主屏幕（PWA），并支持用户通过邀请码自助注册，无需管理员手动创建账号。

**Architecture:** PWA 通过 `manifest.json` + Service Worker 实现（Service Worker 做 App Shell 缓存，离线显示"网络不可用"）。注册在后端验证邀请码（`INVITE_CODE` 环境变量），通过 Matrix API 创建用户。Tuwunel 已配置 `TUWUNEL_ALLOW_REGISTRATION=true`，直接可用。

**Tech Stack:** Web App Manifest, Service Worker Cache API, FastAPI, Matrix Client-Server API (`/_matrix/client/v3/register`)

---

## 文件清单

| 操作 | 文件 | 改动 |
|------|------|------|
| Create | `frontend/public/manifest.json` | PWA manifest |
| Create | `frontend/public/sw.js` | Service Worker（App Shell 缓存） |
| Modify | `frontend/index.html` | 添加 manifest link + SW 注册 script |
| Modify | `backend/matrix_api.py` | 添加 `register_user(username, password)` |
| Modify | `backend/main.py` | 添加 `POST /api/register` 端点 + `INVITE_CODE` 配置 |
| Modify | `frontend/src/api.ts` | 添加 `registerUser(username, password, inviteCode)` |
| Create | `frontend/src/RegisterPage.tsx` | 注册表单 |
| Modify | `frontend/src/LoginPage.tsx` | 添加"注册"链接 |
| Modify | `frontend/src/App.tsx` | 添加 "register" page state |
| Modify | `frontend/src/AdminPanel.tsx` | 添加"邀请码"Tab |

---

### Task 1: PWA manifest.json

**Files:**
- Create: `frontend/public/manifest.json`

- [ ] **Step 1: 创建 manifest**

  ```json
  {
    "name": "WeAt",
    "short_name": "WeAt",
    "description": "团队聊天 + AI 副驾驶",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#ffffff",
    "theme_color": "#07C160",
    "orientation": "portrait",
    "icons": [
      {
        "src": "/icon-192.png",
        "sizes": "192x192",
        "type": "image/png",
        "purpose": "maskable any"
      },
      {
        "src": "/icon-512.png",
        "sizes": "512x512",
        "type": "image/png",
        "purpose": "maskable any"
      }
    ]
  }
  ```

- [ ] **Step 2: 创建占位图标**

  暂用纯色 PNG 作为图标（实际部署前替换）。在 `frontend/public/` 下创建两个文件。最快方式：用 `canvas` 生成，或直接用 Vite 的 `favicon.ico` 先占位。

  ```bash
  # 用 ImageMagick 创建简单绿色方块图标（如没有 ImageMagick 可跳过，先用 favicon 替代）
  cd frontend/public
  # 检查是否有 ImageMagick
  if command -v convert &>/dev/null; then
    convert -size 192x192 xc:#07C160 icon-192.png
    convert -size 512x512 xc:#07C160 icon-512.png
    echo "图标创建完成"
  else
    # 没有 ImageMagick：复制 favicon 作为占位（PWA 仍可安装，只是图标是默认的）
    cp favicon.ico icon-192.png 2>/dev/null || touch icon-192.png
    cp favicon.ico icon-512.png 2>/dev/null || touch icon-512.png
    echo "占位图标（需后续替换）"
  fi
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/public/manifest.json frontend/public/icon-192.png frontend/public/icon-512.png
  git commit -m "feat(pwa): add web app manifest"
  ```

---

### Task 2: Service Worker

**Files:**
- Create: `frontend/public/sw.js`

- [ ] **Step 1: 创建 App Shell 缓存 Service Worker**

  ```js
  const CACHE_NAME = "weat-v1";
  const SHELL = ["/", "/index.html"];

  self.addEventListener("install", (e) => {
    e.waitUntil(
      caches.open(CACHE_NAME).then((c) => c.addAll(SHELL))
    );
    self.skipWaiting();
  });

  self.addEventListener("activate", (e) => {
    e.waitUntil(
      caches.keys().then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
      )
    );
    self.clients.claim();
  });

  self.addEventListener("fetch", (e) => {
    // 只缓存导航请求（HTML shell）；API / WS 请求直接走网络
    if (e.request.mode === "navigate") {
      e.respondWith(
        fetch(e.request).catch(() =>
          caches.match("/index.html").then(
            (cached) =>
              cached ||
              new Response("<h1>网络不可用</h1><p>请检查网络连接后刷新。</p>", {
                headers: { "Content-Type": "text/html; charset=utf-8" },
              })
          )
        )
      );
    }
  });
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/public/sw.js
  git commit -m "feat(pwa): add service worker with app shell cache"
  ```

---

### Task 3: index.html PWA 配置

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: 添加 manifest link + iOS meta + SW 注册**

  读取 `frontend/index.html`，在 `<head>` 内添加：

  ```html
  <!-- PWA -->
  <link rel="manifest" href="/manifest.json" />
  <meta name="theme-color" content="#07C160" />
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-status-bar-style" content="default" />
  <meta name="apple-mobile-web-app-title" content="WeAt" />
  <link rel="apple-touch-icon" href="/icon-192.png" />
  ```

  在 `</body>` 前添加：

  ```html
  <script>
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js');
      });
    }
  </script>
  ```

- [ ] **Step 2: 验证 PWA 可安装**

  运行 `npm run dev`，打开 Chrome DevTools → Application → Manifest，确认 manifest 加载成功，图标显示，可以点"安装"。

  移动端用 Safari 打开 `http://<本机IP>:5173`（需要 HTTPS 或 localhost），点"分享 → 添加到主屏幕"，确认能添加。

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/index.html
  git commit -m "feat(pwa): add manifest link, iOS meta tags, and service worker registration"
  ```

---

### Task 4: 后端 matrix_api.py — register_user

**Files:**
- Modify: `backend/matrix_api.py`

- [ ] **Step 1: 添加 register_user 函数**

  在 `matrix_api.py` 末尾添加：

  ```python
  async def register_user(username: str, password: str) -> dict[str, Any]:
      """通过 Matrix API 注册新用户（需要 Tuwunel ALLOW_REGISTRATION=true）。"""
      return await _post(
          "/_matrix/client/v3/register",
          json={
              "kind": "user",
              "username": username,
              "password": password,
              "auth": {"type": "m.login.dummy"},
          },
      )
  ```

- [ ] **Step 2: 手动测试**

  在本机启动后，直接用 curl 测试（用于验证 Tuwunel 接受 dummy auth）：

  ```bash
  curl -s -X POST http://localhost:8008/_matrix/client/v3/register \
    -H "Content-Type: application/json" \
    -d '{"kind":"user","username":"testregister123","password":"test1234","auth":{"type":"m.login.dummy"}}' | python3 -m json.tool
  ```

  预期：返回 `{"user_id": "@testregister123:localhost", "access_token": "...", ...}`

  如果返回 `M_FORBIDDEN` 或 `M_UNKNOWN`，说明 Tuwunel 配置需要调整：检查 `docker-compose.yml` 确认 `TUWUNEL_ALLOW_REGISTRATION=true` 已生效（重启 matrix container 后再试）。

- [ ] **Step 3: Commit**

  ```bash
  git add backend/matrix_api.py
  git commit -m "feat(register): add register_user to matrix_api"
  ```

---

### Task 5: 后端 main.py — /api/register 端点

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 添加 RegisterRequest model 和 INVITE_CODE 配置**

  在 `main.py` 的 Pydantic models 区（约第 35 行），在 `SendMessageRequest` 后添加：

  ```python
  class RegisterRequest(BaseModel):
      username: str
      password: str
      invite_code: str
  ```

  在 `ADMIN_TOKEN = os.environ.get(...)` 那一行附近，添加：

  ```python
  INVITE_CODE = os.environ.get("INVITE_CODE", "")
  ```

- [ ] **Step 2: 添加注册端点**

  在 `# ── Admin API ──` 区块之前，添加：

  ```python
  @app.post("/api/register")
  async def register(req: RegisterRequest):
      """邀请码注册新用户。需设置 INVITE_CODE 环境变量。"""
      if not INVITE_CODE:
          raise HTTPException(status_code=503, detail="Registration is disabled")
      if req.invite_code != INVITE_CODE:
          raise HTTPException(status_code=403, detail="Invalid invite code")
      if len(req.username) < 3 or len(req.username) > 32:
          raise HTTPException(status_code=400, detail="Username must be 3-32 characters")
      if len(req.password) < 6:
          raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
      try:
          result = await matrix_api.register_user(req.username, req.password)
          return {"user_id": result.get("user_id", "")}
      except Exception as e:
          logger.warning("Registration failed for %s: %s", req.username, e)
          raise HTTPException(status_code=400, detail=str(e))
  ```

- [ ] **Step 3: 验证端点**

  设置环境变量后测试：

  ```bash
  INVITE_CODE=test123 uv run uvicorn backend.main:app --reload

  curl -s -X POST http://localhost:8000/api/register \
    -H "Content-Type: application/json" \
    -d '{"username":"newuser1","password":"pass123","invite_code":"test123"}' | python3 -m json.tool
  ```

  预期：`{"user_id": "@newuser1:localhost"}`

  测试错误码：
  ```bash
  # 错误邀请码 → 403
  curl -s -X POST http://localhost:8000/api/register \
    -d '{"username":"x","password":"pass123","invite_code":"wrong"}' \
    -H "Content-Type: application/json" | python3 -m json.tool

  # INVITE_CODE 未设置 → 503
  uv run uvicorn backend.main:app  # 不设环境变量
  curl -s -X POST http://localhost:8000/api/register \
    -d '{"username":"x","password":"pass123","invite_code":"abc"}' \
    -H "Content-Type: application/json" | python3 -m json.tool
  ```

- [ ] **Step 4: Commit**

  ```bash
  git add backend/main.py
  git commit -m "feat(register): add /api/register endpoint with invite code validation"
  ```

---

### Task 6: 前端 api.ts — registerUser 函数

**Files:**
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: 添加 registerUser 函数**

  在 `api.ts` 中找到 `login` 函数附近，添加：

  ```ts
  export async function registerUser(
    username: string,
    password: string,
    inviteCode: string
  ): Promise<{ user_id: string }> {
    const res = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, invite_code: inviteCode }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `Register failed: ${res.status}`);
    }
    return res.json();
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/src/api.ts
  git commit -m "feat(register): add registerUser API function"
  ```

---

### Task 7: RegisterPage.tsx

**Files:**
- Create: `frontend/src/RegisterPage.tsx`

- [ ] **Step 1: 创建注册页**

  ```tsx
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
      <div className="min-h-full flex items-center justify-center bg-gray-50 px-4">
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
                placeholder="3-32 个字符，字母/数字/下划线"
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
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/src/RegisterPage.tsx
  git commit -m "feat(register): add RegisterPage component"
  ```

---

### Task 8: LoginPage + App.tsx 接入注册流程

**Files:**
- Modify: `frontend/src/LoginPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: LoginPage 添加"注册"链接**

  读取 `frontend/src/LoginPage.tsx`，在提交按钮下方（或表单底部）添加：

  ```tsx
  {onRegister && (
    <p className="text-center text-sm text-gray-400 mt-4">
      没有账号？{" "}
      <button onClick={onRegister} className="text-wechat hover:underline">
        用邀请码注册
      </button>
    </p>
  )}
  ```

  同时在 `LoginPage` 的 `Props` 接口中添加：

  ```ts
  onRegister?: () => void;
  ```

- [ ] **Step 2: App.tsx 添加 register page**

  在 `App.tsx` 中：

  1. 在 `type Page` 中添加 `"register"` ：
     ```ts
     type Page = "login" | "rooms" | "chat" | "admin" | "register";
     ```

  2. 在 `handleLogin` 后添加：
     ```ts
     const handleRegistered = useCallback(() => {
       // 注册成功后跳回登录页
       setPage("login");
     }, []);
     ```

  3. 在渲染 `<LoginPage>` 时添加 `onRegister` prop：
     ```tsx
     if (page === "login") {
       return <LoginPage onLogin={handleLogin} onRegister={() => setPage("register")} />;
     }
     ```

  4. 在 `login` 判断后，`admin` 判断前，添加注册页：
     ```tsx
     if (page === "register") {
       return (
         <RegisterPage
           onSuccess={handleRegistered}
           onBack={() => setPage("login")}
         />
       );
     }
     ```

  5. 在 App.tsx 顶部 import 中添加：
     ```ts
     import RegisterPage from "./RegisterPage";
     ```

- [ ] **Step 3: 验证完整注册流程**

  1. 确认后端已设置 `INVITE_CODE` 环境变量（例如 `INVITE_CODE=weat2026`）
  2. 打开登录页，点"用邀请码注册"
  3. 填写用户名、密码、邀请码，点"注册"
  4. 注册成功后跳转回登录页，用新账号登录，确认能进入房间列表

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/LoginPage.tsx frontend/src/App.tsx
  git commit -m "feat(register): wire RegisterPage into app flow via LoginPage"
  ```

---

### Task 9: AdminPanel 显示邀请码

**Files:**
- Modify: `frontend/src/AdminPanel.tsx`

- [ ] **Step 1: 添加后端 /api/invite-code 端点**

  在 `backend/main.py` 的 Admin API 区块，添加：

  ```python
  @app.get("/api/invite-code")
  async def get_invite_code(_: None = Depends(verify_admin)):
      """管理员查看当前邀请码。"""
      if not INVITE_CODE:
          return {"invite_code": None, "message": "Registration disabled (INVITE_CODE not set)"}
      return {"invite_code": INVITE_CODE}
  ```

- [ ] **Step 2: 在前端 api.ts 添加 adminGetInviteCode**

  ```ts
  export async function adminGetInviteCode(adminToken: string): Promise<{ invite_code: string | null; message?: string }> {
    const res = await fetch(`/api/invite-code?token=${encodeURIComponent(adminToken)}`);
    if (!res.ok) throw new Error(`Failed: ${res.status}`);
    return res.json();
  }
  ```

- [ ] **Step 3: 在 AdminPanel 添加"邀请码"Tab**

  在 `AdminPanel.tsx` 中：

  1. 在 `type Tab = "list" | "create"` 改为 `type Tab = "list" | "create" | "invite"`
  2. 在 Tab 切换 UI 中添加"邀请码"按钮（与"用户列表"/"创建用户"并列）
  3. 添加邀请码 state 和 effect：

  ```tsx
  const [inviteCode, setInviteCode] = useState<string | null>(null);
  const [inviteMsg, setInviteMsg] = useState("");

  useEffect(() => {
    if (tab === "invite") {
      import("./api").then(({ adminGetInviteCode }) =>
        adminGetInviteCode(adminToken)
          .then((r) => {
            setInviteCode(r.invite_code);
            setInviteMsg(r.message || "");
          })
          .catch((e) => setInviteMsg(e.message))
      );
    }
  }, [tab, adminToken]);
  ```

  4. 在 Tab 内容渲染中添加邀请码 Tab 内容：

  ```tsx
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
  ```

- [ ] **Step 4: 验证**

  以管理员身份登录，打开管理面板，点"邀请码"Tab，确认显示当前 `INVITE_CODE` 值，点"复制"复制到剪贴板。

- [ ] **Step 5: Commit**

  ```bash
  git add backend/main.py frontend/src/api.ts frontend/src/AdminPanel.tsx
  git commit -m "feat(register): show invite code in admin panel"
  ```
