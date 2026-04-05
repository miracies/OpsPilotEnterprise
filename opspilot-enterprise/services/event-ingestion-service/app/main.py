from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel, Field
from opspilot_schema.incident import AffectedObject, Incident, RootCauseCandidate
from opspilot_schema.envelope import make_error, make_success

app = FastAPI(title="OpsPilot Event Ingestion Service")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestEventBody(BaseModel):
    source: str
    source_type: str
    object_type: str
    object_id: str
    severity: str
    summary: str


class NormalizedEvent(BaseModel):
    event_id: str
    source: str
    source_type: str
    object_type: str
    object_id: str
    severity: str
    summary: str
    ingested_at: str


_MOCK_INCIDENT_IDS = ("inc-a1b2c3", "inc-d4e5f6", "inc-g7h8i9")


def _mock_incident(incident_id: str, *, detailed: bool) -> Incident:
    if not detailed:
        return Incident(
            id=incident_id,
            title=f"Elevated errors on {incident_id}",
            status="new",
            severity="high",
            source="kubernetes",
            source_type="event",
            affected_objects=[
                AffectedObject(object_type="pod", object_id="pod-7a2f", object_name="checkout-7a2f"),
                AffectedObject(object_type="service", object_id="svc-checkout", object_name="checkout"),
            ],
            first_seen_at=_now(),
            last_updated_at=_now(),
            owner="oncall@example.com",
            ai_analysis_triggered=False,
            summary="Mock incident summary for development.",
        )
    return Incident(
        id=incident_id,
        title=f"Elevated errors on {incident_id}",
        status="analyzing",
        severity="high",
        source="kubernetes",
        source_type="event",
        affected_objects=[
            AffectedObject(object_type="pod", object_id="pod-7a2f", object_name="checkout-7a2f"),
            AffectedObject(object_type="service", object_id="svc-checkout", object_name="checkout"),
        ],
        first_seen_at=_now(),
        last_updated_at=_now(),
        owner="oncall@example.com",
        ai_analysis_triggered=True,
        root_cause_candidates=[
            RootCauseCandidate(
                id="rc-1",
                description="Recent deploy increased timeout pressure on checkout",
                confidence=0.71,
                evidence_refs=["ev-001", "ev-002"],
                category="deployment",
            ),
            RootCauseCandidate(
                id="rc-2",
                description="Downstream payments API intermittent 503s",
                confidence=0.54,
                evidence_refs=["ev-003"],
                category="dependency",
            ),
        ],
        recommended_actions=[
            "Roll back canary to 10% and observe error budget",
            "Open incident bridge and page payments on-call",
        ],
        evidence_refs=["ev-001", "ev-002", "ev-003"],
        summary="Mock incident summary with expanded details for development.",
    )


@app.get("/health")
async def health() -> dict:
    return make_success({"status": "healthy"})


@app.post("/api/v1/events/ingest")
async def ingest_event(body: IngestEventBody) -> dict:
    try:
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        normalized = NormalizedEvent(
            event_id=event_id,
            source=body.source.strip(),
            source_type=body.source_type.strip().lower(),
            object_type=body.object_type.strip(),
            object_id=body.object_id.strip(),
            severity=body.severity.strip().lower(),
            summary=body.summary.strip(),
            ingested_at=_now(),
        )
        return make_success(normalized.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/incidents")
async def list_incidents() -> dict:
    try:
        items = [_mock_incident(i, detailed=False) for i in _MOCK_INCIDENT_IDS]
        return make_success({"incidents": [x.model_dump() for x in items]})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict:
    try:
        inc = _mock_incident(incident_id, detailed=True)
        return make_success(inc.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


class AnalyzeResponse(BaseModel):
    incident_id: str
    status: str = Field(description="Mock analysis job status")
    message: str


@app.post("/api/v1/incidents/{incident_id}/analyze")
async def analyze_incident(incident_id: str) -> dict:
    try:
        payload = AnalyzeResponse(
            incident_id=incident_id,
            status="queued",
            message="Mock analysis triggered; results will be available asynchronously",
        )
        return make_success(payload.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))
