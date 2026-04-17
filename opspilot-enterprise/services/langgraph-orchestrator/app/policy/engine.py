from __future__ import annotations

import re
from typing import Iterable, Optional

from opspilot_schema.policy_rule import RiskEvaluationInput, RiskEvaluationResult, RiskPolicyRule

from .rules import load_rules_from_db


def _matches(rule: RiskPolicyRule, inp: RiskEvaluationInput) -> bool:
    matcher = rule.matcher
    if matcher.domain and inp.domain not in matcher.domain:
        return False
    if matcher.action and inp.action not in matcher.action:
        return False
    if matcher.environment and inp.environment not in matcher.environment:
        return False
    if matcher.resource_scope and inp.resource_scope not in matcher.resource_scope:
        return False
    if matcher.tool and (inp.tool or "") not in matcher.tool:
        return False
    if matcher.command_regex:
        command_blob = "\n".join(inp.command_preview or [])
        if not any(re.search(pattern, command_blob, re.IGNORECASE) for pattern in matcher.command_regex):
            return False
    return True


class RiskStrategyEngine:
    def __init__(self, rules: Optional[Iterable[RiskPolicyRule]] = None) -> None:
        self._rules = sorted(list(rules or load_rules_from_db()), key=lambda item: item.priority)

    def evaluate(self, inp: RiskEvaluationInput) -> RiskEvaluationResult:
        for rule in self._rules:
            if not rule.enabled or not _matches(rule, inp):
                continue
            decision = rule.decision
            allowed_scopes = [scope for scope in decision.allow_scopes if scope in ("once", "session")]
            reasons = [rule.remark or f"命中规则 {rule.rule_code}"]
            if inp.environment == "prod":
                allowed_scopes = [scope for scope in allowed_scopes if scope != "always"]
            return RiskEvaluationResult(
                risk_level=decision.risk_level,
                require_clarify=decision.require_clarify,
                require_approval=decision.require_approval,
                allowed_scopes=allowed_scopes or ["once"],
                deny=decision.deny,
                require_rollback_plan=decision.require_rollback_plan,
                require_change_ticket=decision.require_change_ticket,
                matched_rule_code=rule.rule_code,
                reasons=reasons,
            )
        if inp.environment == "prod":
            return RiskEvaluationResult(
                risk_level="L2",
                require_approval=True,
                allowed_scopes=["once"],
                reasons=["未命中明确规则，生产环境默认按 L2 受控变更处理"],
            )
        return RiskEvaluationResult(
            risk_level="L1",
            require_approval=False,
            allowed_scopes=["once", "session"],
            reasons=["未命中明确规则，非生产环境默认按 L1 低风险处理"],
        )


_default_engine: Optional[RiskStrategyEngine] = None


def evaluate(inp: RiskEvaluationInput, *, fresh: bool = False) -> RiskEvaluationResult:
    global _default_engine
    if fresh or _default_engine is None:
        _default_engine = RiskStrategyEngine()
    return _default_engine.evaluate(inp)
