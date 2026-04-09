"""Chat session endpoints - proxy to orchestrator with in-memory session store."""
from __future__ import annotations

import asyncio
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.chat_exports import get_export
from opspilot_schema.envelope import make_error, make_success

router = APIRouter(prefix="/chat", tags=["chat"])

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8010")
RESOURCE_BFF_URL = os.environ.get("RESOURCE_BFF_URL", "http://127.0.0.1:8000")
VCENTER_PROD_VM_QUERY_KEYWORDS = re.compile(
    r"(vcenter|vsphere).*(\u751f\u4ea7|prod).*(\u865a\u62df\u673a|vm).*(\u591a\u5c11|\u6570\u91cf|count)"
    r"|(\u751f\u4ea7|prod).*(vcenter|vsphere).*(\u865a\u62df\u673a|vm).*(\u591a\u5c11|\u6570\u91cf|count)",
    re.I,
)
VCENTER_PROD_VM_EXPORT_QUERY_KEYWORDS = re.compile(
    r"(vcenter|vsphere).*(\u751f\u4ea7|prod).*(\u865a\u62df\u673a|vm).*(\u5217\u8868|list).*(\u5bfc\u51fa|export)"
    r"|(\u5bfc\u51fa|export).*(vcenter|vsphere).*(\u751f\u4ea7|prod).*(\u865a\u62df\u673a|vm).*(\u5217\u8868|list)",
    re.I,
)
CONFIRM_KEYWORDS = re.compile(r"^(\u786e\u8ba4|\u662f|\u7ee7\u7eed|\u67e5\u8be2|ok|yes)$", re.I)
DIAGNOSIS_KEYWORDS = re.compile(
    r"\u5206\u6790|\u8bca\u65ad|\u6392\u67e5|\u544a\u8b66|\u6839\u56e0|\u5f02\u5e38|\u6545\u969c|\u6392\u969c|\u4e3a\u4ec0\u4e48|\u539f\u56e0|\u68c0\u67e5",
    re.I,
)
PENDING_INTENT = "resource_query_vcenter_prod_vm_count"
EXPORT_COLUMN_ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "name": ("name",),
    "名称": ("name",),
    "vm name": ("name",),
    "ip": ("ip_address",),
    "ip地址": ("ip_address",),
    "ip address": ("ip_address",),
    "host": ("host_name",),
    "host name": ("host_name",),
    "esxi": ("host_name",),
    "所在esxi主机名": ("host_name",),
    "cpu": ("cpu_count",),
    "cpu核数": ("cpu_count",),
    "cpu数量": ("cpu_count",),
    "内存": ("memory_mb",),
    "memory": ("memory_mb",),
    "存储": ("provisioned_gb", "used_gb"),
    "storage": ("provisioned_gb", "used_gb"),
    "datastore": ("datastore_names",),
    "关联的datastore": ("datastore_names",),
    "关联datastore": ("datastore_names",),
}
SUPPORTED_EXPORT_COLUMNS = {
    "name",
    "ip_address",
    "host_name",
    "cpu_count",
    "memory_mb",
    "provisioned_gb",
    "used_gb",
    "datastore_names",
}
DEFAULT_VM_EXPORT_COLUMNS = ["vm_id", "name", "power_state"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_vcenter_prod_vm_query(message: str) -> bool:
    lowered = message.lower()
    has_platform = any(k in lowered for k in ("vcenter", "vsphere"))
    has_env = any(k in message for k in ("生产", "prod"))
    has_vm = any(k in message for k in ("虚拟机", "vm"))
    has_count = any(k in message for k in ("多少", "数量", "count"))
    return has_platform and has_env and has_vm and has_count


def _is_vcenter_prod_vm_export_query(message: str) -> bool:
    lowered = message.lower()
    has_platform = any(k in lowered for k in ("vcenter", "vsphere"))
    has_env = any(k in message for k in ("生产", "prod"))
    has_vm = any(k in message for k in ("虚拟机", "vm"))
    has_list = any(k in message for k in ("列表", "list"))
    has_export = any(k in message for k in ("导出", "export"))
    return has_platform and has_env and has_vm and has_list and has_export


def _is_confirmation(message: str) -> bool:
    return bool(CONFIRM_KEYWORDS.search(message.strip()))


async def _query_vcenter_prod_inventory() -> dict | None:
    url = (
        f"{RESOURCE_BFF_URL.rstrip('/')}/api/v1/resources/vcenter/inventory"
        "?connection_id=conn-vcenter-prod"
    )
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.get(url)
        body = resp.json()
        if not body.get("success"):
            return None
        return body.get("data", {})
    except Exception:
        return None


def _normalize_requested_columns(message: str) -> tuple[list[str], list[str]]:
    lowered = message.lower().strip()
    segment = message.strip()
    marker_positions = []
    for marker in ("包括", "包含", "字段", "列", "with", "include"):
        idx = lowered.find(marker)
        if idx >= 0:
            marker_positions.append(idx + len(marker))
    if marker_positions:
        segment = message[min(marker_positions):]

    raw_tokens = [t.strip() for t in re.split(r"[，,、;；\n]+", segment) if t.strip()]
    requested: list[str] = []
    ignored: list[str] = []
    seen: set[str] = set()

    for token in raw_tokens:
        normalized = token.lower().strip()
        mapped: tuple[str, ...] = ()
        for alias, columns in sorted(EXPORT_COLUMN_ALIAS_MAP.items(), key=lambda kv: len(kv[0]), reverse=True):
            if alias in token or alias in normalized:
                mapped = columns
                break
        if not mapped:
            if any(ch.isalnum() for ch in token) or re.search(r"[\u4e00-\u9fff]", token):
                ignored.append(token)
            continue
        for col in mapped:
            if col in SUPPORTED_EXPORT_COLUMNS and col not in seen:
                requested.append(col)
                seen.add(col)

    return requested, ignored


async def _export_vcenter_prod_vm_inventory(
    session_id: str | None = None,
    requested_columns: list[str] | None = None,
) -> dict | None:
    url = f"{RESOURCE_BFF_URL.rstrip('/')}/api/v1/resources/vcenter/inventory/export"
    payload = {
        "connection_id": "conn-vcenter-prod",
        "format": "csv",
        "session_id": session_id,
        "requested_columns": requested_columns or DEFAULT_VM_EXPORT_COLUMNS,
    }
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(url, json=payload)
        body = resp.json()
        if not body.get("success"):
            return None
        return body.get("data", {})
    except Exception:
        return None


def _format_vcenter_summary(inventory: dict) -> str:
    summary = inventory.get("summary", {})
    vm_count = summary.get("vm_count", 0)
    host_count = summary.get("host_count", 0)
    cluster_count = summary.get("cluster_count", 0)
    powered_off = summary.get("powered_off_vm_count", "N/A")
    unhealthy_hosts = summary.get("unhealthy_host_count", "N/A")

    status_line = "当前资源状态整体健康。"
    if (isinstance(powered_off, int) and powered_off > 0) or (
        isinstance(unhealthy_hosts, int) and unhealthy_hosts > 0
    ):
        status_line = "当前资源状态存在异常，建议优先检查异常对象。"

    return (
        "vCenter 生产环境（目标连接=conn-vcenter-prod）资源查询结果：\n\n"
        f"- VM总数：{vm_count}\n"
        f"- 主机数量：{host_count}\n"
        f"- 集群数量：{cluster_count}\n"
        f"- 关机虚拟机数量：{powered_off}\n"
        f"- 非健康主机数量：{unhealthy_hosts}\n\n"
        f"{status_line}"
    )


def _reasoning_summary(intent_understanding: str, execution_plan: str, result_summary: str) -> dict[str, str]:
    return {
        "intent_understanding": intent_understanding,
        "execution_plan": execution_plan,
        "result_summary": result_summary,
    }


def _predict_agent_and_plan(message: str) -> tuple[str, str]:
    if _is_vcenter_prod_vm_export_query(message) or _is_vcenter_prod_vm_query(message):
        return "ResourceQueryAgent", "识别资源查询/导出意图并调用 vCenter 资源接口"
    if DIAGNOSIS_KEYWORDS.search(message):
        return "RCAAgent", "收集证据并执行诊断分析"
    return "Orchestrator", "执行通用问答"


_sessions: dict[str, dict] = {}
_messages: dict[str, list[dict]] = defaultdict(list)
_evidences: dict[str, list[dict]] = defaultdict(list)
_tool_traces: dict[str, list[dict]] = defaultdict(list)
_diagnoses: dict[str, dict] = {}
_pending_intents: dict[str, str] = {}
_message_tasks: dict[str, asyncio.Task] = {}
_state_lock = asyncio.Lock()


class CreateSessionBody(BaseModel):
    title: str | None = None


class SendMessageBody(BaseModel):
    message: str


def _find_message(session_id: str, message_id: str) -> dict[str, Any] | None:
    for msg in _messages.get(session_id, []):
        if msg.get("id") == message_id:
            return msg
    return None


def _append_progress_event(
    message: dict[str, Any],
    stage: str,
    text: str,
    status: str,
    tool_name: str | None = None,
    agent_name: str | None = None,
) -> None:
    events = message.setdefault("progress_events", [])
    events.append(
        {
            "stage": stage,
            "text": text,
            "ts": _now(),
            "status": status,
            "tool_name": tool_name,
            "agent_name": agent_name,
        }
    )


async def _run_orchestrator(session_id: str, message: str, history: list[dict]) -> dict | None:
    async with httpx.AsyncClient(timeout=600) as client:
        try:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/api/v1/orchestrate/chat",
                json={"session_id": session_id, "message": message, "history": history},
            )
            payload = resp.json()
            if not payload.get("success"):
                return None
            return payload.get("data")
        except Exception:
            return None


async def _build_fallback_data(session_id: str, message: str) -> dict[str, Any]:
    pending = _pending_intents.get(session_id) == PENDING_INTENT
    is_query = _is_vcenter_prod_vm_query(message)
    is_export_query = _is_vcenter_prod_vm_export_query(message)
    is_confirm = _is_confirmation(message)

    if is_export_query:
        requested_columns, ignored_columns = _normalize_requested_columns(message)
        effective_columns = requested_columns or DEFAULT_VM_EXPORT_COLUMNS
        export_data = await _export_vcenter_prod_vm_inventory(session_id, effective_columns)
        if not export_data:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": "触发导出任务失败：无法导出 conn-vcenter-prod 的虚拟机列表，请稍后重试。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户希望导出 vCenter 生产环境虚拟机列表。",
                    "识别导出意图后调用导出接口。",
                    "导出失败，请稍后重试。",
                ),
            }

        actual_columns = export_data.get("export_columns", effective_columns)
        actual_ignored = export_data.get("ignored_columns", ignored_columns)
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": (
                "已触发 vCenter 生产环境（conn-vcenter-prod）虚拟机列表导出任务，可在下方下载文件。\n"
                f"已导出列：{','.join(actual_columns)}"
                + (f"\n已忽略列：{','.join(actual_ignored)}" if actual_ignored else "")
            ),
            "agent_name": "ResourceQueryAgent",
            "tool_traces": [
                {
                    "tool_name": "vmware.export_vcenter_vm_list",
                    "gateway": "api-bff",
                    "input_summary": (
                        '{"connection_id":"conn-vcenter-prod","format":"csv",'
                        f'"requested_columns":"{",".join(actual_columns)}"'
                        "}"
                    ),
                    "output_summary": export_data.get("file_name", "vm-list.csv"),
                    "duration_ms": 0,
                    "status": "success",
                    "timestamp": _now(),
                }
            ],
            "evidence_refs": [],
            "evidences": [],
            "export_file": export_data,
            "export_columns": actual_columns,
            "ignored_columns": actual_ignored,
            "reasoning_summary": _reasoning_summary(
                "用户希望导出 vCenter 生产环境虚拟机列表。",
                "识别导出意图并调用导出接口。",
                "导出任务已创建并返回下载入口。",
            ),
        }

    if (pending and is_confirm) or (is_query and is_confirm):
        _pending_intents.pop(session_id, None)
        inventory = await _query_vcenter_prod_inventory()
        if not inventory:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": "已收到确认，但查询 conn-vcenter-prod 失败，请稍后重试。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户确认查询 vCenter 生产环境资源。",
                    "调用 inventory 接口获取资源状态。",
                    "查询失败，请稍后重试。",
                ),
            }

        summary = inventory.get("summary", {})
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": _format_vcenter_summary(inventory),
            "agent_name": "ResourceQueryAgent",
            "tool_traces": [
                {
                    "tool_name": "vmware.get_vcenter_inventory",
                    "gateway": "vmware-skill-gateway",
                    "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                    "output_summary": (
                        f"clusters={summary.get('cluster_count', 0)}, "
                        f"hosts={summary.get('host_count', 0)}, "
                        f"vms={summary.get('vm_count', 0)}"
                    ),
                    "duration_ms": 0,
                    "status": "success",
                    "timestamp": _now(),
                }
            ],
            "evidence_refs": [],
            "evidences": [],
            "reasoning_summary": _reasoning_summary(
                "用户希望获取 vCenter 生产环境资源概览。",
                "调用 inventory 接口并汇总关键指标。",
                "已返回 VM/主机/集群与健康摘要。",
            ),
        }

    if is_query:
        _pending_intents[session_id] = PENDING_INTENT
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": "检测到你在查询 vCenter 生产环境资源。是否确认查询 目标连接=conn-vcenter-prod？回复“确认”继续。",
            "agent_name": "ResourceQueryAgent",
            "tool_traces": [],
            "evidence_refs": [],
            "evidences": [],
            "reasoning_summary": _reasoning_summary(
                "用户希望查询 vCenter 生产环境资源。",
                "命中资源查询意图并进入确认门禁。",
                "等待用户确认后继续执行。",
            ),
        }

    is_diag = bool(DIAGNOSIS_KEYWORDS.search(message))
    return {
        "message_id": f"msg-{uuid.uuid4().hex[:10]}",
        "assistant_message": f"[本地模式] 收到：{message}",
        "agent_name": "RCAAgent" if is_diag else "Orchestrator",
        "tool_traces": [
            {
                "tool_name": "vmware.get_host_detail",
                "gateway": "vmware-skill-gateway",
                "input_summary": '{"host_id":"host-33"}',
                "output_summary": "CPU: 97.3%",
                "duration_ms": 320,
                "status": "success",
                "timestamp": _now(),
            }
        ]
        if is_diag
        else [],
        "evidence_refs": ["ev-fallback-1"] if is_diag else [],
        "evidences": [
            {
                "evidence_id": "ev-fallback-1",
                "source_type": "metric",
                "summary": "CPU 97.3% (fallback)",
                "confidence": 0.9,
                "timestamp": _now(),
            }
        ]
        if is_diag
        else [],
        "root_cause_candidates": [
            {"description": "Fallback diagnosis", "confidence": 0.85, "category": "unknown"}
        ]
        if is_diag
        else None,
        "recommended_actions": ["检查主机指标"] if is_diag else None,
        "diagnosis_id": f"dg-{uuid.uuid4().hex[:12]}" if is_diag else None,
        "reasoning_summary": _reasoning_summary(
            "用户提出了运维问答或诊断请求。",
            "根据关键词选择本地 fallback 路径。",
            "已返回 fallback 结果。",
        ),
    }


async def _process_message(session_id: str, assistant_id: str, user_message: str) -> None:
    try:
        async with _state_lock:
            target = _find_message(session_id, assistant_id)
            if not target:
                return
            _append_progress_event(target, "tool_invoking", "正在调用 Orchestrator 执行任务", "in_progress")
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in _messages[session_id]
                if m.get("role") in ("user", "assistant") and m.get("id") != assistant_id
            ]

        data = await _run_orchestrator(session_id, user_message, history)
        if not data:
            data = await _build_fallback_data(session_id, user_message)

        async with _state_lock:
            target = _find_message(session_id, assistant_id)
            if not target:
                return

            target["content"] = data.get("assistant_message", "")
            target["agent_name"] = data.get("agent_name")
            target["tool_traces"] = data.get("tool_traces", [])
            target["evidence_refs"] = data.get("evidence_refs", [])
            target["root_cause_candidates"] = data.get("root_cause_candidates")
            target["recommended_actions"] = data.get("recommended_actions")
            target["diagnosis_id"] = data.get("diagnosis_id")
            target["export_file"] = data.get("export_file")
            target["export_columns"] = data.get("export_columns")
            target["ignored_columns"] = data.get("ignored_columns")
            target["reasoning_summary"] = data.get("reasoning_summary") or _reasoning_summary(
                "系统已理解并执行用户请求。",
                "调用匹配的 Agent 与工具完成处理。",
                "已返回最终结果。",
            )
            target["status"] = "completed"
            _append_progress_event(target, "tool_done", "工具调用完成", "success")
            _append_progress_event(target, "completed", "任务执行完成", "success")

            for ev in data.get("evidences", []):
                if not any(e["evidence_id"] == ev["evidence_id"] for e in _evidences[session_id]):
                    _evidences[session_id].append(ev)

            for tt in data.get("tool_traces", []):
                _tool_traces[session_id].append(tt)

            diag_id = data.get("diagnosis_id")
            if diag_id:
                _diagnoses[diag_id] = {
                    "diagnosis_id": diag_id,
                    "session_id": session_id,
                    "description": user_message,
                    "assistant_message": data.get("assistant_message", ""),
                    "root_cause_candidates": data.get("root_cause_candidates", []),
                    "evidence_refs": data.get("evidence_refs", []),
                    "evidences": data.get("evidences", []),
                    "recommended_actions": data.get("recommended_actions", []),
                    "tool_traces": data.get("tool_traces", []),
                    "created_at": _now(),
                }

            _sessions[session_id]["updated_at"] = _now()
            _sessions[session_id]["message_count"] = len(_messages[session_id])
    except Exception as exc:
        async with _state_lock:
            target = _find_message(session_id, assistant_id)
            if target:
                target["status"] = "failed"
                target["content"] = f"任务执行失败：{exc}"
                target["reasoning_summary"] = _reasoning_summary(
                    "系统已识别用户请求。",
                    "执行过程中调用 Agent/工具处理。",
                    f"任务失败：{exc}",
                )
                _append_progress_event(target, "tool_error", "工具调用失败", "error")
                _append_progress_event(target, "failed", "任务执行失败", "error")
            _sessions[session_id]["updated_at"] = _now()
    finally:
        _message_tasks.pop(assistant_id, None)


@router.get("/sessions")
async def list_sessions():
    sessions = sorted(_sessions.values(), key=lambda s: s["updated_at"], reverse=True)
    return make_success(sessions)


@router.post("/sessions")
async def create_session(body: CreateSessionBody):
    sid = f"sess-{uuid.uuid4().hex[:8]}"
    now = _now()
    session = {
        "id": sid,
        "title": body.title or "新会话",
        "created_at": now,
        "updated_at": now,
        "tags": [],
        "message_count": 0,
    }
    _sessions[sid] = session
    return make_success(session)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        return make_success({
            "id": session_id,
            "title": "未知会话",
            "message_count": 0,
        })
    return make_success(session)


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    return make_success(_messages.get(session_id, []))


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: SendMessageBody):
    if session_id not in _sessions:
        now = _now()
        _sessions[session_id] = {
            "id": session_id,
            "title": body.message[:30],
            "created_at": now,
            "updated_at": now,
            "tags": [],
            "message_count": 0,
        }

    agent_name, execution_plan = _predict_agent_and_plan(body.message)

    async with _state_lock:
        user_msg = {
            "id": f"msg-{uuid.uuid4().hex[:10]}",
            "session_id": session_id,
            "role": "user",
            "content": body.message,
            "timestamp": _now(),
        }
        _messages[session_id].append(user_msg)

        assistant_id = f"msg-{uuid.uuid4().hex[:10]}"
        assistant_msg: dict[str, Any] = {
            "id": assistant_id,
            "session_id": session_id,
            "role": "assistant",
            "content": "已收到请求，正在分析意图并准备执行。",
            "timestamp": _now(),
            "agent_name": agent_name,
            "tool_traces": [],
            "evidence_refs": [],
            "status": "in_progress",
            "progress_events": [],
            "reasoning_summary": _reasoning_summary(
                f"已接收用户请求：{body.message[:80]}",
                execution_plan,
                "任务执行中，结果稍后返回。",
            ),
        }
        _append_progress_event(assistant_msg, "received", "已接收用户输入", "success", agent_name=agent_name)
        _append_progress_event(assistant_msg, "intent_parsed", "已完成意图识别", "success", agent_name=agent_name)
        _append_progress_event(assistant_msg, "agent_selected", f"已选择 {agent_name}", "success", agent_name=agent_name)
        _messages[session_id].append(assistant_msg)

        _sessions[session_id]["updated_at"] = _now()
        _sessions[session_id]["message_count"] = len(_messages[session_id])
        if _sessions[session_id]["title"] in {"新会话", body.message[:30]}:
            _sessions[session_id]["title"] = body.message[:30]

    task = asyncio.create_task(_process_message(session_id, assistant_id, body.message))
    _message_tasks[assistant_id] = task

    return make_success(assistant_msg)


@router.get("/sessions/{session_id}/evidence")
async def get_session_evidence(session_id: str):
    return make_success(_evidences.get(session_id, []))


@router.get("/sessions/{session_id}/tool-traces")
async def get_session_traces(session_id: str):
    return make_success(_tool_traces.get(session_id, []))


@router.get("/diagnoses/{diagnosis_id}")
async def get_diagnosis(diagnosis_id: str):
    diag = _diagnoses.get(diagnosis_id)
    if not diag:
        return make_error(f"Diagnosis {diagnosis_id} not found")
    return make_success(diag)


@router.get("/exports/{export_id}/download")
async def download_export_file(export_id: str):
    rec = get_export(export_id)
    if not rec:
        return make_error("导出文件不存在或已过期")
    if not rec.file_path.exists():
        return make_error("导出文件不存在或已被清理")
    return FileResponse(
        path=rec.file_path,
        media_type=rec.mime_type,
        filename=rec.file_name,
    )
