export interface Evidence {
  evidence_id: string;
  source: string;
  source_type: "event" | "metric" | "log" | "topology" | "kb" | "change" | "external_kb";
  object_type: string;
  object_id: string;
  timestamp: string;
  summary: string;
  raw_ref: string | null;
  confidence: number;
  correlation_key: string | null;
}

export interface EvidencePackage {
  package_id: string;
  incident_id: string | null;
  session_id: string | null;
  evidences: Evidence[];
  created_at: string;
}
