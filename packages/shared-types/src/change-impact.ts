export type RiskLevel = "critical" | "high" | "medium" | "low";

export interface ChangeImpactRequest {
  change_type: string;
  target_type: string;
  target_id: string;
  requested_action: string;
  environment: string;
  change_window?: string;
}

export interface ImpactedObject {
  object_type: string;
  object_id: string;
  object_name: string;
  impact_type: string;
  severity: string;
}

export interface ChangeImpactResult {
  analysis_id: string;
  target: {
    target_type: string;
    target_id: string;
    environment: string;
    type?: string;
    id?: string;
    name?: string;
  };
  action: string;
  risk_score: number;
  risk_level: RiskLevel;
  impacted_objects: ImpactedObject[];
  checks_required: string[];
  rollback_plan: string[];
  approval_suggestion: "required" | "recommended" | "not_required";
  dependency_graph: DependencyNode[];
  evidence_sufficiency?: {
    required_evidence_types: string[];
    present_evidence_types: string[];
    missing_critical_evidence: string[];
    sufficiency_score: number;
    freshness_score: number;
  };
  conclusion_status?: "confirmed" | "probable" | "insufficient_evidence" | "contradicted";
  counter_evidence_result?: {
    status: "refuted" | "not_refuted" | "inconclusive";
    checked_hypothesis_id?: string | null;
    summary: string;
    evidence_refs: string[];
  };
  hypotheses?: Array<{
    id: string;
    summary: string;
    confidence: number;
    support_evidence_refs: string[];
    counter_evidence_refs: string[];
    missing_evidence: string[];
    status: "candidate" | "confirmed" | "probable" | "refuted" | "inconclusive";
  }>;
}

export interface DependencyNode {
  id: string;
  name: string;
  type: string;
  children: DependencyNode[];
}
