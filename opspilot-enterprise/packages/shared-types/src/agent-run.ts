export type AgentRunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type AgentStepStatus = "waiting" | "running" | "done" | "failed" | "skipped";

export interface AgentRunStep {
  step_id: string;
  agent_name: string;
  status: AgentStepStatus;
  input_summary: string;
  output_summary: string | null;
  tool_calls: number;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error: string | null;
}

export interface AgentRun {
  id: string;
  intent: string;
  status: AgentRunStatus;
  trigger: "user" | "schedule" | "alert" | "api";
  incident_ref: string | null;
  session_ref: string | null;
  steps: AgentRunStep[];
  total_tool_calls: number;
  total_duration_ms: number | null;
  started_at: string;
  completed_at: string | null;
  output_summary: string | null;
  error: string | null;
}
