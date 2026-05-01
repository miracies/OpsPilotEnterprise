export interface AuditEvent {
  event_id: string;
  run_id: string;
  step_no: number;
  event_type: string;
  actor_type: string;
  actor_id: string;
  summary: string;
  detail?: Record<string, unknown>;
  created_at: string;
}

export interface CheckpointRecord {
  checkpoint_id: string;
  run_id: string;
  step_no: number;
  step_hash: string;
  idempotency_key: string;
  status: "safe" | "waiting" | "failed" | "rolled_back";
  resume_payload: Record<string, unknown>;
  rollback_payload: Record<string, unknown>;
  created_at: string;
  updated_at?: string | null;
}

export interface ResumeResponse {
  run_id: string;
  status: "resumed" | "rolled_back" | "nothing_to_resume" | "rejected";
  resume_from_step?: number | null;
  skipped_steps: number[];
  message: string;
  last_safe_step?: number | null;
  resume_from?: string | null;
  rollback_available: boolean;
  decision_chain: string[];
  tool_outputs: string[];
}
