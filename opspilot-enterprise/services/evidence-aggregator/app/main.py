from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field
from opspilot_schema.evidence import Evidence, EvidencePackage
from opspilot_schema.envelope import make_error, make_success

EvidenceSource = Literal["event", "metric", "log", "topology", "kb", "change", "external_kb"]

app = FastAPI(title="OpsPilot Evidence Aggregator")


class AggregateRequest(BaseModel):
    incident_id: str
    source_refs: list[str] = Field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mock_evidences(incident_id: str, n: int) -> list[Evidence]:
    types: list[tuple[EvidenceSource, str]] = [
        ("event", "deployment"),
        ("metric", "service"),
        ("log", "pod"),
        ("topology", "node"),
        ("kb", "runbook"),
    ]
    out: list[Evidence] = []
    for i in range(n):
        st, ot = types[i % len(types)]
        eid = f"ev-{incident_id[:6]}-{uuid.uuid4().hex[:8]}"
        out.append(
            Evidence(
                evidence_id=eid,
                source=f"src-{i + 1}",
                source_type=st,
                object_type=ot,
                object_id=f"obj-{i + 1}",
                timestamp=_now(),
                summary=f"Correlated signal {i + 1} for incident {incident_id}",
                raw_ref=f"s3://evidence/{eid}.json",
                confidence=0.55 + (i * 0.08) % 0.4,
                correlation_key=f"ck-{incident_id}",
            ),
        )
    return out


@app.get("/health")
async def health() -> dict:
    return make_success({"status": "healthy"})


@app.post("/api/v1/evidence/aggregate")
async def aggregate(body: AggregateRequest) -> dict:
    try:
        n = 3 + (len(body.source_refs) % 3)
        evidences = _mock_evidences(body.incident_id, n)
        pkg = EvidencePackage(
            package_id=f"pkg-{uuid.uuid4().hex[:12]}",
            incident_id=body.incident_id,
            evidences=evidences,
            created_at=_now(),
        )
        return make_success(pkg.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/evidence/{evidence_id}")
async def get_evidence(evidence_id: str) -> dict:
    try:
        ev = Evidence(
            evidence_id=evidence_id,
            source="mock-aggregator",
            source_type="log",
            object_type="service",
            object_id="svc-checkout",
            timestamp=_now(),
            summary="Single evidence record (mock)",
            raw_ref=f"ref://{evidence_id}",
            confidence=0.82,
            correlation_key="ck-mock",
        )
        return make_success(ev.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))
