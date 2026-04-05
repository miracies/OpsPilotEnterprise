export type PolicyType = "approval_gate" | "rate_limit" | "scope_guard" | "time_window" | "risk_threshold" | "audit_only";
export type PolicyStatus = "active" | "inactive" | "draft";
export type PolicyEffect = "allow" | "deny" | "require_approval" | "alert_only";

export interface OpsPolicy {
  id: string;
  name: string;
  description: string;
  type: PolicyType;
  status: PolicyStatus;
  effect: PolicyEffect;
  scope: string[];
  conditions: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  hit_count: number;
  last_hit_at: string | null;
  author: string;
  version: string;
  rego_snippet: string | null;
}

export interface PolicyHitRecord {
  id: string;
  policy_id: string;
  policy_name: string;
  effect: PolicyEffect;
  actor: string;
  tool_name: string;
  resource: string;
  outcome: "blocked" | "allowed" | "escalated";
  timestamp: string;
  trace_id: string;
}
