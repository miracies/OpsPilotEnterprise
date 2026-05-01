export type MemoryScope = "session" | "user" | "org" | "execution";
export type PiiLevel = "none" | "low" | "medium" | "high";

export interface MemoryUpsertRequest {
  tenant_id: string;
  scope: MemoryScope;
  subject_id: string;
  key: string;
  value_text: string;
  source_ref?: string;
  pii_level?: PiiLevel;
  retention_until?: string | null;
  metadata?: Record<string, unknown>;
  embedding?: number[] | null;
}

export interface MemoryUpsertResponse {
  memory_id: string;
  version_no: number;
  scope: MemoryScope;
  subject_id: string;
  key: string;
  created_at: string;
  storage_backend: "sqlite" | "postgres";
}

export interface RagRetrieveRequest {
  run_id?: string | null;
  tenant_id: string;
  query: string;
  top_k?: number;
  scopes?: MemoryScope[];
  environment?: string | null;
  object_type?: string | null;
  object_id?: string | null;
}

export interface RagHit {
  ref_id: string;
  source_type: string;
  title: string;
  summary: string;
  score: number;
  source?: string;
  metadata?: Record<string, unknown>;
}

export interface RagRetrieveResponse {
  query: string;
  hits: RagHit[];
  citations: Array<Record<string, unknown>>;
  evidence_refs: string[];
  insufficient_evidence: boolean;
  reason: string;
}
