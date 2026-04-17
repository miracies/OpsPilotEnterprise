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
TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")
EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")
VCENTER_ENDPOINT = os.environ.get("VCENTER_ENDPOINT", "https://10.0.80.21:443/sdk")
VCENTER_USERNAME = os.environ.get("VCENTER_USERNAME", "administrator@vsphere.local")
VCENTER_PASSWORD = os.environ.get("VCENTER_PASSWORD", "VMware1!")
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
    r"\u5206\u6790|\u8bca\u65ad|\u6392\u67e5|\u544a\u8b66|\u6839\u56e0|\u5f02\u5e38|\u6545\u969c|\u6392\u969c|\u4e3a\u4ec0\u4e48|\u539f\u56e0|\u68c0\u67e5|\u95ee\u9898|\u4ec0\u4e48\u95ee\u9898",
    re.I,
)
VMWARE_KEYWORDS = re.compile(r"vmware|vcenter|esxi|\u865a\u62df\u673a|\u4e3b\u673a|\u6570\u636e\u5b58\u50a8", re.I)
K8S_KEYWORDS = re.compile(r"k8s|kubernetes|pod|deployment|node|namespace|\u5bb9\u5668|\u96c6\u7fa4", re.I)
HOST_IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DIAGNOSIS_STATUS_SIGNALS = re.compile(
    r"overallstatus|connectionstate|yellow|red|gray|\u975e\u5065\u5eb7|\u4e0d\u5065\u5eb7|\u72b6\u6001\u5f02\u5e38|\u5065\u5eb7\u72b6\u6001",
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
GENERIC_OPS_QA_KEYWORDS = re.compile(
    r"是否会|会不会|会有|影响|中断|丢包|风险|原理|注意事项|最佳实践|怎么避免|如何避免",
    re.I,
)
GENERIC_OPS_QA_CONTEXT = re.compile(
    r"虚拟机|vm|vmotion|热迁移|迁移|主机|esxi|vcenter|vsphere|网络|k8s|kubernetes|pod|deployment|容器|存储|数据库|告警|故障|中断",
    re.I,
)
GENERIC_QA_RISK_KEYWORDS = re.compile(r"生产|中断|丢包|故障|风险|宕机|抖动|失败|回退", re.I)
LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-5-turbo")


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


def _is_vcenter_prod_vm_power_query(message: str) -> bool:
    lowered = message.lower()
    has_platform = any(k in lowered for k in ("vcenter", "vsphere"))
    has_env = any(k in message for k in ("生产", "prod"))
    has_vm = any(k in message for k in ("虚拟机", "vm"))
    has_power = any(k in lowered for k in ("power", "power state")) or any(
        k in message for k in ("电源状态", "开机", "关机", "运行状态")
    )
    return has_platform and has_env and has_vm and has_power


def _extract_vm_name_from_message(message: str) -> str | None:
    patterns = [
        r"(?:打开|开启|启动|开机|关闭|关机)\s*([A-Za-z0-9._-]+)\s*(?:的)?电源",
        r"(?:power\s*on|turn\s*on|open|start|power\s*off|turn\s*off|shutdown|stop)\s+([A-Za-z0-9._-]+)",
        r"(?:虚拟机|\bvm\b)\s*[:：]?\s*([A-Za-z0-9._-]+)",
        r"([A-Za-z0-9._-]+)\s*(?:的)?(?:电源状态|运行状态|power\s*state)",
    ]
    stopwords = {"vcenter", "vsphere", "prod", "生产环境", "生产", "vm", "虚拟机", "power", "state"}
    for p in patterns:
        m = re.search(p, message, re.I)
        if not m:
            continue
        candidate = (m.group(1) or "").strip()
        if candidate and candidate.lower() not in stopwords:
            return candidate
    return None


def _find_vm_by_name(inventory: dict[str, Any], vm_name: str) -> dict[str, Any] | None:
    vms = inventory.get("virtual_machines", []) if isinstance(inventory, dict) else []
    name_l = vm_name.lower()
    for vm in vms:
        if str(vm.get("name", "")).lower() == name_l:
            return vm
    for vm in vms:
        if name_l in str(vm.get("name", "")).lower():
            return vm
    return None


def _extract_power_action(message: str) -> str | None:
    lowered = message.lower()
    if any(k in lowered for k in ("power off", "turn off", "shutdown", "close", "stop")) or any(
        k in message for k in ("关闭", "关机", "断电")
    ):
        return "off"
    if any(k in lowered for k in ("power on", "turn on", "boot", "open", "start")) or any(
        k in message for k in ("打开", "开启", "开机", "启动", "上电")
    ):
        return "on"
    return None


def _is_vm_power_action_intent(message: str) -> bool:
    action = _extract_power_action(message)
    vm_name = _extract_vm_name_from_message(message)
    lowered = message.lower()
    has_context = any(k in lowered for k in ("vcenter", "vsphere", "vm")) or any(
        k in message for k in ("虚拟机", "电源")
    )
    return bool(action and vm_name and has_context)


def _extract_host_target_from_message(message: str) -> str | None:
    ip_match = HOST_IP_PATTERN.search(message)
    if ip_match:
        return ip_match.group(0)
    patterns = [
        r"(?:主机|host)\s*[:：]?\s*([A-Za-z0-9._:-]+)",
        r"([A-Za-z0-9._:-]+)\s*(?:主机|host)",
    ]
    stopwords = {
        "vcenter",
        "vsphere",
        "prod",
        "生产",
        "生产环境",
        "health",
        "status",
        "host",
        "esxi",
        "健康状况",
        "分析",
        "overallstatus",
        "connectionstate",
        "powerstate",
        "yellow",
        "red",
        "green",
        "gray",
    }
    for pattern in patterns:
        m = re.search(pattern, message, re.I)
        if not m:
            continue
        target = (m.group(1) or "").strip()
        target_l = target.lower()
        if target and target_l not in stopwords:
            return target
    return None


def _match_host_from_inventory(hosts: list[dict[str, Any]], target: str) -> dict[str, Any] | None:
    target_l = target.strip().lower()
    for host in hosts:
        name_l = str(host.get("name", "")).strip().lower()
        host_id_l = str(host.get("host_id", "")).strip().lower()
        if target_l and (target_l == name_l or target_l == host_id_l):
            return host
    for host in hosts:
        name_l = str(host.get("name", "")).strip().lower()
        host_id_l = str(host.get("host_id", "")).strip().lower()
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


def _vcenter_connection_input() -> dict[str, Any]:
    return {
        "endpoint": VCENTER_ENDPOINT,
        "username": VCENTER_USERNAME,
        "password": VCENTER_PASSWORD,
        "insecure": True,
    }


def _is_confirmation(message: str) -> bool:
    return bool(CONFIRM_KEYWORDS.search(message.strip()))


async def _query_vcenter_prod_inventory() -> dict | None:
    url = (
        f"{RESOURCE_BFF_URL.rstrip('/')}/api/v1/resources/vcenter/inventory"
        "?connection_id=conn-vcenter-prod"
    )
    try:
        async with httpx.AsyncClient(timeout=240.0) as client:
            resp = await client.get(url)
        body = resp.json()
        if not body.get("success"):
            return None
        return body.get("data", {})
    except Exception:
        return None


async def _invoke_tool_gateway(tool_name: str, input_payload: dict[str, Any]) -> dict[str, Any] | None:
    url = f"{TOOL_GATEWAY_URL.rstrip('/')}/api/v1/invoke/{tool_name}"
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, json={"input": input_payload, "dry_run": False})
        body = resp.json()
        if not body.get("success"):
            return None
        return body.get("data", {})
    except Exception:
        return None


async def _write_audit_log(payload: dict[str, Any]) -> None:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            await client.post(f"{EVENT_INGESTION_URL.rstrip('/')}/api/v1/audit/logs", json=payload)
    except Exception:
        return


def _is_generic_ops_qa_intent(message: str) -> bool:
    if _is_diagnostic_query_intent(message):
        return False
    lowered = message.lower()
    has_context = bool(GENERIC_OPS_QA_CONTEXT.search(message))
    has_keyword = bool(GENERIC_OPS_QA_KEYWORDS.search(message)) or any(
        k in lowered for k in ("packet loss", "downtime", "interrupt", "impact", "risk", "vmotion")
    )
    question_like = ("?" in message) or ("\uFF1F" in message) or any(k in message for k in ("吗", "么"))
    return bool(has_context and (has_keyword or question_like))


def _is_risk_sensitive_question(message: str) -> bool:
    return bool(GENERIC_QA_RISK_KEYWORDS.search(message))


def _is_diagnostic_query_intent(message: str) -> bool:
    lowered = message.lower()
    if DIAGNOSIS_KEYWORDS.search(message):
        return True
    has_platform_context = bool(VMWARE_KEYWORDS.search(message) or K8S_KEYWORDS.search(message))
    if not has_platform_context:
        return False
    has_status_signal = bool(DIAGNOSIS_STATUS_SIGNALS.search(message))
    has_question_signal = any(
        token in lowered
        for token in (
            "what problem",
            "what issue",
            "why",
            "reason",
            "possible issue",
        )
    ) or any(token in message for token in ("什么问题", "可能是什么问题", "怎么回事", "原因"))
    return bool(has_status_signal or has_question_signal)


def _expand_qa_terms(message: str) -> list[str]:
    terms: list[str] = []
    lowered = message.lower()
    if "热迁移" in message or "vmotion" in lowered or "迁移" in message:
        terms.extend(["热迁移", "vMotion", "迁移中断", "丢包"])
    if "丢包" in message:
        terms.extend(["丢包", "网络抖动", "arp"])
    if "中断" in message:
        terms.extend(["中断", "业务连续性", "回退"])
    words = re.findall(r"[A-Za-z0-9._-]{2,}", message)
    for w in words[:8]:
        if w.lower() not in {"vcenter", "vsphere"}:
            terms.append(w)
    zh_words = re.findall(r"[\u4e00-\u9fff]{2,6}", message)
    terms.extend(zh_words[:10])
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        k = t.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(t.strip())
    return out[:15]


async def _knowledge_search_for_ops_qa(message: str) -> tuple[list[dict[str, Any]], list[str]]:
    terms = _expand_qa_terms(message)
    url = f"{RESOURCE_BFF_URL.rstrip('/')}/api/v1/knowledge/articles?status=published"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
        body = resp.json()
        if not body.get("success"):
            return [], terms
        items = (body.get("data") or {}).get("items") or []
        scored: list[tuple[float, dict[str, Any]]] = []
        for it in items:
            title = str(it.get("title", ""))
            summary = str(it.get("content_summary", ""))
            tags = " ".join(str(x) for x in (it.get("tags") or []))
            blob = f"{title} {summary} {tags}".lower()
            score = 0.0
            for t in terms:
                if t.lower() in blob:
                    score += 1.0
            if "迁移" in message and ("vmware" in blob or "vmotion" in blob):
                score += 1.2
            if score > 0:
                scored.append((score, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits: list[dict[str, Any]] = []
        for score, it in scored[:3]:
            hits.append(
                {
                    "id": it.get("id"),
                    "title": it.get("title"),
                    "summary": it.get("content_summary") or "",
                    "score": round(score, 2),
                }
            )
        return hits, terms
    except Exception:
        return [], terms


async def _llm_generic_ops_qa(message: str, evidence_text: str, include_risk_guard: bool) -> str | None:
    if not LLM_API_KEY:
        return None
    payload = {
        "model": LLM_MODEL,
        "temperature": 0.2,
        "max_tokens": 1200,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是资深运维专家。请严格用中文并按段落输出：结论、原理、建议"
                    + ("、验证步骤、回退建议" if include_risk_guard else "")
                    + "。要求：结论明确，建议可执行。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题：{message}\n\n"
                    f"可用知识证据：\n{evidence_text if evidence_text.strip() else '- 未命中知识库'}\n\n"
                    "请优先依据证据回答；证据不足时补充通用最佳实践并明确说明。"
                ),
            },
        ],
    }
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{LLM_API_BASE}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        content = str(msg.get("content") or "").strip()
        return content or None
    except Exception:
        return None


def _is_valid_generic_ops_answer(text: str, include_risk_guard: bool) -> bool:
    content = (text or "").strip()
    if len(content) < 60:
        return False
    required = ["结论", "原理", "建议"]
    if include_risk_guard:
        required.extend(["验证步骤", "回退建议"])
    if any(k not in content for k in required):
        return False
    suspicious = ["用户问题：", "可用知识证据：", "请优先依据证据回答", "你是资深运维专家"]
    return not any(k in content for k in suspicious)


def _fallback_generic_ops_qa_text(message: str, hits: list[dict[str, Any]], include_risk_guard: bool) -> str:
    evidence_hint = "；".join([f"{h.get('title')}" for h in hits[:2]]) if hits else "未命中知识库，以下基于通用实践"
    text = (
        "结论：通常不会出现明显业务中断，但可能存在短暂网络抖动窗口。\n\n"
        "原理：迁移过程中计算状态在源与目标主机切换，虚拟网卡重绑定及 ARP/邻居缓存刷新会带来毫秒到秒级波动；"
        "若目标主机资源紧张或网络配置不一致，抖动会放大。\n\n"
        "建议：\n"
        "1. 迁移前确认目标主机 CPU/内存余量与网络 VLAN/MTU 一致。\n"
        "2. 对关键业务先在低峰时段灰度迁移，避免批量同时迁移。\n"
        "3. 迁移前后对核心链路时延、丢包和应用探针做连续观测。\n"
        f"4. 依据：{evidence_hint}。"
    )
    if include_risk_guard:
        text += (
            "\n\n验证步骤：\n"
            "1. 迁移前后持续 ping 目标服务与网关，记录时延/丢包。\n"
            "2. 对业务健康探针和关键交易接口做连续压测/拨测。\n"
            "3. 对比迁移前后主机与虚机网络/CPU 抖动指标。\n"
            "\n回退建议：\n"
            "1. 发现持续异常时立即暂停批量迁移并回迁异常 VM。\n"
            "2. 保留变更窗口内回退路径，恢复至迁移前稳定节点。\n"
            "3. 回退后复盘网络一致性与目标主机负载瓶颈。"
        )
    return text


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
    if _is_diagnostic_query_intent(message):
        return "RCAAgent", "收集运行时证据并执行故障诊断分析"
    if _is_generic_ops_qa_intent(message):
        return "OpsQAAssistant", "检索知识库并生成结构化通用运维问答"
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
    mode: str | None = None


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


def _append_analysis_step_events(message: dict[str, Any], steps: list[dict[str, Any]] | None) -> None:
    if not steps:
        return
    for step in steps:
        agent = str(step.get("agent") or "Agent")
        status = str(step.get("status") or "in_progress")
        stage_status = "success" if status == "success" else "error" if status == "failed" else "in_progress"
        summary = str(step.get("summary") or "执行完成")
        _append_progress_event(
            message,
            "tool_done" if stage_status == "success" else "tool_error" if stage_status == "error" else "tool_invoking",
            f"{agent}: {summary}",
            stage_status,
            agent_name=agent,
        )


async def _run_orchestrator(session_id: str, message: str, history: list[dict], mode: str | None = None) -> dict | None:
    async with httpx.AsyncClient(timeout=600) as client:
        try:
            endpoint = "/api/v1/orchestrate/chat-v2" if mode == "orchestrator_v2" else "/api/v1/orchestrate/chat"
            resp = await client.post(
                f"{ORCHESTRATOR_URL}{endpoint}",
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
    is_power_query = _is_vcenter_prod_vm_power_query(message)
    is_power_action = _is_vm_power_action_intent(message)
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

    if is_power_action:
        vm_name = _extract_vm_name_from_message(message)
        action = _extract_power_action(message)
        if not vm_name or not action:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": "已识别为虚拟机电源操作，但未完整解析到操作和虚拟机名称，请重试。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户希望执行虚拟机电源操作。",
                    "解析操作类型和虚拟机名称。",
                    "解析参数不完整，等待用户重试。",
                ),
            }
        inventory = await _query_vcenter_prod_inventory()
        if not inventory:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": f"执行失败：无法访问 conn-vcenter-prod，未能处理 {vm_name} 的电源操作。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户希望执行虚拟机电源操作。",
                    "先查询 vCenter inventory 定位目标虚拟机。",
                    "inventory 查询失败。",
                ),
            }
        vm = _find_vm_by_name(inventory, vm_name)
        if not vm:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": f"在 conn-vcenter-prod 中未找到虚拟机 {vm_name}，请确认名称。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户希望执行虚拟机电源操作。",
                    "查询 inventory 并按名称匹配虚拟机。",
                    "目标虚拟机不存在。",
                ),
            }

        current_state = str(vm.get("power_state", "")).lower()
        if action == "on" and current_state in {"poweredon", "powered_on", "on"}:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": f"{vm.get('name', vm_name)} 当前已是开机状态（{vm.get('power_state')}），无需重复执行。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户希望打开虚拟机电源。",
                    "检查当前电源状态后决定是否执行。",
                    "目标虚拟机已开机。",
                ),
            }
        if action == "off" and current_state in {"poweredoff", "powered_off", "off"}:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": f"{vm.get('name', vm_name)} 当前已是关机状态（{vm.get('power_state')}），无需重复执行。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户希望关闭虚拟机电源。",
                    "检查当前电源状态后决定是否执行。",
                    "目标虚拟机已关机。",
                ),
            }

        vm_id = vm.get("vm_id")
        tool_name = "vmware.vm_power_on" if action == "on" else "vmware.vm_power_off"
        result = await _invoke_tool_gateway(
            tool_name,
            {"connection": _vcenter_connection_input(), "vm_id": vm_id},
        )
        if not result:
            await _write_audit_log(
                {
                    "event_type": "execution_failed",
                    "severity": "warning",
                    "actor": "ResourceQueryAgent",
                    "actor_type": "agent",
                    "action": tool_name,
                    "resource_type": "VirtualMachine",
                    "resource_id": vm_id,
                    "resource_name": vm.get("name", vm_name),
                    "outcome": "failure",
                    "reason": "tool call failed",
                    "metadata": {
                        "connection_id": "conn-vcenter-prod",
                        "requested_action": action,
                    },
                }
            )
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": f"已识别电源操作请求，但执行 {tool_name} 失败，请稍后重试。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户希望执行虚拟机电源操作。",
                    "调用 vmware 电源控制工具执行动作。",
                    "工具调用失败。",
                ),
            }
        await _write_audit_log(
            {
                "event_type": "execution_completed",
                "severity": "info",
                "actor": "ResourceQueryAgent",
                "actor_type": "agent",
                "action": tool_name,
                "resource_type": "VirtualMachine",
                "resource_id": vm_id,
                "resource_name": vm.get("name", vm_name),
                "outcome": "success",
                "metadata": {
                    "connection_id": "conn-vcenter-prod",
                    "requested_action": action,
                    "task_id": result.get("task_id"),
                    "power_state_before": vm.get("power_state"),
                },
            }
        )
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": (
                f"已触发 {vm.get('name', vm_name)} 的电源{'开启' if action == 'on' else '关闭'}操作。\n"
                f"- VM ID: {vm_id}\n"
                f"- 当前状态(操作前): {vm.get('power_state')}\n"
                f"- 任务ID: {result.get('task_id', 'N/A')}"
            ),
            "agent_name": "ResourceQueryAgent",
            "tool_traces": [
                {
                    "tool_name": tool_name,
                    "gateway": "tool-gateway",
                    "input_summary": f'{{"connection_id":"conn-vcenter-prod","vm_id":"{vm_id}"}}',
                    "output_summary": f'task_id={result.get("task_id", "N/A")}',
                    "duration_ms": 0,
                    "status": "success",
                    "timestamp": _now(),
                }
            ],
            "evidence_refs": [],
            "evidences": [],
            "reasoning_summary": _reasoning_summary(
                "用户希望执行虚拟机电源操作。",
                "匹配目标虚拟机后调用 vmware 电源控制工具。",
                f"已触发 {tool_name}。",
            ),
        }

    if is_power_query:
        vm_name = _extract_vm_name_from_message(message)
        if not vm_name:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": "已识别为 vCenter 生产环境虚拟机电源状态查询，但未解析到虚拟机名称，请补充例如：Test-VM。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户希望查询 vCenter 生产环境虚拟机电源状态。",
                    "调用 inventory 接口前先解析虚拟机名称。",
                    "未提取到虚拟机名称，等待用户补充。",
                ),
            }
        inventory = await _query_vcenter_prod_inventory()
        if not inventory:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": f"查询失败：无法访问 conn-vcenter-prod，未能获取虚拟机 {vm_name} 的电源状态。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户希望查询指定虚拟机电源状态。",
                    "调用 vCenter inventory 接口定位虚拟机。",
                    "inventory 查询失败。",
                ),
            }
        vm = _find_vm_by_name(inventory, vm_name)
        if not vm:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": f"在 conn-vcenter-prod 中未找到虚拟机 {vm_name}，请确认名称是否正确。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户希望查询指定虚拟机电源状态。",
                    "调用 inventory 并按名称检索虚拟机。",
                    "未检索到目标虚拟机。",
                ),
            }
        power_state = vm.get("power_state", "unknown")
        vm_id = vm.get("vm_id", "")
        summary = inventory.get("summary", {})
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": (
                "vCenter 生产环境（conn-vcenter-prod）虚拟机电源状态查询结果：\n\n"
                f"- 虚拟机名称：{vm.get('name', vm_name)}\n"
                f"- 虚拟机ID：{vm_id}\n"
                f"- 电源状态：{power_state}"
            ),
            "agent_name": "ResourceQueryAgent",
            "tool_traces": [
                {
                    "tool_name": "vmware.get_vcenter_inventory",
                    "gateway": "vmware-skill-gateway",
                    "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                    "output_summary": (
                        f"vms={summary.get('vm_count', 0)}, matched_vm={vm.get('name', vm_name)}, "
                        f"power_state={power_state}"
                    ),
                    "duration_ms": 0,
                    "status": "success",
                    "timestamp": _now(),
                }
            ],
            "evidence_refs": [],
            "evidences": [],
            "reasoning_summary": _reasoning_summary(
                "用户希望查询 vCenter 生产环境指定虚拟机电源状态。",
                "调用 inventory 接口并按 VM 名称匹配目标对象。",
                f"已返回 {vm.get('name', vm_name)} 的电源状态：{power_state}。",
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

    if _is_generic_ops_qa_intent(message):
        include_risk_guard = _is_risk_sensitive_question(message)
        await _write_audit_log(
            {
                "event_type": "generic_qa_started",
                "severity": "info",
                "actor": "OpsQAAssistant",
                "actor_type": "agent",
                "action": "generic_ops_qa",
                "outcome": "success",
                "metadata": {"session_id": session_id},
            }
        )
        hits, terms = await _knowledge_search_for_ops_qa(message)
        await _write_audit_log(
            {
                "event_type": "generic_qa_retrieved",
                "severity": "info",
                "actor": "OpsQAAssistant",
                "actor_type": "agent",
                "action": "knowledge.retrieve",
                "outcome": "success",
                "metadata": {"hits": len(hits), "terms": terms[:8]},
            }
        )
        evidence_text = "\n".join(
            f"- [{h.get('id')}] {h.get('title')}: {h.get('summary', '')}" for h in hits
        )
        llm_text = await _llm_generic_ops_qa(message, evidence_text, include_risk_guard)
        used_fallback = not _is_valid_generic_ops_answer(llm_text or "", include_risk_guard)
        assistant_message = llm_text or _fallback_generic_ops_qa_text(message, hits, include_risk_guard)
        if used_fallback:
            assistant_message = _fallback_generic_ops_qa_text(message, hits, include_risk_guard)
        await _write_audit_log(
            {
                "event_type": "generic_qa_fallback" if used_fallback else "generic_qa_completed",
                "severity": "info" if not used_fallback else "warning",
                "actor": "OpsQAAssistant",
                "actor_type": "agent",
                "action": "generic_ops_qa",
                "outcome": "success",
                "metadata": {"hits": len(hits), "used_fallback": used_fallback},
            }
        )
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": assistant_message,
            "agent_name": "OpsQAAssistant",
            "tool_traces": [
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
                    "tool_name": "llm.chat_completion",
                    "gateway": "llm",
                    "input_summary": '{"template":"结论+原理+建议"}',
                    "output_summary": "used_fallback" if used_fallback else "generated",
                    "duration_ms": 0,
                    "status": "success" if not used_fallback else "warning",
                    "timestamp": _now(),
                },
            ],
            "evidence_refs": [str(h.get("id")) for h in hits if h.get("id")],
            "evidences": [
                {
                    "evidence_id": str(h.get("id") or f"kb-{i}"),
                    "source_type": "knowledge",
                    "summary": f"{h.get('title')}",
                    "confidence": min(0.95, 0.55 + float(h.get("score", 0)) * 0.1),
                    "timestamp": _now(),
                    "raw_data": {"kb_id": h.get("id")},
                }
                for i, h in enumerate(hits, 1)
            ],
            "reasoning_summary": _reasoning_summary(
                "用户提出了通用运维问答问题，需要风险导向解释。",
                "先检索知识库证据，再按固定模板生成结论与建议。",
                "已返回结构化运维问答，并附带验证与回退建议。",
            ),
        }

    is_diag = _is_diagnostic_query_intent(message)
    if is_diag and VMWARE_KEYWORDS.search(message):
        inventory = await _query_vcenter_prod_inventory()
        if not inventory:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": "诊断失败：无法获取 conn-vcenter-prod 的实时资源数据，请稍后重试。",
                "agent_name": "RCAAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "root_cause_candidates": [],
                "recommended_actions": ["检查 vCenter 连接配置与网关服务状态后重试"],
                "diagnosis_id": f"dg-{uuid.uuid4().hex[:12]}",
                "reasoning_summary": _reasoning_summary(
                    "用户希望诊断 vCenter 主机健康状态。",
                    "fallback 路径尝试读取实时 inventory 并定位目标主机。",
                    "未获取到实时数据，未使用 mock 返回。",
                ),
            }

        host_target = _extract_host_target_from_message(message)
        if host_target:
            hosts = inventory.get("hosts", []) if isinstance(inventory.get("hosts", []), list) else []
            matched_host = _match_host_from_inventory(hosts, host_target)
            summary = inventory.get("summary", {})
            if not matched_host:
                sample_hosts = [str(h.get("name", "")) for h in hosts[:8] if h.get("name")]
                return {
                    "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                    "assistant_message": (
                        f"未在 conn-vcenter-prod 中找到主机 {host_target}，当前主机样例："
                        + (", ".join(sample_hosts) if sample_hosts else "无")
                    ),
                    "agent_name": "RCAAgent",
                    "tool_traces": [
                        {
                            "tool_name": "vmware.get_vcenter_inventory",
                            "gateway": "vmware-skill-gateway",
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
                    "evidence_refs": ["ev-fallback-host-not-found"],
                    "evidences": [
                        {
                            "evidence_id": "ev-fallback-host-not-found",
                            "source_type": "inventory",
                            "summary": f"在 vCenter 生产环境中未匹配到主机 {host_target}",
                            "confidence": 0.95,
                            "timestamp": _now(),
                        }
                    ],
                    "root_cause_candidates": [
                        {"description": "目标主机不存在或名称/IP 不一致", "confidence": 0.9, "category": "input"}
                    ],
                    "recommended_actions": ["核对主机名称/IP", "先查询主机清单确认目标对象"],
                    "diagnosis_id": f"dg-{uuid.uuid4().hex[:12]}",
                    "reasoning_summary": _reasoning_summary(
                        "用户希望分析指定主机健康状况。",
                        "读取实时主机清单并按目标名称/IP 匹配。",
                        "未匹配到目标主机。",
                    ),
                }

            host_id = matched_host.get("host_id")
            source = matched_host
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

            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": (
                    f"已完成对主机 {host_name}（目标={host_target}）的健康分析：\n\n"
                    f"- 主机ID：{source.get('host_id', host_id or 'N/A')}\n"
                    f"- 连接状态：{connection_state}\n"
                    f"- 总体状态：{overall_status}\n"
                    f"- CPU 使用率：{cpu_percent if cpu_percent is not None else 'N/A'}%\n"
                    f"- 内存使用率：{memory_percent if memory_percent is not None else 'N/A'}%\n"
                    f"- 承载虚拟机数：{vm_count}\n\n"
                    f"结论：{conclusion}"
                ),
                "agent_name": "RCAAgent",
                "tool_traces": [
                    {
                        "tool_name": "vmware.get_vcenter_inventory",
                        "gateway": "vmware-skill-gateway",
                        "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                        "output_summary": f"matched_host={host_name}",
                        "duration_ms": 0,
                        "status": "success",
                        "timestamp": _now(),
                    },
                ],
                "evidence_refs": ["ev-fallback-host-health"],
                "evidences": [
                    {
                        "evidence_id": "ev-fallback-host-health",
                        "source_type": "host_detail",
                        "summary": (
                            f"主机 {host_name} 状态={overall_status}, "
                            f"CPU={cpu_percent if cpu_percent is not None else 'N/A'}%, "
                            f"Memory={memory_percent if memory_percent is not None else 'N/A'}%"
                        ),
                        "confidence": 0.93,
                        "timestamp": _now(),
                    }
                ],
                "root_cause_candidates": [
                    {"description": conclusion, "confidence": 0.9, "category": "infrastructure"}
                ],
                "recommended_actions": [
                    "检查该主机最近告警与硬件事件",
                    "核对该主机承载虚拟机的资源占用与热点分布",
                ],
                "diagnosis_id": f"dg-{uuid.uuid4().hex[:12]}",
                "reasoning_summary": _reasoning_summary(
                    "用户希望分析指定 vCenter 主机健康状况。",
                    "先查询 inventory 锁定目标主机，再调用 host detail 获取实时指标。",
                    "已返回目标主机的健康分析结果。",
                ),
            }

    if is_diag and (VMWARE_KEYWORDS.search(message) or K8S_KEYWORDS.search(message)):
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": "诊断失败：fallback 路径当前未获取到该类型的实时数据，请稍后重试。",
            "agent_name": "RCAAgent",
            "tool_traces": [],
            "evidence_refs": [],
            "evidences": [],
            "root_cause_candidates": [],
            "recommended_actions": ["检查编排服务状态后重试"],
            "diagnosis_id": f"dg-{uuid.uuid4().hex[:12]}",
            "reasoning_summary": _reasoning_summary(
                "用户希望进行基础设施诊断。",
                "fallback 路径尝试调用实时资源接口。",
                "未获取到足够实时数据，未使用 mock 返回。",
            ),
        }

    return {
        "message_id": f"msg-{uuid.uuid4().hex[:10]}",
        "assistant_message": f"[本地模式] 收到：{message}",
        "agent_name": "Orchestrator",
        "tool_traces": [],
        "evidence_refs": [],
        "root_cause": None,
        "evidences": [],
        "root_cause_candidates": None,
        "recommended_actions": None,
        "diagnosis_id": None,
        "reasoning_summary": _reasoning_summary(
            "用户提出了运维问答或诊断请求。",
            "根据关键词选择本地 fallback 路径。",
            "已返回基础回复，未使用 mock 诊断数据。",
        ),
    }


async def _process_message(session_id: str, assistant_id: str, user_message: str, mode: str | None = None) -> None:
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

        data = await _run_orchestrator(session_id, user_message, history, mode)
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
            target["root_cause"] = data.get("root_cause")
            target["root_cause_candidates"] = data.get("root_cause_candidates")
            target["hypotheses"] = data.get("hypotheses", [])
            target["winning_hypothesis"] = data.get("winning_hypothesis")
            target["counter_evidence_result"] = data.get("counter_evidence_result")
            target["conclusion_status"] = data.get("conclusion_status")
            target["evidence_sufficiency"] = data.get("evidence_sufficiency")
            target["contradictions"] = data.get("contradictions", [])
            target["recommended_actions"] = data.get("recommended_actions")
            target["diagnosis_id"] = data.get("diagnosis_id")
            target["export_file"] = data.get("export_file")
            target["export_columns"] = data.get("export_columns")
            target["ignored_columns"] = data.get("ignored_columns")
            target["analysis_steps"] = data.get("analysis_steps", [])
            target["reasoning_summary"] = data.get("reasoning_summary") or _reasoning_summary(
                "系统已理解并执行用户请求。",
                "调用匹配的 Agent 与工具完成处理。",
                "已返回最终结果。",
            )
            target["kind"] = data.get("kind", "text")
            target["intent_recovery"] = data.get("intent_recovery")
            target["clarify_card"] = data.get("clarify_card")
            target["approval_card"] = data.get("approval_card")
            target["resume_card"] = data.get("resume_card")
            target["audit_timeline"] = data.get("audit_timeline")
            _append_analysis_step_events(target, data.get("analysis_steps", []))
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
                    "root_cause": data.get("root_cause"),
                    "root_cause_candidates": data.get("root_cause_candidates", []),
                    "hypotheses": data.get("hypotheses", []),
                    "winning_hypothesis": data.get("winning_hypothesis"),
                    "counter_evidence_result": data.get("counter_evidence_result"),
                    "conclusion_status": data.get("conclusion_status"),
                    "evidence_sufficiency": data.get("evidence_sufficiency"),
                    "contradictions": data.get("contradictions", []),
                    "evidence_refs": data.get("evidence_refs", []),
                    "evidences": data.get("evidences", []),
                    "analysis_steps": data.get("analysis_steps", []),
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
            "analysis_steps": [],
            "kind": "text",
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

    task = asyncio.create_task(_process_message(session_id, assistant_id, body.message, body.mode))
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

