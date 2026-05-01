from __future__ import annotations

from dataclasses import dataclass

from opspilot_schema.intent import ScoreBreakdown


@dataclass(slots=True)
class ScoreResult:
    final: float
    breakdown: ScoreBreakdown


def compute_final_score(
    *,
    rules: float,
    slot_completeness: float,
    entity_match: float,
    memory_boost: float,
    llm_rerank: float,
    domain_gate_score: float = 0.0,
    target_resolution_score: float = 0.0,
) -> ScoreResult:
    base = (
        0.35 * rules
        + 0.20 * slot_completeness
        + 0.15 * entity_match
        + 0.15 * memory_boost
        + 0.15 * llm_rerank
    )
    final = min(1.0, base + 0.12 * domain_gate_score + 0.08 * target_resolution_score)
    return ScoreResult(
        final=round(final, 4),
        breakdown=ScoreBreakdown(
            rules=round(rules, 4),
            slot_completeness=round(slot_completeness, 4),
            entity_match=round(entity_match, 4),
            memory_boost=round(memory_boost, 4),
            llm_rerank=round(llm_rerank, 4),
            domain_gate_score=round(domain_gate_score, 4),
            target_resolution_score=round(target_resolution_score, 4),
        ),
    )


def decide_score(*, top1: float, top2: float, any_missing_slot: bool) -> str:
    if top1 >= 0.78 and (top1 - top2) >= 0.15 and not any_missing_slot:
        return "recovered"
    if top1 >= 0.55 or any_missing_slot:
        return "clarify_required"
    return "rejected"
