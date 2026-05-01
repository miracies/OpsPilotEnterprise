from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from opspilot_schema.envelope import make_error, make_success
from opspilot_schema.intent import IntentAnalyzeInput
from opspilot_schema.interaction import ApprovalCreateRequest, ClarifyCreateRequest, ResourceRef, ResourceScope
from opspilot_schema.policy_rule import RiskEvaluationInput
from opspilot_schema.resume import PlanStep

from app.audit.checkpoint import upsert_checkpoint
from app.audit.events import append_audit_event, list_audit_events
from app.intent_recovery.analyze_service import analyze_intent
from app.interactions.approve import create_approval
from app.interactions.clarify import create_clarify
from app.policy.engine import evaluate as evaluate_risk

router = APIRouter(tags=["orchestrator-v2"])
TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020").rstrip("/")
RESOURCE_BFF_URL = os.environ.get("RESOURCE_BFF_URL", "http://127.0.0.1:8000").rstrip("/")
BROADCOM_SEARCH_URL = "https://support.broadcom.com/web/ecx/search"
_WRITE_ACTIONS = {
    "vm_power",
    "service_restart",
    "scale_deployment",
    "restart_vm",
    "vm_guest_restart",
    "host_restart",
    "run_job",
}
_GENERIC_QA_RISK_KEYWORDS = re.compile(r"生产|影响|中断|丢包|故障|风险|宕机|抖动|失败|回退", re.I)
_GENERIC_QA_TERMS = {
    "vmotion": ["vMotion", "热迁移", "迁移", "虚拟机"],
    "热迁移": ["热迁移", "vMotion", "迁移", "虚拟机"],
    "esxi": ["ESXi", "主机", "VMware"],
    "overallstatus": ["overallStatus", "健康状态", "主机", "告警"],
    "deployment": ["deployment", "Kubernetes", "Pod", "重启"],
    "k8s": ["Kubernetes", "k8s", "Pod", "deployment"],
}
_EXPORT_COLUMN_ALIAS_MAP: dict[str, tuple[str, ...]] = {
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
_DEFAULT_VM_EXPORT_COLUMNS = ["vm_id", "name", "power_state"]


class ChatV2Request(BaseModel):
    session_id: str
    message: str
    history: list[dict[str, Any]] = Field(default_factory=list)
    user_id: str = "web-user"
    channel: str = "web"
    resource_catalog: list[dict[str, Any]] = Field(default_factory=list)
    ui_context: dict[str, Any] = Field(default_factory=dict)


class ChatV2Response(BaseModel):
    session_id: str
    message_id: str
    assistant_message: str
    agent_name: str = "OrchestratorV2"
    kind: str = "text"
    reasoning_summary: dict[str, str]
    intent_recovery: dict[str, Any] | None = None
    execution_intent: dict[str, Any] | None = None
    risk_context: dict[str, Any] | None = None
    memory_refs: list[str] = Field(default_factory=list)
    clarify_card: dict[str, Any] | None = None
    approval_card: dict[str, Any] | None = None
    resume_card: dict[str, Any] | None = None
    audit_timeline: dict[str, Any] | None = None
    diagnosis_id: str | None = None
    evidences: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    root_cause_candidates: list[dict[str, Any]] = Field(default_factory=list)
    analysis_steps: list[dict[str, Any]] = Field(default_factory=list)
    tool_traces: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _message_id() -> str:
    return f"msg-v2-{datetime.now(timezone.utc).strftime('%H%M%S%f')}"


def _reasoning(intent: str, plan: str, result: str) -> dict[str, str]:
    return {
        "intent_understanding": intent,
        "execution_plan": plan,
        "result_summary": result,
    }


def _target_name(run: dict[str, Any]) -> str:
    chosen = run.get("chosen_intent") or {}
    if chosen.get("target_object_resolved"):
        return str(chosen.get("target_object_resolved"))
    if chosen.get("target_object_raw"):
        return str(chosen.get("target_object_raw"))
    for slot in chosen.get("slots", []):
        if slot.get("name") == "target_object":
            return str(slot.get("value"))
    return "未指定目标"


def _resource_scope_from_run(run: dict[str, Any]) -> ResourceScope:
    chosen = run.get("chosen_intent") or {}
    environment = chosen.get("environment") or chosen.get("inferred_environment") or "prod"
    target_name = _target_name(run)
    if target_name == "未指定目标":
        return ResourceScope(environment=environment, resources=[])
    return ResourceScope(environment=environment, resources=[ResourceRef(type=chosen.get("domain") or "resource", id=target_name, name=target_name)])


def _plan_steps_for_run(run: dict[str, Any]) -> list[PlanStep]:
    chosen = run.get("chosen_intent") or {}
    action = chosen.get("action") or "unknown"
    target_name = _target_name(run)
    environment = chosen.get("environment") or chosen.get("inferred_environment") or "prod"
    return [
        PlanStep(seq=1, type="read", action="validate_context", args={"target": target_name, "environment": environment}),
        PlanStep(seq=2, type="write", action=str(action), args={"target": target_name, "environment": environment}),
    ]


def _slot_value(run: dict[str, Any], name: str) -> str | None:
    chosen = run.get("chosen_intent") or {}
    for slot in chosen.get("slots", []):
        if slot.get("name") == name and slot.get("value") not in (None, ""):
            return str(slot.get("value")).strip()
    return None


def _normalize_vmware_kb_query(run: dict[str, Any], raw_message: str) -> str:
    query_text = _slot_value(run, "query_text") or raw_message.strip()
    product = _slot_value(run, "product")
    version = _slot_value(run, "version")
    lower = query_text.lower()
    if product and product.lower() not in lower:
        query_text = f"{product} {query_text}".strip()
    if version and version not in query_text:
        query_text = f"{query_text} {version}".strip()
    if not re.search(r"\b(download|install|kb|article)\b", lower):
        query_text = f"{query_text} download".strip()
    return query_text


async def _invoke_vmware_kb_search(run: dict[str, Any], raw_message: str) -> tuple[dict[str, Any] | None, str | None]:
    query = _normalize_vmware_kb_query(run, raw_message)
    language = _slot_value(run, "language") or "en_US"
    payload = {
        "input": {
            "query": query,
            "segment": "VC",
            "language": language,
            "page_size": 5,
        },
        "dry_run": False,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{TOOL_GATEWAY_URL}/api/v1/invoke/vmware.kb_search", json=payload)
        body = resp.json()
    except Exception as exc:  # noqa: BLE001
        return None, f"kb_search request failed: {exc}"
    if not body.get("success"):
        return None, str(body.get("error") or "kb_search failed")
    data = body.get("data")
    if not isinstance(data, dict):
        return None, "kb_search returned empty payload"
    return data, None


def _format_kb_hit_message(query: str, search_url: str, items: list[dict[str, Any]]) -> tuple[str, list[str]]:
    top_items = [it for it in items if isinstance(it, dict) and it.get("url")][:3]
    refs = [str(it.get("url")) for it in top_items]
    lines = [
        "结论：可以通过 Broadcom Support Portal 获取 ESXi 9.0.3 相关下载与文档入口，建议优先参考以下官方来源。",
        "",
        "官方来源（Top3）：",
    ]
    if top_items:
        for idx, item in enumerate(top_items, 1):
            title = str(item.get("title") or f"官方文档 {idx}").strip()
            url = str(item.get("url")).strip()
            lines.append(f"{idx}. [{title}]({url})")
    else:
        lines.append(f"1. [Broadcom 搜索结果]({search_url})")
    lines.extend(
        [
            "",
            "下载路径建议（门户导航步骤）：",
            "1. 登录 Broadcom Support Portal（需具备有效账号与授权）。",
            "2. 进入对应 VMware 产品线（VC/VT）并定位 ESXi 版本下载页。",
            "3. 按目标版本与补丁级别下载，并核对发行说明与兼容矩阵。",
            "",
            "注意事项（账号权限/许可/版本匹配）：",
            "1. 没有产品授权时，可能只能看到文档而无法下载二进制包。",
            "2. 下载前确认硬件兼容性与 vCenter/集群版本兼容性。",
            f"3. 若需要更精确结果，可在门户搜索：`{query}`，直达链接：[打开搜索页]({search_url})。",
        ]
    )
    return "\n".join(lines), refs


def _format_kb_no_hit_message(query: str, search_url: str) -> str:
    return (
        "结论：当前未命中高相关的 VMware 官方结果，暂不建议直接给出确定下载入口。\n\n"
        "未命中说明：检索结果不足或相关度较低，可能受账号可见范围、关键词或版本写法影响。\n\n"
        "建议改写关键词：\n"
        f"1. `{query}`\n"
        "2. `ESXi 9.0.3 release notes download`\n"
        "3. `VMware ESXi 9.0.3 patch portal`\n\n"
        f"Broadcom 搜索直链：[打开搜索页]({search_url})"
    )


def _format_vcenter_summary(inventory: dict[str, Any]) -> str:
    summary = inventory.get("summary", {}) if isinstance(inventory, dict) else {}
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


def _normalize_requested_columns(message: str) -> tuple[list[str], list[str]]:
    lowered = message.lower().strip()
    segment = message.strip()
    marker_positions: list[int] = []
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
        normalized = token.strip().lower()
        mapped = _EXPORT_COLUMN_ALIAS_MAP.get(token) or _EXPORT_COLUMN_ALIAS_MAP.get(normalized)
        if not mapped:
            if token not in ignored and token not in {"导出vcenter生产环境虚拟机列表", "导出虚拟机列表"}:
                ignored.append(token)
            continue
        for col in mapped:
            if col not in seen:
                requested.append(col)
                seen.add(col)
    if not requested:
        requested = list(_DEFAULT_VM_EXPORT_COLUMNS)
    return requested, ignored


async def _export_vcenter_prod_vm_inventory(
    session_id: str | None,
    requested_columns: list[str] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    payload = {
        "connection_id": "conn-vcenter-prod",
        "format": "csv",
        "session_id": session_id,
        "requested_columns": requested_columns or _DEFAULT_VM_EXPORT_COLUMNS,
    }
    try:
        async with httpx.AsyncClient(timeout=600.0, trust_env=False) as client:
            resp = await client.post(
                f"{RESOURCE_BFF_URL}/api/v1/resources/vcenter/inventory/export",
                json=payload,
            )
        body = resp.json()
    except Exception as exc:  # noqa: BLE001
        return None, f"export request failed: {exc}"
    if not body.get("success"):
        return None, str(body.get("error") or "export failed")
    data = body.get("data")
    if not isinstance(data, dict):
        return None, "export returned empty payload"
    return data, None


def _expand_generic_qa_terms(message: str) -> list[str]:
    lowered = message.lower()
    terms: list[str] = []
    for key, aliases in _GENERIC_QA_TERMS.items():
        if key in lowered or key in message:
            terms.extend(aliases)
    if not terms:
        terms.extend(["运维", "风险", "建议"])
    terms.extend([message.strip()])
    deduped: list[str] = []
    seen: set[str] = set()
    for item in terms:
        text = str(item).strip()
        if text and text.lower() not in seen:
            deduped.append(text)
            seen.add(text.lower())
    return deduped[:8]


async def _knowledge_search_for_ops_qa(message: str) -> tuple[list[dict[str, Any]], list[str]]:
    terms = _expand_generic_qa_terms(message)
    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            resp = await client.get(f"{RESOURCE_BFF_URL}/api/v1/knowledge/articles?status=published")
        body = resp.json()
    except Exception:  # noqa: BLE001
        return [], terms
    if not body.get("success"):
        return [], terms
    items = (body.get("data") or {}).get("items") or []
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in items:
        title = str(item.get("title") or "")
        summary = str(item.get("content_summary") or "")
        tags = " ".join(str(x) for x in (item.get("tags") or []))
        blob = f"{title} {summary} {tags}".lower()
        score = 0.0
        for term in terms:
            if term.lower() in blob:
                score += 1.0
        if "迁移" in message and ("vmware" in blob or "vmotion" in blob):
            score += 1.2
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    hits: list[dict[str, Any]] = []
    for score, item in scored[:3]:
        hits.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "summary": item.get("content_summary") or "",
                "score": round(score, 2),
            }
        )
    return hits, terms


def _fallback_generic_ops_qa_text(message: str, hits: list[dict[str, Any]], include_risk_guard: bool) -> str:
    evidence_hint = "；".join([f"{h.get('title')}" for h in hits[:2]]) if hits else "未命中知识库，以下基于通用实践"
    lower = message.lower()
    if "deployment" in lower or "k8s" in lower or "kubernetes" in lower:
        text = (
            "结论：通常会带来一定业务抖动风险，是否中断取决于副本数、探针和流量切换能力。\n\n"
            "原理：重启 Deployment 会触发 Pod 终止与重建；如果只有单副本、就绪探针不充分，或上游未做摘流，"
            "请求可能在窗口内失败。\n\n"
            "建议：\n"
            "1. 先确认副本数大于 1，并校验 readiness/liveness 探针。\n"
            "2. 在低峰时段分批重启，观察新旧 Pod 切换是否平滑。\n"
            "3. 配合入口流量、错误率与延迟指标做实时监控。\n"
            f"4. 依据：{evidence_hint}。"
        )
    elif "yellow" in lower or "overallstatus" in lower:
        text = (
            "结论：ESXi 主机 overallStatus=yellow 通常表示存在告警但未到完全故障，常见于硬件、连接、存储或资源压力异常。\n\n"
            "原理：vCenter 会综合硬件传感器、主机连接状态、存储链路和资源健康度评估总体状态，任何一类子项异常都可能把 overallStatus 拉成 yellow。\n\n"
            "建议：\n"
            "1. 优先查看主机最近硬件事件、传感器与连接告警。\n"
            "2. 核对 datastore、网络 uplink、HA/DRS 与管理链路状态。\n"
            "3. 结合 CPU、内存、磁盘延迟判断是否存在资源侧瓶颈。\n"
            f"4. 依据：{evidence_hint}。"
        )
    else:
        text = (
            "结论：通常不会出现明显业务中断，但可能存在短暂网络抖动窗口。\n\n"
            "原理：迁移过程中计算状态在源与目标主机切换，虚拟网卡重绑定及 ARP/邻居缓存刷新会带来毫秒到秒级波动；"
            "若目标主机资源紧张或网络配置不一致，抖动会被放大。\n\n"
            "建议：\n"
            "1. 迁移前确认目标主机 CPU/内存余量与网络 VLAN/MTU 一致。\n"
            "2. 对关键业务先在低峰时段灰度迁移，避免批量同时迁移。\n"
            "3. 迁移前后对核心链路时延、丢包和应用探针做连续观测。\n"
            f"4. 依据：{evidence_hint}。"
        )
    if include_risk_guard:
        text += (
            "\n\n验证步骤：\n"
            "1. 在变更前后持续观察关键探针、错误率、时延和丢包。\n"
            "2. 对目标对象和关联链路执行最小必要的连通性/性能验证。\n"
            "3. 把观测窗口覆盖到切换前、中、后三个阶段。\n"
            "\n回退建议：\n"
            "1. 一旦出现持续异常，立即暂停后续动作并恢复到上一稳定状态。\n"
            "2. 保留本次变更窗口内的回退路径与操作记录。\n"
            "3. 回退后再复盘配置一致性、容量余量和链路健康度。"
        )
    return text


async def _query_vcenter_prod_inventory() -> tuple[dict[str, Any] | None, str | None]:
    url = f"{RESOURCE_BFF_URL}/api/v1/resources/vcenter/inventory?connection_id=conn-vcenter-prod"
    try:
        async with httpx.AsyncClient(timeout=240.0, trust_env=False) as client:
            resp = await client.get(url)
        body = resp.json()
    except Exception as exc:  # noqa: BLE001
        return None, f"inventory request failed: {exc}"
    if not body.get("success"):
        return None, str(body.get("error") or "inventory query failed")
    data = body.get("data")
    if not isinstance(data, dict):
        return None, "inventory returned empty payload"
    return data, None


def _prefetched_inventory(ui_context: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(ui_context, dict):
        return None, "ui_context missing"
    data = ui_context.get("prefetched_inventory")
    if not isinstance(data, dict):
        return None, "prefetched inventory unavailable"
    return data, None


def _match_host_from_inventory(hosts: list[dict[str, Any]], target: str) -> dict[str, Any] | None:
    target_l = target.strip().lower()
    target_short = target_l.split(".", 1)[0]
    for host in hosts:
        name_l = str(host.get("name") or "").strip().lower()
        host_id_l = str(host.get("host_id") or "").strip().lower()
        if target_l and (target_l == name_l or target_l == host_id_l):
            return host
    for host in hosts:
        name_l = str(host.get("name") or "").strip().lower()
        host_id_l = str(host.get("host_id") or "").strip().lower()
        if target_short and target_short in {name_l.split(".", 1)[0], host_id_l.split(".", 1)[0]}:
            return host
    for host in hosts:
        name_l = str(host.get("name") or "").strip().lower()
        host_id_l = str(host.get("host_id") or "").strip().lower()
        if target_l and (target_l in name_l or target_l in host_id_l):
            return host
    return None


def _as_percent(used: Any, total: Any) -> float | None:
    try:
        used_f = float(used)
        total_f = float(total)
        if total_f <= 0:
            return None
        return round((used_f / total_f) * 100, 2)
    except (TypeError, ValueError):
        return None


def _host_diag_tool_steps(base_steps: list[dict[str, Any]], target_name: str, status: str) -> list[dict[str, Any]]:
    steps = list(base_steps)
    steps.append(
        {
            "agent": "RCAAgent",
            "stage": "tool_invoking",
            "summary": f"调用资源中：读取主机 {target_name} 的实时 inventory/健康指标",
            "status": "in_progress",
        }
    )
    steps.append(
        {
            "agent": "RCAAgent",
            "stage": "result_summary",
            "summary": f"汇总结果中：已生成主机 {target_name} 的健康诊断结论（{status}）",
            "status": "success",
        }
    )
    return steps


def _build_host_diagnosis_message(
    source: dict[str, Any],
    *,
    host_target: str,
) -> tuple[str, list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    cpu_percent = source.get("cpu_usage_percent")
    if cpu_percent is None:
        cpu_percent = _as_percent(source.get("cpu_usage_mhz"), source.get("cpu_mhz"))
    memory_percent = source.get("memory_usage_percent")
    if memory_percent is None:
        memory_percent = _as_percent(source.get("memory_usage_mb"), source.get("memory_mb"))
    overall_status = str(source.get("overall_status", "unknown"))
    connection_state = str(source.get("connection_state", "unknown"))
    vm_count = source.get("vm_count", 0)
    host_name = str(source.get("name") or host_target)

    conclusion = "该主机当前整体健康。"
    if overall_status.lower() not in {"green", "gray"}:
        conclusion = "该主机处于非健康状态，建议优先处理告警。"
    if isinstance(cpu_percent, (int, float)) and cpu_percent >= 85:
        conclusion = "该主机 CPU 压力偏高，建议尽快排查负载与资源分配。"
    if isinstance(memory_percent, (int, float)) and memory_percent >= 90:
        conclusion = "该主机内存压力偏高，建议尽快排查内存占用与回收。"

    assistant_message = (
        f"已完成对主机 {host_name}（目标={host_target}）的健康分析：\n\n"
        f"- 主机ID：{source.get('host_id', 'N/A')}\n"
        f"- 连接状态：{connection_state}\n"
        f"- 总体状态：{overall_status}\n"
        f"- CPU 使用率：{cpu_percent if cpu_percent is not None else 'N/A'}%\n"
        f"- 内存使用率：{memory_percent if memory_percent is not None else 'N/A'}%\n"
        f"- 承载虚拟机数：{vm_count}\n\n"
        f"结论：{conclusion}"
    )
    recommended_actions = [
        "检查该主机最近告警与硬件事件",
        "核对该主机承载虚拟机的资源占用与热点分布",
    ]
    evidences = [
        {
            "evidence_id": "ev-orch-host-health",
            "source_type": "host_detail",
            "summary": (
                f"主机 {host_name} 状态={overall_status}, "
                f"CPU={cpu_percent if cpu_percent is not None else 'N/A'}%, "
                f"Memory={memory_percent if memory_percent is not None else 'N/A'}%"
            ),
            "confidence": 0.93,
            "timestamp": _now(),
        }
    ]
    tool_traces = [
        {
            "tool_name": "vmware.get_vcenter_inventory",
            "gateway": "resource-bff",
            "input_summary": '{"connection_id":"conn-vcenter-prod"}',
            "output_summary": f"matched_host={host_name}",
            "duration_ms": 0,
            "status": "success",
            "timestamp": _now(),
        }
    ]
    return assistant_message, recommended_actions, evidences, tool_traces


def _clarify_question(run: dict[str, Any]) -> tuple[str, list[str]]:
    chosen = run.get("chosen_intent") or {}
    missing_slots = chosen.get("missing_slots") or []
    resolution_refs = chosen.get("resolution_refs") or []
    target_raw = str(chosen.get("target_object_raw") or "")
    if missing_slots:
        first = missing_slots[0]
        label_map = {
            "target_object": "请补充目标对象名称或 IP。",
            "environment": "请确认环境（prod/test/dev）。",
            "replicas": "请补充目标副本数。",
            "service_name": "请补充服务名。",
        }
        return label_map.get(first, f"请补充槽位：{first}"), []
    if len(resolution_refs) > 1 and (
        float(chosen.get("resolution_confidence") or 0.0) < 0.9 or ("." not in target_raw)
    ):
        choices = [str(item.get("name") or item.get("ref_id") or "候选对象") for item in resolution_refs[:4]]
        return "识别到多个可能的目标对象，请确认本次要分析哪一个。", choices
    if chosen.get("target_object_raw") and not chosen.get("target_object_resolved"):
        return f"未在当前连接中找到目标对象：{chosen.get('target_object_raw')}。请确认名称或切换连接后重试。", []
    candidates = run.get("candidates") or []
    options = [f"{item['intent_code']} ({item['score']:.2f})" for item in candidates[:3]]
    return "系统识别到多个可能意图，请确认本次要执行哪一类操作。", options


def _audit_timeline(run_id: str) -> dict[str, Any]:
    events = list_audit_events(run_id)
    return {
        "run_id": run_id,
        "operator": "orchestrator",
        "decision_chain": [event.summary for event in events if event.event_type in {"RECOVER", "CLARIFY_CREATED", "APPROVE_CREATED", "APPROVE_DECIDED", "RESUME"}],
        "tool_outputs": [event.summary for event in events if event.event_type in {"PRE_EXEC", "POST_EXEC", "ROLLBACK"}],
        "events": [event.model_dump() for event in events],
    }


def _analysis_steps(analysis: Any, run: dict[str, Any]) -> list[dict[str, Any]]:
    chosen = run.get("chosen_intent") or {}
    steps = [
        {
            "agent": "IntentRecovery",
            "stage": "mention_extraction",
            "summary": f"识别诊断对象：{chosen.get('target_object_raw') or '未识别到明确对象'}",
            "status": "success",
        },
        {
            "agent": "IntentRecovery",
            "stage": "target_resolution",
            "summary": (
                f"已解析到{chosen.get('target_type') or '对象'} {chosen.get('target_object_resolved')}"
                if chosen.get("target_object_resolved")
                else "目标对象解析未命中或存在冲突"
            ),
            "status": "success" if chosen.get("target_object_resolved") else "in_progress",
        },
        {
            "agent": "IntentRecovery",
            "stage": "intent_scoring",
            "summary": f"候选意图重排完成：{chosen.get('intent_code') or '未命中'} / {analysis.decision}",
            "status": "success" if analysis.decision != "rejected" else "failed",
        },
    ]
    if analysis.decision == "clarify_required":
        steps.append(
            {
                "agent": "IntentRecovery",
                "stage": "clarify_gate",
                "summary": "需要进一步澄清目标对象或候选冲突",
                "status": "in_progress",
            }
        )
    return steps


def _append_analysis_steps(base_steps: list[dict[str, Any]], *extra: dict[str, Any]) -> list[dict[str, Any]]:
    steps = list(base_steps)
    steps.extend(extra)
    return steps


@router.post("/api/v1/orchestrate/chat-v2")
async def orchestrate_chat_v2(body: ChatV2Request):
    try:
        analysis = analyze_intent(
            IntentAnalyzeInput(
                conversation_id=body.session_id,
                user_id=body.user_id,
                channel=body.channel,
                utterance=body.message,
                history=body.history,
                memory=[str(item.get("content") or "") for item in body.history[-8:]],
                resource_catalog=body.resource_catalog,
                ui_context=body.ui_context,
            )
        )
        recovered = analysis.run
        run = recovered.model_dump()
        analysis_steps = _analysis_steps(analysis, run)
        append_audit_event(run_id=recovered.run_id, event_type="RECOVER", summary=f"恢复意图: {recovered.decision}")
        append_audit_event(
            run_id=recovered.run_id,
            event_type="CONTEXT_COMPLETED",
            summary=f"context_hints={','.join(sorted(analysis.context_hints.keys())) or 'none'}",
        )
        append_audit_event(run_id=recovered.run_id, event_type="NORMALIZED", summary=analysis.normalized_utterance[:120])
        append_audit_event(run_id=recovered.run_id, event_type="DISAMBIGUATED", summary=f"decision={analysis.decision}")
        append_audit_event(
            run_id=recovered.run_id,
            event_type="EXECUTION_INTENT_SET",
            summary=f"mode={analysis.execution_intent.mode}",
        )
        if analysis.memory_refs:
            append_audit_event(run_id=recovered.run_id, event_type="MEMORY_HIT", summary=f"memory_refs={len(analysis.memory_refs)}")
        if recovered.decision == "rejected":
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message="未能稳定恢复你的意图，请换一种说法或补充更明确的目标对象。",
                    kind="intent_recovery",
                    reasoning_summary=_reasoning("系统尝试恢复用户意图。", "基于规则、槽位和记忆做候选评分。", "意图恢复失败，未进入执行阶段。"),
                    intent_recovery=run,
                    execution_intent=analysis.execution_intent.model_dump(),
                    risk_context=analysis.risk_context.model_dump(),
                    memory_refs=analysis.memory_refs,
                    audit_timeline=_audit_timeline(recovered.run_id),
                    analysis_steps=analysis_steps,
                ).model_dump()
            )

        if recovered.decision == "clarify_required":
            question, choices = _clarify_question(run)
            clarify = create_clarify(
                ClarifyCreateRequest(
                    run_id=recovered.run_id,
                    question=question,
                    choices=choices,
                    allow_free_text=True,
                    reason_code="missing_slot" if recovered.missing_slots else "ambiguous_intent",
                    candidate_targets=[
                        {
                            "id": str(item.get("ref_id") or item.get("name") or ""),
                            "label": str(item.get("name") or item.get("ref_id") or "候选对象"),
                            "type": str(item.get("type") or "resource"),
                            "matched_by": str(item.get("matched_by") or ""),
                            "connection_id": item.get("connection_id"),
                            "environment": item.get("environment"),
                        }
                        for item in (run.get("chosen_intent") or {}).get("resolution_refs", [])[:4]
                    ],
                )
            )
            append_audit_event(run_id=recovered.run_id, event_type="CLARIFY_CREATED", summary=question)
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message=question,
                    kind="clarify",
                    reasoning_summary=_reasoning("系统已恢复到候选意图，但关键信息仍不足。", "发起 Clarify 交互补齐关键槽位或确认候选。", "当前未执行任何副作用操作，等待用户补充。"),
                    intent_recovery=run,
                    execution_intent=analysis.execution_intent.model_dump(),
                    risk_context=analysis.risk_context.model_dump(),
                    memory_refs=analysis.memory_refs,
                    clarify_card=clarify.model_dump(),
                    audit_timeline=_audit_timeline(recovered.run_id),
                    analysis_steps=analysis_steps,
                ).model_dump()
            )

        chosen = analysis.selected_intent
        assert chosen is not None

        if chosen.intent_code == "knowledge.vmware_kb_search":
            append_audit_event(run_id=recovered.run_id, event_type="vmware_kb_search_started", summary="触发 VMware KB 搜索")
            kb_data, kb_error = await _invoke_vmware_kb_search(run, body.message)
            query = _normalize_vmware_kb_query(run, body.message)
            search_url = str((kb_data or {}).get("search_url") or f"{BROADCOM_SEARCH_URL}?searchString={query}")
            if kb_error:
                append_audit_event(run_id=recovered.run_id, event_type="vmware_kb_search_failed", summary=kb_error)
                return make_success(
                    ChatV2Response(
                        session_id=body.session_id,
                        message_id=_message_id(),
                        assistant_message=(
                            "检索 VMware KB 失败，请稍后重试。\n\n"
                            f"你也可以先使用 Broadcom 搜索直链：[打开搜索页]({search_url})"
                        ),
                        kind="text",
                        reasoning_summary=_reasoning(
                            "用户在咨询 VMware 文档/下载类问题。",
                            "优先调用 vmware.kb_search 获取官方来源。",
                            "工具调用失败，已返回可重试提示与搜索直链。",
                        ),
                        intent_recovery=run,
                        execution_intent=analysis.execution_intent.model_dump(),
                        risk_context=analysis.risk_context.model_dump(),
                        memory_refs=analysis.memory_refs,
                        analysis_steps=analysis_steps,
                        tool_traces=[
                            {
                                "tool_name": "vmware.kb_search",
                                "gateway": "tool-gateway",
                                "input_summary": f'{{"query":"{query}","segment":"VC","language":"en_US","page_size":5}}',
                                "output_summary": kb_error,
                                "duration_ms": 0,
                                "status": "error",
                                "timestamp": _now(),
                            }
                        ],
                        evidence_refs=[search_url],
                        audit_timeline=_audit_timeline(recovered.run_id),
                    ).model_dump()
                )

            items = (kb_data or {}).get("items") or []
            if isinstance(items, list) and items:
                assistant_message, refs = _format_kb_hit_message(query, search_url, items)
                append_audit_event(
                    run_id=recovered.run_id,
                    event_type="vmware_kb_search_completed",
                    summary=f"命中 {min(len(items), 3)} 条官方来源",
                )
                return make_success(
                    ChatV2Response(
                        session_id=body.session_id,
                        message_id=_message_id(),
                        assistant_message=assistant_message,
                        kind="text",
                        reasoning_summary=_reasoning(
                            "用户在咨询 VMware 文档/下载类问题。",
                            "优先调用 vmware.kb_search，并按相关度整理官方来源。",
                            f"已返回 Top{min(3, len(items))} 官方来源与下载路径建议。",
                        ),
                        intent_recovery=run,
                        execution_intent=analysis.execution_intent.model_dump(),
                        risk_context=analysis.risk_context.model_dump(),
                        memory_refs=analysis.memory_refs,
                        analysis_steps=analysis_steps,
                        tool_traces=[
                            {
                                "tool_name": "vmware.kb_search",
                                "gateway": "tool-gateway",
                                "input_summary": f'{{"query":"{query}","segment":"VC","language":"en_US","page_size":5}}',
                                "output_summary": f"hits={len(items)}",
                                "duration_ms": 0,
                                "status": "success",
                                "timestamp": _now(),
                            }
                        ],
                        evidence_refs=refs,
                        audit_timeline=_audit_timeline(recovered.run_id),
                    ).model_dump()
                )

            append_audit_event(run_id=recovered.run_id, event_type="vmware_kb_search_no_hit", summary="未命中高相关结果")
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message=_format_kb_no_hit_message(query, search_url),
                    kind="text",
                    reasoning_summary=_reasoning(
                        "用户在咨询 VMware 文档/下载类问题。",
                        "优先调用 vmware.kb_search 并评估命中质量。",
                        "未命中高相关来源，已返回搜索直链与关键词改写建议。",
                    ),
                    intent_recovery=run,
                    execution_intent=analysis.execution_intent.model_dump(),
                    risk_context=analysis.risk_context.model_dump(),
                    memory_refs=analysis.memory_refs,
                    analysis_steps=analysis_steps,
                    tool_traces=[
                        {
                            "tool_name": "vmware.kb_search",
                            "gateway": "tool-gateway",
                            "input_summary": f'{{"query":"{query}","segment":"VC","language":"en_US","page_size":5}}',
                            "output_summary": "hits=0",
                            "duration_ms": 0,
                            "status": "warning",
                            "timestamp": _now(),
                        }
                    ],
                    evidence_refs=[search_url],
                    audit_timeline=_audit_timeline(recovered.run_id),
                ).model_dump()
            )

        if chosen.intent_code == "vmware.host.diagnose":
            host_target = _target_name(run)
            append_audit_event(run_id=recovered.run_id, event_type="PLAN", summary=f"读取主机 {host_target} 的实时资源数据")
            inventory, inventory_error = _prefetched_inventory(body.ui_context)
            if not inventory:
                inventory, inventory_error = await _query_vcenter_prod_inventory()
            if inventory_error or not inventory:
                append_audit_event(run_id=recovered.run_id, event_type="FAILED", summary=f"主机诊断失败：{inventory_error or 'inventory unavailable'}")
                return make_success(
                    ChatV2Response(
                        session_id=body.session_id,
                        message_id=_message_id(),
                        assistant_message="诊断失败：无法获取 conn-vcenter-prod 的实时资源数据，请稍后重试。",
                        kind="text",
                        reasoning_summary=_reasoning(
                            "用户希望分析指定 vCenter 主机的健康状况。",
                            "在只读模式下执行实时 inventory 查询并锁定目标主机。",
                            "未获取到实时 inventory，已返回明确错误且未使用 mock。",
                        ),
                        intent_recovery=run,
                        execution_intent=analysis.execution_intent.model_dump(),
                        risk_context=analysis.risk_context.model_dump(),
                        memory_refs=analysis.memory_refs,
                        analysis_steps=_host_diag_tool_steps(analysis_steps, host_target, "失败"),
                        tool_traces=[
                            {
                                "tool_name": "vmware.get_vcenter_inventory",
                                "gateway": "resource-bff",
                                "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                                "output_summary": inventory_error or "inventory unavailable",
                                "duration_ms": 0,
                                "status": "error",
                                "timestamp": _now(),
                            }
                        ],
                        audit_timeline=_audit_timeline(recovered.run_id),
                    ).model_dump()
                )

            hosts = inventory.get("hosts", []) if isinstance(inventory.get("hosts", []), list) else []
            matched_host = _match_host_from_inventory(hosts, host_target)
            if not matched_host:
                append_audit_event(run_id=recovered.run_id, event_type="FAILED", summary=f"未匹配到目标主机 {host_target}")
                return make_success(
                    ChatV2Response(
                        session_id=body.session_id,
                        message_id=_message_id(),
                        assistant_message=f"未在 conn-vcenter-prod 中找到主机 {host_target}，请确认名称或切换连接后重试。",
                        kind="clarify",
                        reasoning_summary=_reasoning(
                            "用户希望分析指定 vCenter 主机的健康状况。",
                            "在只读模式下执行实时 inventory 查询并匹配目标主机。",
                            "inventory 中未匹配到目标主机，已返回可解释的澄清提示。",
                        ),
                        intent_recovery=run,
                        execution_intent=analysis.execution_intent.model_dump(),
                        risk_context=analysis.risk_context.model_dump(),
                        memory_refs=analysis.memory_refs,
                        analysis_steps=_host_diag_tool_steps(analysis_steps, host_target, "未匹配"),
                        tool_traces=[
                            {
                                "tool_name": "vmware.get_vcenter_inventory",
                                "gateway": "resource-bff",
                                "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                                "output_summary": f"target_not_found={host_target}",
                                "duration_ms": 0,
                                "status": "error",
                                "timestamp": _now(),
                            }
                        ],
                        audit_timeline=_audit_timeline(recovered.run_id),
                    ).model_dump()
                )

            append_audit_event(run_id=recovered.run_id, event_type="COMPLETE", summary=f"已完成主机 {host_target} 的只读诊断")
            assistant_message, recommended_actions, evidences, tool_traces = _build_host_diagnosis_message(
                matched_host,
                host_target=host_target,
            )
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message=assistant_message,
                    kind="text",
                    reasoning_summary=_reasoning(
                        "用户希望分析指定 vCenter 主机的健康状况。",
                        "在只读模式下执行实时 inventory 查询，锁定目标主机并汇总健康指标。",
                        "已返回目标主机的健康分析结果与建议动作。",
                    ),
                    intent_recovery=run,
                    execution_intent=analysis.execution_intent.model_dump(),
                    risk_context=analysis.risk_context.model_dump(),
                    memory_refs=analysis.memory_refs,
                    diagnosis_id=f"dg-{recovered.run_id}",
                    evidences=evidences,
                    recommended_actions=recommended_actions,
                    root_cause_candidates=[
                        {
                            "description": assistant_message.split("结论：", 1)[-1],
                            "confidence": 0.9,
                            "category": "infrastructure",
                        }
                    ],
                    analysis_steps=_host_diag_tool_steps(analysis_steps, host_target, "成功"),
                    tool_traces=tool_traces,
                    evidence_refs=[ev["evidence_id"] for ev in evidences],
                    audit_timeline=_audit_timeline(recovered.run_id),
                ).model_dump()
            )

        if chosen.intent_code == "resource.vcenter.inventory_summary":
            append_audit_event(run_id=recovered.run_id, event_type="PLAN", summary="调用 vCenter inventory 获取资源概览")
            inventory, inventory_error = await _query_vcenter_prod_inventory()
            if inventory_error or not inventory:
                append_audit_event(
                    run_id=recovered.run_id,
                    event_type="FAILED",
                    summary=f"资源查询失败：{inventory_error or 'inventory unavailable'}",
                )
                return make_success(
                    ChatV2Response(
                        session_id=body.session_id,
                        message_id=_message_id(),
                        assistant_message="获取 vCenter 生产环境资源概览失败：无法读取 conn-vcenter-prod 的实时 inventory，请稍后重试。",
                        kind="text",
                        reasoning_summary=_reasoning(
                            "用户希望查询 vCenter 生产环境资源概览。",
                            "在只读模式下调用 inventory 接口，汇总 VM、主机、集群与健康摘要。",
                            "实时 inventory 获取失败，已返回明确错误且未使用 mock。",
                        ),
                        intent_recovery=run,
                        execution_intent=analysis.execution_intent.model_dump(),
                        risk_context=analysis.risk_context.model_dump(),
                        memory_refs=analysis.memory_refs,
                        analysis_steps=_append_analysis_steps(
                            analysis_steps,
                            {
                                "agent": "ResourceQueryAgent",
                                "stage": "tool_invoking",
                                "summary": "调用资源中：读取 conn-vcenter-prod 的 inventory",
                                "status": "in_progress",
                            },
                            {
                                "agent": "ResourceQueryAgent",
                                "stage": "tool_error",
                                "summary": f"资源调用失败：{inventory_error or 'inventory unavailable'}",
                                "status": "failed",
                            },
                        ),
                        tool_traces=[
                            {
                                "tool_name": "vmware.get_vcenter_inventory",
                                "gateway": "resource-bff",
                                "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                                "output_summary": inventory_error or "inventory unavailable",
                                "duration_ms": 0,
                                "status": "error",
                                "timestamp": _now(),
                            }
                        ],
                        audit_timeline=_audit_timeline(recovered.run_id),
                    ).model_dump()
                )

            summary = inventory.get("summary", {}) if isinstance(inventory, dict) else {}
            append_audit_event(run_id=recovered.run_id, event_type="COMPLETE", summary="已完成 vCenter 资源概览汇总")
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message=_format_vcenter_summary(inventory),
                    kind="text",
                    reasoning_summary=_reasoning(
                        "用户希望查询 vCenter 生产环境资源概览。",
                        "在只读模式下调用 inventory 接口，并汇总 VM、主机、集群与健康摘要。",
                        "已返回 VM 总数、主机/集群统计和异常摘要。",
                    ),
                    intent_recovery=run,
                    execution_intent=analysis.execution_intent.model_dump(),
                    risk_context=analysis.risk_context.model_dump(),
                    memory_refs=analysis.memory_refs,
                    analysis_steps=_append_analysis_steps(
                        analysis_steps,
                        {
                            "agent": "ResourceQueryAgent",
                            "stage": "tool_invoking",
                            "summary": "调用资源中：读取 conn-vcenter-prod 的 inventory",
                            "status": "in_progress",
                        },
                        {
                            "agent": "ResourceQueryAgent",
                            "stage": "tool_done",
                            "summary": (
                                f"资源调用完成：clusters={summary.get('cluster_count', 0)}, "
                                f"hosts={summary.get('host_count', 0)}, vms={summary.get('vm_count', 0)}"
                            ),
                            "status": "success",
                        },
                        {
                            "agent": "ResourceQueryAgent",
                            "stage": "result_summary",
                            "summary": "汇总结果中：已生成资源数量与健康摘要",
                            "status": "success",
                        },
                    ),
                    tool_traces=[
                        {
                            "tool_name": "vmware.get_vcenter_inventory",
                            "gateway": "resource-bff",
                            "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                            "output_summary": (
                                f"clusters={summary.get('cluster_count', 0)}, "
                                f"hosts={summary.get('host_count', 0)}, vms={summary.get('vm_count', 0)}"
                            ),
                            "duration_ms": 0,
                            "status": "success",
                            "timestamp": _now(),
                        }
                    ],
                    audit_timeline=_audit_timeline(recovered.run_id),
                ).model_dump()
            )

        if chosen.intent_code == "resource.vcenter.vm_export":
            requested_columns, ignored_columns = _normalize_requested_columns(body.message)
            append_audit_event(
                run_id=recovered.run_id,
                event_type="PLAN",
                summary=f"触发 vCenter VM 导出，requested_columns={','.join(requested_columns)}",
            )
            export_data, export_error = await _export_vcenter_prod_vm_inventory(body.session_id, requested_columns)
            if export_error or not export_data:
                append_audit_event(
                    run_id=recovered.run_id,
                    event_type="FAILED",
                    summary=f"导出失败：{export_error or 'export unavailable'}",
                )
                return make_success(
                    ChatV2Response(
                        session_id=body.session_id,
                        message_id=_message_id(),
                        assistant_message="触发导出任务失败：无法导出 conn-vcenter-prod 的虚拟机列表，请稍后重试。",
                        kind="text",
                        reasoning_summary=_reasoning(
                            "用户希望导出 vCenter 生产环境虚拟机列表。",
                            "在只读模式下调用 inventory 导出接口，并按用户指定列生成 CSV。",
                            "导出任务失败，已返回明确错误且未使用 mock。",
                        ),
                        intent_recovery=run,
                        execution_intent=analysis.execution_intent.model_dump(),
                        risk_context=analysis.risk_context.model_dump(),
                        memory_refs=analysis.memory_refs,
                        analysis_steps=_append_analysis_steps(
                            analysis_steps,
                            {
                                "agent": "ResourceQueryAgent",
                                "stage": "tool_invoking",
                                "summary": "调用资源中：触发 vCenter 虚拟机列表导出任务",
                                "status": "in_progress",
                            },
                            {
                                "agent": "ResourceQueryAgent",
                                "stage": "tool_error",
                                "summary": f"资源调用失败：{export_error or 'export unavailable'}",
                                "status": "failed",
                            },
                        ),
                        tool_traces=[
                            {
                                "tool_name": "vmware.export_vcenter_vm_list",
                                "gateway": "resource-bff",
                                "input_summary": (
                                    '{"connection_id":"conn-vcenter-prod","format":"csv",'
                                    f'"requested_columns":"{",".join(requested_columns)}"}}'
                                ),
                                "output_summary": export_error or "export unavailable",
                                "duration_ms": 0,
                                "status": "error",
                                "timestamp": _now(),
                            }
                        ],
                        audit_timeline=_audit_timeline(recovered.run_id),
                    ).model_dump()
                )

            actual_columns = export_data.get("export_columns", requested_columns)
            actual_ignored = export_data.get("ignored_columns", ignored_columns)
            append_audit_event(run_id=recovered.run_id, event_type="COMPLETE", summary="已生成 vCenter VM 导出文件")
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message=(
                        "已触发 vCenter 生产环境（conn-vcenter-prod）虚拟机列表导出任务，可在下方下载文件。\n"
                        f"已导出列：{','.join(actual_columns)}"
                        + (f"\n已忽略列：{','.join(actual_ignored)}" if actual_ignored else "")
                    ),
                    kind="text",
                    reasoning_summary=_reasoning(
                        "用户希望导出 vCenter 生产环境虚拟机列表，并保留指定列顺序。",
                        "解析 requested_columns 后调用 inventory/export 接口生成 CSV。",
                        "已返回下载入口，并明确告知已导出列与忽略列。",
                    ),
                    intent_recovery=run,
                    execution_intent=analysis.execution_intent.model_dump(),
                    risk_context=analysis.risk_context.model_dump(),
                    memory_refs=analysis.memory_refs,
                    analysis_steps=_append_analysis_steps(
                        analysis_steps,
                        {
                            "agent": "ResourceQueryAgent",
                            "stage": "tool_invoking",
                            "summary": "调用资源中：触发 vCenter 虚拟机列表导出任务",
                            "status": "in_progress",
                        },
                        {
                            "agent": "ResourceQueryAgent",
                            "stage": "tool_done",
                            "summary": f"资源调用完成：已生成导出文件 {export_data.get('file_name', 'vm-list.csv')}",
                            "status": "success",
                        },
                        {
                            "agent": "ResourceQueryAgent",
                            "stage": "result_summary",
                            "summary": "汇总结果中：已整理下载入口和导出列信息",
                            "status": "success",
                        },
                    ),
                    tool_traces=[
                        {
                            "tool_name": "vmware.export_vcenter_vm_list",
                            "gateway": "resource-bff",
                            "input_summary": (
                                '{"connection_id":"conn-vcenter-prod","format":"csv",'
                                f'"requested_columns":"{",".join(actual_columns)}"}}'
                            ),
                            "output_summary": export_data.get("file_name", "vm-list.csv"),
                            "duration_ms": 0,
                            "status": "success",
                            "timestamp": _now(),
                        }
                    ],
                    evidence_refs=[str(export_data.get("download_url") or "")] if export_data.get("download_url") else [],
                    audit_timeline=_audit_timeline(recovered.run_id),
                ).model_dump()
                | {
                    "export_file": export_data,
                    "export_columns": actual_columns,
                    "ignored_columns": actual_ignored,
                }
            )

        if chosen.intent_code == "generic_ops_qa":
            include_risk_guard = bool(_GENERIC_QA_RISK_KEYWORDS.search(body.message))
            append_audit_event(run_id=recovered.run_id, event_type="generic_qa_started", summary="触发通用运维问答")
            hits, terms = await _knowledge_search_for_ops_qa(body.message)
            append_audit_event(
                run_id=recovered.run_id,
                event_type="generic_qa_retrieved",
                summary=f"命中知识条目={len(hits)}",
            )
            assistant_message = _fallback_generic_ops_qa_text(body.message, hits, include_risk_guard)
            append_audit_event(
                run_id=recovered.run_id,
                event_type="generic_qa_completed" if hits else "generic_qa_fallback",
                summary="已生成结构化通用运维问答",
            )
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message=assistant_message,
                    kind="text",
                    reasoning_summary=_reasoning(
                        "用户在询问通用运维问题，需要给出结论、原理和建议。",
                        "先检索知识条目，再基于命中证据生成结构化回答；风险问题附带验证步骤与回退建议。",
                        "已返回结构化运维问答，并挂载知识检索轨迹与证据引用。",
                    ),
                    intent_recovery=run,
                    execution_intent=analysis.execution_intent.model_dump(),
                    risk_context=analysis.risk_context.model_dump(),
                    memory_refs=analysis.memory_refs,
                    analysis_steps=_append_analysis_steps(
                        analysis_steps,
                        {
                            "agent": "OpsQAAssistant",
                            "stage": "tool_invoking",
                            "summary": "知识检索中：查询运维知识条目",
                            "status": "in_progress",
                        },
                        {
                            "agent": "OpsQAAssistant",
                            "stage": "tool_done",
                            "summary": f"知识检索完成：命中 {len(hits)} 条候选证据",
                            "status": "success",
                        },
                        {
                            "agent": "OpsQAAssistant",
                            "stage": "result_summary",
                            "summary": "汇总结果中：已生成结论、原理、建议与风险守护项",
                            "status": "success",
                        },
                    ),
                    tool_traces=[
                        {
                            "tool_name": "knowledge.search",
                            "gateway": "knowledge",
                            "input_summary": f'{{"terms":"{",".join(terms[:6])}"}}',
                            "output_summary": f"hits={len(hits)}",
                            "duration_ms": 0,
                            "status": "success",
                            "timestamp": _now(),
                        },
                        {
                            "tool_name": "generic_ops_qa.compose",
                            "gateway": "orchestrator",
                            "input_summary": '{"template":"结论+原理+建议"}',
                            "output_summary": "generated",
                            "duration_ms": 0,
                            "status": "success",
                            "timestamp": _now(),
                        },
                    ],
                    evidence_refs=[str(hit.get("id")) for hit in hits if hit.get("id")],
                    audit_timeline=_audit_timeline(recovered.run_id),
                ).model_dump()
            )

        if analysis.execution_intent.mode != "execute" and chosen.action in _WRITE_ACTIONS:
            append_audit_event(
                run_id=recovered.run_id,
                event_type="EXECUTION_INTENT_SET",
                summary=f"执行意图={analysis.execution_intent.mode}，阻断直接执行",
            )
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message="我已完成意图分析。当前识别为咨询/规划语义，不会直接执行副作用动作；如需执行请明确回复“确认执行”。",
                    kind="intent_recovery",
                    reasoning_summary=_reasoning(
                        "系统识别到本轮请求偏向咨询或规划。",
                        "输出分析结果与风险上下文，不触发执行链路。",
                        f"已按 {analysis.execution_intent.mode} 模式返回下一步建议。",
                    ),
                    intent_recovery=run,
                    execution_intent=analysis.execution_intent.model_dump(),
                    risk_context=analysis.risk_context.model_dump(),
                    memory_refs=analysis.memory_refs,
                    evidence_refs=analysis.evidence_refs,
                    audit_timeline=_audit_timeline(recovered.run_id),
                    analysis_steps=analysis_steps,
                ).model_dump()
            )

        if analysis.execution_intent.mode != "execute":
            append_audit_event(
                run_id=recovered.run_id,
                event_type="EXECUTION_INTENT_SET",
                summary=f"执行意图={analysis.execution_intent.mode}，当前意图未接入只读执行链路",
            )
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message="我已完成意图分析。当前请求属于只读或规划模式，但该意图暂未接入对应的只读执行链路。",
                    kind="intent_recovery",
                    reasoning_summary=_reasoning(
                        "系统识别到本轮请求偏向只读查询或规划。",
                        "已完成意图恢复与风险上下文分析。",
                        f"当前意图尚未接入 {analysis.execution_intent.mode} 模式的执行链路。",
                    ),
                    intent_recovery=run,
                    execution_intent=analysis.execution_intent.model_dump(),
                    risk_context=analysis.risk_context.model_dump(),
                    memory_refs=analysis.memory_refs,
                    evidence_refs=analysis.evidence_refs,
                    audit_timeline=_audit_timeline(recovered.run_id),
                    analysis_steps=analysis_steps,
                ).model_dump()
            )

        risk = evaluate_risk(
            RiskEvaluationInput(
                domain=chosen.domain,
                action=chosen.action,
                environment=(chosen.environment or chosen.inferred_environment or "prod"),
                resource_scope=chosen.resource_scope,
            )
        )
        plan_steps = _plan_steps_for_run(run)
        resource_scope = _resource_scope_from_run(run)
        if risk.deny:
            append_audit_event(run_id=recovered.run_id, event_type="FAILED", summary="命中拒绝策略，终止执行")
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message="该操作命中高风险拒绝策略，当前不能直接执行。",
                    kind="intent_recovery",
                    reasoning_summary=_reasoning("系统已恢复出可执行意图。", "通过风险策略引擎评估环境、范围和动作类型。", "命中 L4/deny 策略，流程已中止。"),
                    intent_recovery=run,
                    execution_intent=analysis.execution_intent.model_dump(),
                    risk_context=analysis.risk_context.model_dump(),
                    memory_refs=analysis.memory_refs,
                    audit_timeline=_audit_timeline(recovered.run_id),
                    analysis_steps=analysis_steps,
                ).model_dump()
            )

        if risk.require_approval:
            approval = create_approval(
                ApprovalCreateRequest(
                    run_id=recovered.run_id,
                    summary=f"对 {resource_scope.resources[0].name if resource_scope.resources else '目标对象'} 执行 {chosen.action}",
                    domain=chosen.domain,
                    action=chosen.action,
                    risk_level=risk.risk_level,
                    resource_scope=resource_scope,
                    command_preview=[f"action={chosen.action}", f"target={_target_name(run)}"],
                    plan_steps=[step.action for step in plan_steps],
                    rollback_plan=["如执行异常，按回滚计划恢复到最近安全点。"],
                    allowed_scopes=risk.allowed_scopes,
                )
            )
            append_audit_event(run_id=recovered.run_id, event_type="APPROVE_CREATED", summary=approval.summary)
            return make_success(
                ChatV2Response(
                    session_id=body.session_id,
                    message_id=_message_id(),
                    assistant_message="操作已进入审批门禁，请确认执行范围、计划和回滚方案。",
                    kind="approval",
                    reasoning_summary=_reasoning("系统已恢复出明确意图。", "按风险策略评估为 L2+，因此创建审批交互。", "等待审批通过后再进入执行阶段。"),
                    intent_recovery=run,
                    execution_intent=analysis.execution_intent.model_dump(),
                    risk_context=analysis.risk_context.model_dump(),
                    memory_refs=analysis.memory_refs,
                    approval_card=approval.model_dump(),
                    audit_timeline=_audit_timeline(recovered.run_id),
                    analysis_steps=analysis_steps,
                ).model_dump()
            )

        for step in plan_steps:
            append_audit_event(run_id=recovered.run_id, event_type="PRE_EXEC", summary=f"准备执行 {step.action}", step_no=step.seq)
            upsert_checkpoint(run_id=recovered.run_id, step=step, status="waiting")
            upsert_checkpoint(run_id=recovered.run_id, step=step, status="safe")
            append_audit_event(run_id=recovered.run_id, event_type="POST_EXEC", summary=f"已完成 {step.action}", step_no=step.seq)
        append_audit_event(run_id=recovered.run_id, event_type="COMPLETE", summary="执行链路已完成")
        checkpoints = [upsert_checkpoint(run_id=recovered.run_id, step=plan_steps[-1], status="safe")]
        return make_success(
            ChatV2Response(
                session_id=body.session_id,
                message_id=_message_id(),
                assistant_message=f"已按低风险路径完成意图 {chosen.intent_code} 的编排执行。",
                kind="resume",
                reasoning_summary=_reasoning("系统已恢复并确认意图。", "低风险动作直接执行，并写入审计与 checkpoint。", "执行完成，可在 runs 页面查看审计和恢复点。"),
                intent_recovery=run,
                execution_intent=analysis.execution_intent.model_dump(),
                risk_context=analysis.risk_context.model_dump(),
                memory_refs=analysis.memory_refs,
                resume_card={
                    "checkpoint_id": checkpoints[-1].checkpoint_id,
                    "run_id": recovered.run_id,
                    "last_safe_step": checkpoints[-1].step_no,
                    "resume_from": f"step {checkpoints[-1].step_no}",
                    "idempotency_key": checkpoints[-1].idempotency_key,
                    "rollback_available": bool(checkpoints[-1].rollback_payload),
                },
                audit_timeline=_audit_timeline(recovered.run_id),
                analysis_steps=analysis_steps,
            ).model_dump()
        )
    except Exception as exc:
        return make_error(str(exc))
