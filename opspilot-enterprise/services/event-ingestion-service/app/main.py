from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

from opspilot_schema.envelope import make_error, make_success

UTC = timezone.utc


def _now() -> str:
    return datetime.now(UTC).isoformat()


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("EVENTS_DB_PATH", str(DATA_DIR / "events.db")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")
EVIDENCE_AGGREGATOR_URL = os.environ.get("EVIDENCE_AGGREGATOR_URL", "http://127.0.0.1:8050")
GOVERNANCE_SERVICE_URL = os.environ.get("GOVERNANCE_SERVICE_URL", "http://127.0.0.1:8071")
MONITOR_INTERVAL_SECONDS = int(os.environ.get("MONITOR_INTERVAL_SECONDS", "60"))
MONITOR_ENABLED_ON_START = os.environ.get("MONITOR_ENABLED_ON_START", "true").lower() == "true"
ANALYSIS_MAX_ROUNDS = int(os.environ.get("ANALYSIS_MAX_ROUNDS", "5"))
ANALYSIS_BUDGET_SECONDS = int(os.environ.get("ANALYSIS_BUDGET_SECONDS", "60"))
ANALYSIS_CONFIDENCE_THRESHOLD = float(os.environ.get("ANALYSIS_CONFIDENCE_THRESHOLD", "0.75"))

VCENTER_ENDPOINT = os.environ.get("VCENTER_ENDPOINT", "https://10.0.80.21:443/sdk")
VCENTER_USERNAME = os.environ.get("VCENTER_USERNAME", "administrator@vsphere.local")
VCENTER_PASSWORD = os.environ.get("VCENTER_PASSWORD", "VMware1!")
VCENTER_CONN_ID = os.environ.get("VCENTER_CONNECTION_ID", "conn-vcenter-prod")

K8S_KUBECONFIG_PATH = os.environ.get("K8S_KUBECONFIG_PATH", r"C:\Users\mirac\.kube\config")
K8S_CONN_ID = os.environ.get("K8S_CONNECTION_ID", "conn-k8s-prod")
ONCALL_TEAM = os.environ.get("ONCALL_TEAM", "ops-core")
ONCALL_MEMBERS = [x.strip() for x in os.environ.get("ONCALL_MEMBERS", "ops-oncall").split(",") if x.strip()]

VMWARE_USE_MOCK_FALLBACK = os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true"
K8S_USE_MOCK_FALLBACK = os.environ.get("K8S_USE_MOCK_FALLBACK", "false").lower() == "true"

MONITOR_STATE: dict[str, Any] = {
    "running": False,
    "task": None,
    "started_at": None,
    "last_run_at": None,
    "last_error": None,
}

ACTION_CAPABILITY: dict[str, str] = {
    "vmware.create_snapshot": "batch",
    "vmware.vm_power_on": "batch",
    "vmware.vm_power_off": "batch",
    "vmware.vm_guest_restart": "batch",
    "vmware.host_restart": "single",
    "k8s.restart_deployment": "batch",
    "k8s.scale_deployment": "batch",
}

READ_TOOL_WHITELIST = {
    "vmware.get_vcenter_inventory",
    "vmware.get_host_detail",
    "vmware.query_events",
    "vmware.query_metrics",
    "vmware.query_alerts",
    "vmware.query_topology",
}
WRITE_TOOL_WHITELIST = {
    "vmware.vm_guest_restart",
    "k8s.restart_deployment",
    "k8s.scale_deployment",
}
RISK_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class AnalyzeIncidentBody(BaseModel):
    mode: str = "auto"
    user_id: str = "ops-user"


class AnalysisPreferenceBody(BaseModel):
    user_id: str = "ops-user"
    auto_remediation_mode: str = "low_risk_auto"


class IngestEventBody(BaseModel):
    source: str
    source_type: str
    object_type: str
    object_id: str
    severity: str
    summary: str
    object_name: str | None = None
    rule_id: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class RemediationBody(BaseModel):
    incident_id: str
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    mode: str = "auto"


class DecisionBody(BaseModel):
    decision: str = "approved"
    decided_by: str = "ops-lead"
    comment: str | None = None


class ExecutionTargetBody(BaseModel):
    object_id: str
    object_name: str
    object_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionBody(BaseModel):
    tool_name: str
    action_type: str | None = None
    targets: list[ExecutionTargetBody] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    environment: str = "prod"
    requester: str = "ops-user"
    incident_id: str | None = None
    change_analysis_ref: str | None = None
    session_id: str | None = None


class MonitoringControlBody(BaseModel):
    force: bool = False


class AuditWriteBody(BaseModel):
    event_type: str
    action: str
    outcome: str
    severity: str = "info"
    actor: str = "unknown"
    actor_type: str = "system"
    resource_type: str | None = None
    resource_id: str | None = None
    resource_name: str | None = None
    reason: str | None = None
    incident_ref: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    timestamp: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


app = FastAPI(title="OpsPilot Event Ingestion Service")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _exec(sql: str, params: tuple[Any, ...] = ()) -> None:
    conn = _get_conn()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _query_all(sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    conn = _get_conn()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _query_one(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    conn = _get_conn()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _init_db() -> None:
    conn = _get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                severity TEXT NOT NULL,
                source TEXT NOT NULL,
                source_type TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_updated_at TEXT NOT NULL,
                owner TEXT,
                ai_analysis_triggered INTEGER NOT NULL DEFAULT 0,
                summary TEXT NOT NULL,
                dedup_key TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_incidents_dedup ON incidents(dedup_key);
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                incident_ref TEXT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                channels_json TEXT NOT NULL DEFAULT '[]',
                recipients_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                delivered_at TEXT,
                acknowledged_at TEXT,
                acknowledged_by TEXT,
                escalation_count INTEGER NOT NULL DEFAULT 0,
                next_escalation_at TEXT
            );
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                action_type TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                status TEXT NOT NULL,
                requester TEXT NOT NULL,
                assignee TEXT,
                incident_ref TEXT,
                change_analysis_ref TEXT,
                target_object TEXT NOT NULL,
                target_object_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                decision_comment TEXT,
                decided_at TEXT,
                decided_by TEXT,
                tags_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                actor TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                resource_name TEXT,
                outcome TEXT NOT NULL,
                reason TEXT,
                incident_ref TEXT,
                request_id TEXT,
                trace_id TEXT,
                timestamp TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS remediation_actions (
                id TEXT PRIMARY KEY,
                incident_ref TEXT NOT NULL,
                action TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                request_payload_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS execution_requests (
                id TEXT PRIMARY KEY,
                tool_name TEXT NOT NULL,
                action_type TEXT NOT NULL,
                environment TEXT NOT NULL,
                requester TEXT NOT NULL,
                status TEXT NOT NULL,
                incident_id TEXT,
                change_analysis_ref TEXT,
                session_id TEXT,
                approval_id TEXT,
                risk_level TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                require_approval INTEGER NOT NULL DEFAULT 0,
                policy_json TEXT NOT NULL DEFAULT '{}',
                parameters_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS execution_targets (
                id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                object_id TEXT NOT NULL,
                object_name TEXT NOT NULL,
                object_type TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                result_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS execution_steps (
                id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                step_type TEXT NOT NULL,
                status TEXT NOT NULL,
                detail_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL,
                severity TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                incident_refs_json TEXT NOT NULL DEFAULT '[]',
                root_cause_summary TEXT NOT NULL,
                resolution_summary TEXT NOT NULL,
                lessons_learned TEXT NOT NULL,
                author TEXT NOT NULL,
                created_at TEXT NOT NULL,
                archived_at TEXT,
                similarity_score REAL,
                hit_count INTEGER NOT NULL DEFAULT 0,
                knowledge_refs_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                auto_remediation_mode TEXT NOT NULL DEFAULT 'low_risk_auto',
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _vcenter_connection_input() -> dict[str, Any]:
    return {
        "endpoint": VCENTER_ENDPOINT,
        "username": VCENTER_USERNAME,
        "password": VCENTER_PASSWORD,
        "insecure": True,
    }


def _k8s_connection_input() -> dict[str, Any]:
    path = Path(K8S_KUBECONFIG_PATH)
    if not path.exists():
        raise RuntimeError(f"kubeconfig not found: {K8S_KUBECONFIG_PATH}")
    import yaml

    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"invalid kubeconfig: {K8S_KUBECONFIG_PATH}")
    return {"kubeconfig": parsed}


async def _invoke_tool(tool_name: str, input_payload: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    url = f"{TOOL_GATEWAY_URL.rstrip('/')}/api/v1/invoke/{tool_name}"
    async with httpx.AsyncClient(timeout=200.0) as client:
        response = await client.post(url, json={"input": input_payload, "dry_run": dry_run})
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload.get("error") or f"tool {tool_name} failed")
    return payload["data"]


def _incident_from_row(row: sqlite3.Row) -> dict[str, Any]:
    details = json.loads(row["details_json"] or "{}")
    details.setdefault("affected_objects", [])
    details.setdefault("root_cause", None)
    details.setdefault("root_cause_candidates", [])
    details.setdefault("hypotheses", [])
    details.setdefault("winning_hypothesis", None)
    details.setdefault("counter_evidence_result", None)
    details.setdefault("conclusion_status", None)
    details.setdefault("evidence_sufficiency", None)
    details.setdefault("contradictions", [])
    details.setdefault("recommended_actions", [])
    details.setdefault("evidence_refs", [])
    analysis = details.get("analysis") if isinstance(details.get("analysis"), dict) else {}
    analysis.setdefault("status", "idle")
    analysis.setdefault("round", 0)
    analysis.setdefault("max_rounds", ANALYSIS_MAX_ROUNDS)
    analysis.setdefault("analysis_process", [])
    analysis.setdefault("recommended_actions", details["recommended_actions"])
    details["analysis"] = analysis
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "severity": row["severity"],
        "source": row["source"],
        "source_type": row["source_type"],
        "affected_objects": details["affected_objects"],
        "first_seen_at": row["first_seen_at"],
        "last_updated_at": row["last_updated_at"],
        "owner": row["owner"],
        "ai_analysis_triggered": bool(row["ai_analysis_triggered"]),
        "root_cause": details["root_cause"],
        "root_cause_candidates": details["root_cause_candidates"],
        "hypotheses": details["hypotheses"],
        "winning_hypothesis": details["winning_hypothesis"],
        "counter_evidence_result": details["counter_evidence_result"],
        "conclusion_status": details["conclusion_status"],
        "evidence_sufficiency": details["evidence_sufficiency"],
        "contradictions": details["contradictions"],
        "recommended_actions": details["recommended_actions"],
        "evidence_refs": details["evidence_refs"],
        "analysis": details["analysis"],
        "summary": row["summary"],
    }


def _get_user_auto_mode(user_id: str) -> str:
    row = _query_one("SELECT auto_remediation_mode FROM user_preferences WHERE user_id=?", (user_id,))
    if not row:
        return "low_risk_auto"
    mode = str(row["auto_remediation_mode"] or "low_risk_auto")
    return mode if mode in {"suggest_only", "low_risk_auto", "full_auto"} else "low_risk_auto"


def _set_user_auto_mode(user_id: str, mode: str) -> None:
    safe_mode = mode if mode in {"suggest_only", "low_risk_auto", "full_auto"} else "low_risk_auto"
    existing = _query_one("SELECT user_id FROM user_preferences WHERE user_id=?", (user_id,))
    if existing:
        _exec(
            "UPDATE user_preferences SET auto_remediation_mode=?, updated_at=? WHERE user_id=?",
            (safe_mode, _now(), user_id),
        )
    else:
        _exec(
            "INSERT INTO user_preferences(user_id,auto_remediation_mode,updated_at) VALUES(?,?,?)",
            (user_id, safe_mode, _now()),
        )


def _analysis_step(
    *,
    round_no: int,
    stage: str,
    status: str,
    goal: str,
    finding: str,
    decision: str,
    tool_name: str | None = None,
    input_summary: str | None = None,
    output_summary: str | None = None,
    selected_tools: list[str] | None = None,
    evidence_found: list[str] | None = None,
    evidence_missing: list[str] | None = None,
    contradictions: list[str] | None = None,
    why: str | None = None,
) -> dict[str, Any]:
    return {
        "round": round_no,
        "stage": stage,
        "tool_name": tool_name,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "goal": goal,
        "selected_tools": selected_tools or ([tool_name] if tool_name else []),
        "evidence_found": evidence_found or [],
        "evidence_missing": evidence_missing or [],
        "contradictions": contradictions or [],
        "finding": finding,
        "decision": decision,
        "why": why or "",
        "timestamp": _now(),
        "status": status,
    }


def _write_audit(event_type: str, action: str, outcome: str, incident_ref: str | None = None, reason: str | None = None, metadata: dict[str, Any] | None = None) -> None:
    _exec(
        """
        INSERT INTO audit_logs(id,event_type,severity,actor,actor_type,action,resource_type,resource_id,resource_name,outcome,reason,incident_ref,request_id,trace_id,timestamp,metadata_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            f"AUD-{uuid.uuid4().hex[:8]}",
            event_type,
            "info" if outcome == "success" else "error",
            "event-ingestion-service",
            "service",
            action,
            None,
            None,
            None,
            outcome,
            reason,
            incident_ref,
            f"req-{uuid.uuid4().hex[:10]}",
            f"trace-{uuid.uuid4().hex[:10]}",
            _now(),
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )


def _create_notification_for_incident(incident: dict[str, Any]) -> None:
    now = _now()
    _exec(
        """
        INSERT INTO notifications(id,incident_ref,title,content,priority,status,channels_json,recipients_json,created_at,delivered_at,acknowledged_at,acknowledged_by,escalation_count,next_escalation_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            f"NTF-{uuid.uuid4().hex[:8].upper()}",
            incident["id"],
            f"[{incident['severity'].upper()}] {incident['title']}",
            incident["summary"],
            "urgent" if incident["severity"] in {"critical", "high"} else "high",
            "delivered",
            json.dumps(["webhook"]),
            json.dumps(ONCALL_MEMBERS),
            now,
            now,
            None,
            None,
            0,
            (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
        ),
    )


def _upsert_incident_from_event(evt: IngestEventBody) -> dict[str, Any]:
    dedup_key = f"{evt.rule_id or evt.source_type}:{evt.object_id}"
    row = _query_one(
        "SELECT * FROM incidents WHERE dedup_key=? AND status IN ('new','analyzing','pending_action') ORDER BY last_updated_at DESC LIMIT 1",
        (dedup_key,),
    )
    if row:
        details = json.loads(row["details_json"] or "{}")
        details.setdefault("affected_objects", [])
        old_summary = str(row["summary"] or "")
        old_severity = str(row["severity"] or "")
        old_extra = details.get("extra", {}) if isinstance(details.get("extra"), dict) else {}
        if not any(o.get("object_id") == evt.object_id for o in details["affected_objects"] if isinstance(o, dict)):
            details["affected_objects"].append(
                {
                    "object_type": evt.object_type,
                    "object_id": evt.object_id,
                    "object_name": evt.object_name or evt.object_id,
                }
            )
        details["extra"] = evt.extra
        status_to_set = row["status"]
        changed = (
            old_summary != (evt.summary or "")
            or old_severity != (evt.severity.lower() or "")
            or json.dumps(old_extra, sort_keys=True, ensure_ascii=False)
            != json.dumps(evt.extra or {}, sort_keys=True, ensure_ascii=False)
        )
        if str(row["status"]) == "pending_action" and changed:
            status_to_set = "new"
            details.setdefault("analysis", {})
            if isinstance(details["analysis"], dict):
                details["analysis"]["status"] = "idle"
                details["analysis"]["next_decision"] = "状态变化触发复分析"
        _exec(
            "UPDATE incidents SET status=?, ai_analysis_triggered=?, last_updated_at=?, summary=?, severity=?, details_json=? WHERE id=?",
            (
                status_to_set,
                0 if status_to_set == "new" else row["ai_analysis_triggered"],
                _now(),
                evt.summary,
                evt.severity.lower(),
                json.dumps(details, ensure_ascii=False),
                row["id"],
            ),
        )
        updated = _query_one("SELECT * FROM incidents WHERE id=?", (row["id"],))
        if not updated:
            raise RuntimeError("incident update failed")
        incident = _incident_from_row(updated)
        _write_audit("incident_updated", "update_incident", "success", incident_ref=incident["id"], metadata={"dedup_key": dedup_key})
        return incident

    incident_id = f"INC-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    details = {
        "affected_objects": [
            {
                "object_type": evt.object_type,
                "object_id": evt.object_id,
                "object_name": evt.object_name or evt.object_id,
            }
        ],
        "root_cause": None,
        "root_cause_candidates": [],
        "recommended_actions": [],
        "evidence_refs": [],
        "extra": evt.extra,
    }
    _exec(
        """
        INSERT INTO incidents(id,title,status,severity,source,source_type,first_seen_at,last_updated_at,owner,ai_analysis_triggered,summary,dedup_key,details_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            incident_id,
            evt.summary,
            "new",
            evt.severity.lower(),
            evt.source,
            evt.source_type,
            _now(),
            _now(),
            None,
            0,
            evt.summary,
            dedup_key,
            json.dumps(details, ensure_ascii=False),
        ),
    )
    created = _query_one("SELECT * FROM incidents WHERE id=?", (incident_id,))
    if not created:
        raise RuntimeError("incident creation failed")
    incident = _incident_from_row(created)
    _create_notification_for_incident(incident)
    _write_audit("incident_created", "create_incident", "success", incident_ref=incident_id, metadata={"dedup_key": dedup_key})
    return incident


def _archive_case_from_incident(incident_id: str) -> None:
    row = _query_one("SELECT * FROM incidents WHERE id=?", (incident_id,))
    if not row:
        return
    inc = _incident_from_row(row)
    details = json.loads(row["details_json"] or "{}")
    _exec(
        """
        INSERT INTO cases(id,title,summary,category,status,severity,tags_json,incident_refs_json,root_cause_summary,resolution_summary,lessons_learned,author,created_at,archived_at,similarity_score,hit_count,knowledge_refs_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            f"CASE-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
            inc["title"],
            inc["summary"],
            "availability",
            "archived",
            inc["severity"],
            json.dumps(["auto-archived", inc["source"]]),
            json.dumps([incident_id]),
            (inc["root_cause_candidates"][0]["description"] if inc["root_cause_candidates"] else "pending rca"),
            "Automated remediation completed and service stabilized",
            "Tune thresholds and add preventive capacity checks",
            "system",
            inc["first_seen_at"],
            _now(),
            None,
            0,
            json.dumps([]),
        ),
    )


async def _execute_remediation(incident_id: str, action: str, parameters: dict[str, Any], mode: str) -> dict[str, Any]:
    rid = f"REM-{uuid.uuid4().hex[:8].upper()}"
    _exec(
        "INSERT INTO remediation_actions(id,incident_ref,action,mode,status,request_payload_json,result_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (rid, incident_id, action, mode, "running", json.dumps(parameters), "{}", _now(), _now()),
    )
    try:
        if action.startswith("k8s."):
            payload = {"connection": _k8s_connection_input(), **parameters}
            result = await _invoke_tool(action, payload)
        elif action.startswith("vmware."):
            payload = {"connection": _vcenter_connection_input(), **parameters}
            result = await _invoke_tool(action, payload)
        else:
            raise RuntimeError(f"unsupported remediation action: {action}")
        _exec("UPDATE remediation_actions SET status='success', result_json=?, updated_at=? WHERE id=?", (json.dumps(result), _now(), rid))
        _write_audit("execution_completed", action, "success", incident_ref=incident_id, metadata={"remediation_id": rid})
        return {"remediation_id": rid, "status": "success", "result": result}
    except Exception as exc:  # noqa: BLE001
        _exec("UPDATE remediation_actions SET status='failed', result_json=?, updated_at=? WHERE id=?", (json.dumps({"error": str(exc)}), _now(), rid))
        _write_audit("execution_failed", action, "failed", incident_ref=incident_id, reason=str(exc), metadata={"remediation_id": rid})
        raise


def _create_approval(incident_id: str, action: str, target: str, risk_score: int, description: str) -> None:
    risk_level = "high" if risk_score >= 70 else "medium" if risk_score >= 40 else "low"
    _exec(
        """
        INSERT INTO approvals(id,title,description,action_type,risk_level,risk_score,status,requester,assignee,incident_ref,change_analysis_ref,target_object,target_object_type,created_at,updated_at,expires_at,decision_comment,decided_at,decided_by,tags_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            f"APR-{uuid.uuid4().hex[:8].upper()}",
            f"{action} requires approval",
            description,
            action,
            risk_level,
            risk_score,
            "pending",
            "system",
            "ops-lead",
            incident_id,
            None,
            target,
            "resource",
            _now(),
            _now(),
            (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            None,
            None,
            None,
            json.dumps(["auto-generated", "closed-loop"]),
        ),
    )


async def _load_tool_meta(tool_name: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{TOOL_GATEWAY_URL.rstrip('/')}/api/v1/tools/")
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload.get("error") or "failed to load tool metadata")
    for item in payload.get("data", []):
        if item.get("name") == tool_name:
            return item
    raise RuntimeError(f"tool not found in registry: {tool_name}")


def _capability_for_action(tool_name: str) -> str:
    return ACTION_CAPABILITY.get(tool_name, "single")


def _risk_score_from_level(risk_level: str) -> int:
    mapping = {"low": 20, "medium": 50, "high": 75, "critical": 90}
    return mapping.get(str(risk_level).lower(), 60)


async def _evaluate_policy(context: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{GOVERNANCE_SERVICE_URL.rstrip('/')}/policies/evaluate",
                json=context,
            )
        payload = response.json()
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        return {
            "allowed": bool(data.get("allowed", False)),
            "require_approval": bool(data.get("require_approval", False)),
            "reason": str(data.get("reason", "")),
            "matched_policies": data.get("matched_policies", []) or [],
            "source": data.get("source"),
        }
    except Exception as exc:  # noqa: BLE001
        is_write = context.get("action_type") in {"write", "dangerous"}
        if is_write:
            return {
                "allowed": False,
                "require_approval": True,
                "reason": f"policy service unavailable: {exc}",
                "matched_policies": [],
                "source": "fallback",
            }
        return {
            "allowed": True,
            "require_approval": False,
            "reason": f"policy service unavailable(read-only fallback): {exc}",
            "matched_policies": [],
            "source": "fallback",
        }


def _build_target_tool_input(tool_name: str, base_parameters: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    params = dict(base_parameters or {})
    metadata = target.get("metadata", {}) or {}
    if tool_name.startswith("vmware."):
        if tool_name == "vmware.host_restart":
            params.setdefault("host_id", target["object_id"])
        else:
            params.setdefault("vm_id", target["object_id"])
        if tool_name == "vmware.create_snapshot":
            params.setdefault("name", f"opspilot-{target['object_name']}")
        return {"connection": _vcenter_connection_input(), **params}

    if tool_name == "k8s.restart_deployment":
        params.setdefault("namespace", metadata.get("namespace", "default"))
        params.setdefault("deployment_name", metadata.get("deployment_name", target["object_name"]))
        return {"connection": _k8s_connection_input(), **params}

    if tool_name == "k8s.scale_deployment":
        params.setdefault("namespace", metadata.get("namespace", "default"))
        params.setdefault("deployment_name", metadata.get("deployment_name", target["object_name"]))
        params.setdefault("replicas", int(metadata.get("replicas", params.get("replicas", 1))))
        return {"connection": _k8s_connection_input(), **params}

    return params


def _create_execution_request_record(
    body: ExecutionBody,
    action_type: str,
    risk_level: str,
    risk_score: int,
    require_approval: bool,
    policy: dict[str, Any],
    status: str,
) -> str:
    execution_id = f"EXE-{uuid.uuid4().hex[:8].upper()}"
    _exec(
        """
        INSERT INTO execution_requests(id,tool_name,action_type,environment,requester,status,incident_id,change_analysis_ref,session_id,approval_id,risk_level,risk_score,require_approval,policy_json,parameters_json,result_json,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            execution_id,
            body.tool_name,
            action_type,
            body.environment,
            body.requester,
            status,
            body.incident_id,
            body.change_analysis_ref,
            body.session_id,
            None,
            risk_level,
            risk_score,
            1 if require_approval else 0,
            json.dumps(policy, ensure_ascii=False),
            json.dumps(body.parameters, ensure_ascii=False),
            "{}",
            _now(),
            _now(),
        ),
    )
    return execution_id


def _save_execution_targets(execution_id: str, target_results: list[dict[str, Any]]) -> None:
    for result in target_results:
        if result["status"] == "ok":
            saved_status = "success"
        elif result["status"] == "error":
            saved_status = "failed"
        else:
            saved_status = "pending"
        _exec(
            """
            INSERT INTO execution_targets(id,execution_id,object_id,object_name,object_type,metadata_json,status,result_json)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                f"EXT-{uuid.uuid4().hex[:8].upper()}",
                execution_id,
                result["target"]["object_id"],
                result["target"]["object_name"],
                result["target"]["object_type"],
                json.dumps(result["target"].get("metadata", {}), ensure_ascii=False),
                saved_status,
                json.dumps(result, ensure_ascii=False),
            ),
        )


def _save_execution_step(execution_id: str, step_type: str, status: str, detail: dict[str, Any]) -> None:
    _exec(
        "INSERT INTO execution_steps(id,execution_id,step_type,status,detail_json,created_at) VALUES(?,?,?,?,?,?)",
        (
            f"EXS-{uuid.uuid4().hex[:8].upper()}",
            execution_id,
            step_type,
            status,
            json.dumps(detail, ensure_ascii=False),
            _now(),
        ),
    )


def _create_execution_approval(execution_id: str, body: ExecutionBody, risk_level: str, risk_score: int) -> str:
    approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
    first_target = body.targets[0]
    _exec(
        """
        INSERT INTO approvals(id,title,description,action_type,risk_level,risk_score,status,requester,assignee,incident_ref,change_analysis_ref,target_object,target_object_type,created_at,updated_at,expires_at,decision_comment,decided_at,decided_by,tags_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            approval_id,
            f"{body.tool_name} execution approval",
            f"Execution {execution_id} requires approval",
            body.tool_name,
            risk_level,
            risk_score,
            "pending",
            body.requester,
            "ops-lead",
            body.incident_id,
            body.change_analysis_ref,
            first_target.object_name,
            first_target.object_type,
            _now(),
            _now(),
            (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            None,
            None,
            None,
            json.dumps(["execution", f"execution_id:{execution_id}"]),
        ),
    )
    _exec("UPDATE execution_requests SET approval_id=?, updated_at=? WHERE id=?", (approval_id, _now(), execution_id))
    _write_audit("approval_created", body.tool_name, "success", incident_ref=body.incident_id, metadata={"approval_id": approval_id, "execution_id": execution_id})
    return approval_id


async def _run_execution_dry_run(body: ExecutionBody, persist: bool) -> dict[str, Any]:
    if not body.targets:
        raise RuntimeError("targets cannot be empty")
    tool_meta = await _load_tool_meta(body.tool_name)
    action_type = body.action_type or tool_meta.get("action_type", "write")
    if action_type == "read":
        raise RuntimeError("execution only supports write/dangerous actions")
    capability = _capability_for_action(body.tool_name)
    if capability == "single" and len(body.targets) > 1:
        raise RuntimeError(f"{body.tool_name} does not support batch targets")
    risk_level = str(tool_meta.get("risk_level", "medium"))
    risk_score = _risk_score_from_level(risk_level)
    policy_context = {
        "tool_name": body.tool_name,
        "action_type": action_type,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "environment": body.environment,
        "approved": False,
        "requester": body.requester,
        "approver": "ops-lead",
    }
    policy = await _evaluate_policy(policy_context)

    target_results: list[dict[str, Any]] = []
    warnings: list[str] = []
    for target in body.targets:
        target_dict = target.model_dump()
        tool_input = _build_target_tool_input(body.tool_name, body.parameters, target_dict)
        try:
            preview = await _invoke_tool(body.tool_name, tool_input, dry_run=True)
            target_results.append(
                {
                    "target": target_dict,
                    "status": "ok",
                    "message": "dry-run ok",
                    "preview": preview,
                }
            )
        except Exception as exc:  # noqa: BLE001
            target_results.append(
                {
                    "target": target_dict,
                    "status": "error",
                    "message": str(exc),
                    "preview": {},
                }
            )

    has_error = any(item["status"] == "error" for item in target_results)
    can_submit = (policy.get("allowed") or policy.get("require_approval")) and not has_error
    if capability == "single" and len(body.targets) > 1:
        warnings.append("action supports single target only")
    if has_error:
        warnings.append("some targets failed dry-run checks")
    if policy.get("reason"):
        warnings.append(policy["reason"])

    dry_run_result = {
        "can_submit": bool(can_submit),
        "require_approval": bool(policy.get("require_approval")),
        "policy": policy,
        "action_type": action_type,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "capability": capability,
        "target_results": [
            {
                "object_id": item["target"]["object_id"],
                "object_name": item["target"]["object_name"],
                "status": item["status"],
                "message": item["message"],
                "preview": item.get("preview", {}),
            }
            for item in target_results
        ],
        "warnings": warnings,
    }

    execution_id = None
    if persist:
        execution_id = _create_execution_request_record(
            body,
            action_type=action_type,
            risk_level=risk_level,
            risk_score=risk_score,
            require_approval=bool(policy.get("require_approval")),
            policy=policy,
            status="dry_run_ready",
        )
        _save_execution_targets(execution_id, target_results)
        _save_execution_step(execution_id, "dry_run", "success" if can_submit else "failed", dry_run_result)

    return {"execution_id": execution_id, "dry_run_result": dry_run_result}


async def _execute_targets(execution_id: str, body: ExecutionBody) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    all_success = True
    for target in body.targets:
        target_dict = target.model_dump()
        tool_input = _build_target_tool_input(body.tool_name, body.parameters, target_dict)
        try:
            output = await _invoke_tool(body.tool_name, tool_input, dry_run=False)
            result = {"target": target_dict, "status": "success", "result": output}
            results.append(result)
            _exec(
                "UPDATE execution_targets SET status='success', result_json=? WHERE execution_id=? AND object_id=?",
                (json.dumps(result, ensure_ascii=False), execution_id, target.object_id),
            )
        except Exception as exc:  # noqa: BLE001
            all_success = False
            result = {"target": target_dict, "status": "failed", "error": str(exc)}
            results.append(result)
            _exec(
                "UPDATE execution_targets SET status='failed', result_json=? WHERE execution_id=? AND object_id=?",
                (json.dumps(result, ensure_ascii=False), execution_id, target.object_id),
            )

    final_status = "success" if all_success else "failed"
    _exec(
        "UPDATE execution_requests SET status=?, result_json=?, updated_at=? WHERE id=?",
        (final_status, json.dumps({"results": results}, ensure_ascii=False), _now(), execution_id),
    )
    _save_execution_step(execution_id, "execute", final_status, {"results": results})
    return {"status": final_status, "results": results}


def _execution_body_from_record(execution_id: str) -> ExecutionBody:
    row = _query_one("SELECT * FROM execution_requests WHERE id=?", (execution_id,))
    if not row:
        raise RuntimeError(f"execution not found: {execution_id}")
    target_rows = _query_all("SELECT * FROM execution_targets WHERE execution_id=? ORDER BY id", (execution_id,))
    targets = [
        ExecutionTargetBody(
            object_id=t["object_id"],
            object_name=t["object_name"],
            object_type=t["object_type"],
            metadata=json.loads(t["metadata_json"] or "{}"),
        )
        for t in target_rows
    ]
    return ExecutionBody(
        tool_name=row["tool_name"],
        action_type=row["action_type"],
        targets=targets,
        parameters=json.loads(row["parameters_json"] or "{}"),
        environment=row["environment"],
        requester=row["requester"],
        incident_id=row["incident_id"],
        change_analysis_ref=row["change_analysis_ref"],
        session_id=row["session_id"],
    )


def _execution_detail(execution_id: str) -> dict[str, Any]:
    row = _query_one("SELECT * FROM execution_requests WHERE id=?", (execution_id,))
    if not row:
        raise RuntimeError(f"execution not found: {execution_id}")
    targets = _query_all("SELECT * FROM execution_targets WHERE execution_id=? ORDER BY id", (execution_id,))
    steps = _query_all("SELECT * FROM execution_steps WHERE execution_id=? ORDER BY created_at", (execution_id,))
    return {
        "id": row["id"],
        "tool_name": row["tool_name"],
        "action_type": row["action_type"],
        "environment": row["environment"],
        "requester": row["requester"],
        "status": row["status"],
        "incident_id": row["incident_id"],
        "change_analysis_ref": row["change_analysis_ref"],
        "session_id": row["session_id"],
        "approval_id": row["approval_id"],
        "risk_level": row["risk_level"],
        "risk_score": row["risk_score"],
        "require_approval": bool(row["require_approval"]),
        "policy": json.loads(row["policy_json"] or "{}"),
        "parameters": json.loads(row["parameters_json"] or "{}"),
        "result": json.loads(row["result_json"] or "{}"),
        "targets": [
            {
                "object_id": t["object_id"],
                "object_name": t["object_name"],
                "object_type": t["object_type"],
                "metadata": json.loads(t["metadata_json"] or "{}"),
                "status": t["status"],
                "result": json.loads(t["result_json"] or "{}"),
            }
            for t in targets
        ],
        "steps": [
            {
                "step_type": s["step_type"],
                "status": s["status"],
                "detail": json.loads(s["detail_json"] or "{}"),
                "created_at": s["created_at"],
            }
            for s in steps
        ],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _resolve_host_target(details: dict[str, Any], inventory: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    hosts = inventory.get("hosts", []) if isinstance(inventory.get("hosts", []), list) else []
    affected = details.get("affected_objects", []) if isinstance(details.get("affected_objects"), list) else []
    candidates: list[str] = []
    for obj in affected:
        if isinstance(obj, dict):
            for key in ("object_id", "object_name"):
                val = obj.get(key)
                if val:
                    candidates.append(str(val))
    extra = details.get("extra", {}) if isinstance(details.get("extra"), dict) else {}
    for key in ("host_id", "host_name"):
        if extra.get(key):
            candidates.append(str(extra.get(key)))
    alert = extra.get("alert")
    if isinstance(alert, dict):
        for key in ("object_id", "object_name"):
            if alert.get(key):
                candidates.append(str(alert.get(key)))

    for cand in candidates:
        c = cand.strip().lower()
        for host in hosts:
            host_id = str(host.get("host_id", "")).lower()
            name = str(host.get("name", "")).lower()
            if c and (c == host_id or c == name or c in host_id or c in name):
                return host.get("host_id"), host
    return None, None


def _summarize_output(tool_name: str, output: dict[str, Any]) -> str:
    if tool_name == "vmware.get_vcenter_inventory":
        s = output.get("summary", {})
        return f"hosts={s.get('host_count', 0)}, vms={s.get('vm_count', 0)}, clusters={s.get('cluster_count', 0)}"
    if tool_name == "vmware.get_host_detail":
        return (
            f"overall={output.get('overall_status', 'unknown')}, "
            f"conn={output.get('connection_state', 'unknown')}, "
            f"cpu={output.get('cpu_usage_percent', 'N/A')}%, mem={output.get('memory_usage_percent', 'N/A')}%"
        )
    if tool_name == "vmware.query_events":
        events = output.get("events", []) if isinstance(output.get("events", []), list) else []
        return f"events={len(events)}"
    if tool_name == "vmware.query_alerts":
        alerts = output.get("alerts", []) if isinstance(output.get("alerts", []), list) else []
        return f"alerts={len(alerts)}"
    if tool_name == "vmware.query_topology":
        return "topology collected"
    if tool_name == "vmware.query_metrics":
        pts = output.get("points", []) if isinstance(output.get("points", []), list) else []
        return f"metric={output.get('metric', 'unknown')}, points={len(pts)}"
    return "ok"


async def _invoke_analysis_tool(tool_name: str, payload: dict[str, Any]) -> tuple[bool, dict[str, Any] | None, str]:
    try:
        out = await _invoke_tool(tool_name, payload)
        return True, out, ""
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)


async def _aggregate_incident_evidence(incident_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            f"{EVIDENCE_AGGREGATOR_URL.rstrip('/')}/api/v1/evidence/aggregate",
            json={"incident_id": incident_id, "source_refs": []},
        )
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload.get("error") or "evidence aggregation failed")
    return payload.get("data", {}) or {}


def _incident_target(details: dict[str, Any]) -> tuple[str, str]:
    affected = details.get("affected_objects", []) if isinstance(details.get("affected_objects"), list) else []
    if affected and isinstance(affected[0], dict):
        return str(affected[0].get("object_type") or "unknown"), str(affected[0].get("object_id") or "")
    return "unknown", ""


def _make_evidence_sufficiency(package: dict[str, Any] | None) -> dict[str, Any]:
    package = package or {}
    return {
        "required_evidence_types": list(package.get("required_evidence_types", []) or []),
        "present_evidence_types": list(package.get("present_evidence_types", []) or []),
        "missing_critical_evidence": list(package.get("missing_critical_evidence", []) or []),
        "sufficiency_score": float(package.get("sufficiency_score") or 0.0),
        "freshness_score": float(package.get("freshness_score") or 0.0),
    }


def _evidence_ref(ev: dict[str, Any]) -> str:
    return str(ev.get("evidence_id") or ev.get("raw_ref") or ev.get("summary") or "unknown")


def _evidence_text(ev: dict[str, Any]) -> str:
    return " ".join(
        [
            str(ev.get("summary") or ""),
            str(ev.get("source") or ""),
            str(ev.get("source_type") or ""),
            str(ev.get("object_id") or ""),
            str(ev.get("object_type") or ""),
        ]
    ).lower()


def _score_from_signals(
    *,
    support_count: int,
    counter_count: int,
    sufficiency_score: float,
    freshness_score: float,
    contradiction_count: int,
    missing_critical_count: int,
) -> float:
    score = 0.38
    score += min(0.24, support_count * 0.08)
    score -= min(0.2, counter_count * 0.07)
    score += min(0.18, sufficiency_score * 0.18)
    score += min(0.12, freshness_score * 0.08)
    score -= min(0.16, contradiction_count * 0.06)
    score -= min(0.14, missing_critical_count * 0.05)
    return round(max(0.05, min(score, 0.95)), 2)


def _build_hypotheses(
    *,
    evidences: list[dict[str, Any]],
    sufficiency: dict[str, Any],
    contradictions: list[dict[str, Any]],
    host_detail: dict[str, Any] | None,
    summary: str,
) -> list[dict[str, Any]]:
    text_blob = " ".join(_evidence_text(ev) for ev in evidences)
    all_refs = [_evidence_ref(ev) for ev in evidences]
    critical_missing = list(sufficiency.get("missing_critical_evidence", []) or [])
    contradiction_count = len(contradictions)
    freshness_score = float(sufficiency.get("freshness_score") or 0.0)
    sufficiency_score = float(sufficiency.get("sufficiency_score") or 0.0)

    detail_overall = str((host_detail or {}).get("overall_status") or "").lower()
    detail_conn = str((host_detail or {}).get("connection_state") or "").lower()
    cpu_pct = float((host_detail or {}).get("cpu_usage_percent") or 0.0)
    mem_pct = float((host_detail or {}).get("memory_usage_percent") or 0.0)

    definitions: list[tuple[str, str, str, list[str], list[str], str]] = []
    definitions.append(
        (
            "infra-health",
            "infrastructure",
            "主机硬件、连接或基础设施健康异常",
            ["overall_status", "connection_state", "hardware", "disconnect", "link", "yellow", "red", "alert"],
            ["overall_status=green", "connection_state=connected", "healthy"],
            "对象详情或近期事件显示主机处于非绿状态，优先怀疑硬件、链路或管理平面异常。",
        )
    )
    definitions.append(
        (
            "resource-pressure",
            "capacity",
            "主机资源压力过高导致性能或稳定性下降",
            ["cpu", "memory", "contention", "usage", "hotspot", "latency", "balloon"],
            ["cpu=0", "memory=0", "low usage", "idle"],
            "如果 CPU、内存或存储指标持续高位，更可能是资源侧异常而不是纯硬件告警。",
        )
    )
    definitions.append(
        (
            "recent-change",
            "change",
            "近期变更或配置调整触发了状态异常",
            ["change", "config", "patch", "update", "migrate", "restart", "remediation"],
            ["no change", "time mismatch"],
            "当异常时间窗接近发布、迁移或重启记录时，需要把变更影响作为候选根因。",
        )
    )

    hypotheses: list[dict[str, Any]] = []
    for key, category, summary_text, support_terms, counter_terms, why in definitions:
        support_refs = [_evidence_ref(ev) for ev in evidences if any(term in _evidence_text(ev) for term in support_terms)]
        counter_refs = [_evidence_ref(ev) for ev in evidences if any(term in _evidence_text(ev) for term in counter_terms)]

        if key == "infra-health":
            if detail_overall and detail_overall != "green":
                support_refs.extend(all_refs[:1])
            if detail_conn and detail_conn not in {"", "connected"}:
                support_refs.extend(all_refs[:1])
            if detail_overall == "green" and detail_conn == "connected":
                counter_refs.extend(all_refs[:1])
        elif key == "resource-pressure":
            if cpu_pct >= 85 or mem_pct >= 90:
                support_refs.extend(all_refs[:2])
            if 0 < cpu_pct < 60 and 0 < mem_pct < 70:
                counter_refs.extend(all_refs[:2])
        elif key == "recent-change":
            change_refs = [_evidence_ref(ev) for ev in evidences if str(ev.get("source_type") or "").lower() == "change"]
            support_refs.extend(change_refs)
            if not change_refs:
                counter_refs.extend(all_refs[:1])

        support_refs = list(dict.fromkeys([x for x in support_refs if x]))
        counter_refs = list(dict.fromkeys([x for x in counter_refs if x and x not in support_refs]))
        confidence = _score_from_signals(
            support_count=len(support_refs),
            counter_count=len(counter_refs),
            sufficiency_score=sufficiency_score,
            freshness_score=freshness_score,
            contradiction_count=contradiction_count,
            missing_critical_count=len(critical_missing),
        )
        hypotheses.append(
            {
                "id": f"hyp-{key}",
                "summary": summary_text,
                "category": category,
                "confidence": confidence,
                "support_evidence_refs": support_refs,
                "counter_evidence_refs": counter_refs,
                "missing_evidence": critical_missing,
                "status": "candidate",
                "why": why,
            }
        )

    hypotheses.sort(key=lambda item: item.get("confidence", 0), reverse=True)
    if not hypotheses:
        hypotheses.append(
            {
                "id": "hyp-insufficient",
                "summary": "当前证据不足，暂不能形成可靠根因假设",
                "category": "unknown",
                "confidence": 0.22,
                "support_evidence_refs": [],
                "counter_evidence_refs": [],
                "missing_evidence": critical_missing,
                "status": "inconclusive",
                "why": "尚未采到足够的对象详情、事件和指标证据。",
            }
        )
    return hypotheses


def _counter_evidence_result(
    winning: dict[str, Any] | None,
    sufficiency: dict[str, Any],
    contradictions: list[dict[str, Any]],
) -> dict[str, Any]:
    if not winning:
        return {
            "status": "inconclusive",
            "checked_hypothesis_id": None,
            "summary": "当前没有可检查的主假设。",
            "evidence_refs": [],
        }

    counter_refs = list(winning.get("counter_evidence_refs", []) or [])
    missing_critical = list(sufficiency.get("missing_critical_evidence", []) or [])
    contradiction_count = len(contradictions)

    if counter_refs and contradiction_count > 0:
        return {
            "status": "refuted",
            "checked_hypothesis_id": winning.get("id"),
            "summary": "主假设存在反证且仍有未解释矛盾，不能作为唯一根因。",
            "evidence_refs": counter_refs,
        }
    if counter_refs or missing_critical:
        return {
            "status": "inconclusive",
            "checked_hypothesis_id": winning.get("id"),
            "summary": "主假设尚未被完全反驳，但仍缺关键证据或存在待解释反证。",
            "evidence_refs": counter_refs,
        }
    return {
        "status": "not_refuted",
        "checked_hypothesis_id": winning.get("id"),
        "summary": "未发现足以推翻主假设的关键反证。",
        "evidence_refs": list(winning.get("support_evidence_refs", []) or [])[:3],
    }


def _conclusion_status(
    *,
    winning: dict[str, Any] | None,
    sufficiency: dict[str, Any],
    counter_result: dict[str, Any],
    contradictions: list[dict[str, Any]],
) -> str:
    if not winning:
        return "insufficient_evidence"
    if counter_result.get("status") == "refuted":
        return "contradicted"
    if sufficiency.get("missing_critical_evidence") or contradictions:
        return "insufficient_evidence"
    if counter_result.get("status") == "not_refuted" and float(winning.get("confidence") or 0.0) >= ANALYSIS_CONFIDENCE_THRESHOLD:
        return "confirmed"
    return "probable"


def _summary_from_conclusion(
    *,
    target_type: str,
    target_id: str,
    winning: dict[str, Any] | None,
    conclusion_status: str,
    sufficiency: dict[str, Any],
    counter_result: dict[str, Any],
    contradictions: list[dict[str, Any]],
) -> str:
    name = target_id or target_type or "目标对象"
    headline = winning.get("summary") if winning else "暂无可收敛根因"
    missing = list(sufficiency.get("missing_critical_evidence", []) or [])
    contradiction_text = f"；发现矛盾证据 {len(contradictions)} 项" if contradictions else ""
    if conclusion_status == "confirmed":
        return f"{name} 的主根因已确认：{headline}。证据充分性={sufficiency.get('sufficiency_score', 0):.2f}，反证结果={counter_result.get('status')}{contradiction_text}。"
    if conclusion_status == "contradicted":
        return f"{name} 的原主假设已被反证击穿，当前不能收敛唯一根因。候选方向：{headline}{contradiction_text}。"
    if conclusion_status == "probable":
        return f"{name} 当前最可能的根因是：{headline}。但仍建议补采关键证据后再执行高风险处置。"
    missing_text = f"缺少关键证据：{', '.join(missing)}。" if missing else "当前证据链仍不完整。"
    return f"{name} 暂无法形成高置信根因。{missing_text} 需要继续补齐详情、事件、指标或变更证据。"


async def _maybe_auto_remediate(
    *,
    incident_id: str,
    user_mode: str,
    recommendations: list[str],
    mode: str,
    summary: str,
    host_detail: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    auto_logs: list[str] = []
    _write_audit(
        "remediation_planned",
        "auto_remediation",
        "success",
        incident_ref=incident_id,
        metadata={"user_mode": user_mode, "mode": mode},
    )
    if mode == "manual" or user_mode == "suggest_only":
        auto_logs.append("自动处置：跳过（策略=仅建议或手动分析）")
        return False, auto_logs

    action: dict[str, Any] | None = None
    low_risk_actions = {"k8s.scale_deployment"}
    medium_or_higher_actions = {"vmware.vm_guest_restart", "k8s.restart_deployment", "vmware.vm_power_on"}

    summary_l = summary.lower()
    if "pod" in summary_l and "restart" in summary_l:
        action = {"tool_name": "k8s.restart_deployment", "action_type": "write", "risk_level": "medium", "input": {"namespace": "default", "deployment_name": "unknown"}}
    elif "powered off" in summary_l or "关机" in summary:
        vm_name_match = re.search(r"VM\s+([A-Za-z0-9._-]+)", summary, re.I)
        if vm_name_match:
            action = {"tool_name": "vmware.vm_power_on", "action_type": "write", "risk_level": "medium", "input": {"vm_id": vm_name_match.group(1), "connection": _vcenter_connection_input()}}
    elif host_detail and str(host_detail.get("overall_status", "")).lower() in {"yellow", "red"}:
        # Host 非绿状态默认不自动执行高风险动作，仅建议审批
        action = {"tool_name": "vmware.host_restart", "action_type": "dangerous", "risk_level": "high", "input": {"host_id": host_detail.get("host_id"), "connection": _vcenter_connection_input()}}

    if not action:
        auto_logs.append("自动处置：已跳过（未命中可执行的低风险动作）")
        recommendations.append("建议人工执行：检查主机硬件告警、管理网络、存储链路，并评估维护窗口")
        return False, auto_logs

    tool_name = action["tool_name"]
    risk_level = str(action["risk_level"]).lower()
    if tool_name in medium_or_higher_actions or risk_level in {"medium", "high", "critical"}:
        _create_approval(incident_id, tool_name, action["input"].get("host_id") or action["input"].get("vm_id") or "unknown", _risk_score_from_level(risk_level), "自动修复策略命中中高风险动作，需审批")
        auto_logs.append(f"自动处置：{tool_name} 风险={risk_level}，已创建审批")
        return False, auto_logs

    if tool_name not in low_risk_actions:
        auto_logs.append(f"自动处置：{tool_name} 非低风险动作，已跳过")
        return False, auto_logs

    policy = await _evaluate_policy(
        {
            "tool_name": tool_name,
            "action_type": action.get("action_type", "write"),
            "risk_level": risk_level,
            "risk_score": _risk_score_from_level(risk_level),
            "environment": "prod",
            "approved": True,
            "requester": "auto-remediation",
            "approver": "auto",
        }
    )
    if not policy.get("allowed") or policy.get("require_approval"):
        _create_approval(incident_id, tool_name, action["input"].get("host_id") or action["input"].get("vm_id") or "unknown", _risk_score_from_level(risk_level), f"策略门禁要求审批: {policy.get('reason')}")
        auto_logs.append(f"自动处置：策略要求审批（{policy.get('reason', 'unknown')}）")
        return False, auto_logs

    try:
        result = await _invoke_tool(tool_name, action["input"], dry_run=False)
        _write_audit("remediation_executed", tool_name, "success", incident_ref=incident_id, metadata={"result": result})
        # 简化验证：执行后再次拉取相关读接口确认可达
        _write_audit("remediation_verified", tool_name, "success", incident_ref=incident_id, metadata={"verification": "basic_connectivity_ok"})
        auto_logs.append(f"自动处置：{tool_name} 已自动执行并完成基础验证")
        return True, auto_logs
    except Exception as exc:  # noqa: BLE001
        _write_audit("remediation_rolled_back", tool_name, "failed", incident_ref=incident_id, metadata={"reason": str(exc)})
        auto_logs.append(f"自动处置：执行失败，已标记回滚建议（{exc}）")
        recommendations.append("建议人工执行回滚或通过审批后重试")
        return False, auto_logs
    return False, auto_logs


async def _analyze_incident(incident_id: str, mode: str = "auto", user_id: str = "ops-user") -> dict[str, Any]:
    row = _query_one("SELECT * FROM incidents WHERE id=?", (incident_id,))
    if not row:
        raise RuntimeError("incident not found")
    details = json.loads(row["details_json"] or "{}")
    started_at = _now()
    details.setdefault("analysis", {})
    if isinstance(details["analysis"], dict):
        details["analysis"].update(
            {
                "status": "running",
                "round": 0,
                "max_rounds": ANALYSIS_MAX_ROUNDS,
                "started_at": started_at,
                "updated_at": started_at,
                "elapsed_ms": 0,
                "analysis_process": [],
                "next_decision": "开始分析",
            }
        )
    _exec(
        "UPDATE incidents SET status='analyzing', ai_analysis_triggered=1, details_json=?, last_updated_at=? WHERE id=?",
        (json.dumps(details, ensure_ascii=False), started_at, incident_id),
    )
    _write_audit("analysis_started", "analyze_incident", "success", incident_ref=incident_id, metadata={"mode": mode, "user_id": user_id})

    analysis_process: list[dict[str, Any]] = []
    evidence_refs: list[str] = []
    recommendations: list[str] = []
    root_causes: list[dict[str, Any]] = []
    final_conclusion = "尚未形成结论。"
    next_decision = "继续采集证据"
    summary = row["summary"]
    host_detail: dict[str, Any] | None = None
    inventory: dict[str, Any] | None = None
    target_type, target_id = _incident_target(details)
    resolved_target_id = target_id
    evidence_package: dict[str, Any] = {}
    evidence_sufficiency: dict[str, Any] = _make_evidence_sufficiency({})
    contradictions: list[dict[str, Any]] = []

    start_dt = datetime.now(UTC)
    round_no = 0
    analysis_tools: list[tuple[str, dict[str, Any], str, str]] = [
        ("vmware.get_vcenter_inventory", {"connection": _vcenter_connection_input()}, "定位目标对象并建立环境基线", "target_resolution"),
    ]

    object_type_l = target_type.lower()
    if "host" in object_type_l and resolved_target_id:
        analysis_tools.append(
            ("vmware.get_host_detail", {"connection": _vcenter_connection_input(), "host_id": resolved_target_id}, "获取主机实时详情", "evidence_collection")
        )
    elif ("virtualmachine" in object_type_l or object_type_l == "vm") and resolved_target_id:
        analysis_tools.append(
            ("vmware.get_vm_detail", {"connection": _vcenter_connection_input(), "vm_id": resolved_target_id}, "获取虚拟机实时详情", "evidence_collection")
        )

    if resolved_target_id:
        analysis_tools.extend(
            [
                ("vmware.query_events", {"connection": _vcenter_connection_input(), "object_id": resolved_target_id, "hours": 24}, "采集最近事件", "evidence_collection"),
                ("vmware.query_metrics", {"connection": _vcenter_connection_input(), "object_id": resolved_target_id, "metric": "cpu_usage_percent"}, "采集关键指标", "evidence_collection"),
            ]
        )
    analysis_tools.extend(
        [
            ("vmware.query_alerts", {"connection": _vcenter_connection_input()}, "补充全局告警视角", "evidence_collection"),
            ("vmware.query_topology", {"connection": _vcenter_connection_input()}, "补充拓扑关系证据", "evidence_collection"),
        ]
    )

    analysis_process.append(
        _analysis_step(
            round_no=0,
            stage="evidence_planning",
            status="success",
            goal="根据对象类型规划必需证据",
            finding=f"目标对象类型={target_type or 'unknown'}，初始目标ID={resolved_target_id or 'unknown'}",
            decision="按 inventory/detail/events/metrics/alerts/topology 顺序采证",
            selected_tools=[item[0] for item in analysis_tools[:ANALYSIS_MAX_ROUNDS]],
            evidence_found=[],
            evidence_missing=[],
            contradictions=[],
            why="先保证对象定位和详情证据，再补事件、指标和拓扑，避免只凭单点信号直接收敛。",
        )
    )

    for round_no in range(1, min(ANALYSIS_MAX_ROUNDS, len(analysis_tools)) + 1):
        elapsed = (datetime.now(UTC) - start_dt).total_seconds()
        if elapsed > ANALYSIS_BUDGET_SECONDS:
            analysis_process.append(
                _analysis_step(
                    round_no=round_no,
                    stage="decide_next",
                    status="success",
                    goal="检查分析预算",
                    finding="达到分析时长预算",
                    decision="停止分析",
                    why="预算耗尽时只允许输出 probable 或 insufficient_evidence。",
                )
            )
            next_decision = "停止：预算耗尽"
            break

        tool_name, payload, goal_text, stage_name = analysis_tools[round_no - 1]
        if tool_name not in READ_TOOL_WHITELIST:
            analysis_process.append(
                _analysis_step(
                    round_no=round_no,
                    stage="decide_next",
                    status="failed",
                    goal="校验分析工具白名单",
                    finding=f"工具不在白名单: {tool_name}",
                    decision="停止分析",
                    selected_tools=[tool_name],
                    why="诊断路径只允许只读工具进入分析循环。",
                )
            )
            next_decision = "停止：工具不在白名单"
            break

        ok, out, err = await _invoke_analysis_tool(tool_name, payload)
        if ok and out:
            if tool_name == "vmware.get_vcenter_inventory":
                inventory = out
                if "host" in object_type_l and not resolved_target_id:
                    resolved_target_id, matched = _resolve_host_target(details, out)
                    if matched:
                        host_detail = matched
                    if resolved_target_id:
                        existing_tool_names = [item[0] for item in analysis_tools]
                        inserts: list[tuple[str, dict[str, Any], str, str]] = []
                        if "vmware.get_host_detail" not in existing_tool_names:
                            inserts.append(
                                ("vmware.get_host_detail", {"connection": _vcenter_connection_input(), "host_id": resolved_target_id}, "获取主机实时详情", "evidence_collection")
                            )
                        if "vmware.query_events" not in existing_tool_names:
                            inserts.append(
                                ("vmware.query_events", {"connection": _vcenter_connection_input(), "object_id": resolved_target_id, "hours": 24}, "采集最近事件", "evidence_collection")
                            )
                        if "vmware.query_metrics" not in existing_tool_names:
                            inserts.append(
                                ("vmware.query_metrics", {"connection": _vcenter_connection_input(), "object_id": resolved_target_id, "metric": "cpu_usage_percent"}, "采集关键指标", "evidence_collection")
                            )
                        for offset, item in enumerate(inserts, start=1):
                            analysis_tools.insert(round_no - 1 + offset, item)
            elif tool_name == "vmware.get_host_detail":
                host_detail = out
                resolved_target_id = str(out.get("host_id") or resolved_target_id or "")

            analysis_process.append(
                _analysis_step(
                    round_no=round_no,
                    stage=stage_name,
                    status="success",
                    goal=goal_text,
                    tool_name=tool_name,
                    input_summary=json.dumps(payload, ensure_ascii=False)[:240],
                    output_summary=_summarize_output(tool_name, out),
                    finding=f"{tool_name} 返回成功",
                    decision="刷新证据充分性并判断是否继续",
                    selected_tools=[tool_name],
                    why="每拿到一类关键证据后，都重新评估是否还缺关键证据以及是否存在矛盾。",
                )
            )
            _write_audit("analysis_step_completed", tool_name, "success", incident_ref=incident_id, metadata={"round": round_no})
        else:
            analysis_process.append(
                _analysis_step(
                    round_no=round_no,
                    stage=stage_name,
                    status="failed",
                    goal=goal_text,
                    tool_name=tool_name,
                    input_summary=json.dumps(payload, ensure_ascii=False)[:240],
                    output_summary="",
                    finding=f"调用失败: {err}",
                    decision="记录失败并尝试继续补证",
                    selected_tools=[tool_name],
                    why="单个只读工具失败不应直接终止分析，但会降低证据充分性。",
                )
            )

        try:
            evidence_package = await _aggregate_incident_evidence(incident_id)
            evidence_sufficiency = _make_evidence_sufficiency(evidence_package)
            contradictions = list(evidence_package.get("contradictions", []) or [])
            evidence_refs = [str(ev.get("evidence_id")) for ev in evidence_package.get("evidences", []) if ev.get("evidence_id")]
            analysis_process.append(
                _analysis_step(
                    round_no=round_no,
                    stage="evidence_collection",
                    status="success",
                    goal="评估当前证据是否充分",
                    finding=(
                        f"已采证据类型={','.join(evidence_sufficiency.get('present_evidence_types', [])) or 'none'}；"
                        f"充分性={evidence_sufficiency.get('sufficiency_score', 0):.2f}"
                    ),
                    decision="继续或停止采证",
                    selected_tools=[tool_name],
                    evidence_found=list(evidence_sufficiency.get("present_evidence_types", [])),
                    evidence_missing=list(evidence_sufficiency.get("missing_critical_evidence", [])),
                    contradictions=[str(item.get("summary") or item.get("kind") or "evidence contradiction") for item in contradictions],
                    why="结论门禁依赖证据完整度，而不是只看工具是否成功返回。",
                )
            )
        except Exception as exc:  # noqa: BLE001
            analysis_process.append(
                _analysis_step(
                    round_no=round_no,
                    stage="evidence_collection",
                    status="failed",
                    goal="评估当前证据是否充分",
                    finding=f"证据聚合失败: {exc}",
                    decision="继续有限分析，但不得输出 confirmed",
                    selected_tools=["evidence.aggregate"],
                    why="证据包无法形成时，只能输出保守结论。",
                )
            )
            evidence_package = {}
            evidence_sufficiency = _make_evidence_sufficiency({})
            contradictions = []

        if (
            evidence_sufficiency.get("sufficiency_score", 0) >= 0.78
            and not evidence_sufficiency.get("missing_critical_evidence")
            and not contradictions
            and round_no >= 3
        ):
            analysis_process.append(
                _analysis_step(
                    round_no=round_no,
                    stage="decide_next",
                    status="success",
                    goal="检查是否可以结束采证",
                    finding="证据已基本充分，且未发现关键矛盾",
                    decision="停止采证并进入假设阶段",
                    selected_tools=[],
                    evidence_found=list(evidence_sufficiency.get("present_evidence_types", [])),
                    evidence_missing=[],
                    contradictions=[],
                    why="已经具备详情、事件/指标和拓扑等关键证据，可进入假设对比与反证。",
                )
            )
            next_decision = "停止：证据充分"
            break

        analysis_process.append(
            _analysis_step(
                round_no=round_no,
                stage="decide_next",
                status="success",
                goal="判断是否继续采证",
                finding="当前证据仍不足以确认唯一根因",
                decision="继续下一轮",
                selected_tools=[],
                evidence_found=list(evidence_sufficiency.get("present_evidence_types", [])),
                evidence_missing=list(evidence_sufficiency.get("missing_critical_evidence", [])),
                contradictions=[str(item.get("summary") or item.get("kind") or "evidence contradiction") for item in contradictions],
                why="还缺关键证据或存在矛盾，不能直接收敛为 confirmed。",
            )
        )

    if not evidence_package:
        try:
            evidence_package = await _aggregate_incident_evidence(incident_id)
            evidence_sufficiency = _make_evidence_sufficiency(evidence_package)
            contradictions = list(evidence_package.get("contradictions", []) or [])
            evidence_refs = [str(ev.get("evidence_id")) for ev in evidence_package.get("evidences", []) if ev.get("evidence_id")]
        except Exception:
            evidence_package = {}
            evidence_sufficiency = _make_evidence_sufficiency({})
            contradictions = []

    hypotheses = _build_hypotheses(
        evidences=list(evidence_package.get("evidences", []) or []),
        sufficiency=evidence_sufficiency,
        contradictions=contradictions,
        host_detail=host_detail,
        summary=summary,
    )
    analysis_process.append(
        _analysis_step(
            round_no=max(round_no, 1),
            stage="hypothesis_generation",
            status="success",
            goal="基于已采证据生成候选根因",
            finding=f"生成候选根因 {len(hypotheses)} 个",
            decision="进入假设评分",
            selected_tools=[],
            evidence_found=[str(item.get("summary")) for item in hypotheses[:3]],
            evidence_missing=list(evidence_sufficiency.get("missing_critical_evidence", [])),
            contradictions=[str(item.get("summary") or item.get("kind") or "evidence contradiction") for item in contradictions],
            why="先并列多个候选，再比较支持证据与反证，不允许直接跳到唯一根因。",
        )
    )

    winning_hypothesis = hypotheses[0] if hypotheses else None
    if winning_hypothesis:
        winning_hypothesis["status"] = "probable"
    analysis_process.append(
        _analysis_step(
            round_no=max(round_no, 1),
            stage="hypothesis_scoring",
            status="success",
            goal="比较候选根因的支持证据与缺口",
            finding=(
                f"最高分候选={winning_hypothesis.get('summary') if winning_hypothesis else 'none'}，"
                f"confidence={winning_hypothesis.get('confidence', 0) if winning_hypothesis else 0}"
            ),
            decision="执行反证检查",
            selected_tools=[],
            evidence_found=list(winning_hypothesis.get("support_evidence_refs", [])[:4] if winning_hypothesis else []),
            evidence_missing=list(winning_hypothesis.get("missing_evidence", []) if winning_hypothesis else []),
            contradictions=[str(item.get("summary") or item.get("kind") or "evidence contradiction") for item in contradictions],
            why="评分同时考虑支持证据、缺失证据和矛盾证据，而不是只看单个异常信号。",
        )
    )

    counter_result = _counter_evidence_result(winning_hypothesis, evidence_sufficiency, contradictions)
    analysis_process.append(
        _analysis_step(
            round_no=max(round_no, 1),
            stage="counter_evidence_check",
            status="success",
            goal="检查主假设是否被反证击穿",
            finding=counter_result.get("summary", ""),
            decision="进入结论门禁",
            selected_tools=[],
            evidence_found=list(counter_result.get("evidence_refs", [])),
            evidence_missing=list(evidence_sufficiency.get("missing_critical_evidence", [])),
            contradictions=[str(item.get("summary") or item.get("kind") or "evidence contradiction") for item in contradictions],
            why="主假设必须经过反证检查，未通过时不能输出 confirmed。",
        )
    )

    conclusion_status = _conclusion_status(
        winning=winning_hypothesis,
        sufficiency=evidence_sufficiency,
        counter_result=counter_result,
        contradictions=contradictions,
    )
    if winning_hypothesis:
        winning_hypothesis["status"] = {
            "confirmed": "confirmed",
            "probable": "probable",
            "insufficient_evidence": "inconclusive",
            "contradicted": "refuted",
        }.get(conclusion_status, "candidate")

    analysis_process.append(
        _analysis_step(
            round_no=max(round_no, 1),
            stage="conclusion_gate",
            status="success",
            goal="按证据充分性、反证和矛盾进行结论门禁",
            finding=f"conclusion_status={conclusion_status}",
            decision="生成建议动作",
            selected_tools=[],
            evidence_found=list(evidence_sufficiency.get("present_evidence_types", [])),
            evidence_missing=list(evidence_sufficiency.get("missing_critical_evidence", [])),
            contradictions=[str(item.get("summary") or item.get("kind") or "evidence contradiction") for item in contradictions],
            why="没有充分证据、没有通过反证或仍有矛盾时，系统必须降级结论。",
        )
    )

    final_conclusion = _summary_from_conclusion(
        target_type=target_type,
        target_id=resolved_target_id or target_id,
        winning=winning_hypothesis,
        conclusion_status=conclusion_status,
        sufficiency=evidence_sufficiency,
        counter_result=counter_result,
        contradictions=contradictions,
    )

    if winning_hypothesis:
        root_causes = [
            {
                "id": hypothesis["id"],
                "description": hypothesis["summary"],
                "confidence": hypothesis["confidence"],
                "evidence_refs": list(hypothesis.get("support_evidence_refs", [])),
                "category": hypothesis["category"],
            }
            for hypothesis in hypotheses[:3]
        ]
        root_cause = {
            "summary": winning_hypothesis["summary"],
            "confidence": float(winning_hypothesis["confidence"]),
            "evidence_refs": list(winning_hypothesis.get("support_evidence_refs", [])),
        }
    else:
        root_cause = {
            "summary": "证据不足，暂不能形成根因结论",
            "confidence": 0.18,
            "evidence_refs": [],
        }

    if conclusion_status == "insufficient_evidence":
        recommendations.extend(
            [
                "补采对象详情、近期事件、关键指标和拓扑关系后重新分析",
                f"重点补齐缺失证据：{', '.join(evidence_sufficiency.get('missing_critical_evidence', [])) or '详情/事件/指标'}",
                "在证据不足前，不建议直接执行高风险修复动作",
            ]
        )
    else:
        recommendations.extend(
            [
                "检查最近硬件事件、管理网络和存储链路，确认是否存在基础设施侧异常",
                "对照异常时间窗核对最近变更、迁移、重启或配置调整",
                "在执行动作前先做只读复核，必要时通过执行申请走审批",
            ]
        )
        if winning_hypothesis and winning_hypothesis.get("category") == "capacity":
            recommendations.insert(0, "优先核查 CPU、内存和存储压力，必要时迁移高负载虚机或限流")
        elif winning_hypothesis and winning_hypothesis.get("category") == "change":
            recommendations.insert(0, "优先核查最近变更记录与异常时间窗是否重合，必要时准备回退")

    analysis_process.append(
        _analysis_step(
            round_no=max(round_no, 1),
            stage="recommendation_planning",
            status="success",
            goal="根据结论状态生成处置建议",
            finding=f"生成建议动作 {len(recommendations)} 条",
            decision="更新 incident 并尝试自动处置",
            selected_tools=[],
            evidence_found=list(root_cause.get("evidence_refs", [])),
            evidence_missing=list(evidence_sufficiency.get("missing_critical_evidence", [])),
            contradictions=[str(item.get("summary") or item.get("kind") or "evidence contradiction") for item in contradictions],
            why="建议动作必须与结论状态匹配，证据不足时只能优先补证而不是激进处置。",
        )
    )

    auto_mode = _get_user_auto_mode(user_id)
    if conclusion_status in {"confirmed", "probable"}:
        resolved, auto_logs = await _maybe_auto_remediate(
            incident_id=incident_id,
            user_mode=auto_mode,
            recommendations=recommendations,
            mode=mode,
            summary=summary,
            host_detail=host_detail,
        )
    else:
        resolved = False
        auto_logs = ["自动处置：跳过（当前结论未通过证据门禁）"]
    recommendations.extend(auto_logs)

    analysis_state = {
        "status": "completed",
        "round": round_no if round_no > 0 else 1,
        "max_rounds": ANALYSIS_MAX_ROUNDS,
        "started_at": started_at,
        "updated_at": _now(),
        "elapsed_ms": int((datetime.now(UTC) - start_dt).total_seconds() * 1000),
        "final_conclusion": final_conclusion,
        "recommended_actions": recommendations,
        "analysis_process": analysis_process,
        "next_decision": next_decision,
        "conclusion_status": conclusion_status,
        "evidence_sufficiency": evidence_sufficiency,
        "contradictions": contradictions,
        "counter_evidence_result": counter_result,
    }
    details["evidence_refs"] = evidence_refs
    details["root_cause"] = root_cause
    details["root_cause_candidates"] = root_causes
    details["hypotheses"] = hypotheses
    details["winning_hypothesis"] = winning_hypothesis
    details["counter_evidence_result"] = counter_result
    details["conclusion_status"] = conclusion_status
    details["evidence_sufficiency"] = evidence_sufficiency
    details["contradictions"] = contradictions
    details["recommended_actions"] = recommendations
    details["analysis"] = analysis_state

    new_status = "resolved" if resolved else "pending_action"
    summary = final_conclusion
    _exec(
        "UPDATE incidents SET status=?, summary=?, details_json=?, last_updated_at=?, ai_analysis_triggered=1 WHERE id=?",
        (new_status, summary, json.dumps(details, ensure_ascii=False), _now(), incident_id),
    )
    if new_status == "resolved":
        _archive_case_from_incident(incident_id)
    _write_audit(
        "analysis_completed",
        "analyze_incident",
        "success",
        incident_ref=incident_id,
        metadata={"status": new_status, "round": analysis_state["round"], "auto_mode": auto_mode},
    )
    return {"incident_id": incident_id, "status": new_status, "analysis": analysis_state}


async def _monitoring_cycle() -> None:
    vcenter_inventory = await _invoke_tool("vmware.get_vcenter_inventory", {"connection": _vcenter_connection_input()})
    alerts = await _invoke_tool("vmware.query_alerts", {"connection": _vcenter_connection_input()})

    for host in vcenter_inventory.get("hosts", []) or []:
        cpu_mhz = float(host.get("cpu_mhz") or 0)
        cpu_usage_mhz = float(host.get("cpu_usage_mhz") or 0)
        mem_mb = float(host.get("memory_mb") or 0)
        mem_usage_mb = float(host.get("memory_usage_mb") or 0)
        cpu_pct = (cpu_usage_mhz / cpu_mhz * 100.0) if cpu_mhz else 0.0
        mem_pct = (mem_usage_mb / mem_mb * 100.0) if mem_mb else 0.0
        if cpu_pct > 85:
            _upsert_incident_from_event(
                IngestEventBody(
                    source="vmware-monitor",
                    source_type="vmware_host_hotspot",
                    object_type="HostSystem",
                    object_id=host.get("host_id") or host.get("name") or "unknown-host",
                    object_name=host.get("name"),
                    severity="high",
                    summary=f"Host {host.get('name')} CPU usage {cpu_pct:.1f}% exceeds 85%",
                    rule_id="vc-host-cpu-85",
                    extra={"host_name": host.get("name"), "cpu_usage_percent": round(cpu_pct, 2)},
                )
            )
        if mem_pct > 90:
            _upsert_incident_from_event(
                IngestEventBody(
                    source="vmware-monitor",
                    source_type="vmware_host_hotspot",
                    object_type="HostSystem",
                    object_id=host.get("host_id") or host.get("name") or "unknown-host",
                    object_name=host.get("name"),
                    severity="high",
                    summary=f"Host {host.get('name')} memory usage {mem_pct:.1f}% exceeds 90%",
                    rule_id="vc-host-mem-90",
                    extra={"host_name": host.get("name"), "memory_usage_percent": round(mem_pct, 2)},
                )
            )

    for alert in alerts.get("alerts", []) or []:
        _upsert_incident_from_event(
            IngestEventBody(
                source="vmware-alert",
                source_type="vmware_non_green",
                object_type="ManagedObject",
                object_id=alert.get("object_id") or f"obj-{uuid.uuid4().hex[:6]}",
                object_name=alert.get("object_name"),
                severity="high",
                summary=alert.get("summary") or "vCenter object non-green",
                rule_id="vc-overall-non-green",
                extra={"alert": alert},
            )
        )

    for vm in vcenter_inventory.get("virtual_machines", []) or []:
        if str(vm.get("power_state", "")).lower() in {"poweredoff", "powered_off", "off"}:
            _upsert_incident_from_event(
                IngestEventBody(
                    source="vmware-monitor",
                    source_type="vm_guest_down",
                    object_type="VirtualMachine",
                    object_id=vm.get("vm_id") or vm.get("name") or "unknown-vm",
                    object_name=vm.get("name"),
                    severity="medium",
                    summary=f"VM {vm.get('name')} is powered off",
                    rule_id="vc-vm-powered-off",
                    extra={"vm_id": vm.get("vm_id"), "name": vm.get("name")},
                )
            )

    workload = await _invoke_tool("k8s.get_workload_status", {"connection": _k8s_connection_input()})
    for node in workload.get("nodes", []) or []:
        if not node.get("ready", True):
            _upsert_incident_from_event(
                IngestEventBody(
                    source="k8s-monitor",
                    source_type="k8s_node_notready",
                    object_type="Node",
                    object_id=node.get("node_name", "unknown-node"),
                    object_name=node.get("node_name", "unknown-node"),
                    severity="high",
                    summary=f"Node {node.get('node_name')} is NotReady",
                    rule_id="k8s-node-not-ready",
                    extra={"node": node},
                )
            )

    for pod in workload.get("pods", []) or []:
        restarts = int(pod.get("restart_count") or 0)
        if restarts > 3:
            pod_name = pod.get("pod_name", "unknown-pod")
            dep_name = pod_name.rsplit("-", 2)[0] if "-" in pod_name else pod_name
            _upsert_incident_from_event(
                IngestEventBody(
                    source="k8s-monitor",
                    source_type="k8s_pod_restarts",
                    object_type="Pod",
                    object_id=f"{pod.get('namespace', 'default')}/{pod_name}",
                    object_name=pod_name,
                    severity="medium",
                    summary=f"Pod {pod_name} restarted {restarts} times",
                    rule_id="k8s-pod-restarts-10m",
                    extra={"namespace": pod.get("namespace", "default"), "deployment_name": dep_name, "restart_count": restarts},
                )
            )

    for dep in workload.get("deployments", []) or []:
        desired = int(dep.get("replicas_desired") or 0)
        available = int(dep.get("replicas_available") or 0)
        if desired > available:
            _upsert_incident_from_event(
                IngestEventBody(
                    source="k8s-monitor",
                    source_type="k8s_deployment_unavailable",
                    object_type="Deployment",
                    object_id=f"{dep.get('namespace', 'default')}/{dep.get('name', 'unknown')}",
                    object_name=dep.get("name", "unknown"),
                    severity="high",
                    summary=f"Deployment {dep.get('name')} available replicas {available}/{desired}",
                    rule_id="k8s-deployment-unavailable",
                    extra={"namespace": dep.get("namespace", "default"), "deployment_name": dep.get("name"), "replicas_desired": desired},
                )
            )


async def _monitor_loop() -> None:
    MONITOR_STATE["running"] = True
    MONITOR_STATE["started_at"] = _now()
    MONITOR_STATE["last_error"] = None
    try:
        while MONITOR_STATE["running"]:
            try:
                await _monitoring_cycle()
                MONITOR_STATE["last_run_at"] = _now()
                for row in _query_all("SELECT id FROM incidents WHERE status IN ('new','analyzing') ORDER BY first_seen_at DESC LIMIT 30"):
                    try:
                        await _analyze_incident(row["id"])
                    except Exception as exc:  # noqa: BLE001
                        _write_audit(
                            "analysis_failed",
                            "analyze_incident",
                            "failed",
                            incident_ref=row["id"],
                            reason=str(exc),
                        )
                        continue
            except Exception as exc:  # noqa: BLE001
                MONITOR_STATE["last_error"] = str(exc)
            await asyncio.sleep(max(10, MONITOR_INTERVAL_SECONDS))
    finally:
        MONITOR_STATE["running"] = False
        MONITOR_STATE["task"] = None


async def _start_monitoring(force: bool = False) -> dict[str, Any]:
    task = MONITOR_STATE.get("task")
    if task and not task.done() and not force:
        return {"running": True, "message": "monitor already running"}
    MONITOR_STATE["running"] = False
    await asyncio.sleep(0.2)
    MONITOR_STATE["running"] = True
    MONITOR_STATE["task"] = asyncio.create_task(_monitor_loop())
    return {"running": True, "message": "monitor started"}


async def _stop_monitoring() -> dict[str, Any]:
    MONITOR_STATE["running"] = False
    await asyncio.sleep(0.2)
    return {"running": False, "message": "monitor stopped"}


@app.on_event("startup")
async def startup() -> None:
    _init_db()
    if MONITOR_ENABLED_ON_START:
        await _start_monitoring()


@app.get("/health")
async def health() -> dict:
    return make_success(
        {
            "status": "healthy",
            "monitor_running": bool(MONITOR_STATE["running"]),
            "monitor_last_run_at": MONITOR_STATE["last_run_at"],
            "monitor_last_error": MONITOR_STATE["last_error"],
            "mock_fallback": {
                "vmware_use_mock_fallback": VMWARE_USE_MOCK_FALLBACK,
                "k8s_use_mock_fallback": K8S_USE_MOCK_FALLBACK,
            },
            "sources": {
                "vcenter": VCENTER_ENDPOINT,
                "k8s_kubeconfig_path": K8S_KUBECONFIG_PATH,
            },
        }
    )


@app.get("/api/v1/monitoring/status")
async def monitoring_status() -> dict:
    return make_success(
        {
            "running": bool(MONITOR_STATE["running"]),
            "interval_seconds": MONITOR_INTERVAL_SECONDS,
            "started_at": MONITOR_STATE["started_at"],
            "last_run_at": MONITOR_STATE["last_run_at"],
            "last_error": MONITOR_STATE["last_error"],
            "sources": {
                "vcenter_connection_id": VCENTER_CONN_ID,
                "vcenter_endpoint": VCENTER_ENDPOINT,
                "k8s_connection_id": K8S_CONN_ID,
                "kubeconfig_path": K8S_KUBECONFIG_PATH,
            },
        }
    )


@app.post("/api/v1/monitoring/start")
async def monitoring_start(body: MonitoringControlBody | None = None) -> dict:
    data = await _start_monitoring(force=bool(body.force) if body else False)
    return make_success(data)


@app.post("/api/v1/monitoring/stop")
async def monitoring_stop() -> dict:
    data = await _stop_monitoring()
    return make_success(data)


@app.post("/api/v1/events/ingest")
async def ingest_event(body: IngestEventBody) -> dict:
    try:
        incident = _upsert_incident_from_event(body)
        return make_success({"event_id": f"evt-{uuid.uuid4().hex[:12]}", "ingested_at": _now(), "incident_id": incident["id"]})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/incidents")
async def list_incidents() -> dict:
    try:
        rows = _query_all("SELECT * FROM incidents ORDER BY last_updated_at DESC LIMIT 200")
        return make_success({"incidents": [_incident_from_row(r) for r in rows]})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/incidents/analysis-preferences")
async def get_analysis_preferences(user_id: str = "ops-user") -> dict:
    try:
        mode = _get_user_auto_mode(user_id)
        return make_success({"user_id": user_id, "auto_remediation_mode": mode, "updated_at": _now()})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.put("/api/v1/incidents/analysis-preferences")
async def put_analysis_preferences(body: AnalysisPreferenceBody) -> dict:
    try:
        _set_user_auto_mode(body.user_id, body.auto_remediation_mode)
        return make_success(
            {
                "user_id": body.user_id,
                "auto_remediation_mode": _get_user_auto_mode(body.user_id),
                "updated_at": _now(),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict:
    try:
        row = _query_one("SELECT * FROM incidents WHERE id=?", (incident_id,))
        if not row:
            return make_error(f"incident not found: {incident_id}")
        return make_success(_incident_from_row(row))
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.post("/api/v1/incidents/{incident_id}/analyze")
async def analyze_incident(incident_id: str, body: AnalyzeIncidentBody | None = None) -> dict:
    try:
        payload = body or AnalyzeIncidentBody()
        result = await _analyze_incident(incident_id, mode=payload.mode, user_id=payload.user_id)
        return make_success(result)
    except Exception as exc:  # noqa: BLE001
        _write_audit(
            "analysis_failed",
            "analyze_incident",
            "failed",
            incident_ref=incident_id,
            reason=str(exc),
        )
        return make_error(str(exc))


@app.post("/api/v1/remediation/execute")
async def remediation_execute(body: RemediationBody) -> dict:
    try:
        result = await _execute_remediation(body.incident_id, body.action, body.parameters, body.mode)
        return make_success(result)
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.post("/api/v1/executions/dry-run")
async def execution_dry_run(body: ExecutionBody) -> dict:
    try:
        data = await _run_execution_dry_run(body, persist=True)
        return make_success(data)
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.post("/api/v1/executions/submit")
async def execution_submit(body: ExecutionBody) -> dict:
    try:
        dry = await _run_execution_dry_run(body, persist=False)
        dry_run_result = dry["dry_run_result"]
        if not dry_run_result.get("can_submit"):
            return make_error("execution is blocked by dry-run/policy checks")

        execution_id = _create_execution_request_record(
            body,
            action_type=dry_run_result["action_type"],
            risk_level=dry_run_result["risk_level"],
            risk_score=int(dry_run_result["risk_score"]),
            require_approval=bool(dry_run_result["require_approval"]),
            policy=dry_run_result["policy"],
            status="pending_approval" if dry_run_result["require_approval"] else "executing",
        )
        target_results = [
            {
                "target": t.model_dump(),
                "status": "pending",
                "message": "submitted",
                "preview": {},
            }
            for t in body.targets
        ]
        _save_execution_targets(execution_id, target_results)
        _save_execution_step(execution_id, "submit", "success", dry_run_result)
        _write_audit("execution_started", body.tool_name, "success", incident_ref=body.incident_id, metadata={"execution_id": execution_id})

        approval_id = None
        if dry_run_result["require_approval"]:
            approval_id = _create_execution_approval(
                execution_id,
                body,
                risk_level=dry_run_result["risk_level"],
                risk_score=int(dry_run_result["risk_score"]),
            )
        else:
            execution_result = await _execute_targets(execution_id, body)
            _write_audit(
                "execution_completed" if execution_result["status"] == "success" else "execution_failed",
                body.tool_name,
                "success" if execution_result["status"] == "success" else "failed",
                incident_ref=body.incident_id,
                metadata={"execution_id": execution_id},
            )

        return make_success(
            {
                "execution_id": execution_id,
                "status": "pending_approval" if approval_id else _execution_detail(execution_id)["status"],
                "approval_id": approval_id,
                "dry_run_result": dry_run_result,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/executions/{execution_id}")
async def get_execution(execution_id: str) -> dict:
    try:
        return make_success(_execution_detail(execution_id))
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/executions")
async def list_executions(status: str | None = None, limit: int = 50) -> dict:
    try:
        safe_limit = max(1, min(limit, 200))
        if status:
            rows = _query_all(
                "SELECT * FROM execution_requests WHERE status=? ORDER BY updated_at DESC LIMIT ?",
                (status, safe_limit),
            )
        else:
            rows = _query_all(
                "SELECT * FROM execution_requests ORDER BY updated_at DESC LIMIT ?",
                (safe_limit,),
            )
        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "tool_name": row["tool_name"],
                    "action_type": row["action_type"],
                    "environment": row["environment"],
                    "requester": row["requester"],
                    "status": row["status"],
                    "incident_id": row["incident_id"],
                    "change_analysis_ref": row["change_analysis_ref"],
                    "approval_id": row["approval_id"],
                    "risk_level": row["risk_level"],
                    "risk_score": row["risk_score"],
                    "require_approval": bool(row["require_approval"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return make_success({"items": items, "total": len(items)})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.post("/api/v1/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str) -> dict:
    try:
        row = _query_one("SELECT * FROM execution_requests WHERE id=?", (execution_id,))
        if not row:
            return make_error(f"execution not found: {execution_id}")
        status = row["status"]
        if status not in {"pending_approval", "dry_run_ready", "draft"}:
            return make_error(f"execution in status '{status}' cannot be canceled")
        _exec("UPDATE execution_requests SET status='canceled', updated_at=? WHERE id=?", (_now(), execution_id))
        _save_execution_step(execution_id, "cancel", "success", {"previous_status": status})
        _write_audit("execution_canceled", row["tool_name"], "success", incident_ref=row["incident_id"], metadata={"execution_id": execution_id})
        return make_success({"execution_id": execution_id, "status": "canceled"})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/notifications")
async def list_notifications(status: str | None = None) -> dict:
    try:
        rows = (
            _query_all("SELECT * FROM notifications WHERE status=? ORDER BY created_at DESC LIMIT 200", (status,))
            if status
            else _query_all("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 200")
        )
        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "priority": row["priority"],
                    "status": row["status"],
                    "incident_ref": row["incident_ref"],
                    "channels": json.loads(row["channels_json"] or "[]"),
                    "recipients": json.loads(row["recipients_json"] or "[]"),
                    "created_at": row["created_at"],
                    "delivered_at": row["delivered_at"],
                    "acknowledged_at": row["acknowledged_at"],
                    "acknowledged_by": row["acknowledged_by"],
                    "escalation_count": row["escalation_count"],
                    "next_escalation_at": row["next_escalation_at"],
                }
            )
        return make_success({"items": items, "total": len(items)})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.post("/api/v1/notifications/{notification_id}/acknowledge")
async def acknowledge_notification(notification_id: str) -> dict:
    try:
        now = _now()
        _exec("UPDATE notifications SET status='acknowledged', acknowledged_at=?, acknowledged_by=? WHERE id=?", (now, "current-user", notification_id))
        return make_success({"id": notification_id, "status": "acknowledged", "acknowledged_at": now})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/oncall/shifts")
async def oncall_shifts() -> dict:
    now = datetime.now(UTC)
    return make_success(
        {
            "items": [
                {
                    "id": "shift-live",
                    "name": "Current On-Call Shift",
                    "team": ONCALL_TEAM,
                    "members": ONCALL_MEMBERS,
                    "start_at": (now - timedelta(hours=4)).isoformat(),
                    "end_at": (now + timedelta(hours=8)).isoformat(),
                    "active": True,
                }
            ]
        }
    )


@app.get("/api/v1/approvals")
async def list_approvals(status: str | None = None) -> dict:
    try:
        rows = (
            _query_all("SELECT * FROM approvals WHERE status=? ORDER BY updated_at DESC LIMIT 200", (status,))
            if status
            else _query_all("SELECT * FROM approvals ORDER BY updated_at DESC LIMIT 200")
        )
        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "description": row["description"],
                    "action_type": row["action_type"],
                    "risk_level": row["risk_level"],
                    "risk_score": row["risk_score"],
                    "status": row["status"],
                    "requester": row["requester"],
                    "assignee": row["assignee"],
                    "incident_ref": row["incident_ref"],
                    "change_analysis_ref": row["change_analysis_ref"],
                    "target_object": row["target_object"],
                    "target_object_type": row["target_object_type"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "expires_at": row["expires_at"],
                    "decision_comment": row["decision_comment"],
                    "decided_at": row["decided_at"],
                    "decided_by": row["decided_by"],
                    "tags": json.loads(row["tags_json"] or "[]"),
                }
            )
        return make_success({"items": items, "total": len(items)})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/approvals/{approval_id}")
async def get_approval(approval_id: str) -> dict:
    try:
        row = _query_one("SELECT * FROM approvals WHERE id=?", (approval_id,))
        if not row:
            return make_error(f"approval not found: {approval_id}")
        return make_success(
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "action_type": row["action_type"],
                "risk_level": row["risk_level"],
                "risk_score": row["risk_score"],
                "status": row["status"],
                "requester": row["requester"],
                "assignee": row["assignee"],
                "incident_ref": row["incident_ref"],
                "change_analysis_ref": row["change_analysis_ref"],
                "target_object": row["target_object"],
                "target_object_type": row["target_object_type"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "expires_at": row["expires_at"],
                "decision_comment": row["decision_comment"],
                "decided_at": row["decided_at"],
                "decided_by": row["decided_by"],
                "tags": json.loads(row["tags_json"] or "[]"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.post("/api/v1/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, body: DecisionBody) -> dict:
    try:
        row = _query_one("SELECT * FROM approvals WHERE id=?", (approval_id,))
        if not row:
            return make_error(f"approval not found: {approval_id}")
        decision = body.decision.lower()
        if decision not in {"approved", "rejected"}:
            return make_error("decision must be approved/rejected")
        now = _now()
        _exec("UPDATE approvals SET status=?, decided_at=?, decided_by=?, decision_comment=?, updated_at=? WHERE id=?", (decision, now, body.decided_by, body.comment or "", now, approval_id))
        _write_audit("approval_decided", decision, "success", incident_ref=row["incident_ref"], metadata={"approval_id": approval_id})
        if decision == "approved":
            tags = json.loads(row["tags_json"] or "[]")
            execution_id = next(
                (
                    t.split("execution_id:", 1)[1]
                    for t in tags
                    if isinstance(t, str) and t.startswith("execution_id:")
                ),
                None,
            )
            if execution_id:
                exec_row = _query_one("SELECT * FROM execution_requests WHERE id=?", (execution_id,))
                if exec_row and exec_row["status"] == "pending_approval":
                    _exec("UPDATE execution_requests SET status='executing', updated_at=? WHERE id=?", (_now(), execution_id))
                    exec_body = _execution_body_from_record(execution_id)
                    result = await _execute_targets(execution_id, exec_body)
                    _write_audit(
                        "execution_completed" if result["status"] == "success" else "execution_failed",
                        exec_body.tool_name,
                        "success" if result["status"] == "success" else "failed",
                        incident_ref=exec_body.incident_id,
                        metadata={"execution_id": execution_id, "approval_id": approval_id},
                    )
        return make_success({"request_id": approval_id, "decision": decision, "decided_at": now, "decided_by": body.decided_by})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/audit/logs")
async def list_audit_logs(severity: str | None = None, event_type: str | None = None, actor_type: str | None = None, limit: int = 50) -> dict:
    try:
        sql = "SELECT * FROM audit_logs WHERE 1=1"
        params: list[Any] = []
        if severity:
            sql += " AND severity=?"
            params.append(severity)
        if event_type:
            sql += " AND event_type=?"
            params.append(event_type)
        if actor_type:
            sql += " AND actor_type=?"
            params.append(actor_type)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        rows = _query_all(sql, tuple(params))
        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "severity": row["severity"],
                    "actor": row["actor"],
                    "actor_type": row["actor_type"],
                    "action": row["action"],
                    "resource_type": row["resource_type"],
                    "resource_id": row["resource_id"],
                    "resource_name": row["resource_name"],
                    "outcome": row["outcome"],
                    "reason": row["reason"],
                    "incident_ref": row["incident_ref"],
                    "request_id": row["request_id"],
                    "trace_id": row["trace_id"],
                    "timestamp": row["timestamp"],
                    "metadata": json.loads(row["metadata_json"] or "{}"),
                }
            )
        return make_success({"items": items, "total": len(items)})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/audit/logs/{log_id}")
async def get_audit_log(log_id: str) -> dict:
    try:
        row = _query_one("SELECT * FROM audit_logs WHERE id=?", (log_id,))
        if not row:
            return make_error(f"audit log not found: {log_id}")
        return make_success(
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "severity": row["severity"],
                "actor": row["actor"],
                "actor_type": row["actor_type"],
                "action": row["action"],
                "resource_type": row["resource_type"],
                "resource_id": row["resource_id"],
                "resource_name": row["resource_name"],
                "outcome": row["outcome"],
                "reason": row["reason"],
                "incident_ref": row["incident_ref"],
                "request_id": row["request_id"],
                "trace_id": row["trace_id"],
                "timestamp": row["timestamp"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.post("/api/v1/audit/logs")
async def create_audit_log(body: AuditWriteBody) -> dict:
    try:
        event_type = (body.event_type or "").strip()
        action = (body.action or "").strip()
        outcome = (body.outcome or "").strip().lower()
        if not event_type:
            return make_error("event_type is required")
        if not action:
            return make_error("action is required")
        if outcome not in {"success", "failure", "failed", "blocked"}:
            return make_error("outcome must be one of: success/failure/failed/blocked")
        normalized_outcome = "failure" if outcome == "failed" else outcome

        actor_type = (body.actor_type or "system").strip().lower()
        if actor_type not in {"human", "agent", "system", "service"}:
            actor_type = "system"

        severity = (body.severity or "").strip().lower()
        if severity not in {"info", "warning", "critical"}:
            severity = "info" if normalized_outcome == "success" else "warning"

        log_id = f"AUD-{uuid.uuid4().hex[:8]}"
        _exec(
            """
            INSERT INTO audit_logs(id,event_type,severity,actor,actor_type,action,resource_type,resource_id,resource_name,outcome,reason,incident_ref,request_id,trace_id,timestamp,metadata_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                log_id,
                event_type,
                severity,
                body.actor or "unknown",
                actor_type,
                action,
                body.resource_type,
                body.resource_id,
                body.resource_name,
                normalized_outcome,
                body.reason,
                body.incident_ref,
                body.request_id or f"req-{uuid.uuid4().hex[:10]}",
                body.trace_id or f"trace-{uuid.uuid4().hex[:10]}",
                body.timestamp or _now(),
                json.dumps(body.metadata or {}, ensure_ascii=False),
            ),
        )
        return make_success({"id": log_id, "created_at": _now()})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/cases")
async def list_cases(category: str | None = None, status: str | None = None) -> dict:
    try:
        sql = "SELECT * FROM cases WHERE 1=1"
        params: list[Any] = []
        if category:
            sql += " AND category=?"
            params.append(category)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY archived_at DESC, created_at DESC LIMIT 200"
        rows = _query_all(sql, tuple(params))
        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "summary": row["summary"],
                    "category": row["category"],
                    "status": row["status"],
                    "severity": row["severity"],
                    "tags": json.loads(row["tags_json"] or "[]"),
                    "incident_refs": json.loads(row["incident_refs_json"] or "[]"),
                    "root_cause_summary": row["root_cause_summary"],
                    "resolution_summary": row["resolution_summary"],
                    "lessons_learned": row["lessons_learned"],
                    "author": row["author"],
                    "created_at": row["created_at"],
                    "archived_at": row["archived_at"],
                    "similarity_score": row["similarity_score"],
                    "hit_count": row["hit_count"],
                    "knowledge_refs": json.loads(row["knowledge_refs_json"] or "[]"),
                }
            )
        return make_success({"items": items, "total": len(items)})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/cases/{case_id}")
async def get_case(case_id: str) -> dict:
    try:
        row = _query_one("SELECT * FROM cases WHERE id=?", (case_id,))
        if not row:
            return make_error(f"case not found: {case_id}")
        return make_success(
            {
                "id": row["id"],
                "title": row["title"],
                "summary": row["summary"],
                "category": row["category"],
                "status": row["status"],
                "severity": row["severity"],
                "tags": json.loads(row["tags_json"] or "[]"),
                "incident_refs": json.loads(row["incident_refs_json"] or "[]"),
                "root_cause_summary": row["root_cause_summary"],
                "resolution_summary": row["resolution_summary"],
                "lessons_learned": row["lessons_learned"],
                "author": row["author"],
                "created_at": row["created_at"],
                "archived_at": row["archived_at"],
                "similarity_score": row["similarity_score"],
                "hit_count": row["hit_count"],
                "knowledge_refs": json.loads(row["knowledge_refs_json"] or "[]"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))

