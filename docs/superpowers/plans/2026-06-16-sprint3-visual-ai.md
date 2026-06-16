# Sprint 3: Frontend Visual Refresh + AI DraftPanel + Streaming

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 应用微信绿主题，改善信息层次，FAB 按钮让 AI 入口可见，DraftPanel 桌面端改为右侧滑出面板，AI 草稿流式输出。

**Architecture:** 主题色通过 Tailwind v4 `@theme` CSS 自定义属性注入，全局替换 `blue-600/700` 为 `wechat`；流式输出通过在 `AgentEvent` 增加 `text_start` 事件类型，Agent 在最终 LLM 调用前触发，DraftPanel 监听后逐字更新草稿。

**Tech Stack:** Tailwind v4 (@theme), React 19, existing SSE streaming in `agent/llm.ts`

---

## 文件清单

| 操作 | 文件 | 改动 |
|------|------|------|
| Modify | `frontend/src/index.css` | 添加 `@theme` 自定义颜色 wechat |
| Modify | `frontend/src/App.tsx` | blue → wechat |
| Modify | `frontend/src/RoomList.tsx` | blue → wechat，字体层级 |
| Modify | `frontend/src/ChatPage.tsx` | blue → wechat，FAB 按钮 |
| Modify | `frontend/src/DraftPanel.tsx` | 桌面右侧滑出 + 流式更新 |
| Modify | `frontend/src/LoginPage.tsx` | blue → wechat |
| Modify | `frontend/src/Settings.tsx` | blue → wechat |
| Modify | `frontend/src/agent/types.ts` | 添加 `text_start` 事件 |
| Modify | `frontend/src/agent/index.ts` | 在最终 LLM turn 前 emit `text_start` |

---

### Task 1: 微信绿主题色

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: 在 index.css 添加 @theme 块**

  在 `@import "tailwindcss";` 后插入：

  ```css
  @theme {
    --color-wechat: #07C160;
    --color-wechat-dark: #059e4e;
    --color-wechat-light: #e8f9f0;
  }
  ```

  这会生成 `bg-wechat`, `text-wechat`, `border-wechat`, `bg-wechat-dark`, `bg-wechat-light` 等 Tailwind 工具类。

- [ ] **Step 2: 验证类名生效**

  运行 `npm run dev`，在浏览器 DevTools 里找任意按钮，用 Classes 面板临时加 `bg-wechat`，确认颜色是 `#07C160`（微信绿）。

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/index.css
  git commit -m "feat(theme): add wechat green custom color to tailwind"
  ```

---

### Task 2: 全局替换 blue → wechat

**Files:**
- Modify: `frontend/src/App.tsx`, `frontend/src/RoomList.tsx`, `frontend/src/ChatPage.tsx`, `frontend/src/LoginPage.tsx`, `frontend/src/Settings.tsx`, `frontend/src/DraftPanel.tsx`, `frontend/src/SummaryPanel.tsx`, `frontend/src/AdminPanel.tsx`

- [ ] **Step 1: 批量替换颜色类名**

  在 `frontend/src/` 目录下执行（macOS sed）：

  ```bash
  cd frontend/src
  # bg-blue-600 → bg-wechat, hover:bg-blue-700 → hover:bg-wechat-dark
  find . -name "*.tsx" -exec sed -i '' \
    -e 's/bg-blue-600/bg-wechat/g' \
    -e 's/bg-blue-700/bg-wechat-dark/g' \
    -e 's/hover:bg-blue-700/hover:bg-wechat-dark/g' \
    -e 's/text-blue-600/text-wechat/g' \
    -e 's/border-blue-400/border-wechat/g' \
    -e 's/focus:ring-blue-400/focus:ring-wechat/g' \
    -e 's/bg-blue-50/bg-wechat-light/g' \
    -e 's/text-blue-200/text-wechat-light/g' \
    {} \;
  ```

- [ ] **Step 2: 手动检查剩余 blue**

  ```bash
  grep -r "blue-" frontend/src/ --include="*.tsx"
  ```

  确认剩余的 blue 都是有意保留的（如错误提示的 `blue`）。对于消息气泡中自己发出的消息颜色（`bg-blue-600`），已被替换为微信绿 `bg-wechat`，这是正确的。

- [ ] **Step 3: 验证视觉效果**

  浏览器刷新，确认：
  - 登录按钮是绿色
  - 发送按钮是绿色
  - 自己的消息气泡是绿色
  - 选中房间高亮是浅绿色
  - 输入框 focus 环是绿色

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/
  git commit -m "feat(theme): replace blue with wechat green across all components"
  ```

---

### Task 3: RoomList 字体层级改善

**Files:**
- Modify: `frontend/src/RoomList.tsx`

- [ ] **Step 1: 调整字体大小（在 Sprint 2 已修改的行基础上）**

  将房间名的 `text-sm font-medium` 改为 `text-[15px] font-semibold leading-tight`，room_id 预览改为 `text-xs text-gray-400`（已经是这样，无需改）。

  找到 Task 1 Sprint 2 中修改的房间名 div：
  ```tsx
  <div className={`font-medium text-sm truncate ${active ? "text-green-700" : "text-gray-800"}`}>{label}</div>
  ```
  改为：
  ```tsx
  <div className={`text-[15px] font-semibold leading-tight truncate ${active ? "text-wechat-dark" : "text-gray-800"}`}>{label}</div>
  ```

- [ ] **Step 2: 验证**

  桌面端确认房间名字体更突出（稍大、加粗），room_id 预览文字更小更灰。

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/RoomList.tsx
  git commit -m "feat(visual): improve room list typography hierarchy"
  ```

---

### Task 4: ChatPage FAB 按钮

**Files:**
- Modify: `frontend/src/ChatPage.tsx`

- [ ] **Step 1: 在消息列表区添加 FAB**

  在 ChatPage 的消息列表 `<div ref={listRef}` 结束标签 `</div>` 之前，添加悬浮 AI 按钮（只在 `llmConfig` 存在时显示，且没有正在进行的 draft 时）：

  ```tsx
  {/* AI FAB */}
  {llmConfig && !draftTarget && (
    <button
      onClick={() => handleAIDraft("")}
      className="sticky bottom-4 right-4 float-right mr-4 mb-0 w-12 h-12 rounded-full bg-wechat text-white shadow-lg hover:bg-wechat-dark active:scale-95 transition-all flex items-center justify-center z-10"
      title="AI 起草"
    >
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.347.347a3.75 3.75 0 00-1.04 2.122 1.5 1.5 0 01-3 0 3.75 3.75 0 00-1.04-2.122l-.347-.347z" />
      </svg>
    </button>
  )}
  ```

  注意：`handleAIDraft("")` 传空字符串表示不针对特定消息，AI 会根据房间历史自由起草。

- [ ] **Step 2: 验证**

  有 LLM 配置时，聊天页右下方显示绿色圆形 FAB 按钮。点击后打开 DraftPanel。

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/ChatPage.tsx
  git commit -m "feat(ai): add floating action button for AI draft in chat"
  ```

---

### Task 5: DraftPanel 桌面端右侧滑出面板

**Files:**
- Modify: `frontend/src/DraftPanel.tsx`

- [ ] **Step 1: 改变桌面端 DraftPanel 布局**

  当前 DraftPanel 是一个居中弹窗（`sm:max-w-lg`）。改为桌面端从右侧滑出：

  将 Sprint 2 修改后的容器：
  ```tsx
  <div className="fixed inset-0 z-50 flex flex-col sm:flex-row sm:items-center sm:justify-center sm:bg-black/30">
    <div className="bg-white flex-1 sm:flex-initial sm:rounded-2xl sm:shadow-xl sm:w-full sm:max-w-lg sm:max-h-[80vh] flex flex-col sm:mx-4">
  ```

  改为：
  ```tsx
  <div className="fixed inset-0 z-50 flex flex-col sm:flex-row sm:justify-end sm:bg-black/20">
    <div className="bg-white flex-1 sm:flex-initial sm:w-96 sm:h-full sm:shadow-2xl sm:border-l flex flex-col sm:animate-none">
  ```

  这样在桌面端（`≥ sm`）：DraftPanel 从右侧贴边显示，宽 `sm:w-96`（384px），全高，不遮挡左侧消息列表。移动端仍然全屏。

- [ ] **Step 2: 验证桌面和移动端**

  - 桌面端：DraftPanel 从右侧贴边显示，聊天消息列表仍可见（部分）
  - 手机端：DraftPanel 全屏显示（Sprint 2 行为不变）

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/DraftPanel.tsx
  git commit -m "feat(ui): draft panel slides in from right on desktop"
  ```

---

### Task 6: Agent 流式输出事件

**Files:**
- Modify: `frontend/src/agent/types.ts`
- Modify: `frontend/src/agent/index.ts`

- [ ] **Step 1: 在 types.ts 添加 text_start 事件**

  找到 `AgentEvent` 类型（约第 74 行），在末尾添加 `text_start`：

  ```ts
  export type AgentEvent =
    | { type: "agent_start" }
    | { type: "agent_end" }
    | { type: "message"; message: Message }
    | { type: "tool_start"; toolName: string }
    | { type: "tool_end"; toolName: string; result: string }
    | { type: "error"; message: string }
    | { type: "thinking"; text: string }
    | { type: "text_start" };  // ← 新增：每次 LLM 开始输出 text 前触发
  ```

- [ ] **Step 2: 在 agent/index.ts 的 streamLLM 调用前 emit text_start**

  找到 `index.ts` 中 `response = await streamLLM(...)` 调用（约第 51 行），在它**之前**插入：

  ```ts
  onEvent({ type: "text_start" });
  ```

  完整上下文（确认位置）：
  ```ts
  onEvent({ type: "thinking", text: "思考中…" });

  let response: AssistantMessage;
  try {
    onEvent({ type: "text_start" }); // ← 插入这行
    response = await streamLLM(
  ```

- [ ] **Step 3: 验证 (console)**

  在 DraftPanel 的 generate 函数里临时加一行：
  ```ts
  (event) => {
    console.log("[Agent event]", event.type);
    ...
  }
  ```
  打开 DraftPanel，点"重新生成"，在 console 应该看到 `text_start` 事件。

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/agent/types.ts frontend/src/agent/index.ts
  git commit -m "feat(agent): emit text_start event before each LLM text response"
  ```

---

### Task 7: DraftPanel 流式显示草稿

**Files:**
- Modify: `frontend/src/DraftPanel.tsx`

- [ ] **Step 1: 修改 generate 函数以接收流式 delta**

  在 DraftPanel 的 `generate` 函数中，找到 `onEvent` 回调（约第 71 行）：

  ```ts
  (event) => {
    // 实时显示思考内容
    if (event.type === "thinking" && event.text) {
      // 不自动覆盖 draft
    }
  },
  ```

  改为：

  ```ts
  (event) => {
    if (event.type === "text_start") {
      // 新一轮 LLM 输出开始，清空草稿准备流式接收
      setDraft("");
      setStatus("generating");
    } else if (event.type === "thinking" && event.text) {
      // 流式 text delta
      setDraft((prev) => prev + event.text);
    }
  },
  ```

- [ ] **Step 2: 移除 "生成中…" loading spinner 的触发条件（已有流式文字无需 spinner）**

  找到：
  ```tsx
  {status === "generating" && !draft && (
    <div className="flex items-center justify-center py-8">
      <div className="animate-spin h-6 w-6 border-2 border-wechat border-t-transparent rounded-full" />
      <span className="ml-2 text-sm text-gray-400">生成中…</span>
    </div>
  )}
  ```

  保持不变—— `!draft` 确保只有在还没有任何流式文字时才显示 spinner（工具调用阶段）。一旦有文字流入，spinner 消失，文字直接出现。

- [ ] **Step 3: 验证流式输出**

  打开 DraftPanel，点"重新生成"：
  - 先显示 spinner（AI 正在获取房间历史）
  - 然后草稿文本框出现，文字逐字流入
  - 完成后变为可编辑状态

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/DraftPanel.tsx
  git commit -m "feat(ai): stream draft text token by token in DraftPanel"
  ```
