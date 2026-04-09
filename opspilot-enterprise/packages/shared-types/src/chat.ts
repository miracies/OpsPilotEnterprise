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

export interface ProgressEvent {
  stage:
    | "received"
    | "intent_parsed"
    | "agent_selected"
    | "tool_invoking"
    | "tool_done"
    | "tool_error"
    | "completed"
    | "failed";
  text: string;
  ts: string;
  status: "in_progress" | "success" | "error";
  tool_name?: string;
  agent_name?: string;
}

export interface ReasoningSummary {
  intent_understanding: string;
  execution_plan: string;
  result_summary: string;
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
  diagnosis_id?: string;
  incident_id?: string;
  export_file?: {
    export_id: string;
    file_name: string;
    download_url: string;
    expires_at: string;
    file_size_bytes: number;
    mime_type: string;
    export_columns?: string[];
    ignored_columns?: string[];
  };
  export_columns?: string[];
  ignored_columns?: string[];
  status?: "in_progress" | "completed" | "failed";
  progress_events?: ProgressEvent[];
  reasoning_summary?: ReasoningSummary;
}
