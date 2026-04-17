export interface Evidence {
  evidence_id: string;
  source: string;
  source_type: "event" | "metric" | "log" | "topology" | "kb" | "change" | "external_kb" | "detail" | "alert";
  object_type: string;
  object_id: string;
  timestamp: string;
  summary: string;
  raw_ref: string | null;
  confidence: number;
  correlation_key: string | null;
}

export interface EvidenceSourceStats {
  source_type: Evidence["source_type"];
  count: number;
  avg_confidence: number;
}

export interface EvidenceCoverage {
  requested_sources: number;
  collected_sources: number;
  missing_sources: number;
  required_evidence_types: string[];
  present_evidence_types: string[];
  missing_critical_evidence: string[];
  sufficiency_score: number;
  freshness_score: number;
}

export interface EvidenceError {
  source: string;
  message: string;
}

export interface EvidenceContradiction {
  type: string;
  summary: string;
  evidence_refs: string[];
  severity: "high" | "medium" | "low";
}

export interface EvidencePackage {
  package_id: string;
  incident_id: string | null;
  session_id: string | null;
  evidences: Evidence[];
  created_at: string;
  source_stats?: EvidenceSourceStats[];
  coverage?: EvidenceCoverage;
  errors?: EvidenceError[];
  required_evidence_types?: string[];
  present_evidence_types?: string[];
  missing_critical_evidence?: string[];
  sufficiency_score?: number;
  freshness_score?: number;
  contradictions?: EvidenceContradiction[];
}
