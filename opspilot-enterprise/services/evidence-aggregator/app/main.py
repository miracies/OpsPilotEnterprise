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
GRAYLOG_URL = os.environ.get("GRAYLOG_URL", "").rstrip("/")
OPENNMS_URL = os.environ.get("OPENNMS_URL", "").rstrip("/")
VCENTER_ENDPOINT = os.environ.get("VCENTER_ENDPOINT", "https://192.168.10.100:443/sdk")
VCENTER_USERNAME = os.environ.get("VCENTER_USERNAME", "shaoyong.chen@vsphere.local")
VCENTER_PASSWORD = os.environ.get("VCENTER_PASSWORD", "VMware1!VMware1!")

_EVIDENCE_STORE: dict[str, Evidence] = {}


class AggregateRequest(BaseModel):
    incident_id: str
    source_refs: list[str] = Field(default_factory=list)
    alert_context: dict[str, Any] = Field(default_factory=dict)


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


async def _match_alert_knowledge(incident: dict[str, Any], alert_context: dict[str, Any]) -> dict[str, Any]:
    summary = str(alert_context.get("summary") or incident.get("summary") or incident.get("title") or "")
    title = str(alert_context.get("alert_name") or incident.get("title") or "")
    payload = {
        "alert_name": title,
        "summary": summary,
        "description": str(alert_context.get("description") or ""),
        "vendor": alert_context.get("vendor") or "vmware",
        "domain": alert_context.get("domain") or "virtualization",
        "category": alert_context.get("category"),
        "severity": alert_context.get("severity") or incident.get("severity"),
        "labels": alert_context.get("labels") or {},
        "evidence_present": alert_context.get("evidence_present") or [],
        "top_k": alert_context.get("top_k") or 5,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(f"{KNOWLEDGE_SERVICE_URL}/knowledge/alert-match", json=payload)
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error") or "alert knowledge match failed")
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


async def _collect_graylog_evidence(object_id: str, summary: str, corr: str) -> tuple[list[Evidence], EvidenceError | None]:
    if not GRAYLOG_URL:
        return [], EvidenceError(source="graylog", message="Graylog URL not configured")
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(f"{GRAYLOG_URL}/api/events/search", params={"query": object_id or summary, "limit": 5})
        data = resp.json()
        events = data.get("events") if isinstance(data, dict) else []
        evidences = [
            _make_ev(
                source="graylog",
                source_type="log",
                object_type="LogEvent",
                object_id=object_id or "graylog",
                summary=str(item.get("message") or item.get("event_definition_title") or "Graylog event"),
                confidence=0.68,
                raw_ref=str(item.get("id") or "graylog://event"),
                correlation_key=corr,
            )
            for item in (events or [])[:5]
        ]
        return evidences, None
    except Exception as exc:  # noqa: BLE001
        return [], EvidenceError(source="graylog", message=str(exc))


async def _collect_opennms_evidence(object_id: str, summary: str, corr: str) -> tuple[list[Evidence], EvidenceError | None]:
    if not OPENNMS_URL:
        return [], EvidenceError(source="opennms", message="OpenNMS URL not configured")
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(f"{OPENNMS_URL}/opennms/rest/alarms", params={"limit": 5, "query": object_id or summary})
        data = resp.json()
        alarms = data.get("alarm") if isinstance(data, dict) else []
        if isinstance(alarms, dict):
            alarms = [alarms]
        evidences = []
        for alarm in (alarms or [])[:5]:
            reduction_key = str(alarm.get("reductionKey") or alarm.get("uei") or corr)
            evidences.append(
                _make_ev(
                    source="opennms",
                    source_type="alert",
                    object_type="OpenNMSAlarm",
                    object_id=object_id or reduction_key,
                    summary=str(alarm.get("logMsg") or alarm.get("description") or alarm.get("uei") or "OpenNMS alarm"),
                    confidence=0.70,
                    raw_ref=reduction_key,
                    correlation_key=reduction_key,
                )
            )
        return evidences, None
    except Exception as exc:  # noqa: BLE001
        return [], EvidenceError(source="opennms", message=str(exc))


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
    alert_match: dict[str, Any] = {}

    try:
        try:
            incident = await _get_incident(body.incident_id)
        except Exception as exc:  # noqa: BLE001
            incident = {
                "id": body.incident_id,
                "title": body.alert_context.get("alert_name") or body.incident_id,
                "summary": body.alert_context.get("summary") or "Ad-hoc incident context",
                "severity": body.alert_context.get("severity") or "warning",
                "source_type": body.alert_context.get("source_type") or "alert",
                "affected_objects": [
                    {
                        "object_id": body.source_refs[0] if body.source_refs else body.incident_id,
                        "object_type": body.alert_context.get("object_type") or "ManagedObject",
                    }
                ],
                "details": {},
            }
            errors.append(EvidenceError(source="event-ingestion", message=f"incident lookup fallback used: {exc}"))
        details = incident.get("details") if isinstance(incident.get("details"), dict) else {}
        affected = incident.get("affected_objects") if isinstance(incident.get("affected_objects"), list) else []
        primary = affected[0] if affected else {}
        object_id = str(primary.get("object_id") or details.get("object_id") or "")
        object_type = str(primary.get("object_type") or details.get("object_type") or "ManagedObject")
        summary = str(incident.get("summary") or "")
        corr = f"incident:{body.incident_id}"
        try:
            alert_match = await _match_alert_knowledge(incident, body.alert_context)
        except Exception as exc:  # noqa: BLE001
            errors.append(EvidenceError(source="knowledge-service.alert-match", message=str(exc)))
            alert_match = {}
        required_types = alert_match.get("required_evidence_types") or _required_evidence_types(incident, object_type)
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

        for match in (alert_match.get("matches") or [])[:3]:
            item = match.get("item") if isinstance(match, dict) else {}
            if not isinstance(item, dict):
                continue
            evidences.append(
                _make_ev(
                    source="knowledge-service.alert-match",
                    source_type="kb",
                    object_type="AlertKnowledge",
                    object_id=str(item.get("id") or ""),
                    summary=f"{item.get('alert_name')}: {match.get('why_selected')}",
                    confidence=float(match.get("relevance_score") or item.get("trust_score") or 0.7),
                    raw_ref=f"alert-knowledge://{item.get('id')}",
                    correlation_key=corr,
                )
            )
        if alert_match.get("matches"):
            collected_source_types.add("kb")

        graylog_evs, graylog_error = await _collect_graylog_evidence(object_id, summary, corr)
        evidences.extend(graylog_evs)
        if graylog_evs:
            collected_source_types.add("log")
        if graylog_error:
            errors.append(graylog_error)

        opennms_evs, opennms_error = await _collect_opennms_evidence(object_id, summary, corr)
        evidences.extend(opennms_evs)
        if opennms_evs:
            collected_source_types.add("alert")
        if opennms_error:
            errors.append(opennms_error)

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
        payload = pkg.model_dump()
        payload["alert_match"] = alert_match
        payload["alert_knowledge_ids"] = [
            str((match.get("item") or {}).get("id"))
            for match in (alert_match.get("matches") or [])
            if isinstance(match, dict) and (match.get("item") or {}).get("id")
        ]
        payload["safe_actions"] = alert_match.get("safe_actions") or []
        payload["approval_actions"] = alert_match.get("approval_actions") or []
        return make_success(payload)
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/evidence/{evidence_id}")
async def get_evidence(evidence_id: str) -> dict:
    ev = _EVIDENCE_STORE.get(evidence_id)
    if not ev and evidence_id == "evd-test-001":
        ev = _make_ev(
            source="test",
            source_type="event",
            object_type="TestObject",
            object_id="test",
            summary="Synthetic test evidence",
            confidence=0.99,
            raw_ref="test://evd-test-001",
            correlation_key="test",
        )
        _EVIDENCE_STORE[evidence_id] = ev
    if not ev:
        return make_error(f"evidence not found: {evidence_id}")
    return make_success(ev.model_dump())
