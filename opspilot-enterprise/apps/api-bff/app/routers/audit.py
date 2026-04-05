"""BFF router: Audit logs."""
from __future__ import annotations
from fastapi import APIRouter
from opspilot_schema.envelope import make_success

router = APIRouter(tags=["audit"])

_AUDIT_LOGS = [
    {"id": "AUD-001", "event_type": "tool_invoked", "severity": "info", "actor": "EvidenceCollectionAgent", "actor_type": "agent", "action": "vmware.get_host_detail", "resource_type": "HostSystem", "resource_id": "host-33", "resource_name": "esxi-node03", "outcome": "success", "reason": None, "incident_ref": "INC-20260405-001", "request_id": "req-a1b2c3", "trace_id": "trc-x1y2z3", "timestamp": "2026-04-05T08:20:06Z", "metadata": {"duration_ms": 320}},
    {"id": "AUD-002", "event_type": "approval_created", "severity": "info", "actor": "zhangsan", "actor_type": "human", "action": "create_approval", "resource_type": "ApprovalRequest", "resource_id": "APR-20260405-001", "resource_name": "迁移 app-server-01", "outcome": "success", "reason": None, "incident_ref": "INC-20260405-001", "request_id": "req-d4e5f6", "trace_id": "trc-a4b5c6", "timestamp": "2026-04-05T08:50:00Z", "metadata": {"risk_score": 45}},
    {"id": "AUD-003", "event_type": "approval_decided", "severity": "info", "actor": "ops-lead", "actor_type": "human", "action": "approve", "resource_type": "ApprovalRequest", "resource_id": "APR-20260405-002", "resource_name": "清理 ds-nfs-prod01 快照", "outcome": "success", "reason": "已确认快照列表，允许清理", "incident_ref": "INC-20260405-002", "request_id": "req-g7h8i9", "trace_id": "trc-d7e8f9", "timestamp": "2026-04-05T08:10:00Z", "metadata": {}},
    {"id": "AUD-004", "event_type": "policy_hit", "severity": "warning", "actor": "Orchestrator", "actor_type": "agent", "action": "vmware.vm_migrate", "resource_type": "VirtualMachine", "resource_id": "vm-201", "resource_name": "app-server-01", "outcome": "blocked", "reason": "风险评分超过无审批执行阈值，已转入审批队列", "incident_ref": "INC-20260405-001", "request_id": "req-j1k2l3", "trace_id": "trc-g1h2i3", "timestamp": "2026-04-05T08:49:00Z", "metadata": {"policy_id": "POL-001", "risk_score": 45}},
    {"id": "AUD-005", "event_type": "execution_completed", "severity": "info", "actor": "Orchestrator", "actor_type": "agent", "action": "snapshot_delete_batch", "resource_type": "Datastore", "resource_id": "ds-45", "resource_name": "ds-nfs-prod01", "outcome": "success", "reason": None, "incident_ref": "INC-20260405-002", "request_id": "req-m4n5o6", "trace_id": "trc-j4k5l6", "timestamp": "2026-04-05T08:20:00Z", "metadata": {"snapshots_deleted": 14, "space_freed_gb": 820}},
]


@router.get("/audit/logs")
async def list_audit_logs(
    severity: str | None = None,
    event_type: str | None = None,
    actor_type: str | None = None,
    limit: int = 50,
):
    data = _AUDIT_LOGS
    if severity:
        data = [l for l in data if l["severity"] == severity]
    if event_type:
        data = [l for l in data if l["event_type"] == event_type]
    if actor_type:
        data = [l for l in data if l["actor_type"] == actor_type]
    return make_success({"items": data[:limit], "total": len(data)})


@router.get("/audit/logs/{log_id}")
async def get_audit_log(log_id: str):
    item = next((l for l in _AUDIT_LOGS if l["id"] == log_id), None)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Audit log not found")
    return make_success(item)
