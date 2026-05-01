"""BFF router: Policy management."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter
from opspilot_schema.envelope import make_error, make_success

router = APIRouter(tags=["policies"])
GOVERNANCE_SERVICE_URL = os.environ.get("GOVERNANCE_SERVICE_URL", "http://127.0.0.1:8071")

_POLICIES = [
    {"id": "POL-001", "name": "高风险操作审批门控", "description": "凡工具调用风险评分超过 30 分的写操作，必须通过人工审批后方可执行。", "type": "approval_gate", "status": "active", "effect": "require_approval", "scope": ["vmware.vm_migrate", "vmware.vm_power_off", "script_exec"], "conditions": {"risk_score_gt": 30}, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-03-01T12:00:00Z", "hit_count": 12, "last_hit_at": "2026-04-05T08:49:00Z", "author": "security-team", "version": "1.1.0", "rego_snippet": "package opspilot.approval\ndefault require_approval = false\nrequire_approval { input.risk_score > 30 }"},
    {"id": "POL-002", "name": "生产环境时间窗口限制", "description": "生产环境写操作仅允许在维护窗口（周三 02:00-06:00）内执行。", "type": "time_window", "status": "active", "effect": "deny", "scope": ["production"], "conditions": {"allowed_hours": {"weekday": 3}}, "created_at": "2026-02-01T00:00:00Z", "updated_at": "2026-02-15T10:00:00Z", "hit_count": 4, "last_hit_at": "2026-04-03T14:22:00Z", "author": "ops-lead", "version": "1.0.0", "rego_snippet": None},
    {"id": "POL-003", "name": "核心 VM 保护策略", "description": "标记为 core-service 的虚拟机，禁止通过 AI 直接执行关机和删除操作。", "type": "scope_guard", "status": "active", "effect": "deny", "scope": ["vmware.vm_power_off", "vmware.vm_delete"], "conditions": {"vm_tag": "core-service"}, "created_at": "2026-01-15T08:00:00Z", "updated_at": "2026-01-15T08:00:00Z", "hit_count": 1, "last_hit_at": "2026-03-10T10:05:00Z", "author": "security-team", "version": "1.0.0", "rego_snippet": "package opspilot.scope\ndefault deny = false\ndeny { input.vm_tags[_] == \"core-service\" }"},
    {"id": "POL-004", "name": "工具调用频率限制", "description": "单个 Agent 每分钟最多调用同一工具 10 次。", "type": "rate_limit", "status": "inactive", "effect": "deny", "scope": ["*"], "conditions": {"max_calls_per_minute": 10}, "created_at": "2026-03-20T00:00:00Z", "updated_at": "2026-04-01T09:00:00Z", "hit_count": 0, "last_hit_at": None, "author": "platform-team", "version": "0.9.0", "rego_snippet": None},
]

_POLICY_HITS = [
    {"id": "PHR-001", "policy_id": "POL-001", "policy_name": "高风险操作审批门控", "effect": "require_approval", "actor": "Orchestrator", "tool_name": "vmware.vm_migrate", "resource": "app-server-01", "outcome": "escalated", "timestamp": "2026-04-05T08:49:00Z", "trace_id": "trc-g1h2i3"},
    {"id": "PHR-002", "policy_id": "POL-003", "policy_name": "核心 VM 保护策略", "effect": "deny", "actor": "Orchestrator", "tool_name": "vmware.vm_power_off", "resource": "db-server-01", "outcome": "blocked", "timestamp": "2026-03-10T10:05:00Z", "trace_id": "trc-p1q2r3"},
]


@router.get("/policies")
async def list_policies(status: str | None = None):
    data = _POLICIES if not status else [p for p in _POLICIES if p["status"] == status]
    return make_success({"items": data, "total": len(data)})


@router.get("/policies/{policy_id}")
async def get_policy(policy_id: str):
    item = next((p for p in _POLICIES if p["id"] == policy_id), None)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Policy not found")
    return make_success(item)


@router.get("/policies/{policy_id}/hits")
async def get_policy_hits(policy_id: str):
    hits = [h for h in _POLICY_HITS if h["policy_id"] == policy_id]
    return make_success({"items": hits, "total": len(hits)})


@router.patch("/policies/{policy_id}/toggle")
async def toggle_policy(policy_id: str):
    return make_success({"id": policy_id, "status": "toggled"})


@router.post("/policies/simulate")
async def simulate_policy(context: dict):
    """Proxy policy simulation to governance evaluate endpoint."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GOVERNANCE_SERVICE_URL.rstrip('/')}/policies/evaluate",
                json=context,
            )
        data = resp.json()
        if isinstance(data, dict) and all(k in data for k in ("request_id", "success", "message", "timestamp")):
            return data
        if resp.is_success:
            return make_success(data)
        return make_error(f"governance simulate failed: status={resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        return make_error(f"governance simulate unreachable: {exc}")
