"""OpsPilot Governance Service - audit, policy (OPA-backed), upgrades."""
from __future__ import annotations

import os
from typing import Optional, Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opspilot_schema.envelope import make_success

app = FastAPI(title="OpsPilot Governance Service", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_AUDIT_LOGS = [
    {"id": "AUD-001", "event_type": "tool_invoked", "severity": "info", "actor": "EvidenceCollectionAgent", "actor_type": "agent", "action": "vmware.get_host_detail", "resource_type": "HostSystem", "resource_id": "host-33", "resource_name": "esxi-node03", "outcome": "success", "reason": None, "incident_ref": "INC-20260405-001", "request_id": "req-a1b2c3", "trace_id": "trc-x1y2z3", "timestamp": "2026-04-05T08:20:06Z", "metadata": {}},
    {"id": "AUD-004", "event_type": "policy_hit", "severity": "warning", "actor": "Orchestrator", "actor_type": "agent", "action": "vmware.vm_migrate", "resource_type": "VirtualMachine", "resource_id": "vm-201", "resource_name": "app-server-01", "outcome": "blocked", "reason": "Risk score exceeded auto-execution threshold", "incident_ref": "INC-20260405-001", "request_id": "req-j1k2l3", "trace_id": "trc-g1h2i3", "timestamp": "2026-04-05T08:49:00Z", "metadata": {"policy_id": "POL-001", "risk_score": 45}},
]

_POLICIES = [
    {"id": "POL-001", "name": "High-risk operation approval gate", "status": "active", "effect": "require_approval", "type": "approval_gate", "hit_count": 12},
    {"id": "POL-002", "name": "Production maintenance window guard", "status": "active", "effect": "deny", "type": "time_window", "hit_count": 4},
]

OPA_URL = os.environ.get("OPA_URL", "http://127.0.0.1:8181").rstrip("/")
OPA_POLICY_PATH = os.environ.get("OPA_POLICY_PATH", "/v1/data/opspilot")
OPA_FAIL_MODE = os.environ.get("OPA_FAIL_MODE", "deny").strip().lower()


@app.get("/health")
async def health():
    return make_success(
        {
            "status": "ok",
            "service": "governance-service",
            "opa_url": OPA_URL,
            "opa_policy_path": OPA_POLICY_PATH,
            "opa_fail_mode": OPA_FAIL_MODE,
        }
    )


@app.get("/audit/logs")
async def list_audit_logs(severity: Optional[str] = None, limit: int = 50):
    data = _AUDIT_LOGS
    if severity:
        data = [l for l in data if l["severity"] == severity]
    return make_success({"items": data[:limit], "total": len(data)})


@app.get("/policies")
async def list_policies(status: Optional[str] = None):
    data = _POLICIES if not status else [p for p in _POLICIES if p["status"] == status]
    return make_success({"items": data, "total": len(data)})


@app.post("/policies/evaluate")
async def evaluate_policy(context: dict):
    """Evaluate policy by external OPA and map to OpsPilot decision shape."""
    opa_endpoint = f"{OPA_URL}{OPA_POLICY_PATH}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(opa_endpoint, json={"input": context})
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("result", {}) if isinstance(payload, dict) else {}
        allowed = bool(data.get("allow", False))
        require_approval = bool(data.get("approval_required", False))
        reason = str(data.get("deny_reason") or ("Approval required" if require_approval else "Allowed"))
        matched_policies = _infer_matched_policies(context, require_approval, reason)
        return make_success(
            {
                "allowed": allowed,
                "require_approval": require_approval,
                "reason": reason,
                "matched_policies": matched_policies,
                "source": "opa",
            }
        )
    except Exception as exc:  # noqa: BLE001
        fallback = _fallback_policy_decision(context, str(exc))
        return make_success({**fallback, "source": "fallback"})


def _infer_matched_policies(context: dict[str, Any], require_approval: bool, reason: str) -> list[str]:
    policies: list[str] = []
    if require_approval:
        policies.append("POL-001")
    if str(context.get("tool_name", "")).strip() == "vmware.vm_power_off" and str(context.get("environment", "")).lower() == "prod":
        policies.append("POL-003")
    if "same person" in reason.lower():
        policies.append("POL-004")
    # deduplicate while preserving order
    deduped: list[str] = []
    seen: set[str] = set()
    for p in policies:
        if p not in seen:
            deduped.append(p)
            seen.add(p)
    return deduped


def _fallback_policy_decision(context: dict[str, Any], error_message: str) -> dict[str, Any]:
    action_type = str(context.get("action_type", "read")).lower()
    is_write = action_type in {"write", "dangerous"}
    if OPA_FAIL_MODE == "allow_readonly":
        if not is_write:
            return {
                "allowed": True,
                "require_approval": False,
                "reason": f"OPA unavailable, fallback allow read-only: {error_message}",
                "matched_policies": [],
            }
        return {
            "allowed": False,
            "require_approval": True,
            "reason": f"OPA unavailable, write action denied by fallback: {error_message}",
            "matched_policies": ["POL-001"],
        }
    # default deny mode: deny writes, allow reads
    if is_write:
        return {
            "allowed": False,
            "require_approval": True,
            "reason": f"OPA unavailable, deny write action: {error_message}",
            "matched_policies": ["POL-001"],
        }
    return {
        "allowed": True,
        "require_approval": False,
        "reason": f"OPA unavailable, fallback allow read-only: {error_message}",
        "matched_policies": [],
    }


@app.get("/upgrades")
async def list_upgrades():
    return make_success({"items": [
        {"id": "PKG-001", "version": "0.2.0", "status": "ready", "environment": "production"},
        {"id": "PKG-002", "version": "0.1.1", "status": "deployed", "environment": "production"},
    ]})

