export type KnowledgeSource = "manual" | "runbook" | "confluence" | "gitlab" | "ai_generated" | "case_derived";
export type KnowledgeStatus = "draft" | "published" | "archived" | "reviewing";

export interface KnowledgeArticle {
  id: string;
  title: string;
  content_summary: string;
  source: KnowledgeSource;
  status: KnowledgeStatus;
  tags: string[];
  categories: string[];
  author: string;
  version: string;
  hit_count: number;
  confidence_score: number;
  relevance_score?: number;
  why_selected?: string;
  citations?: KnowledgeCitation[];
  created_at: string;
  updated_at: string;
  related_incident_ids: string[];
}

export interface KnowledgeCitation {
  article_id: string;
  title: string;
  relevance_score: number;
  why_selected: string;
}

export interface KnowledgeImportJob {
  id: string;
  source_type: KnowledgeSource | "seed" | "prometheus_rules";
  source_url: string | null;
  status: "queued" | "running" | "completed" | "failed";
  articles_imported: number;
  articles_failed: number;
  created?: number;
  updated?: number;
  failed?: number;
  total?: number;
  started_at: string;
  completed_at: string | null;
  error: string | null;
}

export type AlertKnowledgeCategory =
  | "resource"
  | "ha_cluster"
  | "vmotion_drs"
  | "storage"
  | "network"
  | "vm_level"
  | "other";

export type AlertKnowledgeSeverity = "info" | "warning" | "critical";
export type AlertKnowledgeStatus = "draft" | "published" | "deprecated";

export interface AlertKnowledgeAutomation {
  safe_actions: string[];
  approval_actions: string[];
  suppression_window?: string | null;
}

export interface AlertKnowledgeSource {
  type: "manual" | "rule" | "kb" | "case" | "external" | "seed";
  title: string;
  url?: string | null;
  trust_score: number;
}

export interface DecisionRule {
  condition: string;
  conclusion: string;
  confidence_delta: number;
  required_evidence: string[];
}

export interface AlertKnowledge {
  id: string;
  alert_name: string;
  vendor: string;
  domain: string;
  category: AlertKnowledgeCategory;
  severity: AlertKnowledgeSeverity;
  aliases: string[];
  symptoms: string[];
  possible_causes: string[];
  diagnostic_steps: string[];
  decision_tree: DecisionRule[];
  evidence_required: string[];
  evidence_optional: string[];
  remediation: string[];
  automation: AlertKnowledgeAutomation;
  source: AlertKnowledgeSource;
  status: AlertKnowledgeStatus;
  version: string;
  trust_score: number;
  hit_count: number;
  case_refs: string[];
  knowledge_refs: string[];
  tags: string[];
  match_keywords: string[];
  negative_keywords: string[];
  owner?: string | null;
  reviewer?: string | null;
  review_notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertKnowledgeMatch {
  item: AlertKnowledge;
  relevance_score: number;
  why_selected: string;
  matched_fields: string[];
  missing_evidence: string[];
  missing_critical_evidence: string[];
}

export interface AlertMatchResponse {
  matches: AlertKnowledgeMatch[];
  missing_evidence: string[];
  required_evidence_types: string[];
  diagnostic_steps: string[];
  safe_actions: string[];
  approval_actions: string[];
  missing_critical_evidence: string[];
  similar_cases: Array<Record<string, unknown>>;
  why_selected: string;
}
