export type IntentDomain = "vmware" | "k8s" | "host" | "jenkins" | "knowledge" | "unknown";
export type RecoveryDecision = "recovered" | "clarify_required" | "rejected";
export type RiskLevel = "L0" | "L1" | "L2" | "L3" | "L4";
export type ExecutionIntentMode = "read" | "plan" | "execute";

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
  domain_gate_score: number;
  target_resolution_score: number;
}

export interface ResolutionRef {
  ref_id: string;
  name: string;
  type: string;
  matched_by: string;
  connection_id?: string | null;
  environment?: string | null;
  aliases: string[];
  score: number;
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
  target_object_raw?: string | null;
  target_object_resolved?: string | null;
  target_type?: string | null;
  resolution_confidence: number;
  resolution_refs: ResolutionRef[];
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

export interface ExecutionIntent {
  mode: ExecutionIntentMode;
  reason: string;
  target_tool?: string | null;
  guardrails: string[];
}

export interface RiskContext {
  environment: string;
  resource_scope: "single" | "multiple" | "cluster" | "global";
  object_count: number;
}

export interface IntentAnalyzeResponse {
  run_id: string;
  decision: RecoveryDecision;
  selected_intent?: IntentCandidate | null;
  candidates: IntentCandidate[];
  execution_intent: ExecutionIntent;
  risk_context: RiskContext;
  context_hints: Record<string, unknown>;
  normalized_utterance: string;
  memory_refs: string[];
  evidence_refs: string[];
  clarify_reasons: string[];
  rejected_reasons: string[];
  clarify_card?: Record<string, unknown> | null;
  approval_card?: Record<string, unknown> | null;
  rag_plan?: Record<string, unknown> | null;
  run: IntentRecoveryRun;
}
