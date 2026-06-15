/** WeAt 浏览器端 Agent — 类型定义 */

// ── LLM 消息类型（受 pi 启发，极度简化） ──────────────────────────────────

export interface UserMessage {
  role: "user";
  content: string;
}

export interface AssistantMessage {
  role: "assistant";
  content: string;
  toolCalls?: ToolCall[];
  stopReason: "stop" | "toolUse" | "error" | "aborted";
  errorMessage?: string;
}

export interface ToolCall {
  id: string;
  type: "function";
  function: {
    name: string;
    arguments: string; // JSON string
  };
}

export interface ToolResultMessage {
  role: "tool";
  toolCallId: string;
  content: string;
}

export type Message = UserMessage | AssistantMessage | ToolResultMessage;

// ── Tool 定义 ──────────────────────────────────────────────────────────────

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, unknown>; // JSON Schema
}

export interface ToolExecuteContext {
  signal?: AbortSignal;
}

export interface Tool<TParams = Record<string, unknown>> {
  definition: ToolDefinition;
  execute: (
    params: TParams,
    context: ToolExecuteContext
  ) => Promise<string>;
}

// ── LLM 配置 ───────────────────────────────────────────────────────────────

export interface LLMConfig {
  baseUrl: string;
  model: string;
  apiKey: string;
}

// ── Agent 配置 ─────────────────────────────────────────────────────────────

export interface AgentConfig {
  systemPrompt: string;
  tools: Tool[];
  llm: LLMConfig;
  maxTurns?: number;
}

// ── Agent 事件（用于 UI 更新） ──────────────────────────────────────────────

export type AgentEvent =
  | { type: "agent_start" }
  | { type: "agent_end" }
  | { type: "message"; message: Message }
  | { type: "tool_start"; toolName: string }
  | { type: "tool_end"; toolName: string; result: string }
  | { type: "error"; message: string }
  | { type: "thinking"; text: string };
