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
  status: "success" | "error" | "denied" | "warning";
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
  kind?: "text" | "intent_recovery" | "clarify" | "approval" | "resume";
  workflow_update?: {
    trigger: "clarify" | "approval" | "system";
    next_action: string;
    stages: Array<{
      key: string;
      label: string;
      status: "done" | "active" | "pending";
      detail?: string;
    }>;
    updated_at: string;
  };
  tool_traces?: ToolTrace[];
  evidence_refs?: string[];
  root_cause?: {
    summary: string;
    confidence: number;
    evidence_refs: string[];
  };
  root_cause_candidates?: Array<{
    description: string;
    confidence: number;
  }>;
  hypotheses?: Array<{
    id: string;
    summary: string;
    category: string;
    confidence: number;
    support_evidence_refs: string[];
    counter_evidence_refs: string[];
    missing_evidence: string[];
    status: "candidate" | "confirmed" | "probable" | "refuted" | "inconclusive";
    why: string;
  }>;
  winning_hypothesis?: {
    id: string;
    summary: string;
    category: string;
    confidence: number;
    support_evidence_refs: string[];
    counter_evidence_refs: string[];
    missing_evidence: string[];
    status: "candidate" | "confirmed" | "probable" | "refuted" | "inconclusive";
    why: string;
  };
  counter_evidence_result?: {
    status: "refuted" | "not_refuted" | "inconclusive";
    checked_hypothesis_id?: string | null;
    summary: string;
    evidence_refs: string[];
  };
  conclusion_status?: "confirmed" | "probable" | "insufficient_evidence" | "contradicted";
  evidence_sufficiency?: {
    required_evidence_types: string[];
    present_evidence_types: string[];
    missing_critical_evidence: string[];
    sufficiency_score: number;
    freshness_score: number;
  };
  contradictions?: Array<{
    type: string;
    summary: string;
    evidence_refs: string[];
    severity: "high" | "medium" | "low";
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
  analysis_steps?: Array<{
    agent: string;
    stage?: string;
    status: "success" | "failed" | "warning" | "in_progress";
    started_at: string;
    finished_at?: string;
    summary: string;
  }>;
  intent_recovery?: import("./intent").IntentRecoveryRun;
  clarify_card?: import("./interaction").ClarifyRecord;
  approval_card?: import("./interaction").ApprovalRecord;
  resume_card?: import("./interaction").ResumeCardData;
  audit_timeline?: import("./interaction").AuditTimelineData;
}
