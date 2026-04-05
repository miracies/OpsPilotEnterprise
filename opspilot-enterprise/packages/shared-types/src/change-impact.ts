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
    type: string;
    id: string;
    name: string;
  };
  action: string;
  risk_score: number;
  risk_level: RiskLevel;
  impacted_objects: ImpactedObject[];
  checks_required: string[];
  rollback_plan: string[];
  approval_suggestion: "required" | "recommended" | "not_required";
  dependency_graph: DependencyNode[];
}

export interface DependencyNode {
  id: string;
  name: string;
  type: string;
  children: DependencyNode[];
}
