# Sprint 2: Mobile UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对标微信，手机端有原生 App 手感：WeChat 式房间列表行、全屏移动布局（Tab 栏）、键盘遮挡修复、AI 起草全屏模式。

**Architecture:** 移动端从"压缩版侧栏"改为"全屏页面 + 底部 Tab 栏"。`App.tsx` 新增移动端独立布局分支；`DraftPanel` 在移动端改为全屏。桌面端布局不变。

**Tech Stack:** React 19, Tailwind v4 (arbitrary values), `visualViewport` API

---

## 文件清单

| 操作 | 文件 | 改动 |
|------|------|------|
| Modify | `frontend/src/App.tsx` | 移动布局：去掉 compact RoomList nav，新增全屏内容区 + Tab 栏 |
| Modify | `frontend/src/RoomList.tsx` | full 模式改为 WeChat 风格行（彩色头像 + 房间名） |
| Modify | `frontend/src/ChatPage.tsx` | `visualViewport` 键盘修复 |
| Modify | `frontend/src/DraftPanel.tsx` | 移动端全屏（`inset-0` 无背景遮罩） |

---

### Task 1: RoomList WeChat 风格行

**Files:**
- Modify: `frontend/src/RoomList.tsx:165-183`

- [ ] **Step 1: 更新 full 模式的房间行渲染**

  在 `RoomList.tsx` 中，找到 `rooms.map((r) => {` 那段（约第 165 行），将整个 `<button>` 替换为带彩色头像的 WeChat 风格行：

  ```tsx
  {rooms.map((r) => {
    const label = r.name || r.room_id.slice(0, 12) + "...";
    const active = activeRoom?.room_id === r.room_id;
    // 根据名称生成固定颜色（避免每次渲染变化）
    const colors = ["bg-red-400","bg-orange-400","bg-amber-400","bg-green-500","bg-teal-500","bg-blue-500","bg-violet-500","bg-pink-500"];
    const colorIdx = label.charCodeAt(0) % colors.length;
    const avatarColor = colors[colorIdx];
    return (
      <button
        key={r.room_id}
        onClick={() => onSelect(r)}
        className={`w-full flex items-center gap-3 px-4 py-3 border-b border-gray-50 transition-colors active:bg-gray-100 ${
          active ? "bg-green-50" : "hover:bg-gray-50"
        }`}
      >
        {/* 彩色头像 */}
        <div className={`shrink-0 w-12 h-12 rounded-full ${avatarColor} flex items-center justify-center text-white text-lg font-semibold`}>
          {label.charAt(0).toUpperCase()}
        </div>
        {/* 房间信息 */}
        <div className="flex-1 text-left min-w-0">
          <div className={`font-medium text-sm truncate ${active ? "text-green-700" : "text-gray-800"}`}>{label}</div>
          <div className="text-xs text-gray-400 truncate mt-0.5">{r.room_id.slice(0, 30)}</div>
        </div>
        {active && (
          <div className="shrink-0 w-2 h-2 rounded-full bg-green-500" />
        )}
      </button>
    );
  })}
  ```

- [ ] **Step 2: 手动验证**

  桌面端运行 `npm run dev`，打开 http://localhost:5173，确认侧栏房间列表显示彩色头像 + 房间名，选中高亮变为绿色。

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/RoomList.tsx
  git commit -m "feat(mobile): wechat-style room list rows with colored avatars"
  ```

---

### Task 2: App.tsx 移动端全屏布局 + Tab 栏

**Files:**
- Modify: `frontend/src/App.tsx:169-221`

- [ ] **Step 1: 替换移动端布局**

  在 `App.tsx` 的 return 语句中（从 `<div className="flex h-full">` 开始），做以下修改：

  1. 把 `<main className="flex-1 flex flex-col min-w-0">` 改为 `<main className="hidden md:flex flex-1 flex-col min-w-0">` —— 桌面端才显示
  2. 删除整个 `{/* 手机底部导航 */}` 块（compact RoomList nav）
  3. 在 `</main>` 后、Settings 弹窗前，插入移动端内容区和 Tab 栏：

  ```tsx
  {/* 手机全屏内容区 */}
  <div className="md:hidden flex-1 flex flex-col min-w-0 pb-14 overflow-hidden">
    {page === "chat" && activeRoom ? (
      <ChatPage
        room={activeRoom}
        messages={messages}
        onAddMessage={handleAddMessage}
        onBack={handleBackToRooms}
      />
    ) : (
      <RoomList
        rooms={rooms}
        activeRoom={activeRoom}
        onSelect={handleSelectRoom}
        onLogout={handleLogout}
        onRefresh={loadRooms}
        onSettings={() => setShowSettings(true)}
        onAdmin={() => setShowAdmin(true)}
        onCreateRoom={handleCreateRoom}
        onJoinRoom={handleJoinRoom}
      />
    )}
  </div>

  {/* 手机底部 Tab 栏 */}
  <nav className="md:hidden fixed bottom-0 left-0 right-0 h-14 bg-white border-t z-10 flex items-stretch">
    <button
      className={`flex-1 flex flex-col items-center justify-center gap-0.5 text-xs transition-colors ${
        page !== "admin" ? "text-green-600" : "text-gray-400"
      }`}
      onClick={() => {
        if (page === "chat") handleBackToRooms();
      }}
    >
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
      聊天
    </button>
    <button
      className="flex-1 flex flex-col items-center justify-center gap-0.5 text-xs text-gray-400 transition-colors"
      onClick={() => setShowSettings(true)}
    >
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
      设置
    </button>
  </nav>
  ```

- [ ] **Step 2: 验证移动端布局**

  浏览器开 DevTools → 切换到手机尺寸（例如 iPhone 12）：
  - 看到全屏房间列表（WeChat 风格行）
  - 底部 Tab 栏有"聊天"和"设置"两个按钮
  - 选择房间后进入全屏聊天页
  - ChatPage 左上角有返回按钮，点击回到房间列表
  - 点"设置"弹出设置弹窗

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/App.tsx
  git commit -m "feat(mobile): full-screen mobile layout with tab bar"
  ```

---

### Task 3: ChatPage 键盘遮挡修复

**Files:**
- Modify: `frontend/src/ChatPage.tsx`

- [ ] **Step 1: 添加 visualViewport 监听**

  在 `ChatPage.tsx` 的 hooks 区（`const listRef` 附近），添加以下 state 和 effect：

  ```tsx
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const onResize = () => {
      const diff = window.innerHeight - vv.height - vv.offsetTop;
      setKeyboardHeight(diff > 0 ? diff : 0);
    };
    vv.addEventListener("resize", onResize);
    vv.addEventListener("scroll", onResize);
    return () => {
      vv.removeEventListener("resize", onResize);
      vv.removeEventListener("scroll", onResize);
    };
  }, []);
  ```

- [ ] **Step 2: 将 keyboardHeight 应用到输入区**

  找到输入区 `<div className="px-4 py-3 border-t bg-white shrink-0">`，改为：

  ```tsx
  <div
    className="px-4 py-3 border-t bg-white shrink-0"
    style={{ paddingBottom: `calc(0.75rem + ${keyboardHeight}px)` }}
  >
  ```

- [ ] **Step 3: 验证**

  手机尺寸下打开聊天页，点击输入框，确认键盘弹起时输入框随之上移，不被遮住。

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/ChatPage.tsx
  git commit -m "fix(mobile): use visualViewport to prevent keyboard from covering input"
  ```

---

### Task 4: DraftPanel 移动端全屏

**Files:**
- Modify: `frontend/src/DraftPanel.tsx:115-116`

- [ ] **Step 1: 修改容器类**

  找到 DraftPanel.tsx 第 115 行：
  ```tsx
  <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/30">
    <div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-xl w-full sm:max-w-lg max-h-[80vh] flex flex-col mx-0 sm:mx-4">
  ```

  改为：
  ```tsx
  <div className="fixed inset-0 z-50 flex flex-col sm:flex-row sm:items-center sm:justify-center sm:bg-black/30">
    <div className="bg-white flex-1 sm:flex-initial sm:rounded-2xl sm:shadow-xl sm:w-full sm:max-w-lg sm:max-h-[80vh] flex flex-col sm:mx-4">
  ```

  这样在手机端（`< sm`）DraftPanel 占满全屏；桌面端保持居中弹窗。

- [ ] **Step 2: 验证**

  手机尺寸下点击消息的 AI 起草按钮：
  - 打开全屏 AI 草稿页面
  - 有上下文信息区、草稿文本区、指令输入 + 发送按钮
  - 桌面端仍然是底部弹起的小面板

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/DraftPanel.tsx
  git commit -m "feat(mobile): draft panel goes full screen on mobile"
  ```

---

### Task 5: ChatPage 消息气泡头像

**Files:**
- Modify: `frontend/src/ChatPage.tsx:286-333`

- [ ] **Step 1: 在对方消息气泡左侧添加头像圆圈**

  找到 ChatPage.tsx 中消息渲染的 `return (` 内，`<div key={msg.id} className={...}>` 整块。当前结构是 `flex justify-start/end`，内部只有一个气泡。改为对方消息时左侧加头像：

  ```tsx
  {messages.map((msg) => {
    const isMe = msg.sender === userId;
    const senderName = displayName(msg.sender);
    const avatarColors = ["bg-red-400","bg-orange-400","bg-amber-400","bg-green-500","bg-teal-500","bg-blue-500","bg-violet-500","bg-pink-500"];
    const avatarColor = avatarColors[senderName.charCodeAt(0) % avatarColors.length];
    return (
      <div
        key={msg.id}
        className={`group flex items-end gap-2 ${isMe ? "justify-end" : "justify-start"}`}
      >
        {/* 对方头像 */}
        {!isMe && (
          <div className={`shrink-0 w-8 h-8 rounded-full ${avatarColor} flex items-center justify-center text-white text-xs font-semibold mb-1`}>
            {senderName.charAt(0).toUpperCase()}
          </div>
        )}

        <div className="relative max-w-[75%] sm:max-w-[65%]">
          {/* 其余气泡内容保持不变 */}
  ```

  注意：要在原来气泡 `</div>` 结束后、外层 `</div>` 前，加上占位（isMe 时没有头像，但需要对齐）：

  ```tsx
        </div>

        {/* 自己头像（占位保持对齐，不显示） */}
        {isMe && <div className="w-8 shrink-0" />}
      </div>
    );
  })}
  ```

- [ ] **Step 2: 验证**

  打开聊天页，对方消息左侧有彩色头像圆圈（首字母），自己的消息右侧有空位保持对齐。

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/ChatPage.tsx
  git commit -m "feat(mobile): add sender avatar to chat bubbles"
  ```

---

### Task 6: 原生手感（tap 反馈 + 滚动）

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: 添加移动端全局样式**

  在 `index.css` 末尾追加：

  ```css
  /* 移动端触摸反馈 */
  @media (hover: none) {
    button:active {
      transform: scale(0.97);
      transition: transform 0.1s;
    }
  }

  /* iOS overflow scroll 顺滑 */
  .overflow-y-auto {
    -webkit-overflow-scrolling: touch;
  }

  /* 防止 iOS Safari 双击缩放 */
  button, input, textarea {
    touch-action: manipulation;
  }
  ```

- [ ] **Step 2: 验证**

  手机 Safari 下点击房间列表，确认有轻微的缩放反馈感（非常细微），滚动顺滑。

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/index.css
  git commit -m "feat(mobile): native touch feedback and smooth scroll"
  ```
