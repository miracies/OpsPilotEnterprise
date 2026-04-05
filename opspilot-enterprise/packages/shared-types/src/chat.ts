export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  tags: string[];
  message_count: number;
}

export type MessageRole = "user" | "assistant" | "system";

export interface ToolTrace {
  tool_name: string;
  gateway: string;
  input_summary: string;
  output_summary: string;
  duration_ms: number;
  status: "success" | "error" | "denied";
  timestamp: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  tool_traces?: ToolTrace[];
  evidence_refs?: string[];
  root_cause_candidates?: Array<{
    description: string;
    confidence: number;
  }>;
  recommended_actions?: string[];
  agent_name?: string;
}
