from __future__ import annotations

import hashlib
import uuid
from typing import Literal

from fastapi import FastAPI
from opspilot_schema.change_impact import (
    ChangeImpactRequest,
    ChangeImpactResult,
    DependencyNode,
    ImpactedObject,
)
from opspilot_schema.envelope import make_error, make_success

app = FastAPI(title="OpsPilot Change Impact Service")


def _risk_score_from_action(requested_action: str) -> int:
    h = int(hashlib.sha256(requested_action.encode()).hexdigest()[:8], 16)
    return 20 + (h % 61)


def _risk_level(score: int) -> Literal["critical", "high", "medium", "low"]:
    if score >= 70:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _approval_suggestion(
    level: Literal["critical", "high", "medium", "low"],
) -> Literal["required", "recommended", "not_required"]:
    if level in ("critical", "high"):
        return "required"
    if level == "medium":
        return "recommended"
    return "not_required"


@app.get("/health")
async def health() -> dict:
    return make_success({"status": "healthy"})


@app.post("/api/v1/change-impact/analyze")
async def analyze_change_impact(body: ChangeImpactRequest) -> dict:
    try:
        risk_score = _risk_score_from_action(body.requested_action)
        risk_level = _risk_level(risk_score)
        analysis_id = f"cia-{uuid.uuid4().hex[:12]}"

        impacted = [
            ImpactedObject(
                object_type="service",
                object_id=f"svc-{body.target_id[:8]}",
                object_name="checkout-api",
                impact_type="latency",
                severity="high",
            ),
            ImpactedObject(
                object_type="database",
                object_id=f"db-{body.target_id[:8]}",
                object_name="orders-primary",
                impact_type="load",
                severity="medium",
            ),
            ImpactedObject(
                object_type="queue",
                object_id="q-notify",
                object_name="notifications",
                impact_type="backpressure",
                severity="low",
            ),
        ]

        checks = [
            "Verify canary metrics for p95 latency and error rate",
            "Confirm database connection pool limits and slow query log",
            "Review feature flags tied to this deployment",
            "Run synthetic transaction smoke tests in staging",
        ]

        rollback = [
            "Revert deployment to previous image tag via pipeline rollback job",
            "Scale replicas back to pre-change levels if autoscaling drifted",
        ]

        nodes = [
            DependencyNode(id="node-gateway", name="api-gateway", type="gateway", children=[]),
            DependencyNode(id="node-checkout", name="checkout-api", type="service", children=[]),
            DependencyNode(id="node-db", name="orders-db", type="database", children=[]),
        ]
        graph = nodes[: 2 + (risk_score % 2)]

        result = ChangeImpactResult(
            analysis_id=analysis_id,
            target={
                "target_type": body.target_type,
                "target_id": body.target_id,
                "environment": body.environment,
            },
            action=body.requested_action,
            risk_score=risk_score,
            risk_level=risk_level,
            impacted_objects=impacted[: 2 + (risk_score % 2)],
            checks_required=checks[: 3 + (risk_score % 2)],
            rollback_plan=rollback[: 1 + (risk_score % 2)],
            approval_suggestion=_approval_suggestion(risk_level),
            dependency_graph=graph,
        )
        return make_success(result.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))

