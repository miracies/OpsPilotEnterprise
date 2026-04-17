export type ActionType = "read" | "write" | "dangerous";

export type ToolLifecycleStatus =
  | "draft"
  | "registered"
  | "configuring"
  | "ready"
  | "enabled"
  | "degraded"
  | "disabled"
  | "upgrading"
  | "error"
  | "retired";

export type ToolDomain =
  | "vmware"
  | "kubernetes"
  | "network"
  | "storage"
  | "knowledge"
  | "workflow"
  | "integration"
  | "platform";

export interface ToolMeta {
  name: string;
  display_name: string;
  description?: string;
  category: string;
  domain: ToolDomain | string;
  provider: string;
  action_type: ActionType;
  risk_level: "low" | "medium" | "high" | "critical";
  approval_required: boolean;
  timeout_seconds: number;
  idempotent: boolean;
  version: string;
  tags: string[];
  lifecycle_status?: ToolLifecycleStatus;
  connection_ref?: string;
  supported_connection_types?: string[];
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  registered_at?: string;
  updated_at?: string;
}

export interface ToolHealthStatus {
  name: string;
  provider: string;
  healthy: boolean;
  last_check: string;
  latency_ms: number;
  error_message?: string;
}

export interface ToolInvocation {
  id: string;
  tool_name: string;
  caller: string;
  caller_type: "agent" | "user" | "system";
  input_summary: string;
  output_summary: string;
  status: "success" | "error" | "denied" | "timeout";
  duration_ms: number;
  dry_run: boolean;
  policy_result?: "allow" | "deny" | "approval_required";
  timestamp: string;
  trace_id: string;
}

export interface GatewayInfo {
  id: string;
  name: string;
  display_name: string;
  domain: ToolDomain | string;
  url: string;
  status: "healthy" | "degraded" | "unreachable";
  tool_count: number;
  last_heartbeat: string;
  latency_ms: number;
  version: string;
}

export interface ToolCapability {
  name: string;
  description: string;
  action_type: ActionType;
  parameters: string[];
}

export interface ToolManifest {
  tool_name: string;
  version: string;
  author: string;
  license: string;
  min_platform_version: string;
  dependencies: string[];
  capabilities: ToolCapability[];
  supported_connection_types: string[];
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  changelog: string;
}

export interface ConnectionBinding {
  connection_id: string;
  connection_name: string;
  connection_type: string;
  target_url: string;
  status: "active" | "inactive" | "error";
  bound_at: string;
  last_used: string;
}

export interface ToolAuditStats {
  tool_name: string;
  total_invocations: number;
  success_count: number;
  error_count: number;
  denied_count: number;
  avg_duration_ms: number;
  p95_duration_ms: number;
  last_invoked: string;
  invocations_today: number;
  invocations_7d: number;
  top_callers: Array<{ caller: string; count: number }>;
  daily_trend: Array<{ date: string; count: number; success: number }>;
}

export interface ToolHealthCheckResult {
  tool_name: string;
  healthy: boolean;
  latency_ms: number;
  checked_at: string;
  checks: Array<{
    name: string;
    passed: boolean;
    message: string;
  }>;
}
