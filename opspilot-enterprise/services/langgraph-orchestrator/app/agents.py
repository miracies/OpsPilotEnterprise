from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseSubAgent(ABC):
    """Structural stub for the SubAgent pattern (not wired into routing yet)."""

    name: str = "base"
    description: str = "Base sub-agent"

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class IntentAgent(BaseSubAgent):
    name = "intent"
    description = "Classifies user intent and extracts structured slots"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"intent": "diagnose_incident", "slots": {"service": "checkout"}, "confidence": 0.86}


class EvidenceCollectionAgent(BaseSubAgent):
    name = "evidence"
    description = "Collects correlated signals from metrics, logs, and events"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "evidence_refs": ["ev-metric-1", "ev-log-2"],
            "sources_queried": ["prometheus", "loki"],
        }


class KBRetrievalAgent(BaseSubAgent):
    name = "kb"
    description = "Retrieves runbooks and knowledge base articles"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"articles": [{"id": "kb-42", "title": "Checkout latency playbook"}]}


class RCAAgent(BaseSubAgent):
    name = "rca"
    description = "Proposes ranked root cause hypotheses"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "root_cause_candidates": [
                {"id": "rca-1", "description": "Canary rollout regression", "confidence": 0.62},
            ],
        }


class NotificationAgent(BaseSubAgent):
    name = "notify"
    description = "Sends notifications to incident channels"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"delivered_to": ["#incidents"], "message_id": "msg-mock-1"}


class CaseArchiveAgent(BaseSubAgent):
    name = "archive"
    description = "Archives case summaries and attachments"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"archive_ref": "case-mock-9f3a", "status": "stored"}
