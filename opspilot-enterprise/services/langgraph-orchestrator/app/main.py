from __future__ import annotations

import logging
import os
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from app.llm_client import DIAGNOSIS_SYSTEM_PROMPT, SYSTEM_PROMPT, chat_completion, check_llm_health
from opspilot_schema.change_impact import ChangeImpactRequest
from opspilot_schema.envelope import make_error, make_success

_env_path = Path(__file__).resolve().parents[2] / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpsPilot LangGraph Orchestrator")

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")
CHANGE_IMPACT_SERVICE_URL = os.environ.get("CHANGE_IMPACT_SERVICE_URL", "http://127.0.0.1:8040")
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
    r"\u5206\u6790|\u8bca\u65ad|\u6392\u67e5|\u544a\u8b66|\u6839\u56e0|\u5f02\u5e38|\u6545\u969c|\u6392\u969c|\u4e3a\u4ec0\u4e48|\u539f\u56e0|\u68c0\u67e5",
    re.I,
)
VMWARE_KEYWORDS = re.compile(r"vmware|vcenter|esxi|\u865a\u62df\u673a|\u4e3b\u673a|\u6570\u636e\u5b58\u50a8", re.I)
K8S_KEYWORDS = re.compile(r"k8s|kubernetes|pod|deployment|node|namespace|\u5bb9\u5668|\u96c6\u7fa4", re.I)


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
        target = ("vmware", f"{RESOURCE_BFF_URL.rstrip('/')}/api/v1/resources/vcenter/inventory")
    if not target:
        return None

    kind, url = target
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.get(url)
        body = resp.json()
        if not body.get("success"):
            return None

        data = body.get("data", {})
        summary = data.get("summary", {})
        if kind == "vmware":
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
                        "input_summary": "{}",
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


def _build_diagnosis(
    description: str,
    assistant_content: str | None = None,
    object_id: str | None = None,
    evidences: list[dict] | None = None,
    tool_traces: list[dict] | None = None,
    root_cause_candidates: list[dict] | None = None,
    recommended_actions: list[str] | None = None,
) -> dict:
    diagnosis_id = f"dg-{_uid()}"
    diag_evidences = evidences or MOCK_EVIDENCES
    diag_tool_traces = tool_traces or _build_tool_traces(description)

    if not assistant_content:
        assistant_content = _build_mock_diagnosis_text(description)

    return {
        "diagnosis_id": diagnosis_id,
        "description": description,
        "object_id": object_id,
        "assistant_message": assistant_content,
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
        "recommended_actions": recommended_actions
        or [
            "检查 app-server-01 JVM 堆内存配置和 GC 日志",
            "对 esxi-node03 当前 VM 负载做平衡评估",
            "考虑将 app-server-01 迁移到低负载主机",
        ],
        "tool_traces": diag_tool_traces,
        "simulated_at": _now(),
        "created_at": _now(),
    }


@app.get("/health")
async def health() -> dict:
    llm_status = await check_llm_health()
    return make_success({"status": "healthy", "llm": llm_status})


@app.post("/api/v1/orchestrate/diagnose")
async def orchestrate_diagnose(body: DiagnoseRequest) -> dict:
    try:
        runtime_context = await _fetch_real_context(body.description)
        evidence_source = runtime_context["evidences"] if runtime_context else MOCK_EVIDENCES
        evidence_summary = "\n".join(
            f"- [{e['source_type']}] {e['summary']} (置信度 {e['confidence']:.0%})" for e in evidence_source
        )
        llm_text = await _llm_diagnosis(body.description, evidence_summary)
        data = _build_diagnosis(
            body.description,
            llm_text,
            body.object_id,
            evidences=runtime_context["evidences"] if runtime_context else None,
            tool_traces=runtime_context["tool_traces"] if runtime_context else None,
            root_cause_candidates=runtime_context["root_cause_candidates"] if runtime_context else None,
            recommended_actions=runtime_context["recommended_actions"] if runtime_context else None,
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

        if DIAGNOSIS_KEYWORDS.search(body.message):
            runtime_context = await _fetch_real_context(body.message)
            evidence_source = runtime_context["evidences"] if runtime_context else MOCK_EVIDENCES
            evidence_summary = "\n".join(
                f"- [{e['source_type']}] {e['summary']} (置信度 {e['confidence']:.0%})" for e in evidence_source
            )
            llm_text = await _llm_diagnosis(body.message, evidence_summary)
            diag = _build_diagnosis(
                body.message,
                llm_text,
                evidences=runtime_context["evidences"] if runtime_context else None,
                tool_traces=runtime_context["tool_traces"] if runtime_context else None,
                root_cause_candidates=runtime_context["root_cause_candidates"] if runtime_context else None,
                recommended_actions=runtime_context["recommended_actions"] if runtime_context else None,
            )
            return make_success(
                {
                    "session_id": body.session_id,
                    "message_id": f"msg-{_uid()}",
                    "assistant_message": diag["assistant_message"],
                    "agent_name": "RCAAgent",
                    "diagnosis_id": diag["diagnosis_id"],
                    "root_cause_candidates": diag["root_cause_candidates"],
                    "evidence_refs": diag["evidence_refs"],
                    "evidences": diag["evidences"],
                    "recommended_actions": diag["recommended_actions"],
                    "tool_traces": diag["tool_traces"],
                    "reasoning_summary": _reasoning_summary(
                        "用户希望进行诊断分析。",
                        "收集运行时证据并调用诊断模型生成根因与建议。",
                        "已输出诊断结论、证据引用和建议动作。",
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
