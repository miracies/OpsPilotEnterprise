from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

from opspilot_schema.evidence import (
    Evidence,
    EvidenceContradiction,
    EvidenceCoverage,
    EvidenceError,
    EvidencePackage,
    EvidenceSourceStats,
)
from opspilot_schema.envelope import make_error, make_success

EvidenceSource = Literal["event", "metric", "log", "topology", "kb", "change", "external_kb", "detail", "alert"]

app = FastAPI(title="OpsPilot Evidence Aggregator")

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020").rstrip("/")
EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060").rstrip("/")
KNOWLEDGE_SERVICE_URL = os.environ.get("KNOWLEDGE_SERVICE_URL", "http://127.0.0.1:8072").rstrip("/")
VCENTER_ENDPOINT = os.environ.get("VCENTER_ENDPOINT", "https://10.0.80.21:443/sdk")
VCENTER_USERNAME = os.environ.get("VCENTER_USERNAME", "administrator@vsphere.local")
VCENTER_PASSWORD = os.environ.get("VCENTER_PASSWORD", "VMware1!")

_EVIDENCE_STORE: dict[str, Evidence] = {}


class AggregateRequest(BaseModel):
    incident_id: str
    source_refs: list[str] = Field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connection() -> dict[str, Any]:
    return {
        "endpoint": VCENTER_ENDPOINT,
        "username": VCENTER_USERNAME,
        "password": VCENTER_PASSWORD,
        "insecure": True,
    }


async def _invoke_tool(tool_name: str, input_payload: dict[str, Any], timeout_sec: float = 12.0) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        resp = await client.post(
            f"{TOOL_GATEWAY_URL}/api/v1/invoke/{tool_name}",
            json={"input": input_payload, "dry_run": False},
        )
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error") or f"invoke failed: {tool_name}")
    return body.get("data", {}) or {}


async def _get_incident(incident_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/incidents/{incident_id}")
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error") or f"incident not found: {incident_id}")
    return body.get("data", {}) or {}


async def _search_kb(query_text: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            f"{KNOWLEDGE_SERVICE_URL}/knowledge/articles",
            params={"status": "published", "q": query_text},
        )
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error") or "knowledge query failed")
    return (body.get("data") or {}).get("items", []) or []


def _required_evidence_types(incident: dict[str, Any], object_type: str) -> list[str]:
    source_type = str(incident.get("source_type") or "").lower()
    object_type_l = object_type.lower()
    if "host" in object_type_l or source_type == "vmware_non_green":
        return ["detail", "event", "alert", "metric", "topology", "change"]
    if "virtualmachine" in object_type_l or "vm" in object_type_l or source_type == "vm_guest_down":
        return ["detail", "event", "metric", "topology", "change"]
    if "pod" in object_type_l or "deployment" in object_type_l or source_type.startswith("k8s_"):
        return ["detail", "event", "metric", "topology", "change"]
    return ["event", "detail", "topology"]


def _freshness_score(evidences: list[Evidence]) -> float:
    if not evidences:
        return 0.0
    now = datetime.now(timezone.utc)
    fresh_count = 0
    for ev in evidences:
        try:
            ts = datetime.fromisoformat(ev.timestamp.replace("Z", "+00:00"))
            if (now - ts).total_seconds() <= 3600:
                fresh_count += 1
        except Exception:
            continue
    return round(fresh_count / max(len(evidences), 1), 2)


def _make_ev(
    *,
    source: str,
    source_type: EvidenceSource,
    object_type: str,
    object_id: str,
    summary: str,
    confidence: float,
    raw_ref: str | None = None,
    correlation_key: str | None = None,
) -> Evidence:
    ev = Evidence(
        evidence_id=f"ev-{uuid.uuid4().hex[:12]}",
        source=source,
        source_type=source_type,
        object_type=object_type,
        object_id=object_id,
        timestamp=_now(),
        summary=summary,
        raw_ref=raw_ref,
        confidence=max(0.0, min(confidence, 1.0)),
        correlation_key=correlation_key,
    )
    _EVIDENCE_STORE[ev.evidence_id] = ev
    return ev


def _detect_contradictions(evidences: list[Evidence]) -> list[EvidenceContradiction]:
    contradictions: list[EvidenceContradiction] = []
    detail_evs = [e for e in evidences if e.source_type == "detail"]
    alert_evs = [e for e in evidences if e.source_type == "alert"]
    metric_evs = [e for e in evidences if e.source_type == "metric"]

    green_detail = next(
        (e for e in detail_evs if "overall_status=green" in e.summary.lower() or "status=green" in e.summary.lower()),
        None,
    )
    active_alert = next(
        (e for e in alert_evs if "yellow" in e.summary.lower() or "red" in e.summary.lower() or "alert" in e.summary.lower()),
        None,
    )
    if green_detail and active_alert:
        contradictions.append(
            EvidenceContradiction(
                type="status_mismatch",
                summary="Object detail indicates healthy state while alert evidence still indicates an active issue.",
                evidence_refs=[green_detail.evidence_id, active_alert.evidence_id],
                severity="high",
            )
        )

    quiet_metric = next(
        (e for e in metric_evs if "latest={}" in e.summary.lower() or "latest=[]" in e.summary.lower()),
        None,
    )
    abnormal_detail = next(
        (e for e in detail_evs if "yellow" in e.summary.lower() or "red" in e.summary.lower() or "notready" in e.summary.lower()),
        None,
    )
    if quiet_metric and abnormal_detail:
        contradictions.append(
            EvidenceContradiction(
                type="metric_detail_mismatch",
                summary="Detail evidence indicates an unhealthy object, but metrics do not show a matching anomaly.",
                evidence_refs=[quiet_metric.evidence_id, abnormal_detail.evidence_id],
                severity="medium",
            )
        )

    return contradictions


@app.get("/health")
async def health() -> dict:
    return make_success({"status": "healthy"})


@app.post("/api/v1/evidence/aggregate")
async def aggregate(body: AggregateRequest) -> dict:
    evidences: list[Evidence] = []
    errors: list[EvidenceError] = []
    collected_source_types: set[str] = set()

    try:
        incident = await _get_incident(body.incident_id)
        details = incident.get("details") if isinstance(incident.get("details"), dict) else {}
        affected = incident.get("affected_objects") if isinstance(incident.get("affected_objects"), list) else []
        primary = affected[0] if affected else {}
        object_id = str(primary.get("object_id") or details.get("object_id") or "")
        object_type = str(primary.get("object_type") or details.get("object_type") or "ManagedObject")
        summary = str(incident.get("summary") or "")
        corr = f"incident:{body.incident_id}"
        required_types = _required_evidence_types(incident, object_type)
        requested_sources = len(required_types)

        if summary:
            evidences.append(
                _make_ev(
                    source="event-ingestion",
                    source_type="event",
                    object_type=object_type,
                    object_id=object_id or body.incident_id,
                    summary=summary,
                    confidence=0.78,
                    raw_ref=f"incident://{body.incident_id}",
                    correlation_key=corr,
                )
            )
            collected_source_types.add("event")

        async def _safe_call(source: str, coro):
            try:
                return source, await coro, None
            except Exception as exc:  # noqa: BLE001
                return source, None, str(exc)

        tasks: list[asyncio.Task] = []
        object_type_l = object_type.lower()
        detail_tool_name: str | None = None
        if object_id:
            if "host" in object_type_l:
                detail_tool_name = "vmware.get_host_detail"
            elif "virtualmachine" in object_type_l or "vm" in object_type_l:
                detail_tool_name = "vmware.get_vm_detail"

            if detail_tool_name:
                detail_payload = {"connection": _connection()}
                detail_payload["host_id" if detail_tool_name.endswith("host_detail") else "vm_id"] = object_id
                tasks.append(
                    asyncio.create_task(
                        _safe_call(
                            detail_tool_name,
                            _invoke_tool(detail_tool_name, detail_payload, timeout_sec=10.0),
                        )
                    )
                )

            tasks.append(
                asyncio.create_task(
                    _safe_call(
                        "vmware.query_events",
                        _invoke_tool(
                            "vmware.query_events",
                            {"connection": _connection(), "object_id": object_id, "hours": 24},
                            timeout_sec=10.0,
                        ),
                    )
                )
            )
            tasks.append(
                asyncio.create_task(
                    _safe_call(
                        "vmware.query_metrics",
                        _invoke_tool(
                            "vmware.query_metrics",
                            {"connection": _connection(), "object_id": object_id, "metric": "cpu_usage_percent"},
                            timeout_sec=10.0,
                        ),
                    )
                )
            )
            tasks.append(
                asyncio.create_task(
                    _safe_call(
                        "vmware.query_alerts",
                        _invoke_tool("vmware.query_alerts", {"connection": _connection()}, timeout_sec=10.0),
                    )
                )
            )

        tasks.append(
            asyncio.create_task(
                _safe_call(
                    "vmware.get_vcenter_inventory",
                    _invoke_tool("vmware.get_vcenter_inventory", {"connection": _connection()}, timeout_sec=12.0),
                )
            )
        )

        results = await asyncio.gather(*tasks)
        for source, output, err in results:
            if err:
                errors.append(EvidenceError(source=source, message=err))
                continue

            if source == "vmware.query_events" and output:
                for item in (output.get("events") or [])[:8]:
                    evidences.append(
                        _make_ev(
                            source="vmware.query_events",
                            source_type="event",
                            object_type=object_type,
                            object_id=object_id,
                            summary=str(item.get("full_message") or item.get("message") or "vCenter event"),
                            confidence=0.74,
                            raw_ref=f"tool://vmware.query_events/{object_id}",
                            correlation_key=corr,
                        )
                    )
                collected_source_types.add("event")
            elif source in {"vmware.get_host_detail", "vmware.get_vm_detail"} and output:
                detail_bits: list[str] = []
                for key in ("overall_status", "connection_state", "power_state", "host_name", "datastore_name"):
                    value = output.get(key)
                    if value not in (None, ""):
                        detail_bits.append(f"{key}={value}")
                evidences.append(
                    _make_ev(
                        source=source,
                        source_type="detail",
                        object_type=object_type,
                        object_id=object_id,
                        summary=", ".join(detail_bits) or f"{source} available",
                        confidence=0.86,
                        raw_ref=f"tool://{source}/{object_id}",
                        correlation_key=corr,
                    )
                )
                collected_source_types.add("detail")
            elif source == "vmware.query_metrics" and output:
                points = output.get("points") or output.get("series") or []
                latest = points[-1] if isinstance(points, list) and points else {}
                evidences.append(
                    _make_ev(
                        source="vmware.query_metrics",
                        source_type="metric",
                        object_type=object_type,
                        object_id=object_id,
                        summary=f"metric={output.get('metric', 'cpu_usage_percent')} latest={latest}",
                        confidence=0.72,
                        raw_ref=f"tool://vmware.query_metrics/{object_id}",
                        correlation_key=corr,
                    )
                )
                collected_source_types.add("metric")
            elif source == "vmware.query_alerts" and output:
                added = False
                for alert in (output.get("alerts") or [])[:6]:
                    alert_blob = json.dumps(alert, ensure_ascii=False).lower()
                    if object_id and object_id.lower() not in alert_blob and str(primary.get("object_name", "")).lower() not in alert_blob:
                        continue
                    evidences.append(
                        _make_ev(
                            source="vmware.query_alerts",
                            source_type="alert",
                            object_type=object_type,
                            object_id=object_id or body.incident_id,
                            summary=str(alert.get("message") or alert.get("summary") or "vCenter alert"),
                            confidence=0.76,
                            raw_ref="tool://vmware.query_alerts",
                            correlation_key=corr,
                        )
                    )
                    added = True
                if added:
                    collected_source_types.add("alert")
            elif source == "vmware.get_vcenter_inventory" and output:
                summary_data = output.get("summary", {})
                evidences.append(
                    _make_ev(
                        source="vmware.get_vcenter_inventory",
                        source_type="topology",
                        object_type="TopologyGraph",
                        object_id=object_id or "vcenter",
                        summary=(
                            f"inventory clusters={summary_data.get('cluster_count', 0)}, "
                            f"hosts={summary_data.get('host_count', 0)}, vms={summary_data.get('vm_count', 0)}"
                        ),
                        confidence=0.70,
                        raw_ref="tool://vmware.get_vcenter_inventory",
                        correlation_key=corr,
                    )
                )
                collected_source_types.add("topology")

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                audit_resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/audit/logs", params={"limit": 100})
            audit_body = audit_resp.json()
            if audit_body.get("success"):
                for item in (audit_body.get("data") or {}).get("items", []):
                    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                    metadata_blob = json.dumps(metadata, ensure_ascii=False)
                    if object_id and object_id not in metadata_blob and body.incident_id not in metadata_blob:
                        continue
                    evidences.append(
                        _make_ev(
                            source="event-ingestion.audit",
                            source_type="change",
                            object_type=object_type,
                            object_id=object_id or body.incident_id,
                            summary=f"{item.get('event_type')}: {item.get('action')}",
                            confidence=0.64,
                            raw_ref=f"audit://{item.get('id')}",
                            correlation_key=corr,
                        )
                    )
                if any(ev.source_type == "change" for ev in evidences):
                    collected_source_types.add("change")
        except Exception as exc:  # noqa: BLE001
            errors.append(EvidenceError(source="event-ingestion.audit", message=str(exc)))

        try:
            kb_query = summary or object_id or incident.get("title") or "incident"
            articles = await _search_kb(str(kb_query))
            for article in articles[:3]:
                evidences.append(
                    _make_ev(
                        source="knowledge-service",
                        source_type="kb",
                        object_type="KnowledgeArticle",
                        object_id=str(article.get("id") or ""),
                        summary=str(article.get("title") or "knowledge article"),
                        confidence=float(article.get("confidence_score") or 0.65),
                        raw_ref=f"knowledge://{article.get('id')}",
                        correlation_key=corr,
                    )
                )
            if articles:
                collected_source_types.add("kb")
        except Exception as exc:  # noqa: BLE001
            errors.append(EvidenceError(source="knowledge-service", message=str(exc)))

        errors.append(EvidenceError(source="logs", message="log source not configured in current deployment"))

        present_types = sorted({ev.source_type for ev in evidences})
        missing_critical = [ev_type for ev_type in required_types if ev_type not in present_types]
        freshness_score = _freshness_score(evidences)
        sufficiency_score = round(
            max(
                0.0,
                min(
                    1.0,
                    (len([ev_type for ev_type in required_types if ev_type in present_types]) / max(len(required_types), 1)) * 0.8
                    + freshness_score * 0.2,
                ),
            ),
            2,
        )
        contradictions = _detect_contradictions(evidences)

        source_stats: list[EvidenceSourceStats] = []
        for source_type in {"event", "metric", "topology", "kb", "log", "change", "external_kb", "detail", "alert"}:
            items = [ev for ev in evidences if ev.source_type == source_type]
            if not items:
                continue
            avg = sum(ev.confidence for ev in items) / max(len(items), 1)
            source_stats.append(
                EvidenceSourceStats(
                    source_type=source_type,
                    count=len(items),
                    avg_confidence=round(avg, 3),
                )
            )

        coverage = EvidenceCoverage(
            requested_sources=requested_sources,
            collected_sources=len(collected_source_types),
            missing_sources=max(0, requested_sources - len(collected_source_types)),
            required_evidence_types=required_types,
            present_evidence_types=present_types,
            missing_critical_evidence=missing_critical,
            sufficiency_score=sufficiency_score,
            freshness_score=freshness_score,
        )

        pkg = EvidencePackage(
            package_id=f"pkg-{uuid.uuid4().hex[:12]}",
            incident_id=body.incident_id,
            evidences=evidences,
            created_at=_now(),
            source_stats=source_stats,
            coverage=coverage,
            errors=errors,
            required_evidence_types=required_types,
            present_evidence_types=present_types,
            missing_critical_evidence=missing_critical,
            sufficiency_score=sufficiency_score,
            freshness_score=freshness_score,
            contradictions=contradictions,
        )
        return make_success(pkg.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/evidence/{evidence_id}")
async def get_evidence(evidence_id: str) -> dict:
    ev = _EVIDENCE_STORE.get(evidence_id)
    if not ev:
        return make_error(f"evidence not found: {evidence_id}")
    return make_success(ev.model_dump())
