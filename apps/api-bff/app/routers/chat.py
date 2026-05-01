"""Chat session endpoints - proxy to orchestrator with in-memory session store."""
from __future__ import annotations

import asyncio
import csv
import logging
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.chat_exports import get_export, register_export
from app.services.vmware_intent import (
    RESOURCE_SPECS,
    WRITE_ACTIONS,
    VmwareIntent,
    collection_for_intent,
    count_for_intent,
    filter_label,
    intent_to_dict,
    parse_vmware_intent,
    row_brief,
    row_name,
)
from opspilot_schema.envelope import make_error, make_success

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8010")
RESOURCE_BFF_URL = os.environ.get("RESOURCE_BFF_URL", "http://127.0.0.1:8000")
TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")
TOOL_GATEWAY_FALLBACK_URL = os.environ.get("TOOL_GATEWAY_FALLBACK_URL", "http://127.0.0.1:8020")
EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://127.0.0.1:9090")
DOWNLOAD_BASE_URL = os.environ.get("DOWNLOAD_BASE_URL", "http://127.0.0.1:8000")
CHAT_EXPORT_DIR = Path(os.environ.get("CHAT_EXPORT_DIR", "data/chat_exports"))
DEFAULT_CHAT_MODE = os.environ.get("DEFAULT_CHAT_MODE", "orchestrator_v2").strip().lower()
VCENTER_ENDPOINT = os.environ.get("VCENTER_ENDPOINT", "https://192.168.10.100:443/sdk")
VCENTER_USERNAME = os.environ.get("VCENTER_USERNAME", "shaoyong.chen@vsphere.local")
VCENTER_PASSWORD = os.environ.get("VCENTER_PASSWORD", "VMware1!VMware1!")
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
VMWARE_KEYWORDS = re.compile(r"vmware|vcenter|esxi|\bhost\b|\u865a\u62df\u673a|\u4e3b\u673a|\u6570\u636e\u5b58\u50a8", re.I)
K8S_KEYWORDS = re.compile(r"k8s|kubernetes|pod|deployment|node|namespace|\u5bb9\u5668|\u96c6\u7fa4", re.I)
HOST_IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
HOST_FQDN_PATTERN = re.compile(r"\b[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+\b")
ESX_SHORT_HOST_PATTERN = re.compile(r"\besx\d+\b", re.I)
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
VMWARE_KB_CONTEXT = re.compile(r"vmware|esxi|vcenter|vsphere|broadcom|kb|知识库|文档", re.I)
VMWARE_KB_ACTION = re.compile(
    r"download|install|version|patch|article|compatibility|how do i|where|文档|下载|安装|版本|补丁|兼容|怎么下|如何下载",
    re.I,
)
VMWARE_VERSION_PATTERN = re.compile(r"\b\d+(?:\.\d+){1,3}\b")
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


def _is_vcenter_prod_host_query(message: str) -> bool:
    lowered = message.lower()
    has_platform = any(k in lowered for k in ("vcenter", "vsphere"))
    has_env = any(k in message for k in ("生产", "prod"))
    has_host = any(k in lowered for k in ("esxi", "host")) or any(k in message for k in ("主机",))
    has_count = any(k in message for k in ("多少", "数量", "count"))
    return has_platform and has_env and has_host and has_count


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
    fqdn_match = HOST_FQDN_PATTERN.search(message)
    if fqdn_match and ("esx" in fqdn_match.group(0).lower() or "host" in fqdn_match.group(0).lower()):
        return fqdn_match.group(0)
    esx_match = ESX_SHORT_HOST_PATTERN.search(message)
    if esx_match:
        return esx_match.group(0)
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
        async with httpx.AsyncClient(timeout=240.0, trust_env=False) as client:
            resp = await client.get(url)
        body = resp.json()
        if not body.get("success"):
            return None
        return body.get("data", {})
    except Exception:
        return None


def _is_explicit_host_diagnosis(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    has_diag = bool(DIAGNOSIS_KEYWORDS.search(text) or re.search(r"健康|health|状态|overallstatus", text, re.I))
    has_host = bool(re.search(r"主机|host|esxi", text, re.I))
    has_explicit_target = bool(HOST_IP_PATTERN.search(text) or HOST_FQDN_PATTERN.search(text))
    return has_diag and has_host and has_explicit_target


def _should_prefetch_vmware_inventory(message: str, mode: str | None) -> bool:
    if mode != "orchestrator_v2":
        return False
    text = (message or "").strip()
    if not text or _is_vmware_kb_query_intent(text):
        return False
    vmware_signal = bool(VMWARE_KEYWORDS.search(text) or ESX_SHORT_HOST_PATTERN.search(text))
    if not vmware_signal:
        return False
    if _is_explicit_host_diagnosis(text):
        return False
    return True


def _resource_aliases(name: str) -> list[str]:
    text = (name or "").strip()
    if not text:
        return []
    aliases = [text]
    if "." in text:
        aliases.append(text.split(".", 1)[0])
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _build_vcenter_resource_catalog(inventory: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(inventory, dict):
        return []
    catalog: list[dict[str, Any]] = []
    for host in inventory.get("hosts", []) or []:
        name = str(host.get("name") or "").strip()
        host_id = str(host.get("host_id") or name).strip()
        if not name and not host_id:
            continue
        catalog.append(
            {
                "id": host_id or name,
                "name": name or host_id,
                "aliases": _resource_aliases(name or host_id),
                "type": "host",
                "connection_id": "conn-vcenter-prod",
                "environment": "prod",
            }
        )
    for vm in inventory.get("virtual_machines", []) or []:
        name = str(vm.get("name") or "").strip()
        vm_id = str(vm.get("vm_id") or name).strip()
        if not name and not vm_id:
            continue
        catalog.append(
            {
                "id": vm_id or name,
                "name": name or vm_id,
                "aliases": _resource_aliases(name or vm_id),
                "type": "vm",
                "connection_id": "conn-vcenter-prod",
                "environment": "prod",
            }
        )
    return catalog


def _should_use_local_vcenter_resource_path(message: str) -> bool:
    intent = parse_vmware_intent(message)
    if intent and (intent.action in WRITE_ACTIONS or intent.action in {"count", "list", "summary", "detail", "metric", "capacity", "relationship", "topn"}):
        return True
    if _is_vmware_metric_followup_query(message):
        return True
    return (
        _is_vcenter_prod_vm_query(message)
        or _is_vcenter_prod_host_query(message)
        or _is_vcenter_prod_vm_export_query(message)
        or _is_vcenter_prod_vm_power_query(message)
        or _is_vm_power_action_intent(message)
    )


def _is_vmware_metric_followup_query(message: str) -> bool:
    text = (message or "").strip()
    lowered = text.lower()
    if not text:
        return False
    if "vcenter" in lowered and ("告警" in text or "事件" in text):
        return True
    if "esxi" in lowered and "导出" in text and ("使用率" in text or "报表" in text):
        return True
    if _extract_host_target_from_message(text) and any(
        token in text for token in ("上的虚拟机", "承载虚拟机", "最近事件", "关联 datastore", "关联datastore", "健康状态")
    ):
        return True
    return False


def _is_vcenter_alert_event_query(message: str) -> bool:
    text = message or ""
    lowered = text.lower()
    return "vcenter" in lowered and ("告警" in text or "事件" in text)


def _is_esxi_metric_report_export_query(message: str) -> bool:
    text = message or ""
    lowered = text.lower()
    return "导出" in text and "esxi" in lowered and ("使用率" in text or "报表" in text)


def _is_host_vm_list_followup(message: str) -> bool:
    return bool(_extract_host_target_from_message(message) and any(token in message for token in ("上的虚拟机", "承载虚拟机")))


def _is_host_event_followup(message: str) -> bool:
    return bool(_extract_host_target_from_message(message) and "最近事件" in message)


def _is_host_datastore_latency_followup(message: str) -> bool:
    text = message or ""
    return bool(
        _extract_host_target_from_message(text)
        and ("关联 datastore" in text or "关联datastore" in text)
        and ("延迟" in text or "latency" in text.lower())
    )


def _is_host_health_diagnosis_followup(message: str) -> bool:
    return bool(_extract_host_target_from_message(message) and "健康状态" in message and ("诊断" in message or "分析" in message))


async def _invoke_tool_gateway_with_error(
    tool_name: str,
    input_payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    base_urls: list[str] = []
    for candidate in (
        TOOL_GATEWAY_URL,
        TOOL_GATEWAY_FALLBACK_URL,
        "http://127.0.0.1:8020",
    ):
        if candidate and candidate not in base_urls:
            base_urls.append(candidate)

    last_error: str | None = None
    for base_url in base_urls:
        url = f"{base_url.rstrip('/')}/api/v1/invoke/{tool_name}"
        try:
            async with httpx.AsyncClient(timeout=180.0, trust_env=False) as client:
                resp = await client.post(url, json={"input": input_payload, "dry_run": False})
            body = resp.json()
            if body.get("success"):
                return body.get("data", {}), None
            last_error = str(body.get("error") or "tool invoke failed")
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue
    return None, last_error


async def _invoke_tool_gateway(tool_name: str, input_payload: dict[str, Any]) -> dict[str, Any] | None:
    data, _ = await _invoke_tool_gateway_with_error(tool_name, input_payload)
    return data


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


def _is_vmware_kb_query_intent(message: str) -> bool:
    if _is_diagnostic_query_intent(message):
        return False
    return bool(VMWARE_KB_CONTEXT.search(message) and VMWARE_KB_ACTION.search(message))


def _normalize_vmware_kb_query(message: str) -> str:
    query = message.strip()
    lower = query.lower()
    if "esxi" in lower and "download" not in lower and "下载" not in query:
        query = f"{query} download"
    version_match = VMWARE_VERSION_PATTERN.search(query)
    if version_match and "version" not in lower and "版本" not in query:
        query = f"{query} version {version_match.group(0)}"
    return query.strip()


def _format_vmware_kb_hit_reply(query: str, search_url: str, items: list[dict[str, Any]]) -> tuple[str, list[str]]:
    top_items = [it for it in items if isinstance(it, dict) and it.get("url")][:3]
    refs = [str(it.get("url")) for it in top_items]
    lines = [
        "结论：可通过 Broadcom Support Portal 获取对应 ESXi 版本下载与文档入口，建议优先参考以下官方来源。",
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
            "2. 进入 VMware 产品对应页面，定位 ESXi 9.0.3 下载入口。",
            "3. 下载前核对 release notes、补丁说明与兼容性矩阵。",
            "",
            "注意事项（账号权限/许可/版本匹配）：",
            "1. 没有授权时可能只能查看文档，无法下载安装包。",
            "2. 先确认与现有 vCenter、硬件平台的兼容关系。",
            f"3. 如需自行检索，请使用直链：[打开搜索页]({search_url})，关键词建议：`{query}`。",
        ]
    )
    return "\n".join(lines), refs


def _format_vmware_kb_no_hit_reply(query: str, search_url: str) -> str:
    return (
        "结论：当前未命中高相关 VMware 官方结果，暂不直接给出确定下载链接。\n\n"
        "未命中说明：可能受账号可见范围、关键词写法或版本表达方式影响。\n\n"
        "建议改写关键词：\n"
        f"1. `{query}`\n"
        "2. `ESXi 9.0.3 release notes download`\n"
        "3. `VMware ESXi 9.0.3 patch`\n\n"
        f"Broadcom 搜索直链：[打开搜索页]({search_url})"
    )


async def _invoke_vmware_kb_search_fallback(message: str) -> tuple[dict[str, Any] | None, str | None]:
    query = _normalize_vmware_kb_query(message)
    payload = {
        "query": query,
        "segment": "VC",
        "language": "en_US",
        "page_size": 5,
    }
    data, err = await _invoke_tool_gateway_with_error("vmware.kb_search", payload)
    if not data:
        return None, f"vmware.kb_search 调用失败: {err or 'unknown error'}"
    return data, None


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


METRIC_PROMETHEUS_NAMES = {
    "cpu_usage_percent": "opspilot_vmware_host_cpu_usage_percent",
    "cpu_capacity_mhz": "opspilot_vmware_host_cpu_capacity_mhz",
    "memory_usage_percent": "opspilot_vmware_host_memory_usage_percent",
    "memory_capacity_mb": "opspilot_vmware_host_memory_capacity_mb",
    "datastore_free_percent": "opspilot_vmware_datastore_free_percent",
    "datastore_capacity_gb": "opspilot_vmware_datastore_capacity_gb",
    "datastore_iops": "opspilot_vmware_datastore_iops",
    "datastore_latency_ms": "opspilot_vmware_datastore_latency_ms",
    "datastore_throughput_mbps": "opspilot_vmware_datastore_throughput_mbps",
}

METRIC_UNITS = {
    "cpu_usage_percent": "%",
    "cpu_capacity_mhz": "MHz",
    "memory_usage_percent": "%",
    "memory_capacity_mb": "MB",
    "datastore_free_percent": "%",
    "datastore_capacity_gb": "GB",
    "datastore_iops": "IOPS",
    "datastore_latency_ms": "ms",
    "datastore_throughput_mbps": "MB/s",
}

METRIC_LABELS = {
    "cpu_usage_percent": "CPU 使用率",
    "cpu_capacity_mhz": "CPU 容量",
    "memory_usage_percent": "内存使用率",
    "memory_capacity_mb": "内存容量",
    "datastore_free_percent": "Datastore 剩余容量占比",
    "datastore_capacity_gb": "Datastore 总容量",
    "datastore_iops": "Datastore IOPS",
    "datastore_latency_ms": "Datastore 读写延迟",
    "datastore_throughput_mbps": "Datastore 吞吐量",
}


def _metric_label(metric_name: str | None) -> str:
    return METRIC_LABELS.get(metric_name or "", metric_name or "指标")


def _metric_unit(metric_name: str | None) -> str:
    return METRIC_UNITS.get(metric_name or "", "")


def _metric_value_from_row(row: dict[str, Any], metric_name: str | None) -> float | None:
    try:
        if metric_name == "cpu_usage_percent":
            if row.get("cpu_usage_percent") is not None:
                return round(float(row["cpu_usage_percent"]), 2)
            total = float(row.get("cpu_mhz") or 0)
            used = float(row.get("cpu_usage_mhz") or 0)
            return round(used * 100 / total, 2) if total > 0 else None
        if metric_name == "cpu_capacity_mhz":
            return round(float(row.get("cpu_mhz")), 2)
        if metric_name == "memory_usage_percent":
            if row.get("memory_usage_percent") is not None:
                return round(float(row["memory_usage_percent"]), 2)
            total = float(row.get("memory_mb") or 0)
            used = float(row.get("memory_usage_mb") or 0)
            return round(used * 100 / total, 2) if total > 0 else None
        if metric_name == "memory_capacity_mb":
            return round(float(row.get("memory_mb")), 2)
        if metric_name == "datastore_free_percent":
            capacity = float(row.get("capacity_gb") or 0)
            free = float(row.get("free_gb") or 0)
            return round(free * 100 / capacity, 2) if capacity > 0 else None
        if metric_name == "datastore_capacity_gb":
            return round(float(row.get("capacity_gb")), 2)
        if metric_name and row.get(metric_name) is not None:
            return round(float(row.get(metric_name)), 2)
    except (TypeError, ValueError):
        return None
    return None


def _row_id_for_resource(row: dict[str, Any], resource_type: str | None) -> str:
    if resource_type == "host":
        return str(row.get("host_id") or row.get("id") or row_name(row))
    if resource_type == "vm":
        return str(row.get("vm_id") or row.get("id") or row_name(row))
    if resource_type == "datastore":
        return str(row.get("id") or row.get("datastore_id") or row_name(row))
    if resource_type == "cluster":
        return str(row.get("cluster_id") or row.get("id") or row_name(row))
    return row_name(row)


def _resolve_vmware_rows(inventory: dict[str, Any], intent: VmwareIntent) -> list[dict[str, Any]]:
    rows = collection_for_intent(inventory, intent)
    target = (intent.target_object or "").strip().lower()
    if not target:
        return rows
    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    for row in rows:
        candidates = {
            str(row.get("name") or "").lower(),
            str(row.get("host_id") or "").lower(),
            str(row.get("vm_id") or "").lower(),
            str(row.get("cluster_id") or "").lower(),
            str(row.get("id") or "").lower(),
        }
        if target in candidates:
            exact.append(row)
        elif any(target in item for item in candidates if item):
            partial.append(row)
    return exact or partial


def _aggregation_value(series: list[dict[str, Any]], aggregation: str) -> float | None:
    values: list[float] = []
    for point in series:
        try:
            values.append(float(point.get("value")))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    if aggregation == "avg":
        return round(sum(values) / len(values), 2)
    if aggregation == "max":
        return round(max(values), 2)
    if aggregation == "min":
        return round(min(values), 2)
    return round(values[-1], 2)


def _prometheus_query_for(intent: VmwareIntent, row: dict[str, Any] | None = None) -> str | None:
    metric = METRIC_PROMETHEUS_NAMES.get(intent.metric_name or "")
    if not metric:
        return None
    labels: list[str] = ['connection_id="conn-vcenter-prod"']
    if row is not None:
        if intent.resource_type == "host":
            if row.get("host_id"):
                labels.append(f'host_id="{row.get("host_id")}"')
        elif intent.resource_type == "datastore":
            if row.get("id"):
                labels.append(f'datastore_id="{row.get("id")}"')
        elif intent.resource_type == "vm":
            if row.get("vm_id"):
                labels.append(f'vm_id="{row.get("vm_id")}"')
    return f"{metric}{{{','.join(labels)}}}"


async def _query_prometheus(intent: VmwareIntent, row: dict[str, Any] | None = None) -> dict[str, Any] | None:
    query = _prometheus_query_for(intent, row)
    if not query:
        return None
    base = PROMETHEUS_URL.rstrip("/")
    endpoint = "/api/v1/query_range" if intent.time_range_minutes else "/api/v1/query"
    params: dict[str, Any] = {"query": query}
    if intent.time_range_minutes:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        params.update(
            {
                "start": now_ts - intent.time_range_minutes * 60,
                "end": now_ts,
                "step": intent.step_seconds,
            }
        )
    try:
        async with httpx.AsyncClient(timeout=4.0, trust_env=False) as client:
            resp = await client.get(f"{base}{endpoint}", params=params)
        body = resp.json()
    except Exception:
        return None
    if body.get("status") != "success":
        return None
    result = ((body.get("data") or {}).get("result") or [])
    if not result:
        return None
    first = result[0]
    series: list[dict[str, Any]] = []
    if intent.time_range_minutes:
        for ts, value in first.get("values") or []:
            try:
                series.append({"timestamp": datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat(), "value": float(value)})
            except (TypeError, ValueError):
                continue
    else:
        value_pair = first.get("value") or []
        if len(value_pair) >= 2:
            try:
                series.append({"timestamp": datetime.fromtimestamp(float(value_pair[0]), tz=timezone.utc).isoformat(), "value": float(value_pair[1])})
            except (TypeError, ValueError):
                return None
    value = _aggregation_value(series, intent.aggregation)
    if value is None:
        return None
    return {
        "source": "prometheus",
        "tool_name": "prometheus.query_range" if intent.time_range_minutes else "prometheus.query",
        "query": query,
        "series": series,
        "value": value,
        "unit": _metric_unit(intent.metric_name),
    }


async def _query_vcenter_metric(intent: VmwareIntent, row: dict[str, Any]) -> dict[str, Any] | None:
    object_id = _row_id_for_resource(row, intent.resource_type)
    data, error = await _invoke_tool_gateway_with_error(
        "vmware.query_metrics",
        {
            "connection": _vcenter_connection_input(),
            "object_type": intent.resource_type,
            "object_id": object_id,
            "metric": intent.metric_name,
            "metrics": [intent.metric_name] if intent.metric_name else [],
            "range_minutes": intent.time_range_minutes,
            "step_seconds": intent.step_seconds,
            "source": "vcenter",
        },
    )
    if not data:
        return {"source": "vcenter", "error": error or "metric unavailable", "series": [], "value": None, "unit": _metric_unit(intent.metric_name)}
    series = data.get("series") or []
    if not isinstance(series, list) and isinstance(data.get("metrics"), dict) and intent.metric_name:
        series = (data["metrics"].get(intent.metric_name) or {}).get("series") or []
    normalized = [point for point in series if isinstance(point, dict)]
    value = _aggregation_value(normalized, intent.aggregation)
    return {
        "source": str(data.get("source") or "vcenter"),
        "tool_name": "vmware.query_metrics",
        "series": normalized,
        "value": value,
        "unit": _metric_unit(intent.metric_name),
        "error": None if value is not None else data.get("error"),
    }


def _build_clarify_for_vmware(intent: VmwareIntent, rows: list[dict[str, Any]]) -> dict[str, Any]:
    choices = [
        {
            "id": _row_id_for_resource(row, intent.resource_type),
            "label": row_name(row),
            "description": _row_id_for_resource(row, intent.resource_type),
        }
        for row in rows[:8]
    ]
    return {
        "message_id": f"msg-{uuid.uuid4().hex[:10]}",
        "assistant_message": "匹配到多个 VMware 对象，请补充更精确的对象名称或 ID。",
        "agent_name": "ResourceQueryAgent",
        "tool_traces": [],
        "evidence_refs": [],
        "evidences": [],
        "intent_recovery": {"vmware_intent": intent_to_dict(intent)},
        "clarify_card": {
            "question": "请选择要查询的 VMware 对象",
            "choices": choices,
            "allow_free_text": True,
            "reason_code": "ambiguous_vmware_object",
        },
        "reasoning_summary": _reasoning_summary(
            "用户希望查询 VMware 对象指标或关系。",
            "按本体解析后在 inventory 中定位对象。",
            "对象名称存在多个候选，已请求澄清。",
        ),
    }


async def _format_vmware_metric_or_capacity(intent: VmwareIntent, inventory: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str]:
    rows = _resolve_vmware_rows(inventory, intent)
    if intent.target_object and len(rows) > 1:
        raise ValueError("ambiguous")
    if not rows:
        return "未在 conn-vcenter-prod 中找到匹配的 VMware 对象，请确认名称或 ID。", [], "not_found"
    row = rows[0]
    metric_name = intent.metric_name or ("datastore_free_percent" if intent.resource_type == "datastore" else None)
    direct_value = _metric_value_from_row(row, metric_name) if not intent.time_range_minutes else None
    metric_result: dict[str, Any] | None = None
    if direct_value is None:
        prometheus_result = await _query_prometheus(intent, row)
        metric_result = prometheus_result or await _query_vcenter_metric(intent, row)
    value = direct_value if direct_value is not None else (metric_result or {}).get("value")
    source = "inventory" if direct_value is not None else str((metric_result or {}).get("source") or "vcenter")
    unit = _metric_unit(metric_name)
    if value is None:
        message = f"{row_name(row)} 的 {_metric_label(metric_name)} 当前不可用；该指标可能未由 vCenter 或 Prometheus 暴露。"
        trace = [
            {
                "tool_name": (metric_result or {}).get("tool_name", "vmware.query_metrics"),
                "gateway": source,
                "input_summary": str(intent_to_dict(intent)),
                "output_summary": (metric_result or {}).get("error") or "metric unavailable",
                "duration_ms": 0,
                "status": "error",
                "timestamp": _now(),
            }
        ]
        return message, trace, "metric_unavailable"

    window = f"过去 {intent.time_range_minutes} 分钟" if intent.time_range_minutes else "当前"
    agg = {"avg": "平均", "max": "峰值", "min": "最低", "latest": "最新"}.get(intent.aggregation, intent.aggregation)
    message = (
        f"vCenter 生产环境（conn-vcenter-prod）{row_name(row)} 的 {_metric_label(metric_name)}：\n\n"
        f"- 时间窗口：{window}\n"
        f"- 统计方式：{agg}\n"
        f"- 数值：{value}{unit}\n"
        f"- 数据来源：{source}"
    )
    tool_name = "vmware.get_vcenter_inventory" if source == "inventory" else (metric_result or {}).get("tool_name", "vmware.query_metrics")
    trace = [
        {
            "tool_name": tool_name,
            "gateway": source,
            "input_summary": str(intent_to_dict(intent)),
            "output_summary": f"{metric_name}={value}{unit}",
            "duration_ms": 0,
            "status": "success",
            "timestamp": _now(),
        }
    ]
    return message, trace, f"{metric_name}={value}{unit};source={source}"


def _is_host_cpu_memory_overview_intent(intent: VmwareIntent) -> bool:
    text = intent.raw_text.lower()
    has_cpu = "cpu" in text
    has_memory = "内存" in intent.raw_text or "memory" in text or "mem" in text
    return (
        intent.action == "metric"
        and intent.resource_type == "host"
        and not intent.target_object
        and intent.time_range_minutes > 0
        and has_cpu
        and has_memory
    )


def _fallback_metric_series(value: float | None, minutes: int, step_seconds: int) -> list[dict[str, Any]]:
    if value is None:
        return []
    now = datetime.now(timezone.utc)
    window = max(minutes, 1)
    step = max(step_seconds, 60)
    point_count = max(2, min(24, int((window * 60) / step) + 1))
    start = now - timedelta(minutes=window)
    if point_count == 1:
        offsets = [0]
    else:
        offsets = [round(i * window * 60 / (point_count - 1)) for i in range(point_count)]
    return [
        {
            "timestamp": (start + timedelta(seconds=offset)).isoformat(),
            "value": round(float(value), 2),
            "source": "vcenter_inventory",
        }
        for offset in offsets
    ]


def _series_stats(series: list[dict[str, Any]]) -> dict[str, Any]:
    values: list[float] = []
    for point in series:
        try:
            values.append(float(point.get("value")))
        except (TypeError, ValueError):
            continue
    if not values:
        return {"current": None, "avg": None, "peak": None, "high_minutes": 0, "critical_minutes": 0}
    return {
        "current": round(values[-1], 2),
        "avg": round(sum(values) / len(values), 2),
        "peak": round(max(values), 2),
        "high_minutes": sum(5 for value in values if value >= 80),
        "critical_minutes": sum(5 for value in values if value >= 90),
    }


def _series_point_value(series: list[dict[str, Any]], index: int) -> float | None:
    if index >= len(series):
        return None
    try:
        return float(series[index].get("value"))
    except (TypeError, ValueError):
        return None


def _build_overview_series(host_series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    max_len = max(
        (
            max(len(item.get("cpu_series", []) or []), len(item.get("memory_series", []) or []))
            for item in host_series
        ),
        default=0,
    )
    overview: list[dict[str, Any]] = []
    for idx in range(max_len):
        timestamps = []
        cpu_values: list[float] = []
        memory_values: list[float] = []
        for item in host_series:
            cpu_series = item.get("cpu_series", []) or []
            memory_series = item.get("memory_series", []) or []
            if idx < len(cpu_series):
                timestamps.append(cpu_series[idx].get("timestamp"))
            elif idx < len(memory_series):
                timestamps.append(memory_series[idx].get("timestamp"))
            cpu_value = _series_point_value(cpu_series, idx)
            memory_value = _series_point_value(memory_series, idx)
            if cpu_value is not None:
                cpu_values.append(cpu_value)
            if memory_value is not None:
                memory_values.append(memory_value)
        timestamp = next((str(item) for item in timestamps if item), "")
        if not timestamp:
            continue
        overview.append(
            {
                "timestamp": timestamp,
                "cpu_avg": round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else None,
                "cpu_max": round(max(cpu_values), 2) if cpu_values else None,
                "memory_avg": round(sum(memory_values) / len(memory_values), 2) if memory_values else None,
                "memory_max": round(max(memory_values), 2) if memory_values else None,
            }
        )
    return overview


def _metric_status(summary_stats: dict[str, Any], top_hosts: list[dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    cpu_peak = float((summary_stats.get("cpu") or {}).get("peak") or 0)
    memory_peak = float((summary_stats.get("memory") or {}).get("peak") or 0)
    has_critical = any(
        float(host.get("cpu_peak") or 0) >= 90 or float(host.get("memory_peak") or 0) >= 90
        for host in top_hosts
    )
    has_warning = any(
        float(host.get("cpu_peak") or 0) >= 80 or float(host.get("memory_peak") or 0) >= 80
        for host in top_hosts
    )
    if has_critical:
        status = "异常"
        risk = "存在高风险资源压力"
    elif has_warning:
        status = "偏高"
        risk = "存在资源压力，需要关注持续时间"
    else:
        status = "正常"
        risk = "未发现持续 CPU 或内存饱和"

    insights = [
        f"CPU：集群平均 {(summary_stats.get('cpu') or {}).get('avg', 'N/A')}%，峰值 {cpu_peak:.2f}%。",
        f"内存：集群平均 {(summary_stats.get('memory') or {}).get('avg', 'N/A')}%，峰值 {memory_peak:.2f}%。",
        f"风险：{risk}。",
    ]
    actions: list[str] = []
    if top_hosts:
        primary = top_hosts[0]
        host_name = str(primary.get("name") or primary.get("host_id") or "目标主机")
        if float(primary.get("memory_peak") or 0) >= 80 or float(primary.get("cpu_peak") or 0) >= 80:
            actions.extend(
                [
                    f"查看 {host_name} 上的虚拟机",
                    f"查看 {host_name} 最近事件",
                    f"查看 {host_name} 关联 datastore 延迟",
                    f"诊断 {host_name} 健康状态",
                ]
            )
        else:
            actions.extend(["查看最近vCenter告警和事件", "导出ESXi资源使用率报表"])
    return status, insights, actions


def _metric_next_action_items(actions: list[str], status: str, top_hosts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    top_host = top_hosts[0] if top_hosts else {}
    host_name = str(top_host.get("name") or top_host.get("host_id") or "").strip()
    host_id = str(top_host.get("host_id") or "").strip()
    for label in actions:
        prompt = label
        kind = "query"
        intent: dict[str, Any] = {"domain": "vmware", "status": status}
        target: dict[str, Any] = {}
        if label in {"查看最近 vCenter 告警和事件", "查看最近vCenter告警和事件"}:
            prompt = "查看生产环境最近24小时 vCenter 告警和事件"
            kind = "events"
            intent["action"] = "query_alerts_events"
        elif label in {"导出 ESXi 资源使用率报表", "导出ESXi资源使用率报表"}:
            prompt = "导出生产环境ESXi主机过去1小时CPU和内存使用率报表"
            kind = "export"
            intent["action"] = "export_metric_report"
        elif "上的虚拟机" in label:
            prompt = f"查看生产环境 {host_name} 上的虚拟机"
            kind = "relationship"
            intent["action"] = "list_host_vms"
            target = {"resource_type": "host", "name": host_name, "host_id": host_id}
        elif "最近事件" in label:
            prompt = f"查看生产环境 {host_name} 最近事件"
            kind = "events"
            intent["action"] = "query_host_events"
            target = {"resource_type": "host", "name": host_name, "host_id": host_id}
        elif "关联 datastore 延迟" in label:
            prompt = f"查看生产环境 {host_name} 关联 datastore 延迟"
            kind = "metric"
            intent["action"] = "query_host_datastore_latency"
            target = {"resource_type": "host", "name": host_name, "host_id": host_id}
        elif "健康状态" in label:
            prompt = f"诊断生产环境 {host_name} 健康状态"
            kind = "diagnose"
            intent["action"] = "diagnose_host_health"
            target = {"resource_type": "host", "name": host_name, "host_id": host_id}
        items.append({"label": label, "prompt": prompt, "kind": kind, "target": target, "intent": intent})
    return items


async def _build_host_cpu_memory_metric_result(intent: VmwareIntent, inventory: dict[str, Any]) -> tuple[str, dict[str, Any], list[dict[str, Any]], list[str], str]:
    rows = [row for row in collection_for_intent(inventory, intent) if isinstance(row, dict)]
    if not rows:
        message = "未在 conn-vcenter-prod 中找到 ESXi 主机，无法生成 CPU/内存趋势。"
        metric_result = {
            "scope": "esxi_hosts",
            "window": "1h",
            "source": "none",
            "series": [],
            "host_series": [],
            "summary_stats": {"host_count": 0},
            "top_hosts": [],
            "insights": ["未找到 ESXi 主机。"],
            "next_actions": ["先查询 vCenter 主机清单确认连接状态"],
            "next_action_items": [
                {
                    "label": "先查询 vCenter 主机清单确认连接状态",
                    "prompt": "列出生产环境 ESXi 主机",
                    "kind": "query",
                    "target": {"resource_type": "host"},
                    "intent": {"domain": "vmware", "action": "list_hosts"},
                }
            ],
        }
        return message, metric_result, [], metric_result["next_actions"], "host_count=0"

    metric_names = ("cpu_usage_percent", "memory_usage_percent")
    host_series: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    used_prometheus = False
    prometheus_failed = False

    for row in rows:
        per_host: dict[str, Any] = {
            "host_id": row.get("host_id"),
            "name": row_name(row),
            "cluster_id": row.get("cluster_id"),
        }
        for metric_name in metric_names:
            metric_intent = VmwareIntent(
                domain=intent.domain,
                action="metric",
                resource_type="host",
                environment=intent.environment,
                metric_name=metric_name,
                time_range_minutes=intent.time_range_minutes or 60,
                step_seconds=intent.step_seconds,
                aggregation="latest",
                raw_text=intent.raw_text,
            )
            metric_result = None if prometheus_failed else await _query_prometheus(metric_intent, row)
            if metric_result and metric_result.get("series"):
                used_prometheus = True
                series = metric_result["series"]
                source = "prometheus"
            else:
                if not used_prometheus:
                    prometheus_failed = True
                value = _metric_value_from_row(row, metric_name)
                series = _fallback_metric_series(value, intent.time_range_minutes or 60, intent.step_seconds)
                source = "vcenter_inventory"
            per_host[f"{'cpu' if metric_name == 'cpu_usage_percent' else 'memory'}_series"] = series
            per_host[f"{'cpu' if metric_name == 'cpu_usage_percent' else 'memory'}_source"] = source
        cpu_stats = _series_stats(per_host.get("cpu_series", []) or [])
        memory_stats = _series_stats(per_host.get("memory_series", []) or [])
        per_host.update(
            {
                "cpu_current": cpu_stats["current"],
                "cpu_avg": cpu_stats["avg"],
                "cpu_peak": cpu_stats["peak"],
                "cpu_high_minutes": cpu_stats["high_minutes"],
                "memory_current": memory_stats["current"],
                "memory_avg": memory_stats["avg"],
                "memory_peak": memory_stats["peak"],
                "memory_high_minutes": memory_stats["high_minutes"],
                "max_usage": max(float(cpu_stats["peak"] or 0), float(memory_stats["peak"] or 0)),
                "primary_pressure": "memory" if float(memory_stats["peak"] or 0) >= float(cpu_stats["peak"] or 0) else "cpu",
            }
        )
        host_series.append(per_host)

    overview_series = _build_overview_series(host_series)
    cpu_stats = _series_stats([{"value": item.get("cpu_avg")} for item in overview_series if item.get("cpu_avg") is not None])
    memory_stats = _series_stats([{"value": item.get("memory_avg")} for item in overview_series if item.get("memory_avg") is not None])
    cpu_peak = max((float(item.get("cpu_max") or 0) for item in overview_series), default=0)
    memory_peak = max((float(item.get("memory_max") or 0) for item in overview_series), default=0)
    cpu_stats["peak"] = round(cpu_peak, 2)
    memory_stats["peak"] = round(memory_peak, 2)

    top_hosts = sorted(host_series, key=lambda item: float(item.get("max_usage") or 0), reverse=True)[:5]
    summary_stats = {
        "host_count": len(rows),
        "cpu": cpu_stats,
        "memory": memory_stats,
        "thresholds": {"warning": 80, "critical": 90},
    }
    status, insights, next_actions = _metric_status(summary_stats, top_hosts)
    next_action_items = _metric_next_action_items(next_actions, status, top_hosts)
    source = "prometheus" if used_prometheus else "vcenter_inventory"
    source_label = "Prometheus" if used_prometheus else "vCenter 实时 inventory（Prometheus 无可用历史数据）"
    top_names = "、".join(str(host.get("name")) for host in top_hosts[:3] if host.get("name")) or "无"
    message = (
        f"过去 1 小时生产环境 {len(rows)} 台 ESXi 主机 CPU/内存整体状态：{status}。\n\n"
        "关键结论：\n"
        f"- CPU：集群平均 {cpu_stats.get('avg', 'N/A')}%，峰值 {cpu_stats.get('peak', 'N/A')}%。\n"
        f"- 内存：集群平均 {memory_stats.get('avg', 'N/A')}%，峰值 {memory_stats.get('peak', 'N/A')}%。\n"
        f"- 重点主机：{top_names}。\n"
        f"- 数据来源：{source_label}。\n"
        f"- 建议：{next_actions[0] if next_actions else '继续观察最近告警和资源趋势。'}"
    )
    traces.append(
        {
            "tool_name": "prometheus.query_range" if used_prometheus else "vmware.get_vcenter_inventory",
            "gateway": source,
            "input_summary": str(intent_to_dict(intent)),
            "output_summary": f"hosts={len(rows)};cpu_peak={cpu_stats.get('peak')};memory_peak={memory_stats.get('peak')}",
            "duration_ms": 0,
            "status": "success",
            "timestamp": _now(),
        }
    )
    metric_result = {
        "scope": "esxi_hosts",
        "window": "1h",
        "source": source,
        "metrics": [
            {"name": "cpu_usage_percent", "label": "CPU 使用率", "unit": "%"},
            {"name": "memory_usage_percent", "label": "内存使用率", "unit": "%"},
        ],
        "series": overview_series,
        "host_series": host_series,
        "summary_stats": summary_stats,
        "top_hosts": top_hosts,
        "insights": insights,
        "next_actions": next_actions,
        "next_action_items": next_action_items,
        "status": status,
    }
    return message, metric_result, traces, next_actions, f"hosts={len(rows)};status={status};source={source}"


def _latest_esxi_metric_result(session_id: str) -> dict[str, Any] | None:
    for message in reversed(_messages.get(session_id, [])):
        metric_result = message.get("metric_result")
        if isinstance(metric_result, dict) and metric_result.get("scope") == "esxi_hosts":
            return metric_result
    return None


def _host_from_message(inventory: dict[str, Any], message: str) -> dict[str, Any] | None:
    target = _extract_host_target_from_message(message)
    if not target:
        return None
    hosts = inventory.get("hosts", []) if isinstance(inventory.get("hosts", []), list) else []
    return _match_host_from_inventory(hosts, target)


def _host_identity(host: dict[str, Any] | None) -> tuple[str, str]:
    if not host:
        return "", ""
    return str(host.get("host_id") or host.get("id") or host.get("name") or ""), str(host.get("name") or host.get("host_id") or "")


def _severity_rank(item: dict[str, Any]) -> int:
    value = str(item.get("severity") or item.get("level") or item.get("status") or "").lower()
    if value in {"critical", "error", "red"}:
        return 0
    if value in {"warning", "warn", "yellow"}:
        return 1
    return 2


async def _query_vcenter_alerts_and_events(host: dict[str, Any] | None = None, hours: int = 24) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    traces: list[dict[str, Any]] = []
    connection = _vcenter_connection_input()
    host_id, host_name = _host_identity(host)
    alerts_data, alerts_error = await _invoke_tool_gateway_with_error("vmware.query_alerts", {"connection": connection})
    alerts = []
    if alerts_data:
        alerts = [item for item in (alerts_data.get("alerts") or []) if isinstance(item, dict)]
        if host_name:
            alerts = [
                item
                for item in alerts
                if host_id in {str(item.get("object_id") or ""), str(item.get("entity_id") or "")}
                or host_name.lower() in str(item.get("object_name") or item.get("summary") or item.get("message") or "").lower()
            ]
    traces.append(
        {
            "tool_name": "vmware.query_alerts",
            "gateway": "tool-gateway",
            "input_summary": '{"connection_id":"conn-vcenter-prod"}',
            "output_summary": f"alerts={len(alerts)}" if alerts_data else (alerts_error or "query failed"),
            "duration_ms": 0,
            "status": "success" if alerts_data else "error",
            "timestamp": _now(),
        }
    )

    object_id = host_id or "conn-vcenter-prod"
    events_data, events_error = await _invoke_tool_gateway_with_error(
        "vmware.query_events",
        {"connection": connection, "object_id": object_id, "hours": hours},
    )
    events = []
    if events_data:
        events = [item for item in (events_data.get("events") or []) if isinstance(item, dict)]
    traces.append(
        {
            "tool_name": "vmware.query_events",
            "gateway": "tool-gateway",
            "input_summary": f'{{"object_id":"{object_id}","hours":{hours}}}',
            "output_summary": f"events={len(events)}" if events_data else (events_error or "query failed"),
            "duration_ms": 0,
            "status": "success" if events_data else "error",
            "timestamp": _now(),
        }
    )
    return sorted(alerts, key=_severity_rank), events, traces


async def _build_vcenter_alert_event_data(message: str, inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    host = _host_from_message(inventory or {}, message) if inventory else None
    host_id, host_name = _host_identity(host)
    alerts, events, traces = await _query_vcenter_alerts_and_events(host, hours=24)
    scope = f"主机 {host_name}" if host_name else "vCenter 生产环境"
    lines = [
        f"{scope} 最近 24 小时告警和事件：",
        "",
        f"- 活跃/异常告警：{len(alerts)} 条",
        f"- 事件：{len(events)} 条",
    ]
    if alerts:
        lines.append("- 告警 Top5：")
        for idx, item in enumerate(alerts[:5], 1):
            lines.append(
                f"  {idx}. [{item.get('severity') or item.get('level') or 'info'}] "
                f"{item.get('object_name') or host_name or item.get('object_id') or '对象'}："
                f"{item.get('summary') or item.get('message') or '无摘要'}"
            )
    else:
        lines.append("- 告警 Top5：无")
    if events:
        lines.append("- 最近事件 Top5：")
        for idx, item in enumerate(events[:5], 1):
            lines.append(
                f"  {idx}. [{item.get('level') or item.get('severity') or 'info'}] "
                f"{item.get('created_time') or item.get('timestamp') or 'N/A'} "
                f"{item.get('message') or item.get('event_type') or item.get('type') or '事件'}"
            )
    else:
        lines.append("- 最近事件 Top5：无或当前数据源未返回事件")
    if not alerts and not events:
        lines.append("\n结论：当前未发现可展示的告警或事件；如仍怀疑风险，可继续发起主机健康诊断或扩大时间窗口。")

    return {
        "message_id": f"msg-{uuid.uuid4().hex[:10]}",
        "assistant_message": "\n".join(lines),
        "agent_name": "ResourceQueryAgent",
        "tool_traces": traces,
        "evidence_refs": [],
        "evidences": [],
        "recommended_actions": (["诊断生产环境 " + host_name + " 健康状态"] if host_name else ["过去1小时，esxi主机的cpu使用率和内存使用率"]),
        "reasoning_summary": _reasoning_summary(
            "用户希望查看 vCenter 告警和事件。",
            "调用 VMware 告警和事件只读工具，按目标对象和最近 24 小时汇总。",
            f"已返回告警 {len(alerts)} 条、事件 {len(events)} 条。",
        ),
    }


def _format_report_number(value: Any) -> str:
    if isinstance(value, (int, float)):
        return str(round(float(value), 2))
    return ""


def _write_esxi_metric_report(metric_result: dict[str, Any], session_id: str | None) -> dict[str, Any]:
    CHAT_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    file_name = f"vcenter-conn-vcenter-prod-esxi-usage-{now.strftime('%Y%m%dT%H%M%SZ')}.csv"
    file_path = CHAT_EXPORT_DIR / file_name
    columns = [
        "host_id",
        "name",
        "cpu_current_percent",
        "cpu_avg_percent",
        "cpu_peak_percent",
        "cpu_high_minutes",
        "memory_current_percent",
        "memory_avg_percent",
        "memory_peak_percent",
        "memory_high_minutes",
        "primary_pressure",
        "source",
        "window",
    ]
    with file_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for host in metric_result.get("host_series") or metric_result.get("top_hosts") or []:
            if not isinstance(host, dict):
                continue
            writer.writerow(
                {
                    "host_id": host.get("host_id") or "",
                    "name": host.get("name") or "",
                    "cpu_current_percent": _format_report_number(host.get("cpu_current")),
                    "cpu_avg_percent": _format_report_number(host.get("cpu_avg")),
                    "cpu_peak_percent": _format_report_number(host.get("cpu_peak")),
                    "cpu_high_minutes": host.get("cpu_high_minutes") or 0,
                    "memory_current_percent": _format_report_number(host.get("memory_current")),
                    "memory_avg_percent": _format_report_number(host.get("memory_avg")),
                    "memory_peak_percent": _format_report_number(host.get("memory_peak")),
                    "memory_high_minutes": host.get("memory_high_minutes") or 0,
                    "primary_pressure": host.get("primary_pressure") or "",
                    "source": metric_result.get("source") or "",
                    "window": metric_result.get("window") or "",
                }
            )
    record = register_export(file_path=file_path, file_name=file_name, session_id=session_id)
    download_path = f"/api/v1/chat/exports/{record.export_id}/download"
    payload = record.to_api_dict(download_url=download_path)
    payload["export_columns"] = columns
    payload["ignored_columns"] = []
    return payload


async def _build_esxi_metric_report_export_data(session_id: str, message: str) -> dict[str, Any]:
    metric_result = _latest_esxi_metric_result(session_id)
    traces: list[dict[str, Any]] = []
    if not metric_result:
        inventory = await _query_vcenter_prod_inventory()
        if not inventory:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": "导出失败：无法获取 conn-vcenter-prod 的 ESXi 指标数据，请稍后重试。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary("用户希望导出 ESXi 使用率报表。", "尝试重新查询最近 1 小时 CPU/内存指标。", "指标查询失败。"),
            }
        intent = VmwareIntent(
            domain="vmware",
            action="metric",
            resource_type="host",
            environment="prod",
            metric_name="cpu_usage_percent",
            time_range_minutes=60,
            step_seconds=300,
            raw_text=message,
        )
        _, metric_result, traces, _, _ = await _build_host_cpu_memory_metric_result(intent, inventory)
    export_data = _write_esxi_metric_report(metric_result, session_id)
    return {
        "message_id": f"msg-{uuid.uuid4().hex[:10]}",
        "assistant_message": (
            "已导出生产环境 ESXi 主机过去 1 小时 CPU/内存使用率报表，可在下方下载文件。\n"
            f"- 主机数量：{(metric_result.get('summary_stats') or {}).get('host_count', len(metric_result.get('host_series') or []))}\n"
            f"- 数据来源：{metric_result.get('source') or 'unknown'}\n"
            f"- 文件：{export_data.get('file_name')}"
        ),
        "agent_name": "ResourceQueryAgent",
        "tool_traces": traces
        + [
            {
                "tool_name": "vmware.export_esxi_metric_report",
                "gateway": "api-bff",
                "input_summary": '{"connection_id":"conn-vcenter-prod","window":"1h","metrics":"cpu,memory"}',
                "output_summary": export_data.get("file_name", "esxi-usage.csv"),
                "duration_ms": 0,
                "status": "success",
                "timestamp": _now(),
            }
        ],
        "evidence_refs": [],
        "evidences": [],
        "export_file": export_data,
        "export_columns": export_data.get("export_columns", []),
        "ignored_columns": [],
        "reasoning_summary": _reasoning_summary(
            "用户希望导出 ESXi 资源使用率报表。",
            "优先复用当前会话最近一次指标结果，没有缓存时重新查询。",
            "已生成 CSV 下载文件。",
        ),
    }


async def _build_host_vm_list_data(message: str, inventory: dict[str, Any]) -> dict[str, Any]:
    host = _host_from_message(inventory, message)
    if not host:
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": "未找到目标 ESXi 主机，请确认主机名称或 ID。",
            "agent_name": "ResourceQueryAgent",
            "tool_traces": [],
            "evidence_refs": [],
            "evidences": [],
            "reasoning_summary": _reasoning_summary("用户希望查看主机上的虚拟机。", "读取 inventory 并匹配目标主机。", "未匹配到目标主机。"),
        }
    host_id, host_name = _host_identity(host)
    vms = [
        vm
        for vm in inventory.get("virtual_machines", []) or []
        if isinstance(vm, dict)
        and (
            str(vm.get("host_id") or "") == host_id
            or str(vm.get("host_name") or "").lower() == host_name.lower()
            or host_name.lower() in str(vm.get("host_name") or "").lower()
        )
    ]
    lines = [
        f"生产环境 {host_name} 上的虚拟机：",
        "",
        f"- 匹配数量：{len(vms)}",
    ]
    if vms:
        lines.append("- 对象清单：")
        for idx, vm in enumerate(vms[:20], 1):
            lines.append(f"  {idx}. {row_brief(vm, 'vm')}")
        if len(vms) > 20:
            lines.append(f"  ... 还有 {len(vms) - 20} 台未展示")
    else:
        lines.append("- 对象清单：无匹配对象或当前 inventory 未包含 host_id 关联。")
    return {
        "message_id": f"msg-{uuid.uuid4().hex[:10]}",
        "assistant_message": "\n".join(lines),
        "agent_name": "ResourceQueryAgent",
        "tool_traces": [
            {
                "tool_name": "vmware.get_vcenter_inventory",
                "gateway": "vmware-skill-gateway",
                "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                "output_summary": f"host={host_name};vms={len(vms)}",
                "duration_ms": 0,
                "status": "success",
                "timestamp": _now(),
            }
        ],
        "evidence_refs": [],
        "evidences": [],
        "recommended_actions": [f"诊断生产环境 {host_name} 健康状态", f"查看生产环境 {host_name} 最近事件"],
        "reasoning_summary": _reasoning_summary("用户希望查看主机承载的虚拟机。", "基于实时 inventory 按 host_id/host_name 派生 VM 清单。", f"匹配到 {len(vms)} 台虚拟机。"),
    }


async def _build_host_datastore_latency_data(message: str, inventory: dict[str, Any]) -> dict[str, Any]:
    host = _host_from_message(inventory, message)
    if not host:
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": "未找到目标 ESXi 主机，无法查询关联 datastore 延迟。",
            "agent_name": "ResourceQueryAgent",
            "tool_traces": [],
            "evidence_refs": [],
            "evidences": [],
            "reasoning_summary": _reasoning_summary("用户希望查看主机关联 datastore 延迟。", "读取 inventory 并匹配目标主机。", "未匹配到目标主机。"),
        }
    host_id, host_name = _host_identity(host)
    related: list[dict[str, Any]] = []
    for ds in inventory.get("datastores", []) or []:
        if not isinstance(ds, dict):
            continue
        host_ids = {str(item) for item in ds.get("host_ids", []) or []}
        host_names = {str(item).lower() for item in ds.get("host_names", []) or []}
        if host_id in host_ids or host_name.lower() in host_names:
            related.append(ds)
    traces: list[dict[str, Any]] = [
        {
            "tool_name": "vmware.get_vcenter_inventory",
            "gateway": "vmware-skill-gateway",
            "input_summary": '{"connection_id":"conn-vcenter-prod"}',
            "output_summary": f"host={host_name};datastores={len(related)}",
            "duration_ms": 0,
            "status": "success",
            "timestamp": _now(),
        }
    ]
    rows: list[tuple[dict[str, Any], float | None, str]] = []
    for ds in related[:10]:
        metric_intent = VmwareIntent(
            domain="vmware",
            action="metric",
            resource_type="datastore",
            environment="prod",
            metric_name="datastore_latency_ms",
            time_range_minutes=60,
            step_seconds=300,
            aggregation="avg",
            raw_text=message,
        )
        result = await _query_prometheus(metric_intent, ds)
        value = (result or {}).get("value")
        source = str((result or {}).get("source") or "unavailable")
        rows.append((ds, float(value) if isinstance(value, (int, float)) else None, source))
    lines = [
        f"生产环境 {host_name} 关联 datastore 最近 1 小时延迟：",
        "",
        f"- 关联 datastore：{len(related)} 个",
    ]
    if rows:
        lines.append("- 延迟指标：")
        for idx, (ds, value, source) in enumerate(rows, 1):
            value_text = f"{round(value, 2)}ms" if value is not None else "不可用"
            lines.append(f"  {idx}. {row_name(ds)}：{value_text}（来源：{source}）")
    else:
        lines.append("- 延迟指标：无关联 datastore 或当前 inventory 未包含关联信息。")
    if not any(value is not None for _, value, _ in rows):
        lines.append("\n说明：当前未取得 datastore 延迟历史数据，可继续查看 datastore 容量或主机最近事件辅助判断。")
    traces.append(
        {
            "tool_name": "prometheus.query_range",
            "gateway": "prometheus",
            "input_summary": '{"metric":"datastore_latency_ms","window":"1h"}',
            "output_summary": f"datastores={len(rows)};available={sum(1 for _, value, _ in rows if value is not None)}",
            "duration_ms": 0,
            "status": "success" if any(value is not None for _, value, _ in rows) else "warning",
            "timestamp": _now(),
        }
    )
    return {
        "message_id": f"msg-{uuid.uuid4().hex[:10]}",
        "assistant_message": "\n".join(lines),
        "agent_name": "ResourceQueryAgent",
        "tool_traces": traces,
        "evidence_refs": [],
        "evidences": [],
        "recommended_actions": [f"查看生产环境 {host_name} 最近事件", f"诊断生产环境 {host_name} 健康状态"],
        "reasoning_summary": _reasoning_summary("用户希望查看主机关联 datastore 延迟。", "基于 inventory 对齐关联 datastore，并查询最近 1 小时延迟指标。", "已返回可用延迟数据或不可用说明。"),
    }


def _format_vmware_relationship(intent: VmwareIntent, inventory: dict[str, Any]) -> tuple[str, str]:
    rows = _resolve_vmware_rows(inventory, intent)
    if not rows:
        return "未在 conn-vcenter-prod 中找到匹配的 VMware 对象，请确认名称或 ID。", "not_found"
    row = rows[0]
    target = intent.relationship_target or ("datastore" if intent.resource_type == "host" else "host")
    related: list[dict[str, Any]] = []
    if intent.resource_type == "host" and target == "datastore":
        host_id = str(row.get("host_id") or "")
        host_name = str(row.get("name") or "")
        for ds in inventory.get("datastores", []) or []:
            host_ids = [str(item) for item in ds.get("host_ids", []) or []]
            host_names = [str(item) for item in ds.get("host_names", []) or []]
            if host_id in host_ids or host_name in host_names:
                related.append(ds)
        if not related and isinstance(row.get("datastores"), list):
            related = [item for item in row["datastores"] if isinstance(item, dict)]
    elif intent.resource_type == "host" and target == "vm":
        host_id = str(row.get("host_id") or "")
        related = [vm for vm in inventory.get("virtual_machines", []) or [] if isinstance(vm, dict) and str(vm.get("host_id") or "") == host_id]
        if not related and isinstance(row.get("vms"), list):
            related = [item for item in row["vms"] if isinstance(item, dict)]
    elif intent.resource_type == "datastore" and target == "host":
        host_ids = {str(item) for item in row.get("host_ids", []) or []}
        host_names = {str(item) for item in row.get("host_names", []) or []}
        related = [
            host
            for host in inventory.get("hosts", []) or []
            if isinstance(host, dict) and (str(host.get("host_id") or "") in host_ids or str(host.get("name") or "") in host_names)
        ]
    lines = [
        f"vCenter 生产环境（conn-vcenter-prod）{row_name(row)} 关联的 {RESOURCE_SPECS[target].label}：",
        "",
        f"- 匹配数量：{len(related)}",
    ]
    if related:
        lines.append("- 对象清单：")
        for idx, item in enumerate(related[:20], start=1):
            lines.append(f"  {idx}. {row_brief(item, target)}")
        if len(related) > 20:
            lines.append(f"  ... 还有 {len(related) - 20} 个对象未展示")
    else:
        lines.append("- 对象清单：无匹配对象或当前 inventory 未包含该关联")
    return "\n".join(lines), f"relationship_matches={len(related)}"


async def _format_vmware_topn(intent: VmwareIntent, inventory: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str]:
    rows = collection_for_intent(inventory, intent)
    scored: list[tuple[float, dict[str, Any], str]] = []
    for row in rows:
        metric_result = await _query_prometheus(intent, row)
        value = (metric_result or {}).get("value")
        source = str((metric_result or {}).get("source") or "inventory")
        if value is None:
            value = _metric_value_from_row(row, intent.metric_name)
        if value is None:
            continue
        scored.append((float(value), row, source))
    reverse = intent.aggregation != "min" and "最低" not in intent.raw_text and "最小" not in intent.raw_text
    scored.sort(key=lambda item: item[0], reverse=reverse)
    top_rows = scored[: intent.limit]
    unit = _metric_unit(intent.metric_name)
    lines = [
        f"vCenter 生产环境（conn-vcenter-prod）{_metric_label(intent.metric_name)} Top {intent.limit}：",
        "",
        f"- 排序方向：{'从高到低' if reverse else '从低到高'}",
        "- 对象清单：",
    ]
    if top_rows:
        for idx, (value, row, source) in enumerate(top_rows, start=1):
            lines.append(f"  {idx}. {row_name(row)}：{round(value, 2)}{unit}（来源：{source}）")
    else:
        lines.append("  无可用指标数据")
    trace = [
        {
            "tool_name": "prometheus.query" if top_rows and top_rows[0][2] == "prometheus" else "vmware.get_vcenter_inventory",
            "gateway": "prometheus" if top_rows and top_rows[0][2] == "prometheus" else "inventory",
            "input_summary": str(intent_to_dict(intent)),
            "output_summary": f"ranked={len(top_rows)}",
            "duration_ms": 0,
            "status": "success" if top_rows else "error",
            "timestamp": _now(),
        }
    ]
    return "\n".join(lines), trace, f"topn={len(top_rows)}"


def _format_vmware_query_result(intent: VmwareIntent, inventory: dict[str, Any]) -> tuple[str, str]:
    if not intent.resource_type:
        return _format_vcenter_summary(inventory), "summary"
    spec = RESOURCE_SPECS[intent.resource_type]
    label = filter_label(intent)
    condition = f"（条件：{label}）" if label else ""

    if intent.action == "count":
        count = count_for_intent(inventory, intent)
        unit = "台" if intent.resource_type in {"vm", "host"} else "个"
        sep = " " if spec.label and spec.label[0].isascii() else ""
        message = (
            f"vCenter 生产环境（conn-vcenter-prod）当前共有 {count} {unit}{sep}{spec.label}{condition}。\n\n"
            + _format_vcenter_summary(inventory)
        )
        return message, f"{intent.resource_type}_count={count}"

    if intent.action in {"list", "detail"}:
        rows = collection_for_intent(inventory, intent)
        count = len(rows)
        lines = [
            f"vCenter 生产环境（conn-vcenter-prod）{spec.label}列表{condition}：",
            "",
            f"- 匹配数量：{count}",
        ]
        if rows:
            lines.append("- 对象清单：")
            for idx, row in enumerate(rows[:20], start=1):
                lines.append(f"  {idx}. {row_brief(row, intent.resource_type)}")
            if count > 20:
                lines.append(f"  ... 还有 {count - 20} 个对象未展示")
        else:
            lines.append("- 对象清单：无匹配对象")
        return "\n".join(lines), f"{intent.resource_type}_matches={count}"

    return _format_vcenter_summary(inventory), "summary"


async def _build_vmware_resource_query_data(intent: VmwareIntent) -> dict[str, Any]:
    inventory = await _query_vcenter_prod_inventory()
    if not inventory:
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": "获取 vCenter 生产环境资源数据失败：无法读取 conn-vcenter-prod 的实时 inventory，请稍后重试。",
            "agent_name": "ResourceQueryAgent",
            "tool_traces": [],
            "evidence_refs": [],
            "evidences": [],
            "intent_recovery": {"vmware_intent": intent_to_dict(intent)},
            "reasoning_summary": _reasoning_summary(
                "用户希望查询 vCenter 生产环境资源。",
                "按轻量 VMware 本体解析为结构化资源查询并调用 inventory。",
                "inventory 查询失败。",
            ),
        }

    if vmware_intent := (intent if intent.action in {"metric", "capacity", "relationship", "topn"} else None):
        metric_result = None
        recommended_actions: list[str] = []
        if _is_host_cpu_memory_overview_intent(vmware_intent):
            assistant_message, metric_result, traces, recommended_actions, output_summary = await _build_host_cpu_memory_metric_result(vmware_intent, inventory)
        elif vmware_intent.action in {"metric", "capacity"}:
            rows = _resolve_vmware_rows(inventory, vmware_intent)
            if len(rows) > 1:
                return _build_clarify_for_vmware(vmware_intent, rows)
            assistant_message, traces, output_summary = await _format_vmware_metric_or_capacity(vmware_intent, inventory)
        elif vmware_intent.action == "relationship":
            rows = _resolve_vmware_rows(inventory, vmware_intent)
            if vmware_intent.target_object and len(rows) > 1:
                return _build_clarify_for_vmware(vmware_intent, rows)
            assistant_message, output_summary = _format_vmware_relationship(vmware_intent, inventory)
            traces = [
                {
                    "tool_name": "vmware.get_vcenter_inventory",
                    "gateway": "vmware-skill-gateway",
                    "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                    "output_summary": output_summary,
                    "duration_ms": 0,
                    "status": "success",
                    "timestamp": _now(),
                }
            ]
        else:
            assistant_message, traces, output_summary = await _format_vmware_topn(vmware_intent, inventory)
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": assistant_message,
            "agent_name": "ResourceQueryAgent",
            "tool_traces": traces,
            "evidence_refs": [],
            "evidences": [],
            "intent_recovery": {"vmware_intent": intent_to_dict(vmware_intent)},
            "metric_result": metric_result,
            "recommended_actions": recommended_actions,
            "reasoning_summary": _reasoning_summary(
                "用户希望查询 VMware 配置、容量、性能或关联关系。",
                "按 VMware 本体解析为结构化只读查询，优先 Prometheus 历史指标，失败时回退 vCenter 实时数据。",
                f"查询完成：{output_summary}。",
            ),
        }

    assistant_message, output_summary = _format_vmware_query_result(intent, inventory)
    return {
        "message_id": f"msg-{uuid.uuid4().hex[:10]}",
        "assistant_message": assistant_message,
        "agent_name": "ResourceQueryAgent",
        "tool_traces": [
            {
                "tool_name": "vmware.get_vcenter_inventory",
                "gateway": "vmware-skill-gateway",
                "input_summary": '{"connection_id":"conn-vcenter-prod"}',
                "output_summary": output_summary,
                "duration_ms": 0,
                "status": "success",
                "timestamp": _now(),
            }
        ],
        "evidence_refs": [],
        "evidences": [],
        "intent_recovery": {"vmware_intent": intent_to_dict(intent)},
        "reasoning_summary": _reasoning_summary(
            "用户希望查询 vCenter 生产环境资源。",
            (
                "按轻量 VMware 本体解析为 "
                f"{intent.resource_type}.{intent.action}"
                + (f" 并应用过滤条件：{filter_label(intent)}。" if intent.filters else "。")
            ),
            "已基于实时 inventory 返回确定性结果。",
        ),
    }


def _build_vmware_write_block_data(intent: VmwareIntent) -> dict[str, Any]:
    action_label = {
        "power_on": "开机",
        "power_off": "关机",
        "migrate": "迁移",
        "restart": "重启",
        "delete": "删除",
        "snapshot": "快照",
    }.get(intent.action, intent.action)
    resource_label = RESOURCE_SPECS[intent.resource_type].label if intent.resource_type else "VMware 对象"
    return {
        "message_id": f"msg-{uuid.uuid4().hex[:10]}",
        "assistant_message": (
            f"已识别到高风险 VMware 执行意图：{resource_label} {action_label}。\n\n"
            "当前策略默认拦截执行类操作，不会直接调用工具。请在审批/确认流程中补充目标对象、变更窗口和回退方案后再执行。"
        ),
        "agent_name": "ChangeGuardAgent",
        "tool_traces": [
            {
                "tool_name": f"vmware.{intent.action}",
                "gateway": "policy-gate",
                "input_summary": str(intent_to_dict(intent)),
                "output_summary": "blocked_until_approval",
                "duration_ms": 0,
                "status": "blocked",
                "timestamp": _now(),
            }
        ],
        "evidence_refs": [],
        "evidences": [],
        "intent_recovery": {"vmware_intent": intent_to_dict(intent)},
        "approval_card": {
            "title": f"确认 VMware {action_label} 操作",
            "risk_level": intent.risk_level,
            "action": intent.action,
            "resource_type": intent.resource_type,
            "environment": intent.environment,
            "status": "required",
        },
        "recommended_actions": ["确认目标对象名称", "补充变更窗口", "补充回退方案", "通过审批后再执行"],
        "reasoning_summary": _reasoning_summary(
            "用户表达了 VMware 执行类意图。",
            "按轻量 VMware 本体识别为高风险写操作，并应用默认审批拦截策略。",
            "未执行任何副作用操作，已返回审批提示。",
        ),
    }


def _predict_agent_and_plan(message: str) -> tuple[str, str]:
    intent = parse_vmware_intent(message)
    if intent and intent.action in WRITE_ACTIONS:
        return "ChangeGuardAgent", "识别 VMware 高风险执行意图并进入审批/确认门禁"
    if intent and intent.action in {"count", "list", "summary", "detail", "metric", "capacity", "relationship", "topn"}:
        return "ResourceQueryAgent", "基于 VMware 本体解析资源、容量、性能或关联查询"
    if _is_vcenter_prod_vm_export_query(message) or _is_vcenter_prod_vm_query(message) or _is_vcenter_prod_host_query(message):
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
    async with httpx.AsyncClient(timeout=600, trust_env=False) as client:
        try:
            endpoint = "/api/v1/orchestrate/chat-v2" if mode == "orchestrator_v2" else "/api/v1/orchestrate/chat"
            inventory = None
            resource_catalog: list[dict[str, Any]] = []
            ui_context: dict[str, Any] = {}
            should_prefetch_inventory = _should_prefetch_vmware_inventory(message, mode)
            if should_prefetch_inventory:
                logger.info("chat orchestrator prefetch start session_id=%s", session_id)
                inventory = await _query_vcenter_prod_inventory()
                resource_catalog = _build_vcenter_resource_catalog(inventory)
                ui_context = {
                    "connection_id": "conn-vcenter-prod",
                    "environment": "prod",
                }
                if isinstance(inventory, dict) and inventory:
                    ui_context["prefetched_inventory"] = inventory
                logger.info(
                    "chat orchestrator prefetch done session_id=%s catalog_count=%s has_prefetched=%s",
                    session_id,
                    len(resource_catalog),
                    bool(ui_context.get("prefetched_inventory")),
                )
            elif mode == "orchestrator_v2" and (VMWARE_KEYWORDS.search(message) or ESX_SHORT_HOST_PATTERN.search(message)):
                ui_context = {"connection_id": "conn-vcenter-prod", "environment": "prod"}
            logger.info("chat orchestrator request start session_id=%s mode=%s endpoint=%s", session_id, mode, endpoint)
            resp = await client.post(
                f"{ORCHESTRATOR_URL}{endpoint}",
                json={
                    "session_id": session_id,
                    "message": message,
                    "history": history,
                    "resource_catalog": resource_catalog,
                    "ui_context": ui_context,
                },
            )
            payload = resp.json()
            logger.info(
                "chat orchestrator request done session_id=%s status_code=%s success=%s",
                session_id,
                resp.status_code,
                payload.get("success") if isinstance(payload, dict) else None,
            )
            if not payload.get("success"):
                return None
            return payload.get("data")
        except Exception as exc:
            logger.exception("chat orchestrator request failed session_id=%s error=%s", session_id, exc)
            return None


async def _build_fallback_data(session_id: str, message: str) -> dict[str, Any]:
    vmware_intent = parse_vmware_intent(message)
    pending = _pending_intents.get(session_id) == PENDING_INTENT
    is_query = _is_vcenter_prod_vm_query(message)
    is_host_query = _is_vcenter_prod_host_query(message)
    is_export_query = _is_vcenter_prod_vm_export_query(message)
    is_power_query = _is_vcenter_prod_vm_power_query(message)
    is_power_action = _is_vm_power_action_intent(message)
    is_confirm = _is_confirmation(message)

    if _is_esxi_metric_report_export_query(message):
        return await _build_esxi_metric_report_export_data(session_id, message)

    if _is_vcenter_alert_event_query(message) and not _extract_host_target_from_message(message):
        return await _build_vcenter_alert_event_data(message)

    if _is_host_vm_list_followup(message) or _is_host_event_followup(message) or _is_host_datastore_latency_followup(message):
        inventory = await _query_vcenter_prod_inventory()
        if not inventory:
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": "查询失败：无法读取 conn-vcenter-prod 的实时 inventory，请稍后重试。",
                "agent_name": "ResourceQueryAgent",
                "tool_traces": [],
                "evidence_refs": [],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户点击了 VMware 指标结果的后续建议。",
                    "需要读取实时 inventory 对齐目标对象后执行只读查询。",
                    "inventory 查询失败。",
                ),
            }
        if _is_host_vm_list_followup(message):
            return await _build_host_vm_list_data(message, inventory)
        if _is_host_event_followup(message):
            return await _build_vcenter_alert_event_data(message, inventory)
        if _is_host_datastore_latency_followup(message):
            return await _build_host_datastore_latency_data(message, inventory)

    if vmware_intent and vmware_intent.action in WRITE_ACTIONS:
        return _build_vmware_write_block_data(vmware_intent)

    if vmware_intent and vmware_intent.action in {"count", "list", "summary", "detail", "metric", "capacity", "relationship", "topn"}:
        return await _build_vmware_resource_query_data(vmware_intent)

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

    if (pending and is_confirm) or (is_query and is_confirm) or is_query or is_host_query:
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
        vm_count = summary.get("vm_count", len(inventory.get("virtual_machines", []) or []))
        host_count = summary.get("host_count", len(inventory.get("hosts", []) or []))
        headline = (
            f"vCenter 生产环境（conn-vcenter-prod）当前共有 {host_count} 台 ESXi 主机。"
            if is_host_query
            else f"vCenter 生产环境（conn-vcenter-prod）当前共有 {vm_count} 台虚拟机。"
        )
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": f"{headline}\n\n" + _format_vcenter_summary(inventory),
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

    if _is_vmware_kb_query_intent(message):
        await _write_audit_log(
            {
                "event_type": "vmware_kb_search_started",
                "severity": "info",
                "actor": "OpsQAAssistant",
                "actor_type": "agent",
                "action": "vmware.kb_search",
                "outcome": "success",
                "metadata": {"session_id": session_id},
            }
        )
        kb_data, kb_error = await _invoke_vmware_kb_search_fallback(message)
        query = _normalize_vmware_kb_query(message)
        search_url = str((kb_data or {}).get("search_url") or f"https://support.broadcom.com/web/ecx/search?searchString={query}")
        if kb_error:
            await _write_audit_log(
                {
                    "event_type": "vmware_kb_search_failed",
                    "severity": "warning",
                    "actor": "OpsQAAssistant",
                    "actor_type": "agent",
                    "action": "vmware.kb_search",
                    "outcome": "failure",
                    "metadata": {"reason": kb_error},
                }
            )
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": (
                    "检索 VMware KB 失败，请稍后重试。\n\n"
                    f"你也可以先使用 Broadcom 搜索直链：[打开搜索页]({search_url})"
                ),
                "agent_name": "OpsQAAssistant",
                "tool_traces": [
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
                "evidence_refs": [search_url],
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户提出 VMware 文档/下载类问答。",
                    "fallback 直接调用 vmware.kb_search 检索官方来源。",
                    "工具调用失败，已返回可重试提示与搜索直链。",
                ),
            }

        items = (kb_data or {}).get("items") or []
        if isinstance(items, list) and items:
            assistant_message, refs = _format_vmware_kb_hit_reply(query, search_url, items)
            await _write_audit_log(
                {
                    "event_type": "vmware_kb_search_completed",
                    "severity": "info",
                    "actor": "OpsQAAssistant",
                    "actor_type": "agent",
                    "action": "vmware.kb_search",
                    "outcome": "success",
                    "metadata": {"hits": len(items)},
                }
            )
            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": assistant_message,
                "agent_name": "OpsQAAssistant",
                "tool_traces": [
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
                "evidence_refs": refs,
                "evidences": [],
                "reasoning_summary": _reasoning_summary(
                    "用户提出 VMware 文档/下载类问答。",
                    "fallback 优先检索官方 KB，并按相关度输出 Top3。",
                    f"已返回 {min(3, len(items))} 条官方来源及下载建议。",
                ),
            }

        await _write_audit_log(
            {
                "event_type": "vmware_kb_search_no_hit",
                "severity": "warning",
                "actor": "OpsQAAssistant",
                "actor_type": "agent",
                "action": "vmware.kb_search",
                "outcome": "success",
                "metadata": {"hits": 0},
            }
        )
        return {
            "message_id": f"msg-{uuid.uuid4().hex[:10]}",
            "assistant_message": _format_vmware_kb_no_hit_reply(query, search_url),
            "agent_name": "OpsQAAssistant",
            "tool_traces": [
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
            "evidence_refs": [search_url],
            "evidences": [],
            "reasoning_summary": _reasoning_summary(
                "用户提出 VMware 文档/下载类问答。",
                "fallback 调用 vmware.kb_search 并评估结果质量。",
                "未命中高相关结果，已返回搜索直链与关键词改写建议。",
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
    if is_diag and (VMWARE_KEYWORDS.search(message) or ESX_SHORT_HOST_PATTERN.search(message) or HOST_FQDN_PATTERN.search(message)):
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

            alerts, events, alert_event_traces = await _query_vcenter_alerts_and_events(matched_host, hours=24)
            alert_lines = []
            if alerts:
                top_alert = alerts[0]
                alert_lines.append(
                    f"- 最近告警：{len(alerts)} 条，最高优先级："
                    f"[{top_alert.get('severity') or top_alert.get('level') or 'info'}] "
                    f"{top_alert.get('summary') or top_alert.get('message') or '无摘要'}"
                )
            else:
                alert_lines.append("- 最近告警：未发现该主机关联告警")
            if events:
                alert_lines.append(f"- 最近事件：{len(events)} 条，最新：{events[0].get('message') or events[0].get('event_type') or events[0].get('type') or '事件'}")
            else:
                alert_lines.append("- 最近事件：无或当前事件源未返回数据")

            return {
                "message_id": f"msg-{uuid.uuid4().hex[:10]}",
                "assistant_message": (
                    f"已完成对主机 {host_name}（目标={host_target}）的健康分析：\n\n"
                    f"- 主机ID：{source.get('host_id', host_id or 'N/A')}\n"
                    f"- 连接状态：{connection_state}\n"
                    f"- 总体状态：{overall_status}\n"
                    f"- CPU 使用率：{cpu_percent if cpu_percent is not None else 'N/A'}%\n"
                    f"- 内存使用率：{memory_percent if memory_percent is not None else 'N/A'}%\n"
                    f"- 承载虚拟机数：{vm_count}\n"
                    + "\n".join(alert_lines)
                    + "\n\n"
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
                ]
                + alert_event_traces,
                "evidence_refs": ["ev-fallback-host-health", "ev-fallback-host-alert-events"],
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
                    },
                    {
                        "evidence_id": "ev-fallback-host-alert-events",
                        "source_type": "alert_event",
                        "summary": f"主机 {host_name} 最近 24 小时告警 {len(alerts)} 条，事件 {len(events)} 条",
                        "confidence": 0.85,
                        "timestamp": _now(),
                    }
                ],
                "root_cause_candidates": [
                    {"description": conclusion, "confidence": 0.9, "category": "infrastructure"}
                ],
                "recommended_actions": [
                    "检查该主机最近告警与硬件事件",
                    "核对该主机承载虚拟机的资源占用与热点分布",
                    f"查看生产环境 {host_name} 关联 datastore 延迟",
                ],
                "diagnosis_id": f"dg-{uuid.uuid4().hex[:12]}",
                "reasoning_summary": _reasoning_summary(
                    "用户希望分析指定 vCenter 主机健康状况。",
                    "先查询 inventory 锁定目标主机，再调用 host detail 获取实时指标。",
                    "已返回目标主机的健康分析结果。",
                ),
            }

    if is_diag and (VMWARE_KEYWORDS.search(message) or ESX_SHORT_HOST_PATTERN.search(message) or HOST_FQDN_PATTERN.search(message) or K8S_KEYWORDS.search(message)):
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
        logger.info("chat task start session_id=%s assistant_id=%s mode=%s", session_id, assistant_id, mode)
        async with _state_lock:
            target = _find_message(session_id, assistant_id)
            if not target:
                logger.warning("chat task missing target before start session_id=%s assistant_id=%s", session_id, assistant_id)
                return
            _append_progress_event(target, "tool_invoking", "正在调用 Orchestrator 执行任务", "in_progress")
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in _messages[session_id]
                if m.get("role") in ("user", "assistant") and m.get("id") != assistant_id
            ]

        if _should_use_local_vcenter_resource_path(user_message):
            logger.info("chat task using local vcenter resource path session_id=%s assistant_id=%s", session_id, assistant_id)
            data = await _build_fallback_data(session_id, user_message)
        else:
            data = await _run_orchestrator(session_id, user_message, history, mode)
        if not data:
            logger.info("chat task using fallback session_id=%s assistant_id=%s", session_id, assistant_id)
            data = await _build_fallback_data(session_id, user_message)
        else:
            logger.info("chat task received orchestrator data session_id=%s assistant_id=%s kind=%s", session_id, assistant_id, data.get("kind"))

        async with _state_lock:
            target = _find_message(session_id, assistant_id)
            if not target:
                logger.warning("chat task missing target during writeback session_id=%s assistant_id=%s", session_id, assistant_id)
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
            target["metric_result"] = data.get("metric_result")
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
            target["diagnosis_id"] = data.get("diagnosis_id")
            target["intent_recovery"] = data.get("intent_recovery")
            target["execution_intent"] = data.get("execution_intent")
            target["risk_context"] = data.get("risk_context")
            target["memory_refs"] = data.get("memory_refs", [])
            target["recommended_actions"] = data.get("recommended_actions", [])
            target["root_cause_candidates"] = data.get("root_cause_candidates", [])
            target["clarify_card"] = data.get("clarify_card")
            target["approval_card"] = data.get("approval_card")
            target["resume_card"] = data.get("resume_card")
            target["rerun_result"] = data.get("rerun_result")
            target["execution_progress"] = data.get("execution_progress")
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
            logger.info("chat task writeback completed session_id=%s assistant_id=%s", session_id, assistant_id)
    except Exception as exc:
        logger.exception("chat task failed session_id=%s assistant_id=%s error=%s", session_id, assistant_id, exc)
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
        logger.info("chat task end session_id=%s assistant_id=%s", session_id, assistant_id)


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

    selected_mode = (body.mode or DEFAULT_CHAT_MODE or "legacy").strip().lower()
    if selected_mode not in {"legacy", "orchestrator_v2"}:
        selected_mode = "legacy"
    task = asyncio.create_task(_process_message(session_id, assistant_id, body.message, selected_mode))
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

