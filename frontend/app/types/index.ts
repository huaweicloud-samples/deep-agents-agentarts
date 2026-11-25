export interface Thread {
  id: string;
  userId: string;
  name: string;
  title?: string;
  agentId: string;
  archived: boolean;
  createdAt: string;
  updatedAt: string;
  lastRunAt?: string | null;
}

export interface ThreadListResponse {
  threads: Thread[];
  nextCursor?: string | null;
  joinCode?: string | null;
}

export interface FunctionCallItem {
  name: string;
  arguments: string;
}

export interface ToolCallItem {
  id: string;
  type: "function";
  function: FunctionCallItem;
}

export interface UserMessageItem {
  id: string;
  role: "user";
  content: string | any[];
}

export interface AssistantMessageItem {
  id: string;
  role: "assistant";
  content: string | any[];
  toolCalls?: ToolCallItem[];
}

export interface ToolMessageItem {
  id: string;
  role: "tool";
  content: string | any[];
  toolCallId: string;
}

export interface ReasoningMessageItem {
  id: string;
  role: "reasoning";
  content: string | any[];
}

export type ThreadMessageItem =
  | UserMessageItem
  | AssistantMessageItem
  | ToolMessageItem
  | ReasoningMessageItem;

export interface ThreadMessagesResponse {
  thread_id: string;
  messages: ThreadMessageItem[];
}

export interface UploadResponse {
  status: "ok";
  url: string;
  sandbox_path: string;
  filename: string;
  mime_type: string;
  size: number;
  thread_id: string;
}

export interface HealthResponse {
  status: string;
  project: string;
  version: string;
  api_prefix: string;
}


