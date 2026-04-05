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

export interface IncidentTimelineEntry {
  timestamp: string;
  type: "event" | "analysis" | "notification" | "action" | "resolution";
  summary: string;
  agent?: string;
  detail?: string;
}
