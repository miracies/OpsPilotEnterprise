from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from opspilot_schema.memory import (
    MemoryAgentAnalyzeRequest,
    MemoryCreateRequest,
    MemoryEntity,
    MemoryEvidenceRef,
)


def extract_memory_candidates(body: MemoryAgentAnalyzeRequest) -> tuple[bool, list[MemoryCreateRequest], str]:
    if body.input_type in {"incident_summary", "diagnosis_result", "incident"}:
        return _extract_incident_memory(body)
    return False, [], "input type has no long-term memory extractor"


def _extract_incident_memory(body: MemoryAgentAnalyzeRequest) -> tuple[bool, list[MemoryCreateRequest], str]:
    content = body.content or {}
    root_cause = _text(content.get("root_cause") or _nested(content, "root_cause.description"))
    symptom = _text(content.get("symptom") or _nested(content, "symptom.description") or content.get("summary"))
    result = _text(content.get("result") or _nested(content, "resolution.result") or content.get("status"))
    incident_id = _text(content.get("incident_id") or content.get("id") or body.request_id)
    severity = _text(content.get("severity") or _nested(content, "incident.severity") or "P3")
    resource_type = _text(content.get("resource_type") or content.get("target_type") or "resource")
    resource_id = _text(content.get("resource_id") or content.get("target_id") or _nested(content, "resource.vm") or "")
    resource_name = _text(content.get("resource_name") or content.get("target_name") or _nested(content, "resource.vm") or resource_id)
    evidence = content.get("evidence") or content.get("evidences") or []
    actions = content.get("actions") or _nested(content, "resolution.actions") or content.get("recommended_actions") or []

    value_markers = [
        bool(root_cause),
        severity.upper() in {"P0", "P1", "P2", "CRITICAL", "HIGH"},
        "resolved" in result.lower() or "恢复" in result,
        "ha" in _jsonish(content).lower(),
        "vsan" in _jsonish(content).lower(),
        "hardware" in _jsonish(content).lower() or "硬件" in _jsonish(content),
        "change" in _jsonish(content).lower() or "变更" in _jsonish(content),
    ]
    if not any(value_markers):
        return False, [], "incident has no confirmed root cause or reusable operational value"

    tags = ["incident"]
    blob = _jsonish(content).lower()
    for tag in ("vmware", "vsan", "ha", "storage", "network", "latency", "production", "change"):
        if tag in blob:
            tags.append(tag)
    if "vmware" not in tags and ("vm" in resource_type.lower() or "esxi" in blob or "vcenter" in blob):
        tags.append("vmware")
    tags = sorted(set(tags))

    confidence = _confidence(content)
    importance = "critical" if severity.upper() in {"P0", "CRITICAL"} else "high" if severity.upper() in {"P1", "P2", "HIGH"} else "medium"
    now = datetime.now(timezone.utc).date().isoformat()
    title_target = resource_name or incident_id
    title = f"{title_target} incident memory: {root_cause or symptom or incident_id}".strip()
    summary = f"{now}: {symptom or 'Incident analyzed'}"
    if root_cause:
        summary += f"; root cause: {root_cause}"
    if result:
        summary += f"; result: {result}"

    entities = []
    if resource_id or resource_name:
        entities.append(
            MemoryEntity(
                entity_type=_normalize_entity_type(resource_type),
                entity_id=resource_id or None,
                entity_name=resource_name or None,
                properties={"source_resource_type": resource_type},
            )
        )
    resource = content.get("resource")
    if isinstance(resource, dict):
        for key in ("vc", "datacenter", "cluster", "host", "vm", "datastore"):
            if resource.get(key):
                entities.append(MemoryEntity(entity_type=key, entity_id=str(resource.get(key)), entity_name=str(resource.get(key))))

    evidence_refs = []
    if isinstance(evidence, list):
        for idx, item in enumerate(evidence[:20], start=1):
            if isinstance(item, dict):
                evidence_refs.append(
                    MemoryEvidenceRef(
                        evidence_id=str(item.get("evidence_id") or item.get("id") or f"{incident_id}-evidence-{idx}"),
                        evidence_type=str(item.get("type") or item.get("source_type") or "evidence"),
                        evidence_uri=item.get("uri"),
                    )
                )
            else:
                evidence_refs.append(MemoryEvidenceRef(evidence_id=f"{incident_id}-evidence-{idx}", evidence_type="text"))

    memory = MemoryCreateRequest(
        tenant_id=body.tenant_id,
        user_id=body.user_id,
        memory_type="vmware_incident_memory" if "vmware" in tags else "incident_memory",
        title=title[:500],
        summary=summary[:2000],
        content={
            "incident_id": incident_id,
            "severity": severity,
            "symptom": symptom,
            "root_cause": root_cause,
            "resolution": result,
            "actions": actions if isinstance(actions, list) else [str(actions)],
            "raw": content,
        },
        source=body.source,
        source_id=incident_id,
        importance=importance,
        confidence=confidence,
        retention_policy="long_term",
        entities=entities,
        tags=tags,
        evidence_refs=evidence_refs,
    )
    return True, [memory], "incident memory candidate extracted"


def _nested(data: dict[str, Any], dotted: str) -> Any:
    value: Any = data
    for part in dotted.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return _jsonish(value)
    return str(value).strip()


def _jsonish(value: Any) -> str:
    try:
        import json

        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _confidence(content: dict[str, Any]) -> float:
    for value in (
        content.get("confidence"),
        _nested(content, "root_cause.confidence"),
        _nested(content, "analysis.confidence"),
    ):
        try:
            if value is not None:
                return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            pass
    return 0.82 if content.get("root_cause") else 0.62


def _normalize_entity_type(value: str) -> str:
    lowered = (value or "").lower()
    if lowered in {"vmware.vm", "virtual_machine", "virtualmachine"}:
        return "vm"
    if lowered in {"vmware.host", "esxi", "hostsystem"}:
        return "host"
    if lowered in {"vmware.cluster"}:
        return "cluster"
    if lowered in {"vmware.datastore"}:
        return "datastore"
    return lowered.replace("vmware.", "") or "resource"

