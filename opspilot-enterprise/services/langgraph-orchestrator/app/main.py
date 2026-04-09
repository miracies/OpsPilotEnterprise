from __future__ import annotations

import os
import re
import uuid
import random
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[2] / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from opspilot_schema.change_impact import ChangeImpactRequest
from opspilot_schema.envelope import make_error, make_success

from app.llm_client import (
    chat_completion,
    check_llm_health,
    SYSTEM_PROMPT,
    DIAGNOSIS_SYSTEM_PROMPT,
    LLM_ENABLED,
    LLM_MODEL,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpsPilot LangGraph Orchestrator")

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")
CHANGE_IMPACT_SERVICE_URL = os.environ.get("CHANGE_IMPACT_SERVICE_URL", "http://127.0.0.1:8040")
RESOURCE_BFF_URL = os.environ.get("RESOURCE_BFF_URL", "http://127.0.0.1:8000")

DIAGNOSIS_KEYWORDS = re.compile(r"分析|诊断|排查|告警|根因|异常|故障|排障|为什么|原因|查看.*问题|检查")
VMWARE_KEYWORDS = re.compile(r"vmware|vcenter|esxi|虚拟机|主机|数据存储", re.I)
K8S_KEYWORDS = re.compile(r"k8s|kubernetes|pod|deployment|node|namespace|容器|集群", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class DiagnoseRequest(BaseModel):
    description: str
    object_id: str | None = None


class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list[dict] | None = None


MOCK_EVIDENCES = [
    {
        "evidence_id": f"ev-{_uid()}",
        "source_type": "metric",
        "summary": "esxi-node03 CPU usage 飙升至 97.3%，持续超过 30 分钟",
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
    {
        "evidence_id": f"ev-{_uid()}",
        "source_type": "event",
        "summary": "08:00 触发 storage vMotion 将 db-server-02 迁移至 esxi-node03",
        "confidence": 0.75,
        "timestamp": _now(),
        "raw_data": {"event_type": "VmMigratedEvent", "vm": "db-server-02"},
    },
    {
        "evidence_id": f"ev-{_uid()}",
        "source_type": "topology",
        "summary": "app-server-01 与 db-primary 位于同一 esxi-node03，存在资源争用风险",
        "confidence": 0.70,
        "timestamp": _now(),
        "raw_data": {"host": "esxi-node03", "vms": ["app-server-01", "db-primary"]},
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
            "tool_name": "vmware.query_metrics",
            "gateway": "vmware-skill-gateway",
            "input_summary": '{"host_id": "host-33", "metric": "cpu.usage"}',
            "output_summary": "1h trend: 72% → 97%",
            "duration_ms": random.randint(300, 600),
            "status": "success",
            "timestamp": _now(),
        },
        {
            "tool_name": "vmware.query_events",
            "gateway": "vmware-skill-gateway",
            "input_summary": '{"host_id": "host-33", "hours": 4}',
            "output_summary": "3 events found",
            "duration_ms": random.randint(150, 400),
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
        if kind == "vmware":
            summary = data.get("summary", {})
            evidences = [
                {
                    "evidence_id": f"ev-{_uid()}",
                    "source_type": "inventory",
                    "summary": f"vCenter 当前共有 {summary.get('cluster_count', 0)} 个集群、{summary.get('host_count', 0)} 台主机、{summary.get('vm_count', 0)} 台虚拟机",
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
                        "summary": f"发现 {summary['unhealthy_host_count']} 台主机处于非绿色状态",
                        "confidence": 0.86,
                        "timestamp": _now(),
                        "raw_data": {"hosts": data.get("hosts", [])},
                    }
                )
            traces = [
                {
                    "tool_name": "vmware.get_vcenter_inventory",
                    "gateway": "vmware-skill-gateway",
                    "input_summary": "{}",
                    "output_summary": f"clusters={summary.get('cluster_count', 0)}, hosts={summary.get('host_count', 0)}, vms={summary.get('vm_count', 0)}",
                    "duration_ms": 420,
                    "status": "success",
                    "timestamp": _now(),
                }
            ]
            root_causes = [
                {
                    "description": "vCenter 实时资源状态中存在主机或虚拟机异常，需要优先检查非绿色对象",
                    "confidence": 0.78 if summary.get("unhealthy_host_count", 0) else 0.58,
                    "category": "infrastructure",
                }
            ]
            actions = [
                "检查 vCenter 中非绿色主机的硬件与连接状态",
                "核对异常虚拟机的电源状态、资源占用与近期事件",
            ]
            return {"kind": kind, "evidences": evidences, "tool_traces": traces, "root_cause_candidates": root_causes, "recommended_actions": actions}

        summary = data.get("summary", {})
        evidences = [
            {
                "evidence_id": f"ev-{_uid()}",
                "source_type": "inventory",
                "summary": f"Kubernetes 当前共有 {summary.get('node_count', 0)} 个节点、{summary.get('pod_count', 0)} 个 Pod、{summary.get('deployment_count', 0)} 个 Deployment",
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
        traces = [
            {
                "tool_name": "k8s.get_workload_status",
                "gateway": "kubernetes-skill-gateway",
                "input_summary": "{}",
                "output_summary": f"nodes={summary.get('node_count', 0)}, pods={summary.get('pod_count', 0)}, deployments={summary.get('deployment_count', 0)}",
                "duration_ms": 380,
                "status": "success",
                "timestamp": _now(),
            }
        ]
        root_causes = [
            {
                "description": "Kubernetes 实时状态显示存在未就绪 Pod 或节点，需要优先检查调度与工作负载健康",
                "confidence": 0.82 if summary.get("unhealthy_pod_count", 0) else 0.6,
                "category": "platform",
            }
        ]
        actions = [
            "查看未就绪 Pod 的事件、探针与最近日志",
            "检查节点 Ready 状态、资源压力与驱逐事件",
        ]
        return {"kind": kind, "evidences": evidences, "tool_traces": traces, "root_cause_candidates": root_causes, "recommended_actions": actions}
    except Exception:
        return None


def _build_mock_diagnosis_text(description: str) -> str:
    """Fallback diagnosis text when LLM is unavailable."""
    return (
        "## 诊断结论\n\n"
        f"针对「{description}」的诊断分析已完成。\n\n"
        "### 根因候选\n"
        "1. **app-server-01 Java Full GC 风暴导致 CPU 飙升** (置信度 87%)\n"
        "2. **存储 vMotion 引起临时资源争用** (置信度 62%)\n\n"
        "### 建议动作\n"
        "- 检查 app-server-01 JVM 堆内存配置和 GC 日志\n"
        "- 对 esxi-node03 当前 VM 负载做平衡评估\n"
        "- 考虑将 app-server-01 迁移到低负载主机"
    )


async def _llm_diagnosis(description: str, evidence_summary: str) -> str | None:
    """Use LLM to generate diagnosis analysis based on evidence."""
    evidence_context = (
        f"用户问题：{description}\n\n"
        f"采集到的证据：\n{evidence_summary}"
    )
    return await chat_completion(
        [{"role": "user", "content": evidence_context}],
        system_prompt=DIAGNOSIS_SYSTEM_PROMPT,
        temperature=0.3,
    )


async def _llm_chat(message: str, history: list[dict] | None = None) -> str | None:
    """Use LLM for general chat with conversation history."""
    messages = []
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
    evidence_refs = [e["evidence_id"] for e in diag_evidences]

    diag_root_causes = root_cause_candidates or [
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
    ]

    diag_actions = recommended_actions or [
        "检查 app-server-01 JVM 堆内存配置和 GC 日志",
        "对 esxi-node03 当前 VM 负载做平衡评估",
        "考虑将 app-server-01 迁移到低负载主机",
    ]

    if not assistant_content:
        assistant_content = _build_mock_diagnosis_text(description)

    return {
        "diagnosis_id": diagnosis_id,
        "description": description,
        "object_id": object_id,
        "assistant_message": assistant_content,
        "root_cause_candidates": diag_root_causes,
        "evidence_refs": evidence_refs,
        "evidences": diag_evidences,
        "recommended_actions": diag_actions,
        "tool_traces": diag_tool_traces,
        "simulated_at": _now(),
        "created_at": _now(),
    }


@app.get("/health")
async def health() -> dict:
    llm_status = await check_llm_health()
    return make_success({
        "status": "healthy",
        "llm": llm_status,
    })


@app.post("/api/v1/orchestrate/diagnose")
async def orchestrate_diagnose(body: DiagnoseRequest) -> dict:
    try:
        runtime_context = await _fetch_real_context(body.description)
        evidence_source = runtime_context["evidences"] if runtime_context else MOCK_EVIDENCES
        evidence_summary = "\n".join(
            f"- [{e['source_type']}] {e['summary']} (置信度 {e['confidence']:.0%})"
            for e in evidence_source
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
    """LLM-powered chat with diagnosis intent detection."""
    try:
        is_diagnosis = bool(DIAGNOSIS_KEYWORDS.search(body.message))

        if is_diagnosis:
            runtime_context = await _fetch_real_context(body.message)
            evidence_source = runtime_context["evidences"] if runtime_context else MOCK_EVIDENCES
            evidence_summary = "\n".join(
                f"- [{e['source_type']}] {e['summary']} (置信度 {e['confidence']:.0%})"
                for e in evidence_source
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

            message_id = f"msg-{_uid()}"
            data = {
                "session_id": body.session_id,
                "message_id": message_id,
                "assistant_message": diag["assistant_message"],
                "agent_name": "RCAAgent",
                "diagnosis_id": diag["diagnosis_id"],
                "root_cause_candidates": diag["root_cause_candidates"],
                "evidence_refs": diag["evidence_refs"],
                "evidences": diag["evidences"],
                "recommended_actions": diag["recommended_actions"],
                "tool_traces": diag["tool_traces"],
            }
            return make_success(data)

        # General chat → call LLM
        llm_reply = await _llm_chat(body.message, body.history)
        fallback = f"收到您的消息：「{body.message}」\n\n如需诊断分析，请描述具体的告警或故障情况。"
        assistant_text = llm_reply or fallback

        message_id = f"msg-{_uid()}"
        data = {
            "session_id": body.session_id,
            "message_id": message_id,
            "assistant_message": assistant_text,
            "agent_name": "Orchestrator",
            "tool_traces": [],
            "evidence_refs": [],
            "evidences": [],
        }
        return make_success(data)
    except Exception as exc:
        logger.exception("orchestrate_chat error")
        return make_error(str(exc))
