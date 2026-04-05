"""OpsPilot Governance Service - audit, policy (OPA stub), upgrades."""
from __future__ import annotations
from typing import Optional, Any
from fastapi import FastAPI, HTTPException
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
    {"id": "AUD-004", "event_type": "policy_hit", "severity": "warning", "actor": "Orchestrator", "actor_type": "agent", "action": "vmware.vm_migrate", "resource_type": "VirtualMachine", "resource_id": "vm-201", "resource_name": "app-server-01", "outcome": "blocked", "reason": "风险评分超过无审批执行阈值", "incident_ref": "INC-20260405-001", "request_id": "req-j1k2l3", "trace_id": "trc-g1h2i3", "timestamp": "2026-04-05T08:49:00Z", "metadata": {"policy_id": "POL-001", "risk_score": 45}},
]

_POLICIES = [
    {"id": "POL-001", "name": "高风险操作审批门控", "status": "active", "effect": "require_approval", "type": "approval_gate", "hit_count": 12},
    {"id": "POL-002", "name": "生产环境时间窗口限制", "status": "active", "effect": "deny", "type": "time_window", "hit_count": 4},
]


@app.get("/health")
async def health():
    return make_success({"status": "ok", "service": "governance-service"})


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
    """OPA-style policy evaluation stub."""
    risk_score = context.get("risk_score", 0)
    action_type = context.get("action_type", "read")
    result = {
        "allowed": action_type == "read" or risk_score <= 30,
        "require_approval": risk_score > 30 and action_type == "write",
        "reason": "High risk score requires approval" if risk_score > 30 else "Allowed",
        "matched_policies": ["POL-001"] if risk_score > 30 else [],
    }
    return make_success(result)


@app.get("/upgrades")
async def list_upgrades():
    return make_success({"items": [
        {"id": "PKG-001", "version": "0.2.0", "status": "ready", "environment": "production"},
        {"id": "PKG-002", "version": "0.1.1", "status": "deployed", "environment": "production"},
    ]})
