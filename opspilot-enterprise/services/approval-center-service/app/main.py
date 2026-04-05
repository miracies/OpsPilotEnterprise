"""OpsPilot Approval Center Service - handles approval requests and notifications."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opspilot_schema.envelope import make_success
from opspilot_schema.approval import ApprovalRequest, ApprovalDecision
from opspilot_schema.notification import NotificationItem

app = FastAPI(title="OpsPilot Approval Center Service", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STORE: dict[str, dict] = {
    "APR-20260405-001": {"id": "APR-20260405-001", "title": "迁移 app-server-01 到 esxi-node04", "action_type": "vm_migrate", "risk_level": "medium", "risk_score": 45, "status": "pending", "requester": "zhangsan", "assignee": "ops-lead", "incident_ref": "INC-20260405-001", "target_object": "app-server-01", "target_object_type": "VirtualMachine", "created_at": "2026-04-05T08:50:00Z", "updated_at": "2026-04-05T08:50:00Z", "expires_at": "2026-04-05T10:50:00Z", "decision_comment": None, "decided_at": None, "decided_by": None, "tags": ["vmware"], "description": "因 esxi-node03 CPU 告警，需将 app-server-01 迁移至 esxi-node04。", "change_analysis_ref": "cia-001"},
}


@app.get("/health")
async def health():
    return make_success({"status": "ok", "service": "approval-center-service"})


@app.get("/approvals")
async def list_approvals(status: Optional[str] = None):
    items = list(_STORE.values())
    if status:
        items = [i for i in items if i["status"] == status]
    return make_success({"items": items, "total": len(items)})


@app.get("/approvals/{approval_id}")
async def get_approval(approval_id: str):
    item = _STORE.get(approval_id)
    if not item:
        raise HTTPException(status_code=404, detail="Approval not found")
    return make_success(item)


@app.post("/approvals")
async def create_approval(body: dict):
    approval_id = f"APR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    item = {**body, "id": approval_id, "status": "pending", "created_at": datetime.utcnow().isoformat() + "Z", "updated_at": datetime.utcnow().isoformat() + "Z", "decision_comment": None, "decided_at": None, "decided_by": None}
    _STORE[approval_id] = item
    return make_success(item)


@app.post("/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, decision: dict):
    if approval_id not in _STORE:
        raise HTTPException(status_code=404, detail="Approval not found")
    _STORE[approval_id]["status"] = decision.get("decision", "approved")
    _STORE[approval_id]["decision_comment"] = decision.get("comment")
    _STORE[approval_id]["decided_at"] = datetime.utcnow().isoformat() + "Z"
    _STORE[approval_id]["decided_by"] = decision.get("decided_by", "system")
    _STORE[approval_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
    return make_success(_STORE[approval_id])


@app.get("/notifications")
async def list_notifications():
    return make_success({"items": [
        {"id": "NTF-001", "title": "【严重】esxi-node03 CPU 持续 >95%", "priority": "urgent", "status": "acknowledged", "incident_ref": "INC-20260405-001", "created_at": "2026-04-05T08:16:30Z"},
    ]})
