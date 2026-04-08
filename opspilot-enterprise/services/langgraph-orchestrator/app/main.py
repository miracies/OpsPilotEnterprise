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

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8030")
CHANGE_IMPACT_SERVICE_URL = os.environ.get("CHANGE_IMPACT_SERVICE_URL", "http://127.0.0.1:8040")

DIAGNOSIS_KEYWORDS = re.compile(r"分析|诊断|排查|告警|根因|异常|故障|排障|为什么|原因|查看.*问题|检查")


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


def _build_diagnosis(description: str, assistant_content: str | None = None, object_id: str | None = None) -> dict:
    diagnosis_id = f"dg-{_uid()}"
    tool_traces = _build_tool_traces(description)
    evidence_refs = [e["evidence_id"] for e in MOCK_EVIDENCES]

    root_cause_candidates = [
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

    recommended_actions = [
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
        "root_cause_candidates": root_cause_candidates,
        "evidence_refs": evidence_refs,
        "evidences": MOCK_EVIDENCES,
        "recommended_actions": recommended_actions,
        "tool_traces": tool_traces,
        "simulated_at": _now(),
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
        evidence_summary = "\n".join(
            f"- [{e['source_type']}] {e['summary']} (置信度 {e['confidence']:.0%})"
            for e in MOCK_EVIDENCES
        )
        llm_text = await _llm_diagnosis(body.description, evidence_summary)
        data = _build_diagnosis(body.description, llm_text, body.object_id)
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
            evidence_summary = "\n".join(
                f"- [{e['source_type']}] {e['summary']} (置信度 {e['confidence']:.0%})"
                for e in MOCK_EVIDENCES
            )
            llm_text = await _llm_diagnosis(body.message, evidence_summary)
            diag = _build_diagnosis(body.message, llm_text)

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
