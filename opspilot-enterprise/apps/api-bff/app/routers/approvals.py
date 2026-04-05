"""BFF router: Approvals."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from opspilot_schema.envelope import make_success

router = APIRouter(tags=["approvals"])

_APPROVALS = [
    {"id": "APR-20260405-001", "title": "迁移 app-server-01 到 esxi-node04", "action_type": "vm_migrate", "risk_level": "medium", "risk_score": 45, "status": "pending", "requester": "zhangsan", "assignee": "ops-lead", "incident_ref": "INC-20260405-001", "change_analysis_ref": "cia-001", "target_object": "app-server-01", "target_object_type": "VirtualMachine", "created_at": "2026-04-05T08:50:00Z", "updated_at": "2026-04-05T08:50:00Z", "expires_at": "2026-04-05T10:50:00Z", "decision_comment": None, "decided_at": None, "decided_by": None, "tags": ["vmware", "migration"], "description": "因 esxi-node03 CPU 告警，需将 app-server-01 迁移至 esxi-node04。"},
    {"id": "APR-20260405-002", "title": "清理 ds-nfs-prod01 过期快照", "action_type": "snapshot_delete", "risk_level": "low", "risk_score": 18, "status": "approved", "requester": "lisi", "assignee": "ops-lead", "incident_ref": "INC-20260405-002", "change_analysis_ref": None, "target_object": "ds-nfs-prod01", "target_object_type": "Datastore", "created_at": "2026-04-05T07:45:00Z", "updated_at": "2026-04-05T08:10:00Z", "expires_at": None, "decision_comment": "已确认快照列表，允许清理。", "decided_at": "2026-04-05T08:10:00Z", "decided_by": "ops-lead", "tags": ["capacity"], "description": "快照堆积导致容量告警，需批量删除 7 天前快照。"},
    {"id": "APR-20260404-005", "title": "升级 esxi-node01 网卡固件至 v3.11", "action_type": "config_change", "risk_level": "high", "risk_score": 72, "status": "rejected", "requester": "wangwu", "assignee": "ops-lead", "incident_ref": "INC-20260404-005", "change_analysis_ref": None, "target_object": "esxi-node01", "target_object_type": "HostSystem", "created_at": "2026-04-04T14:00:00Z", "updated_at": "2026-04-04T15:30:00Z", "expires_at": None, "decision_comment": "风险过高，需先在测试环境验证。", "decided_at": "2026-04-04T15:30:00Z", "decided_by": "ops-lead", "tags": ["hardware"], "description": "vmnic2 链路中断疑似固件 Bug，需升级网卡固件。"},
]


@router.get("/approvals")
async def list_approvals(status: str | None = None):
    data = _APPROVALS if not status else [a for a in _APPROVALS if a["status"] == status]
    return make_success({"items": data, "total": len(data)})


@router.get("/approvals/{approval_id}")
async def get_approval(approval_id: str):
    item = next((a for a in _APPROVALS if a["id"] == approval_id), None)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Approval not found")
    return make_success(item)


@router.post("/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, decision: dict):
    return make_success({
        "request_id": approval_id,
        "decision": decision.get("decision", "approved"),
        "decided_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "decided_by": decision.get("decided_by", "ops-lead"),
        "audit_ref": f"AUD-{uuid.uuid4().hex[:6].upper()}",
    })
