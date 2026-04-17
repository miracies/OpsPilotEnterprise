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
) -> ScoreResult:
    final = (
        0.35 * rules
        + 0.20 * slot_completeness
        + 0.15 * entity_match
        + 0.15 * memory_boost
        + 0.15 * llm_rerank
    )
    return ScoreResult(
        final=round(final, 4),
        breakdown=ScoreBreakdown(
            rules=round(rules, 4),
            slot_completeness=round(slot_completeness, 4),
            entity_match=round(entity_match, 4),
            memory_boost=round(memory_boost, 4),
            llm_rerank=round(llm_rerank, 4),
        ),
    )


def decide_score(*, top1: float, top2: float, any_missing_slot: bool) -> str:
    if top1 >= 0.78 and (top1 - top2) >= 0.15 and not any_missing_slot:
        return "recovered"
    if top1 >= 0.55 or any_missing_slot:
        return "clarify_required"
    return "rejected"
