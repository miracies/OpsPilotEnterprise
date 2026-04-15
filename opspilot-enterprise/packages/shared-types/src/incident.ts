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
  root_cause_candidates: RootCauseCandidate[];
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

export type AnalysisStatus = "idle" | "running" | "completed" | "failed";

export interface IncidentAnalysisStep {
  round: number;
  stage: string;
  tool_name?: string;
  input_summary?: string;
  output_summary?: string;
  finding: string;
  decision: string;
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
