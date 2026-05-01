from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from opspilot_schema.memory import MemoryCreateRequest, MemoryPolicyRule

DEFAULT_BLOCKED_PATTERNS = [
    r"password\s*[:=]\s*\S+",
    r"passwd\s*[:=]\s*\S+",
    r"token\s*[:=]\s*\S+",
    r"api[_-]?key\s*[:=]\s*\S+",
    r"secret\s*[:=]\s*\S+",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
]


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str = ""


class MemoryPolicy:
    def __init__(self, rules: list[MemoryPolicyRule] | None = None) -> None:
        self.rules = rules or default_policy_rules()

    def validate(self, request: MemoryCreateRequest) -> PolicyDecision:
        blob = json.dumps(request.model_dump(), ensure_ascii=False)
        for pattern in DEFAULT_BLOCKED_PATTERNS:
            if re.search(pattern, blob, re.I):
                return PolicyDecision(False, f"sensitive credential pattern blocked: {pattern}")

        if not request.title.strip() or not request.summary.strip():
            return PolicyDecision(False, "title and summary are required")
        if not request.tenant_id.strip() or not request.source.strip():
            return PolicyDecision(False, "tenant_id and source are required")
        if request.confidence < 0.2:
            return PolicyDecision(False, "confidence is too low for long-term memory")

        enabled = [r for r in self.rules if r.enabled and (not r.memory_type or r.memory_type == request.memory_type)]
        for rule in enabled:
            if request.confidence < rule.min_confidence:
                return PolicyDecision(False, f"confidence below policy threshold: {rule.name}")
            for field in rule.required_fields:
                value = _field_value(request, field)
                if value in (None, "", [], {}):
                    return PolicyDecision(False, f"required field missing: {field}")
            for pattern in rule.blocked_patterns:
                if re.search(pattern, blob, re.I):
                    return PolicyDecision(False, f"blocked by policy {rule.name}: {pattern}")
        return PolicyDecision(True, "allowed")


def _field_value(request: MemoryCreateRequest, dotted: str) -> Any:
    value: Any = request.model_dump()
    for part in dotted.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def default_policy_rules() -> list[MemoryPolicyRule]:
    return [
        MemoryPolicyRule(
            id="policy-incident-confirmed-root-cause",
            name="Confirmed incident memory",
            memory_type="vmware_incident_memory",
            min_confidence=0.5,
            retention_policy="long_term",
            required_fields=["content.root_cause", "content.symptom"],
            blocked_patterns=DEFAULT_BLOCKED_PATTERNS,
        ),
        MemoryPolicyRule(
            id="policy-general-memory",
            name="General long-term memory",
            min_confidence=0.35,
            retention_policy="long_term",
            required_fields=[],
            blocked_patterns=DEFAULT_BLOCKED_PATTERNS,
        ),
    ]

