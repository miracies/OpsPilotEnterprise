export type IncidentStatus =
  | "new"
  | "analyzing"
  | "pending_action"
  | "resolved"
  | "archived";

export type SeverityLevel = "critical" | "high" | "medium" | "low" | "info";

export interface Incident {
  id: string;
  title: string;
  status: IncidentStatus;
  severity: SeverityLevel;
  source: string;
  source_type: string;
  affected_objects: AffectedObject[];
  first_seen_at: string;
  last_updated_at: string;
  owner: string | null;
  ai_analysis_triggered: boolean;
  root_cause?: RootCause;
  root_cause_candidates: RootCauseCandidate[];
  hypotheses?: Hypothesis[];
  winning_hypothesis?: Hypothesis;
  counter_evidence_result?: CounterEvidenceResult;
  conclusion_status?: "confirmed" | "probable" | "insufficient_evidence" | "contradicted";
  evidence_sufficiency?: EvidenceSufficiency;
  contradictions?: Array<{ type: string; summary: string; evidence_refs?: string[]; severity?: string }>;
  recommended_actions: string[];
  evidence_refs: string[];
  analysis?: IncidentAnalysis;
  summary: string;
}

export interface AffectedObject {
  object_type: string;
  object_id: string;
  object_name: string;
}

export interface RootCauseCandidate {
  id: string;
  description: string;
  confidence: number;
  evidence_refs: string[];
  category: string;
}

export interface RootCause {
  summary: string;
  confidence: number;
  evidence_refs: string[];
}

export interface EvidenceSufficiency {
  required_evidence_types: string[];
  present_evidence_types: string[];
  missing_critical_evidence: string[];
  sufficiency_score: number;
  freshness_score: number;
}

export interface Hypothesis {
  id: string;
  summary: string;
  category: string;
  confidence: number;
  support_evidence_refs: string[];
  counter_evidence_refs: string[];
  missing_evidence: string[];
  status: "candidate" | "confirmed" | "probable" | "refuted" | "inconclusive";
  why: string;
}

export interface CounterEvidenceResult {
  status: "refuted" | "not_refuted" | "inconclusive";
  checked_hypothesis_id?: string | null;
  summary: string;
  evidence_refs: string[];
}

export type AnalysisStatus = "idle" | "running" | "completed" | "failed";

export interface IncidentAnalysisStep {
  round: number;
  stage: string;
  goal?: string;
  tool_name?: string;
  selected_tools?: string[];
  input_summary?: string;
  output_summary?: string;
  evidence_found?: string[];
  evidence_missing?: string[];
  contradictions?: string[];
  finding: string;
  decision: string;
  why?: string;
  timestamp: string;
  status: "success" | "failed" | "running";
}

export interface IncidentAnalysis {
  status: AnalysisStatus;
  round: number;
  max_rounds: number;
  started_at?: string;
  updated_at?: string;
  elapsed_ms?: number;
  final_conclusion?: string;
  recommended_actions?: string[];
  analysis_process: IncidentAnalysisStep[];
  next_decision?: string;
}

export interface IncidentTimelineEntry {
  timestamp: string;
  type: "event" | "analysis" | "notification" | "action" | "resolution";
  summary: string;
  agent?: string;
  detail?: string;
}
