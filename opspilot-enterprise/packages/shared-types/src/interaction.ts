import type { IntentDomain, RiskLevel } from "./intent";

export type InteractionKind = "clarify" | "approve";
export type ApprovalScope = "once" | "session";
export type ApprovalDecisionOutcome = "approved" | "rejected" | "expired";

export interface ResourceRef {
  type: string;
  id: string;
  name: string;
}

export interface ResourceScope {
  environment: string;
  resources: ResourceRef[];
}

export interface ClarifyRecord {
  interaction_id: string;
  run_id: string;
  question: string;
  choices: string[];
  allow_free_text: boolean;
  reason_code: "ambiguous_intent" | "missing_slot" | "conflicting_resource" | "unsafe_default";
  status: "pending" | "answered" | "approved" | "rejected" | "expired";
  expires_at: string;
  created_at: string;
  created_by: string;
  selected_choice?: string | null;
  free_text?: string | null;
  responded_at?: string | null;
  responded_by?: string | null;
}

export interface ApprovalRecord {
  approval_id: string;
  run_id: string;
  summary: string;
  domain: IntentDomain;
  action: string;
  risk_level: RiskLevel;
  resource_scope: ResourceScope;
  command_preview: string[];
  plan_steps: string[];
  rollback_plan: string[];
  allowed_scopes: ApprovalScope[];
  status: "pending" | "answered" | "approved" | "rejected" | "expired";
  decision?: ApprovalDecisionOutcome | null;
  final_scope?: ApprovalScope | null;
  comment?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  expires_at: string;
  created_at: string;
  created_by: string;
}

export interface ResumeCardData {
  checkpoint_id: string;
  run_id: string;
  last_safe_step?: number | null;
  resume_from?: string | null;
  idempotency_key: string;
  rollback_available: boolean;
}

export interface AuditTimelineData {
  run_id: string;
  operator?: string | null;
  decision_chain: string[];
  tool_outputs: string[];
  events: Array<{
    event_id: string;
    event_type: string;
    summary: string;
    created_at: string;
    actor_type: string;
    actor_id: string;
    step_no: number;
  }>;
}
