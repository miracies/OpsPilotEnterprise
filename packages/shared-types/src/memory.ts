export type MemoryType =
  | "user_memory"
  | "resource_memory"
  | "incident_memory"
  | "vmware_incident_memory"
  | "change_memory"
  | "knowledge_memory";

export type MemoryImportance = "low" | "medium" | "high" | "critical";
export type MemoryRetentionPolicy = "short_term" | "medium_term" | "long_term" | "permanent";
export type MemoryStatus = "active" | "archived" | "deleted" | "invalid" | "expired" | "downgraded" | "duplicate";
export type MemoryMergeStrategy = "append_evidence" | "replace_summary" | "mark_duplicate";

export interface MemoryEntity {
  id?: string | null;
  entity_type: string;
  entity_id?: string | null;
  entity_name?: string | null;
  properties?: Record<string, unknown>;
}

export interface MemoryEvidenceRef {
  id?: string | null;
  evidence_id: string;
  evidence_type?: string | null;
  evidence_uri?: string | null;
}

export interface MemoryRelation {
  id?: string | null;
  source_memory_id: string;
  relation_type: string;
  target_type: string;
  target_id: string;
  weight: number;
  properties?: Record<string, unknown>;
}

export interface MemoryItem {
  id: string;
  tenant_id: string;
  user_id?: string | null;
  memory_type: string;
  title: string;
  summary: string;
  content: Record<string, unknown>;
  source: string;
  source_id?: string | null;
  importance: MemoryImportance;
  confidence: number;
  retention_policy: MemoryRetentionPolicy;
  status: MemoryStatus;
  created_at: string;
  updated_at: string;
  expire_at?: string | null;
  entities: MemoryEntity[];
  tags: string[];
  evidence_refs: MemoryEvidenceRef[];
  relations: MemoryRelation[];
  score?: number | null;
  graph_sync_status?: string | null;
}

export interface MemorySearchFilters {
  memory_type?: string | null;
  tags?: string[];
  entity_type?: string | null;
  entity_id?: string | null;
  status?: MemoryStatus | null;
  source?: string | null;
  min_confidence?: number | null;
}

export interface MemorySearchRequest {
  tenant_id: string;
  query: string;
  filters?: MemorySearchFilters;
  top_k?: number;
  include_graph?: boolean;
}

export interface MemorySearchHit {
  memory: MemoryItem;
  score: number;
  reasons: string[];
}

export interface MemoryPolicyRule {
  id: string;
  name: string;
  enabled: boolean;
  memory_type?: string | null;
  min_confidence: number;
  retention_policy: MemoryRetentionPolicy;
  blocked_patterns: string[];
  required_fields: string[];
  updated_at?: string | null;
}

export interface MemoryContextResponse {
  similar_incidents: MemorySearchHit[];
  resource_history: MemorySearchHit[];
  risk_signals: string[];
  recommended_actions: string[];
  citations: Array<Record<string, unknown>>;
}

export interface SopCandidate {
  id: string;
  tenant_id: string;
  title: string;
  summary: string;
  source_memory_ids: string[];
  recommended_steps: string[];
  status: "candidate" | "promoted" | "rejected";
  knowledge_article_id?: string | null;
  created_at: string;
  updated_at: string;
}

