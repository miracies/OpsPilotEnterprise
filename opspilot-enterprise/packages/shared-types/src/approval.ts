export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired" | "recalled";
export type ApprovalRiskLevel = "low" | "medium" | "high" | "critical";
export type ApprovalActionType = "vm_migrate" | "vm_power_off" | "snapshot_delete" | "config_change" | "script_exec" | "upgrade" | "rollback" | "other";

export interface ApprovalRequest {
  id: string;
  title: string;
  description: string;
  action_type: ApprovalActionType;
  risk_level: ApprovalRiskLevel;
  risk_score: number;
  status: ApprovalStatus;
  requester: string;
  assignee: string | null;
  incident_ref: string | null;
  change_analysis_ref: string | null;
  target_object: string;
  target_object_type: string;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
  decision_comment: string | null;
  decided_at: string | null;
  decided_by: string | null;
  tags: string[];
}

export interface ApprovalDecision {
  request_id: string;
  decision: "approved" | "rejected";
  comment: string;
  decided_by: string;
  decided_at: string;
}
