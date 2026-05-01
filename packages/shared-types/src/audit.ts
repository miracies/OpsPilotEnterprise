export type AuditEventType =
  | "approval_created" | "approval_decided" | "approval_expired"
  | "tool_invoked" | "execution_started" | "execution_completed" | "execution_failed"
  | "incident_created" | "incident_resolved"
  | "policy_hit" | "policy_bypassed"
  | "case_archived" | "knowledge_updated"
  | "user_login" | "user_logout" | "config_changed";

export type AuditSeverity = "info" | "warning" | "critical";

export interface AuditLog {
  id: string;
  event_type: AuditEventType;
  severity: AuditSeverity;
  actor: string;
  actor_type: "human" | "agent" | "system";
  action: string;
  resource_type: string;
  resource_id: string;
  resource_name: string;
  outcome: "success" | "failure" | "blocked";
  reason: string | null;
  incident_ref: string | null;
  request_id: string;
  trace_id: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}
