"""BFF router: Agent runs."""
from __future__ import annotations
from fastapi import APIRouter
from opspilot_schema.envelope import make_success

router = APIRouter(tags=["agent-runs"])

_RUNS = [
    {"id": "RUN-001", "intent": "diagnose_incident", "status": "completed", "trigger": "alert", "incident_ref": "INC-20260405-001", "session_ref": "sess-001", "steps": [{"step_id": "s1", "agent_name": "IntentAgent", "status": "done", "input_summary": "alert: esxi-node03 CPU > 95%", "output_summary": '{"intent":"diagnose_incident"}', "tool_calls": 0, "started_at": "2026-04-05T08:12:05Z", "completed_at": "2026-04-05T08:12:06Z", "duration_ms": 380, "error": None}, {"step_id": "s2", "agent_name": "EvidenceCollectionAgent", "status": "done", "input_summary": '{"host":"esxi-node03"}', "output_summary": "collected 4 evidence items", "tool_calls": 3, "started_at": "2026-04-05T08:12:10Z", "completed_at": "2026-04-05T08:15:00Z", "duration_ms": 2870, "error": None}, {"step_id": "s3", "agent_name": "KBRetrievalAgent", "status": "done", "input_summary": '{"query":"java gc cpu"}', "output_summary": "retrieved KB-001", "tool_calls": 1, "started_at": "2026-04-05T08:15:00Z", "completed_at": "2026-04-05T08:15:30Z", "duration_ms": 480, "error": None}, {"step_id": "s4", "agent_name": "RCAAgent", "status": "done", "input_summary": '{"evidence_refs":["evd-001","evd-002"]}', "output_summary": "2 root cause candidates", "tool_calls": 0, "started_at": "2026-04-05T08:15:30Z", "completed_at": "2026-04-05T08:16:00Z", "duration_ms": 510, "error": None}, {"step_id": "s5", "agent_name": "NotificationAgent", "status": "done", "input_summary": '{"recipients":["zhangsan"]}', "output_summary": "delivered to 1 recipient", "tool_calls": 1, "started_at": "2026-04-05T08:16:00Z", "completed_at": "2026-04-05T08:16:30Z", "duration_ms": 320, "error": None}], "total_tool_calls": 5, "total_duration_ms": 4560, "started_at": "2026-04-05T08:12:05Z", "completed_at": "2026-04-05T08:16:30Z", "output_summary": "诊断完成：2 个根因候选，已发送值班通知。", "error": None},
    {"id": "RUN-002", "intent": "analyze_change_impact", "status": "completed", "trigger": "user", "incident_ref": "INC-20260405-001", "session_ref": "sess-001", "steps": [{"step_id": "s1", "agent_name": "IntentAgent", "status": "done", "input_summary": "user: 分析迁移 app-server-01 的影响", "output_summary": '{"intent":"analyze_change_impact"}', "tool_calls": 0, "started_at": "2026-04-05T08:25:05Z", "completed_at": "2026-04-05T08:25:06Z", "duration_ms": 210, "error": None}, {"step_id": "s2", "agent_name": "ChangeCorrelationAgent", "status": "done", "input_summary": '{"target":"vm-201","action":"vm_migrate"}', "output_summary": "risk_score: 45, 3 impacted objects", "tool_calls": 1, "started_at": "2026-04-05T08:25:06Z", "completed_at": "2026-04-05T08:25:30Z", "duration_ms": 520, "error": None}], "total_tool_calls": 1, "total_duration_ms": 730, "started_at": "2026-04-05T08:25:05Z", "completed_at": "2026-04-05T08:25:30Z", "output_summary": "变更影响分析完成，风险等级：中。", "error": None},
    {"id": "RUN-003", "intent": "diagnose_incident", "status": "running", "trigger": "alert", "incident_ref": "INC-20260405-002", "session_ref": None, "steps": [{"step_id": "s1", "agent_name": "IntentAgent", "status": "done", "input_summary": "alert: ds-nfs-prod01 capacity < 10%", "output_summary": '{"intent":"diagnose_incident"}', "tool_calls": 0, "started_at": "2026-04-05T07:30:35Z", "completed_at": "2026-04-05T07:30:36Z", "duration_ms": 190, "error": None}, {"step_id": "s2", "agent_name": "EvidenceCollectionAgent", "status": "done", "input_summary": '{"datastore":"ds-45"}', "output_summary": "collected 1 evidence item", "tool_calls": 2, "started_at": "2026-04-05T07:30:36Z", "completed_at": "2026-04-05T07:31:00Z", "duration_ms": 850, "error": None}, {"step_id": "s3", "agent_name": "RCAAgent", "status": "running", "input_summary": '{"evidence_refs":["evd-005"]}', "output_summary": None, "tool_calls": 0, "started_at": "2026-04-05T07:31:00Z", "completed_at": None, "duration_ms": None, "error": None}], "total_tool_calls": 2, "total_duration_ms": None, "started_at": "2026-04-05T07:30:35Z", "completed_at": None, "output_summary": None, "error": None},
]


@router.get("/agent-runs")
async def list_agent_runs(status: str | None = None, incident_ref: str | None = None):
    data = _RUNS
    if status:
        data = [r for r in data if r["status"] == status]
    if incident_ref:
        data = [r for r in data if r.get("incident_ref") == incident_ref]
    return make_success({"items": data, "total": len(data)})


@router.get("/agent-runs/{run_id}")
async def get_agent_run(run_id: str):
    item = next((r for r in _RUNS if r["id"] == run_id), None)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Agent run not found")
    return make_success(item)
