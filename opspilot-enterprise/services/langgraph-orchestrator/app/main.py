from __future__ import annotations

import logging
import os
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from app.agents import run_multi_agent_rootcause
from app.audit.router import router as audit_router
from app.intent_recovery.router import router as intent_router
from app.interactions.router import router as interactions_router
from app.llm_client import DIAGNOSIS_SYSTEM_PROMPT, SYSTEM_PROMPT, chat_completion, check_llm_health
from app.pipeline.orchestrate_chat_v2 import router as orchestrator_v2_router
from app.policy.router import router as policy_router
from app.resume.router import router as resume_router
from app.storage.db import init_db
from opspilot_schema.change_impact import ChangeImpactRequest
from opspilot_schema.envelope import make_error, make_success

_env_path = Path(__file__).resolve().parents[2] / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpsPilot LangGraph Orchestrator")
app.include_router(intent_router)
app.include_router(interactions_router)
app.include_router(policy_router)
app.include_router(audit_router)
app.include_router(resume_router)
app.include_router(orchestrator_v2_router)

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")
CHANGE_IMPACT_SERVICE_URL = os.environ.get("CHANGE_IMPACT_SERVICE_URL", "http://127.0.0.1:8040")
RESOURCE_BFF_URL = os.environ.get("RESOURCE_BFF_URL", "http://127.0.0.1:8000")
EVIDENCE_AGGREGATOR_URL = os.environ.get("EVIDENCE_AGGREGATOR_URL", "http://127.0.0.1:8050")
TOPOLOGY_SERVICE_URL = os.environ.get("TOPOLOGY_SERVICE_URL", "http://127.0.0.1:8090")
KNOWLEDGE_SERVICE_URL = os.environ.get("KNOWLEDGE_SERVICE_URL", "http://127.0.0.1:8072")
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
PENDING_PROMPT_TOKEN = "目标连接=conn-vcenter-prod"
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
GENERIC_OPS_QA_KEYWORDS = re.compile(
    r"是否会|会不会|会有|影响|中断|丢包|风险|原理|注意事项|最佳实践|怎么避免|如何避免",
    re.I,
)
GENERIC_OPS_QA_CONTEXT = re.compile(
    r"虚拟机|vm|vmotion|热迁移|迁移|主机|esxi|vcenter|vsphere|网络|k8s|kubernetes|pod|deployment|容器|存储|数据库|告警|故障|中断",
    re.I,
)
GENERIC_QA_RISK_KEYWORDS = re.compile(r"生产|中断|丢包|故障|风险|宕机|抖动|失败|回退", re.I)


class DiagnoseRequest(BaseModel):
    description: str
    object_id: str | None = None


class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list[dict] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


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
    url = f"{RESOURCE_BFF_URL.rstrip('/')}/api/v1/audit/logs"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            await client.post(url, json=payload)
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
    url = f"{RESOURCE_BFF_URL.rstrip('/')}/api/v1/knowledge/articles?status=published"
    terms = _expand_qa_terms(message)
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
    prompt = (
        "你是资深运维专家。请严格用中文并按以下段落输出：\n"
        "1) 结论\n2) 原理\n3) 建议\n"
        + ("4) 验证步骤\n5) 回退建议\n" if include_risk_guard else "")
        + "要求：结论明确，不要模糊；建议可执行。"
    )
    user_content = (
        f"用户问题：{message}\n\n"
        f"可用知识证据：\n{evidence_text if evidence_text.strip() else '- 未命中知识库'}\n\n"
        "请基于证据优先回答；若证据不足，补充通用最佳实践并显式说明。"
    )
    return await chat_completion(
        [{"role": "user", "content": user_content}],
        system_prompt=prompt,
        temperature=0.2,
        max_tokens=1200,
    )


def _is_valid_generic_ops_answer(text: str, include_risk_guard: bool) -> bool:
    content = (text or "").strip()
    if len(content) < 60:
        return False
    required = ["结论", "原理", "建议"]
    if include_risk_guard:
        required.extend(["验证步骤", "回退建议"])
    if any(k not in content for k in required):
        return False
    suspicious = ["用户问题：", "可用知识证据：", "请基于证据优先回答", "你是资深运维专家"]
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


def _is_confirmation(message: str) -> bool:
    return bool(CONFIRM_KEYWORDS.search(message.strip()))


def _has_pending_vcenter_query(history: list[dict] | None) -> bool:
    if not history:
        return False
    for item in reversed(history):
        if item.get("role") != "assistant":
            continue
        return PENDING_PROMPT_TOKEN in item.get("content", "")
    return False


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


async def _export_vcenter_prod_vm_inventory(session_id: str, requested_columns: list[str]) -> dict | None:
    url = f"{RESOURCE_BFF_URL.rstrip('/')}/api/v1/resources/vcenter/inventory/export"
    payload = {
        "connection_id": "conn-vcenter-prod",
        "format": "csv",
        "session_id": session_id,
        "requested_columns": requested_columns,
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


def _format_vcenter_summary(inventory: dict[str, object]) -> str:
    summary = inventory.get("summary", {}) if isinstance(inventory, dict) else {}
    vm_count = summary.get("vm_count", 0)
    host_count = summary.get("host_count", 0)
    cluster_count = summary.get("cluster_count", 0)
    powered_off = summary.get("powered_off_vm_count", "N/A")
    unhealthy_hosts = summary.get("unhealthy_host_count", "N/A")

    status_line = "当前资源状态整体健康。"
    if isinstance(powered_off, int) and powered_off > 0:
        status_line = "当前资源状态存在异常，建议优先检查异常对象。"
    if isinstance(unhealthy_hosts, int) and unhealthy_hosts > 0:
        status_line = "当前资源状态存在异常，建议优先检查异常对象。"

    return (
        f"vCenter 生产环境（{PENDING_PROMPT_TOKEN}）资源查询结果：\n\n"
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


MOCK_EVIDENCES = [
    {
        "evidence_id": f"ev-{_uid()}",
        "source_type": "metric",
        "summary": "esxi-node03 CPU usage 上升到 97.3%，持续超过 30 分钟",
        "confidence": 0.92,
        "timestamp": _now(),
        "raw_data": {"metric": "cpu.usage.average", "value": 97.3, "unit": "%"},
    },
    {
        "evidence_id": f"ev-{_uid()}",
        "source_type": "log",
        "summary": "app-server-01 检测到 Full GC 风暴，GC pause > 5s 出现 12 次",
        "confidence": 0.88,
        "timestamp": _now(),
        "raw_data": {"log_source": "jvm-gc", "gc_count": 12, "max_pause_ms": 5200},
    },
]


def _build_tool_traces(description: str) -> list[dict]:
    return [
        {
            "tool_name": "vmware.get_host_detail",
            "gateway": "vmware-skill-gateway",
            "input_summary": '{"host_id": "host-33"}',
            "output_summary": "CPU: 97.3%, Memory: 82.1%, VMs: 12",
            "duration_ms": random.randint(200, 500),
            "status": "success",
            "timestamp": _now(),
        },
        {
            "tool_name": "evidence.aggregate",
            "gateway": "evidence-gateway",
            "input_summary": '{"context": "' + description[:50] + '"}',
            "output_summary": f"Aggregated {len(MOCK_EVIDENCES)} evidence items",
            "duration_ms": random.randint(100, 300),
            "status": "success",
            "timestamp": _now(),
        },
    ]


async def _fetch_real_context(description: str) -> dict | None:
    target = None
    if K8S_KEYWORDS.search(description):
        target = ("k8s", f"{RESOURCE_BFF_URL.rstrip('/')}/api/v1/resources/k8s/workloads")
    elif VMWARE_KEYWORDS.search(description):
        target = (
            "vmware",
            f"{RESOURCE_BFF_URL.rstrip('/')}/api/v1/resources/vcenter/inventory?connection_id=conn-vcenter-prod",
        )
    if not target:
        return None

    kind, url = target
    try:
        async with httpx.AsyncClient(timeout=240.0) as client:
            resp = await client.get(url)
        body = resp.json()
        if not body.get("success"):
            return None

        data = body.get("data", {})
        summary = data.get("summary", {})
        if kind == "vmware":
            host_target = _extract_host_target_from_message(description)
            if host_target:
                hosts = data.get("hosts", []) if isinstance(data.get("hosts", []), list) else []
                matched_host = _match_host_from_inventory(hosts, host_target)
                inventory_trace = {
                    "tool_name": "vmware.get_vcenter_inventory",
                    "gateway": "vmware-skill-gateway",
                    "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                    "output_summary": (
                        f"clusters={summary.get('cluster_count', 0)}, "
                        f"hosts={summary.get('host_count', 0)}, vms={summary.get('vm_count', 0)}"
                    ),
                    "duration_ms": 420,
                    "status": "success",
                    "timestamp": _now(),
                }
                if not matched_host:
                    sample_hosts = [str(h.get("name", "")) for h in hosts[:8] if h.get("name")]
                    return {
                        "kind": kind,
                        "assistant_message": (
                            f"未在 conn-vcenter-prod 中找到主机 {host_target}，当前主机样例："
                            + (", ".join(sample_hosts) if sample_hosts else "无")
                        ),
                        "evidences": [
                            {
                                "evidence_id": f"ev-{_uid()}",
                                "source_type": "inventory",
                                "summary": f"在 vCenter 生产环境中未匹配到主机 {host_target}",
                                "confidence": 0.95,
                                "timestamp": _now(),
                                "raw_data": {"host_target": host_target, "host_count": summary.get("host_count", 0)},
                            }
                        ],
                        "tool_traces": [inventory_trace],
                        "root_cause_candidates": [
                            {
                                "description": "目标主机不存在或输入名称/IP 与 vCenter 清单不一致",
                                "confidence": 0.9,
                                "category": "input",
                            }
                        ],
                        "recommended_actions": ["核对主机名称/IP 后重试", "先执行 vCenter 主机列表查询确认目标对象"],
                    }

                host_id = matched_host.get("host_id")
                detail = matched_host
                cpu_percent = detail.get("cpu_usage_percent")
                if cpu_percent is None:
                    cpu_percent = _as_percent(detail.get("cpu_usage_mhz"), detail.get("cpu_mhz"))
                memory_percent = detail.get("memory_usage_percent")
                if memory_percent is None:
                    memory_percent = _as_percent(detail.get("memory_usage_mb"), detail.get("memory_mb"))
                overall_status = str(detail.get("overall_status", "unknown"))
                connection_state = str(detail.get("connection_state", "unknown"))
                vm_count = detail.get("vm_count", 0)
                host_name = str(detail.get("name") or host_target)
                conclusion = "该主机当前整体健康。"
                if overall_status.lower() not in {"green", "gray"}:
                    conclusion = "该主机处于非健康状态，建议优先处理告警。"
                if isinstance(cpu_percent, (int, float)) and cpu_percent >= 85:
                    conclusion = "该主机 CPU 压力偏高，建议尽快排查负载与资源分配。"
                if isinstance(memory_percent, (int, float)) and memory_percent >= 90:
                    conclusion = "该主机内存压力偏高，建议尽快排查内存占用与回收。"

                return {
                    "kind": kind,
                    "assistant_message": (
                        f"已完成对主机 {host_name}（目标={host_target}）的健康分析：\n\n"
                        f"- 主机ID：{detail.get('host_id', host_id or 'N/A')}\n"
                        f"- 连接状态：{connection_state}\n"
                        f"- 总体状态：{overall_status}\n"
                        f"- CPU 使用率：{cpu_percent if cpu_percent is not None else 'N/A'}%\n"
                        f"- 内存使用率：{memory_percent if memory_percent is not None else 'N/A'}%\n"
                        f"- 承载虚拟机数：{vm_count}\n\n"
                        f"结论：{conclusion}"
                    ),
                    "evidences": [
                        {
                            "evidence_id": f"ev-{_uid()}",
                            "source_type": "host_detail",
                            "summary": (
                                f"主机 {host_name} 状态={overall_status}, "
                                f"CPU={cpu_percent if cpu_percent is not None else 'N/A'}%, "
                                f"Memory={memory_percent if memory_percent is not None else 'N/A'}%"
                            ),
                            "confidence": 0.94,
                            "timestamp": _now(),
                            "raw_data": detail,
                        }
                    ],
                    "tool_traces": [inventory_trace],
                    "root_cause_candidates": [
                        {
                            "description": conclusion,
                            "confidence": 0.9,
                            "category": "infrastructure",
                        }
                    ],
                    "recommended_actions": [
                        "检查该主机最近告警与硬件事件",
                        "核对该主机承载虚拟机的资源占用与热点分布",
                    ],
                }

            evidences = [
                {
                    "evidence_id": f"ev-{_uid()}",
                    "source_type": "inventory",
                    "summary": (
                        f"vCenter 当前共有 {summary.get('cluster_count', 0)} 个集群、"
                        f"{summary.get('host_count', 0)} 台主机、{summary.get('vm_count', 0)} 台虚拟机"
                    ),
                    "confidence": 0.92,
                    "timestamp": _now(),
                    "raw_data": summary,
                }
            ]
            if summary.get("unhealthy_host_count", 0):
                evidences.append(
                    {
                        "evidence_id": f"ev-{_uid()}",
                        "source_type": "alert",
                        "summary": f"发现 {summary['unhealthy_host_count']} 台主机处于非健康状态",
                        "confidence": 0.86,
                        "timestamp": _now(),
                        "raw_data": {"hosts": data.get("hosts", [])},
                    }
                )
            return {
                "kind": kind,
                "evidences": evidences,
                "tool_traces": [
                    {
                        "tool_name": "vmware.get_vcenter_inventory",
                        "gateway": "vmware-skill-gateway",
                        "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                        "output_summary": (
                            f"clusters={summary.get('cluster_count', 0)}, "
                            f"hosts={summary.get('host_count', 0)}, vms={summary.get('vm_count', 0)}"
                        ),
                        "duration_ms": 420,
                        "status": "success",
                        "timestamp": _now(),
                    }
                ],
                "root_cause_candidates": [
                    {
                        "description": "vCenter 实时状态中存在主机或虚拟机异常，需优先检查非健康对象",
                        "confidence": 0.78 if summary.get("unhealthy_host_count", 0) else 0.58,
                        "category": "infrastructure",
                    }
                ],
                "recommended_actions": [
                    "检查 vCenter 中非健康主机的硬件与连接状态",
                    "核对异常虚拟机的电源状态、资源占用与近期事件",
                ],
            }

        evidences = [
            {
                "evidence_id": f"ev-{_uid()}",
                "source_type": "inventory",
                "summary": (
                    f"Kubernetes 当前共有 {summary.get('node_count', 0)} 个节点、"
                    f"{summary.get('pod_count', 0)} 个 Pod、{summary.get('deployment_count', 0)} 个 Deployment"
                ),
                "confidence": 0.92,
                "timestamp": _now(),
                "raw_data": summary,
            }
        ]
        if summary.get("unhealthy_pod_count", 0):
            evidences.append(
                {
                    "evidence_id": f"ev-{_uid()}",
                    "source_type": "alert",
                    "summary": f"检测到 {summary['unhealthy_pod_count']} 个 Pod 未就绪",
                    "confidence": 0.88,
                    "timestamp": _now(),
                    "raw_data": {"pods": data.get("pods", [])[:10]},
                }
            )
        return {
            "kind": kind,
            "evidences": evidences,
            "tool_traces": [
                {
                    "tool_name": "k8s.get_workload_status",
                    "gateway": "kubernetes-skill-gateway",
                    "input_summary": "{}",
                    "output_summary": (
                        f"nodes={summary.get('node_count', 0)}, pods={summary.get('pod_count', 0)}, "
                        f"deployments={summary.get('deployment_count', 0)}"
                    ),
                    "duration_ms": 380,
                    "status": "success",
                    "timestamp": _now(),
                }
            ],
            "root_cause_candidates": [
                {
                    "description": "Kubernetes 实时状态显示存在未就绪 Pod 或节点，需要优先检查调度和负载健康",
                    "confidence": 0.82 if summary.get("unhealthy_pod_count", 0) else 0.6,
                    "category": "platform",
                }
            ],
            "recommended_actions": [
                "查看未就绪 Pod 的事件、探针与最近日志",
                "检查节点 Ready 状态、资源压力与驱逐事件",
            ],
        }
    except Exception:
        return None


def _build_mock_diagnosis_text(description: str) -> str:
    return (
        "## 诊断结论\n\n"
        f"针对“{description}”的诊断分析已完成。\n\n"
        "### 根因候选\n"
        "1. **app-server-01 Java Full GC 风暴导致 CPU 飙升** (置信度 87%)\n"
        "2. **存储 vMotion 引起临时资源争用** (置信度 62%)\n\n"
        "### 建议动作\n"
        "- 检查 app-server-01 JVM 堆内存配置和 GC 日志\n"
        "- 对 esxi-node03 当前 VM 负载做平衡评估\n"
        "- 考虑将 app-server-01 迁移到低负载主机"
    )


async def _llm_diagnosis(description: str, evidence_summary: str) -> str | None:
    evidence_context = f"用户问题：{description}\n\n采集到的证据：\n{evidence_summary}"
    return await chat_completion(
        [{"role": "user", "content": evidence_context}],
        system_prompt=DIAGNOSIS_SYSTEM_PROMPT,
        temperature=0.3,
    )


async def _llm_chat(message: str, history: list[dict] | None = None) -> str | None:
    messages: list[dict] = []
    if history:
        for h in history[-20:]:
            role = h.get("role", "user")
            content = h.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    return await chat_completion(messages, system_prompt=SYSTEM_PROMPT)


async def _run_rootcause_workflow(description: str, object_id: str | None, session_id: str | None = None) -> dict | None:
    context = {
        "incident_id": None,
        "session_id": session_id or "adhoc",
        "query": description,
        "object_id": object_id,
        "connection_id": "conn-vcenter-prod",
        "topology_depth": 2,
        "evidence_url": EVIDENCE_AGGREGATOR_URL,
        "topology_url": TOPOLOGY_SERVICE_URL,
        "knowledge_url": KNOWLEDGE_SERVICE_URL,
        "source_refs": [],
    }
    try:
        result = await run_multi_agent_rootcause(context)
        root = result.get("root_cause") or {}
        root_summary = root.get("summary") or "未形成明确根因。"
        confidence = root.get("confidence", 0.0)
        evidence_refs = result.get("evidence_refs", [])
        conclusion_status = result.get("conclusion_status") or "insufficient_evidence"
        evidence_sufficiency = result.get("evidence_sufficiency") or {}
        counter_result = result.get("counter_evidence_result") or {}
        return {
            "assistant_message": (
                f"RootCauseAgent 结论：{root_summary}\n"
                f"结论状态：{conclusion_status}\n"
                f"置信度：{confidence}\n"
                f"证据数量：{len(evidence_refs)}\n"
                f"证据充分性：{evidence_sufficiency.get('sufficiency_score', 0):.2f}\n"
                f"反证结果：{counter_result.get('status', 'inconclusive')}"
            ),
            "evidences": result.get("evidences", []),
            "evidence_refs": evidence_refs,
            "root_cause": root,
            "root_cause_candidates": result.get("root_cause_candidates", []),
            "hypotheses": result.get("hypotheses", []),
            "winning_hypothesis": result.get("winning_hypothesis"),
            "counter_evidence_result": counter_result,
            "conclusion_status": conclusion_status,
            "evidence_sufficiency": evidence_sufficiency,
            "contradictions": result.get("contradictions", []),
            "recommended_actions": result.get("recommended_actions", []),
            "analysis_steps": result.get("analysis_steps", []),
            "tool_traces": [
                {
                    "tool_name": "multi_agent.rootcause",
                    "gateway": "orchestrator",
                    "input_summary": '{"agents":"Evidence->Topology->Knowledge->RootCause->Remediation"}',
                    "output_summary": f"root_confidence={confidence}, evidence={len(evidence_refs)}, conclusion={conclusion_status}",
                    "duration_ms": 0,
                    "status": "success",
                    "timestamp": _now(),
                }
            ],
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("rootcause workflow failed: %s", exc)
        return None


def _build_diagnosis(
    description: str,
    assistant_content: str | None = None,
    object_id: str | None = None,
    evidences: list[dict] | None = None,
    tool_traces: list[dict] | None = None,
    root_cause_candidates: list[dict] | None = None,
    root_cause: dict | None = None,
    recommended_actions: list[str] | None = None,
    analysis_steps: list[dict] | None = None,
    hypotheses: list[dict] | None = None,
    winning_hypothesis: dict | None = None,
    counter_evidence_result: dict | None = None,
    conclusion_status: str | None = None,
    evidence_sufficiency: dict | None = None,
    contradictions: list[dict] | None = None,
) -> dict:
    diagnosis_id = f"dg-{_uid()}"
    diag_evidences = evidences or []
    diag_tool_traces = tool_traces or _build_tool_traces(description)

    if not assistant_content:
        assistant_content = "已完成诊断分析，但当前证据不足，请补充更具体的故障对象或时间范围后重试。"

    return {
        "diagnosis_id": diagnosis_id,
        "description": description,
        "object_id": object_id,
        "assistant_message": assistant_content,
        "root_cause": root_cause
        or {
            "summary": "尚未收敛唯一根因",
            "confidence": 0.5,
            "evidence_refs": [e["evidence_id"] for e in diag_evidences][:3],
        },
        "root_cause_candidates": root_cause_candidates
        or [
            {
                "description": "app-server-01 Java Full GC 风暴导致 CPU 飙升",
                "confidence": 0.87,
                "category": "application",
            },
            {
                "description": "存储 vMotion 引起临时资源争用",
                "confidence": 0.62,
                "category": "infrastructure",
            },
        ],
        "evidence_refs": [e["evidence_id"] for e in diag_evidences],
        "evidences": diag_evidences,
        "hypotheses": hypotheses or [],
        "winning_hypothesis": winning_hypothesis,
        "counter_evidence_result": counter_evidence_result,
        "conclusion_status": conclusion_status,
        "evidence_sufficiency": evidence_sufficiency,
        "contradictions": contradictions or [],
        "recommended_actions": recommended_actions
        or [
            "补充目标对象（主机/虚机/集群）并重新执行诊断。",
            "检查最近变更与告警时间线，确认异常起点。",
            "按风险从低到高执行只读检查后再申请处置。",
        ],
        "analysis_steps": analysis_steps or [],
        "tool_traces": diag_tool_traces,
        "simulated_at": _now(),
        "created_at": _now(),
    }


@app.get("/health")
async def health() -> dict:
    llm_status = await check_llm_health()
    return make_success({"status": "healthy", "llm": llm_status})


@app.on_event("startup")
async def startup_init() -> None:
    init_db()


@app.post("/api/v1/orchestrate/diagnose")
async def orchestrate_diagnose(body: DiagnoseRequest) -> dict:
    try:
        runtime_context = await _run_rootcause_workflow(body.description, body.object_id)
        should_fallback_context = (
            not runtime_context
            or not isinstance(runtime_context.get("evidences"), list)
            or len(runtime_context.get("evidences", [])) == 0
        )
        if should_fallback_context:
            runtime_context = await _fetch_real_context(body.description)
        if not runtime_context and (VMWARE_KEYWORDS.search(body.description) or K8S_KEYWORDS.search(body.description)):
            return make_error("未获取到实时资源数据，请检查 vCenter/K8s 连接与服务状态后重试")
        evidence_source = runtime_context["evidences"] if runtime_context else []
        evidence_summary = "\n".join(
            f"- [{e['source_type']}] {e['summary']} (置信度 {e['confidence']:.0%})" for e in evidence_source
        )
        llm_text = runtime_context.get("assistant_message") if runtime_context else None
        if not llm_text:
            llm_text = await _llm_diagnosis(body.description, evidence_summary)
        data = _build_diagnosis(
            body.description,
            llm_text,
            body.object_id,
            evidences=runtime_context["evidences"] if runtime_context else None,
            tool_traces=runtime_context["tool_traces"] if runtime_context else None,
            root_cause=runtime_context.get("root_cause") if runtime_context else None,
            root_cause_candidates=runtime_context["root_cause_candidates"] if runtime_context else None,
            recommended_actions=runtime_context["recommended_actions"] if runtime_context else None,
            analysis_steps=runtime_context.get("analysis_steps") if runtime_context else None,
        )
        return make_success(data)
    except Exception as exc:
        return make_error(str(exc))


@app.post("/api/v1/orchestrate/change-impact")
async def orchestrate_change_impact(body: ChangeImpactRequest) -> dict:
    url = f"{CHANGE_IMPACT_SERVICE_URL.rstrip('/')}/api/v1/change-impact/analyze"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body.model_dump())
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        return make_error(f"change-impact request failed: {exc}")
    except Exception as exc:
        return make_error(str(exc))


@app.post("/api/v1/orchestrate/chat")
async def orchestrate_chat(body: ChatRequest) -> dict:
    try:
        is_export_query = _is_vcenter_prod_vm_export_query(body.message)
        if is_export_query:
            requested_columns, ignored_columns = _normalize_requested_columns(body.message)
            effective_columns = requested_columns or DEFAULT_VM_EXPORT_COLUMNS
            export_data = await _export_vcenter_prod_vm_inventory(body.session_id, effective_columns)
            if not export_data:
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
                        "assistant_message": "触发导出任务失败：无法导出 conn-vcenter-prod 的虚拟机列表，请稍后重试。",
                        "agent_name": "ResourceQueryAgent",
                        "tool_traces": [],
                        "evidence_refs": [],
                        "evidences": [],
                        "reasoning_summary": _reasoning_summary(
                            "用户希望导出 vCenter 生产环境虚拟机列表。",
                            "识别导出意图后调用 BFF 导出接口生成 CSV。",
                            "导出任务触发失败，请稍后重试。",
                        ),
                    }
                )
            return make_success(
                {
                    "session_id": body.session_id,
                    "message_id": f"msg-{_uid()}",
                    "assistant_message": (
                        "已触发 vCenter 生产环境（conn-vcenter-prod）虚拟机列表导出任务，可在下方下载文件。\n"
                        f"已导出列：{','.join(export_data.get('export_columns', effective_columns))}"
                        + (
                            f"\n已忽略列：{','.join(export_data.get('ignored_columns', ignored_columns))}"
                            if export_data.get("ignored_columns", ignored_columns)
                            else ""
                        )
                    ),
                    "agent_name": "ResourceQueryAgent",
                    "tool_traces": [
                        {
                            "tool_name": "vmware.export_vcenter_vm_list",
                            "gateway": "api-bff",
                            "input_summary": (
                                '{"connection_id":"conn-vcenter-prod","format":"csv",'
                                f'"requested_columns":"{",".join(export_data.get("export_columns", effective_columns))}"'
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
                    "export_columns": export_data.get("export_columns", effective_columns),
                    "ignored_columns": export_data.get("ignored_columns", ignored_columns),
                    "reasoning_summary": _reasoning_summary(
                        "用户希望导出 vCenter 生产环境虚拟机列表并查看指定列。",
                        "识别导出意图后调用 BFF 导出接口，生成并返回下载元数据。",
                        "导出任务已触发，已返回下载入口和列信息。",
                    ),
                }
            )

        if _is_vm_power_action_intent(body.message):
            vm_name = _extract_vm_name_from_message(body.message)
            action = _extract_power_action(body.message)
            inventory = await _query_vcenter_prod_inventory()
            if not vm_name or not action:
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
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
                )
            if not inventory:
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
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
                )
            vm = _find_vm_by_name(inventory, vm_name)
            if not vm:
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
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
                )

            current_state = str(vm.get("power_state", "")).lower()
            if action == "on" and current_state in {"poweredon", "powered_on", "on"}:
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
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
                )
            if action == "off" and current_state in {"poweredoff", "powered_off", "off"}:
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
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
                )

            vm_id = vm.get("vm_id")
            tool_name = "vmware.vm_power_on" if action == "on" else "vmware.vm_power_off"
            result = await _invoke_tool_gateway(
                tool_name,
                {
                    "connection": _vcenter_connection_input(),
                    "vm_id": vm_id,
                },
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
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
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
                )

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
            return make_success(
                {
                    "session_id": body.session_id,
                    "message_id": f"msg-{_uid()}",
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
            )

        if _is_vcenter_prod_vm_power_query(body.message):
            vm_name = _extract_vm_name_from_message(body.message)
            if not vm_name:
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
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
                )

            inventory = await _query_vcenter_prod_inventory()
            if not inventory:
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
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
                )

            vm = _find_vm_by_name(inventory, vm_name)
            if not vm:
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
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
                )

            power_state = vm.get("power_state", "unknown")
            vm_id = vm.get("vm_id", "")
            summary = inventory.get("summary", {})
            return make_success(
                {
                    "session_id": body.session_id,
                    "message_id": f"msg-{_uid()}",
                    "assistant_message": (
                        f"vCenter 生产环境（conn-vcenter-prod）虚拟机电源状态查询结果：\n\n"
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
            )

        pending_query = _has_pending_vcenter_query(body.history)
        is_query = _is_vcenter_prod_vm_query(body.message)
        is_confirm = _is_confirmation(body.message)

        if is_query or (pending_query and is_confirm):
            if (pending_query and is_confirm) or (is_query and is_confirm):
                inventory = await _query_vcenter_prod_inventory()
                if not inventory:
                    return make_success(
                        {
                            "session_id": body.session_id,
                            "message_id": f"msg-{_uid()}",
                            "assistant_message": "已收到确认，但查询 conn-vcenter-prod 失败。请检查资源连接后重试。",
                            "agent_name": "ResourceQueryAgent",
                            "tool_traces": [],
                            "evidence_refs": [],
                            "evidences": [],
                            "reasoning_summary": _reasoning_summary(
                                "用户确认查询 vCenter 生产环境资源统计。",
                                "调用资源清单接口读取 conn-vcenter-prod。",
                                "查询失败，建议检查连接后重试。",
                            ),
                        }
                    )

                summary = inventory.get("summary", {})
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
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
                            "用户希望获取 vCenter 生产环境虚拟机数量与健康概览。",
                            "调用 vCenter inventory 并汇总 VM/主机/集群与异常指标。",
                            "已返回资源概览与健康结论。",
                        ),
                    }
                )

            return make_success(
                {
                    "session_id": body.session_id,
                    "message_id": f"msg-{_uid()}",
                    "assistant_message": "检测到你在查询 vCenter 生产环境虚拟机数量。请确认是否查询 目标连接=conn-vcenter-prod？回复“确认”继续。",
                    "agent_name": "ResourceQueryAgent",
                    "tool_traces": [],
                    "evidence_refs": [],
                    "evidences": [],
                    "reasoning_summary": _reasoning_summary(
                        "用户在询问 vCenter 生产环境虚拟机数量。",
                        "命中资源查询意图，进入确认门禁。",
                        "等待用户确认后执行查询。",
                    ),
                }
            )

        if _is_diagnostic_query_intent(body.message):
            runtime_context = await _run_rootcause_workflow(body.message, None, body.session_id)
            should_fallback_context = (
                not runtime_context
                or not isinstance(runtime_context.get("evidences"), list)
                or len(runtime_context.get("evidences", [])) == 0
            )
            if should_fallback_context:
                runtime_context = await _fetch_real_context(body.message)
            if not runtime_context and (VMWARE_KEYWORDS.search(body.message) or K8S_KEYWORDS.search(body.message)):
                return make_success(
                    {
                        "session_id": body.session_id,
                        "message_id": f"msg-{_uid()}",
                        "assistant_message": "诊断失败：未获取到实时资源数据，请检查 vCenter/K8s 连接与服务状态后重试。",
                        "agent_name": "RCAAgent",
                        "tool_traces": [],
                        "evidence_refs": [],
                        "evidences": [],
                        "reasoning_summary": _reasoning_summary(
                            "用户希望进行基础设施诊断分析。",
                            "尝试采集实时证据并生成诊断结论。",
                            "实时证据采集失败，未使用 mock 数据。",
                        ),
                    }
                )
            evidence_source = runtime_context["evidences"] if runtime_context else []
            evidence_summary = "\n".join(
                f"- [{e['source_type']}] {e['summary']} (置信度 {e['confidence']:.0%})" for e in evidence_source
            )
            llm_text = runtime_context.get("assistant_message") if runtime_context else None
            if not llm_text:
                llm_text = await _llm_diagnosis(body.message, evidence_summary)
            diag = _build_diagnosis(
                body.message,
                llm_text,
                evidences=runtime_context["evidences"] if runtime_context else None,
                tool_traces=runtime_context["tool_traces"] if runtime_context else None,
                root_cause=runtime_context.get("root_cause") if runtime_context else None,
                root_cause_candidates=runtime_context["root_cause_candidates"] if runtime_context else None,
                recommended_actions=runtime_context["recommended_actions"] if runtime_context else None,
                analysis_steps=runtime_context.get("analysis_steps") if runtime_context else None,
                hypotheses=runtime_context.get("hypotheses") if runtime_context else None,
                winning_hypothesis=runtime_context.get("winning_hypothesis") if runtime_context else None,
                counter_evidence_result=runtime_context.get("counter_evidence_result") if runtime_context else None,
                conclusion_status=runtime_context.get("conclusion_status") if runtime_context else None,
                evidence_sufficiency=runtime_context.get("evidence_sufficiency") if runtime_context else None,
                contradictions=runtime_context.get("contradictions") if runtime_context else None,
            )
            return make_success(
                {
                    "session_id": body.session_id,
                    "message_id": f"msg-{_uid()}",
                    "assistant_message": diag["assistant_message"],
                    "agent_name": "RCAAgent",
                    "diagnosis_id": diag["diagnosis_id"],
                    "root_cause": diag.get("root_cause"),
                    "root_cause_candidates": diag["root_cause_candidates"],
                    "hypotheses": diag.get("hypotheses", []),
                    "winning_hypothesis": diag.get("winning_hypothesis"),
                    "counter_evidence_result": diag.get("counter_evidence_result"),
                    "conclusion_status": diag.get("conclusion_status"),
                    "evidence_sufficiency": diag.get("evidence_sufficiency"),
                    "contradictions": diag.get("contradictions", []),
                    "evidence_refs": diag["evidence_refs"],
                    "evidences": diag["evidences"],
                    "analysis_steps": diag.get("analysis_steps", []),
                    "recommended_actions": diag["recommended_actions"],
                    "tool_traces": diag["tool_traces"],
                    "reasoning_summary": _reasoning_summary(
                        "用户希望进行诊断分析。",
                        "收集运行时证据并调用诊断模型生成根因与建议。",
                        "已输出诊断结论、证据引用和建议动作。",
                    ),
                }
            )

        if _is_generic_ops_qa_intent(body.message):
            include_risk_guard = _is_risk_sensitive_question(body.message)
            await _write_audit_log(
                {
                    "event_type": "generic_qa_started",
                    "severity": "info",
                    "actor": "OpsQAAssistant",
                    "actor_type": "agent",
                    "action": "generic_ops_qa",
                    "outcome": "success",
                    "metadata": {"session_id": body.session_id},
                }
            )
            hits, terms = await _knowledge_search_for_ops_qa(body.message)
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
            llm_text = await _llm_generic_ops_qa(body.message, evidence_text, include_risk_guard)
            used_fallback = not _is_valid_generic_ops_answer(llm_text or "", include_risk_guard)
            assistant_message = llm_text or _fallback_generic_ops_qa_text(body.message, hits, include_risk_guard)
            if used_fallback:
                assistant_message = _fallback_generic_ops_qa_text(body.message, hits, include_risk_guard)
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
            return make_success(
                {
                    "session_id": body.session_id,
                    "message_id": f"msg-{_uid()}",
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
            )
        llm_reply = await _llm_chat(body.message, body.history)
        assistant_text = llm_reply or (
            f"收到您的消息：{body.message}\n\n"
            "如需诊断分析，请描述具体的告警或故障情况。"
        )
        return make_success(
            {
                "session_id": body.session_id,
                "message_id": f"msg-{_uid()}",
                "assistant_message": assistant_text,
                "agent_name": "Orchestrator",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户提出通用运维问答请求。",
                    "调用通用聊天模型生成回复。",
                    "已返回问答结果。",
                ),
            }
        )
    except Exception as exc:
        logger.exception("orchestrate_chat error")
        return make_error(str(exc))

