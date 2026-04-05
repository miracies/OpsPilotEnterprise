export type ActionType = "read" | "write" | "dangerous";

export interface ToolMeta {
  name: string;
  display_name: string;
  category: string;
  domain: string;
  provider: string;
  action_type: ActionType;
  risk_level: "low" | "medium" | "high" | "critical";
  approval_required: boolean;
  timeout_seconds: number;
  idempotent: boolean;
  version: string;
  tags: string[];
}

export interface ToolHealthStatus {
  name: string;
  provider: string;
  healthy: boolean;
  last_check: string;
  latency_ms: number;
}
