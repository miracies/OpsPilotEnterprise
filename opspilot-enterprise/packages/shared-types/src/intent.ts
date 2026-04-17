export type IntentDomain = "vmware" | "k8s" | "host" | "jenkins" | "knowledge" | "unknown";
export type RecoveryDecision = "recovered" | "clarify_required" | "rejected";
export type RiskLevel = "L0" | "L1" | "L2" | "L3" | "L4";

export interface SlotValue {
  name: string;
  value: unknown;
  source: "user" | "memory" | "cmdb" | "tool_discovery" | "inferred";
  confidence: number;
}

export interface EvidenceRef {
  type: "session" | "knowledge" | "cmdb" | "tool_discovery";
  ref_id: string;
  summary: string;
  score: number;
}

export interface ScoreBreakdown {
  rules: number;
  entity_match: number;
  slot_completeness: number;
  memory_boost: number;
  llm_rerank: number;
}

export interface IntentCandidate {
  intent_code: string;
  domain: IntentDomain;
  action: string;
  description: string;
  resource_scope: "single" | "multiple" | "cluster" | "global";
  environment?: string | null;
  memory_refs: string[];
  score: number;
  score_breakdown: ScoreBreakdown;
  slots: SlotValue[];
  missing_slots: string[];
  inferred_environment?: string | null;
  inferred_risk_level?: RiskLevel | null;
  evidence: EvidenceRef[];
}

export interface IntentRecoveryRun {
  run_id: string;
  conversation_id: string;
  user_id: string;
  channel: string;
  tenant_id?: string | null;
  raw_utterance: string;
  normalized_utterance: string;
  candidates: IntentCandidate[];
  chosen_intent?: IntentCandidate | null;
  decision: RecoveryDecision;
  clarify_reasons: string[];
  rejected_reasons: string[];
  created_at: string;
}
