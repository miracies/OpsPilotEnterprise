export type ExecutionStatus =
  | "draft"
  | "dry_run_ready"
  | "pending_approval"
  | "executing"
  | "success"
  | "failed"
  | "canceled";

export interface ExecutionTarget {
  object_id: string;
  object_name: string;
  object_type: string;
  metadata?: Record<string, unknown>;
}

export interface ExecutionDryRunTargetResult {
  object_id: string;
  object_name: string;
  status: "ok" | "error";
  message: string;
  preview?: Record<string, unknown>;
}

export interface ExecutionDryRunResult {
  can_submit: boolean;
  require_approval: boolean;
  policy: {
    allowed: boolean;
    require_approval: boolean;
    reason: string;
    matched_policies: string[];
    source?: string;
  };
  action_type: string;
  risk_level: string;
  risk_score: number;
  capability: "single" | "batch";
  target_results: ExecutionDryRunTargetResult[];
  warnings: string[];
}

export interface ExecutionRequest {
  id: string;
  tool_name: string;
  action_type: string;
  environment: string;
  requester: string;
  status: ExecutionStatus;
  incident_id: string | null;
  change_analysis_ref: string | null;
  approval_id: string | null;
  targets: ExecutionTarget[];
  parameters: Record<string, unknown>;
  dry_run_result: ExecutionDryRunResult | null;
  result: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}
