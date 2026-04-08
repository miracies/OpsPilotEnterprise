export type ConnectionType =
  | "vcenter"
  | "kubeconfig"
  | "network_device"
  | "storage_array"
  | "milvus"
  | "elasticsearch"
  | "opa"
  | "n8n"
  | "rag_index"
  | "llm"
  | "itsm"
  | "notification";

export type ConnectionStatus = "active" | "inactive" | "error" | "testing";

export interface ConnectionProfile {
  id: string;
  name: string;
  display_name: string;
  type: ConnectionType | string;
  category: string;
  endpoint: string;
  scope?: string;
  credential_ref: string;
  proxy_config?: string;
  status: ConnectionStatus;
  enabled: boolean;
  version?: string;
  description?: string;
  created_at: string;
  updated_at: string;
  last_tested: string | null;
  last_test_result?: "pass" | "fail" | null;
  last_test_latency_ms?: number;
  bound_tools: string[];
  tags: string[];
}

export interface ConnectivityTestResult {
  connection_id: string;
  success: boolean;
  latency_ms: number;
  tested_at: string;
  checks: Array<{
    name: string;
    passed: boolean;
    message: string;
    duration_ms: number;
  }>;
}

export interface KeyRotationRecord {
  id: string;
  connection_id: string;
  rotated_by: string;
  old_credential_ref: string;
  new_credential_ref: string;
  rotated_at: string;
  status: "success" | "failed" | "pending";
  note?: string;
}

export interface ConnectionAuditRecord {
  id: string;
  connection_id: string;
  action: string;
  actor: string;
  detail: string;
  timestamp: string;
  ip?: string;
}
