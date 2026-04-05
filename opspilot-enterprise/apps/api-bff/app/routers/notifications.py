"""BFF router: Notifications & On-call."""
from __future__ import annotations
from fastapi import APIRouter
from opspilot_schema.envelope import make_success

router = APIRouter(tags=["notifications"])

_NOTIFICATIONS = [
    {"id": "NTF-001", "title": "【严重】esxi-node03 CPU 持续 >95%", "content": "故障事件 INC-20260405-001 已触发，请立即处理。", "priority": "urgent", "status": "acknowledged", "incident_ref": "INC-20260405-001", "channels": ["dingtalk", "sms"], "recipients": ["zhangsan"], "created_at": "2026-04-05T08:16:30Z", "delivered_at": "2026-04-05T08:16:35Z", "acknowledged_at": "2026-04-05T08:45:00Z", "acknowledged_by": "zhangsan", "escalation_count": 0, "next_escalation_at": None},
    {"id": "NTF-002", "title": "【中】ds-nfs-prod01 容量告警", "content": "存储 ds-nfs-prod01 可用空间已低于 10%，请尽快处理。", "priority": "high", "status": "escalated", "incident_ref": "INC-20260405-002", "channels": ["dingtalk"], "recipients": ["lisi", "ops-team"], "created_at": "2026-04-05T07:30:30Z", "delivered_at": "2026-04-05T07:30:35Z", "acknowledged_at": None, "acknowledged_by": None, "escalation_count": 1, "next_escalation_at": "2026-04-05T09:30:00Z"},
    {"id": "NTF-003", "title": "【信息】INC-20260404-005 已解决", "content": "cluster-prod-az1 HA 切换故障已处理完毕。", "priority": "normal", "status": "acknowledged", "incident_ref": "INC-20260404-005", "channels": ["dingtalk"], "recipients": ["lisi", "ops-lead"], "created_at": "2026-04-05T01:30:00Z", "delivered_at": "2026-04-05T01:30:05Z", "acknowledged_at": "2026-04-05T01:31:00Z", "acknowledged_by": "lisi", "escalation_count": 0, "next_escalation_at": None},
    {"id": "NTF-004", "title": "【高】审批申请待处理（超时风险）", "content": "APR-20260405-001 已等待超过 1 小时。", "priority": "high", "status": "escalated", "incident_ref": None, "channels": ["wecom", "email"], "recipients": ["ops-lead"], "created_at": "2026-04-05T09:50:00Z", "delivered_at": "2026-04-05T09:50:05Z", "acknowledged_at": None, "acknowledged_by": None, "escalation_count": 2, "next_escalation_at": "2026-04-05T10:50:00Z"},
]

_ONCALL = [
    {"id": "shift-001", "name": "生产环境 4 月第一周值班", "team": "运维一组", "members": ["zhangsan", "lisi"], "start_at": "2026-04-04T08:00:00Z", "end_at": "2026-04-07T08:00:00Z", "active": True},
    {"id": "shift-002", "name": "生产环境 4 月第二周值班", "team": "运维二组", "members": ["wangwu", "zhaoliu"], "start_at": "2026-04-07T08:00:00Z", "end_at": "2026-04-14T08:00:00Z", "active": False},
]


@router.get("/notifications")
async def list_notifications(status: str | None = None):
    data = _NOTIFICATIONS if not status else [n for n in _NOTIFICATIONS if n["status"] == status]
    return make_success({"items": data, "total": len(data)})


@router.post("/notifications/{notification_id}/acknowledge")
async def acknowledge_notification(notification_id: str):
    return make_success({"id": notification_id, "status": "acknowledged"})


@router.get("/oncall/shifts")
async def list_oncall_shifts():
    return make_success({"items": _ONCALL})
