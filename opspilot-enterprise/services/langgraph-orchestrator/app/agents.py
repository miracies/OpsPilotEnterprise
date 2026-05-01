from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import httpx

UTC = timezone.utc


def _now() -> str:
    return datetime.now(UTC).isoformat()


class BaseSubAgent(ABC):
    name: str = "base"
    description: str = "Base sub-agent"

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class EvidenceAgent(BaseSubAgent):
    name = "EvidenceAgent"
    description = "Collects evidence package for the incident-like context"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        incident_id = context.get("incident_id") or f"adhoc-{context.get('session_id', 'chat')}"
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{context['evidence_url'].rstrip('/')}/api/v1/evidence/aggregate",
                json={
                    "incident_id": incident_id,
                    "source_refs": context.get("source_refs", []),
                    "alert_context": {
                        "alert_name": context.get("alert_name") or context.get("query"),
                        "summary": context.get("query") or context.get("description"),
                        "description": context.get("description") or context.get("query"),
                        "vendor": context.get("vendor", "vmware"),
                        "domain": context.get("domain", "virtualization"),
                        "category": context.get("category"),
                        "severity": context.get("severity"),
                        "labels": context.get("labels", {}),
                        "object_type": context.get("object_type"),
                    },
                },
            )
        payload = resp.json()
        if not payload.get("success"):
            return {"ok": False, "error": payload.get("error") or "evidence aggregation failed", "evidence": []}
        data = payload.get("data", {}) or {}
        evidences = data.get("evidences", [])
        return {
            "ok": True,
            "evidence": evidences,
            "evidence_refs": [x.get("evidence_id") for x in evidences if x.get("evidence_id")],
            "errors": data.get("errors", []),
            "coverage": data.get("coverage", {}),
            "source_stats": data.get("source_stats", []),
            "required_evidence_types": data.get("required_evidence_types", []),
            "present_evidence_types": data.get("present_evidence_types", []),
            "missing_critical_evidence": data.get("missing_critical_evidence", []),
            "sufficiency_score": data.get("sufficiency_score", 0.0),
            "freshness_score": data.get("freshness_score", 0.0),
            "contradictions": data.get("contradictions", []),
            "alert_match": data.get("alert_match", {}),
            "alert_knowledge_ids": data.get("alert_knowledge_ids", []),
            "safe_actions": data.get("safe_actions", []),
            "approval_actions": data.get("approval_actions", []),
        }


class TopologyAgent(BaseSubAgent):
    name = "TopologyAgent"
    description = "Loads topology subgraph for the target object/incident"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        incident_id = context.get("incident_id")
        params = {"depth": context.get("topology_depth", 2)}
        async with httpx.AsyncClient(timeout=45.0) as client:
            if incident_id:
                resp = await client.get(
                    f"{context['topology_url'].rstrip('/')}/api/v1/topology/incidents/{incident_id}",
                    params=params,
                )
            else:
                graph_params = {
                    "connection_id": context.get("connection_id", "conn-vcenter-prod"),
                    "depth": context.get("topology_depth", 2),
                }
                if context.get("object_id"):
                    graph_params["object_id"] = context["object_id"]
                resp = await client.get(
                    f"{context['topology_url'].rstrip('/')}/api/v1/topology/graph",
                    params=graph_params,
                )
        payload = resp.json()
        if not payload.get("success"):
            return {"ok": False, "error": payload.get("error") or "topology query failed", "topology": {}}
        return {"ok": True, "topology": payload.get("data", {}) or {}}


class KnowledgeAgent(BaseSubAgent):
    name = "KnowledgeAgent"
    description = "Retrieves alert knowledge, ranked article citations, and similar cases"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        query = context.get("query") or ""
        alert_match: dict[str, Any] = {}
        alert_articles: list[dict[str, Any]] = []
        similar_cases: list[dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{context['knowledge_url'].rstrip('/')}/knowledge/alert-match",
                    json={
                        "alert_name": query,
                        "summary": query,
                        "vendor": context.get("vendor", "vmware"),
                        "domain": context.get("domain", "virtualization"),
                        "severity": context.get("severity"),
                        "evidence_present": context.get("present_evidence_types", []),
                        "top_k": 5,
                    },
                )
            payload = resp.json()
            if payload.get("success"):
                alert_match = payload.get("data", {}) or {}
                for match in (alert_match.get("matches") or [])[:5]:
                    item = match.get("item") if isinstance(match, dict) else {}
                    if not isinstance(item, dict):
                        continue
                    alert_articles.append(
                        {
                            "id": item.get("id"),
                            "title": item.get("alert_name"),
                            "content_summary": " | ".join(item.get("possible_causes") or []),
                            "source": "alert_knowledge",
                            "status": item.get("status"),
                            "tags": item.get("tags") or [],
                            "confidence_score": item.get("trust_score"),
                            "relevance_score": match.get("relevance_score"),
                            "why_selected": match.get("why_selected"),
                            "missing_evidence": match.get("missing_evidence") or [],
                            "diagnostic_steps": item.get("diagnostic_steps") or [],
                            "automation": item.get("automation") or {},
                        }
                    )
        except Exception:
            alert_match = context.get("alert_match", {}) if isinstance(context.get("alert_match"), dict) else {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{context['knowledge_url'].rstrip('/')}/knowledge/articles",
                params={"status": "published", "q": query},
            )
        payload = resp.json()
        if not payload.get("success"):
            return {"ok": False, "error": payload.get("error") or "knowledge retrieval failed", "articles": alert_articles}
        items = (payload.get("data") or {}).get("items", []) or []
        try:
            cases_url = context.get("cases_url")
            if cases_url:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    case_resp = await client.post(
                        f"{str(cases_url).rstrip('/')}/api/v1/cases/similar",
                        json={
                            "title": query,
                            "summary": query,
                            "tags": ["vmware"],
                            "knowledge_refs": [
                                str(x.get("id"))
                                for x in alert_articles
                                if x.get("id")
                            ],
                            "limit": 5,
                        },
                    )
                case_payload = case_resp.json()
                if case_payload.get("success"):
                    similar_cases = (case_payload.get("data") or {}).get("items", []) or []
        except Exception:
            similar_cases = []
        combined = alert_articles + items[: max(0, 5 - len(alert_articles))]
        return {
            "ok": True,
            "articles": combined[:5],
            "alert_match": alert_match or context.get("alert_match", {}),
            "alert_knowledge_ids": [
                str(x.get("id"))
                for x in alert_articles
                if x.get("id")
            ] or context.get("alert_knowledge_ids", []),
            "safe_actions": (alert_match.get("safe_actions") or context.get("safe_actions") or []),
            "approval_actions": (alert_match.get("approval_actions") or context.get("approval_actions") or []),
            "similar_cases": similar_cases,
            "similar_case_ids": [str(x.get("id")) for x in similar_cases if x.get("id")],
        }


class RootCauseAgent(BaseSubAgent):
    name = "RootCauseAgent"
    description = "Produces single root cause and ranked candidates from evidence"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        evidence = context.get("evidence", [])
        topology = context.get("topology", {})
        articles = context.get("articles", [])
        refs = [x.get("evidence_id") for x in evidence if x.get("evidence_id")]
        contradictions = context.get("contradictions", []) or []
        missing_critical = context.get("missing_critical_evidence", []) or []
        sufficiency_score = float(context.get("sufficiency_score") or 0.0)
        freshness_score = float(context.get("freshness_score") or 0.0)

        metric_refs = [e.get("evidence_id") for e in evidence if e.get("source_type") == "metric" and e.get("evidence_id")]
        event_refs = [e.get("evidence_id") for e in evidence if e.get("source_type") == "event" and e.get("evidence_id")]
        alert_refs = [e.get("evidence_id") for e in evidence if e.get("source_type") == "alert" and e.get("evidence_id")]
        detail_refs = [e.get("evidence_id") for e in evidence if e.get("source_type") == "detail" and e.get("evidence_id")]
        change_refs = [e.get("evidence_id") for e in evidence if e.get("source_type") == "change" and e.get("evidence_id")]

        hypotheses: list[dict[str, Any]] = []

        def _score(base: float, support_refs: list[str], counter_refs: list[str]) -> float:
            value = base
            value += min(0.18, len(support_refs) * 0.07)
            value -= min(0.16, len(counter_refs) * 0.06)
            value += min(0.15, sufficiency_score * 0.16)
            value += min(0.1, freshness_score * 0.06)
            value -= min(0.18, len(contradictions) * 0.06)
            value -= min(0.14, len(missing_critical) * 0.05)
            if topology and (topology.get("nodes") or []):
                value += 0.04
            if articles:
                value += 0.03
            return round(max(0.08, min(value, 0.95)), 2)

        hypotheses.append(
            {
                "id": "hyp-infra-health",
                "summary": "基础设施健康异常或连接问题导致对象状态异常。",
                "category": "infrastructure",
                "confidence": _score(0.44, detail_refs + event_refs[:2] + alert_refs[:2], [] if detail_refs else refs[:1]),
                "support_evidence_refs": list(dict.fromkeys(detail_refs + event_refs[:2] + alert_refs[:2])),
                "counter_evidence_refs": [] if detail_refs else refs[:1],
                "missing_evidence": missing_critical,
                "status": "candidate",
                "why": "详情、事件和告警同时命中时，优先怀疑主机/连接侧异常。",
            }
        )
        hypotheses.append(
            {
                "id": "hyp-resource-pressure",
                "summary": "资源压力或性能瓶颈导致抖动、告警或状态下降。",
                "category": "capacity",
                "confidence": _score(0.4, metric_refs + alert_refs[:1], refs[:1] if not metric_refs else []),
                "support_evidence_refs": list(dict.fromkeys(metric_refs + alert_refs[:1])),
                "counter_evidence_refs": refs[:1] if not metric_refs else [],
                "missing_evidence": missing_critical,
                "status": "candidate",
                "why": "有指标证据时更适合怀疑资源侧问题；没有指标时不能给高置信。",
            }
        )
        hypotheses.append(
            {
                "id": "hyp-recent-change",
                "summary": "近期变更、迁移或重启引入了异常。",
                "category": "change",
                "confidence": _score(0.34, change_refs + event_refs[:1], refs[:1] if not change_refs else []),
                "support_evidence_refs": list(dict.fromkeys(change_refs + event_refs[:1])),
                "counter_evidence_refs": refs[:1] if not change_refs else [],
                "missing_evidence": missing_critical,
                "status": "candidate",
                "why": "如果异常时间窗附近存在变更证据，应将其作为候选根因而不是忽略。",
            }
        )
        hypotheses.sort(key=lambda item: item.get("confidence", 0), reverse=True)
        winning = hypotheses[0] if hypotheses else None

        if not winning:
            conclusion_status = "insufficient_evidence"
            counter_result = {
                "status": "inconclusive",
                "checked_hypothesis_id": None,
                "summary": "当前没有足够证据形成主假设。",
                "evidence_refs": [],
            }
        else:
            counter_refs = list(winning.get("counter_evidence_refs", []) or [])
            if counter_refs and contradictions:
                conclusion_status = "contradicted"
                winning["status"] = "refuted"
                counter_result = {
                    "status": "refuted",
                    "checked_hypothesis_id": winning.get("id"),
                    "summary": "主假设存在反证且仍有矛盾未解释。",
                    "evidence_refs": counter_refs,
                }
            elif missing_critical or sufficiency_score < 0.6:
                conclusion_status = "insufficient_evidence"
                winning["status"] = "inconclusive"
                counter_result = {
                    "status": "inconclusive",
                    "checked_hypothesis_id": winning.get("id"),
                    "summary": "仍缺关键证据或证据充分性不足，不能确认唯一根因。",
                    "evidence_refs": counter_refs,
                }
                winning["confidence"] = min(float(winning.get("confidence") or 0.18), 0.59)
            elif float(winning.get("confidence") or 0.0) >= 0.78:
                conclusion_status = "confirmed"
                winning["status"] = "confirmed"
                counter_result = {
                    "status": "not_refuted",
                    "checked_hypothesis_id": winning.get("id"),
                    "summary": "未发现足以推翻主假设的关键反证。",
                    "evidence_refs": list(winning.get("support_evidence_refs", []))[:3],
                }
            else:
                conclusion_status = "probable"
                winning["status"] = "probable"
                counter_result = {
                    "status": "inconclusive",
                    "checked_hypothesis_id": winning.get("id"),
                    "summary": "主假设暂未被反驳，但仍建议补证后再下最终结论。",
                    "evidence_refs": counter_refs,
                }

        summary = winning.get("summary") if winning else "证据不足，暂无法收敛唯一根因。"
        candidates = [
            {
                "id": item["id"],
                "description": item["summary"],
                "confidence": item["confidence"],
                "category": item["category"],
                "evidence_refs": item.get("support_evidence_refs", []),
            }
            for item in hypotheses
        ]

        return {
            "ok": True,
            "root_cause": {
                "summary": summary,
                "confidence": round(float(winning.get("confidence") or 0.18), 2) if winning else 0.18,
                "evidence_refs": list(winning.get("support_evidence_refs", [])) if winning else refs,
            },
            "root_cause_candidates": candidates,
            "hypotheses": hypotheses,
            "winning_hypothesis": winning,
            "counter_evidence_result": counter_result,
            "conclusion_status": conclusion_status,
            "evidence_sufficiency": {
                "required_evidence_types": context.get("required_evidence_types", []),
                "present_evidence_types": context.get("present_evidence_types", []),
                "missing_critical_evidence": missing_critical,
                "sufficiency_score": sufficiency_score,
                "freshness_score": freshness_score,
            },
            "contradictions": contradictions,
        }


class RemediationAgent(BaseSubAgent):
    name = "RemediationAgent"
    description = "Generates remediation recommendations from root cause and risk policy"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        root = context.get("root_cause") or {}
        summary = str(root.get("summary") or "")
        actions: list[str] = []
        safe_actions = context.get("safe_actions") or []
        approval_actions = context.get("approval_actions") or []
        if safe_actions:
            actions.append("Safe collection actions: " + ", ".join(str(x) for x in safe_actions[:5]))
        if approval_actions:
            actions.append("Approval-required actions: " + ", ".join(str(x) for x in approval_actions[:5]))
        if "资源" in summary or "压力" in summary:
            actions.extend(
                [
                    "优先执行低风险动作：检查并回收异常高占用工作负载资源。",
                    "若持续高负载，评估并执行虚拟机迁移或限流策略。",
                ]
            )
        else:
            actions.extend(
                [
                    "收集最近变更记录并比对异常时间窗口。",
                    "对异常对象执行只读健康检查，并评估是否进入审批处置。",
                ]
            )
        return {"ok": True, "recommended_actions": actions, "safe_actions": safe_actions, "approval_actions": approval_actions}


async def run_multi_agent_rootcause(context: dict[str, Any]) -> dict[str, Any]:
    """Collaborative workflow: Evidence -> Topology -> Knowledge -> RootCause -> Remediation."""

    steps: list[dict[str, Any]] = []
    state = dict(context)

    for agent in (EvidenceAgent(), TopologyAgent(), KnowledgeAgent(), RootCauseAgent(), RemediationAgent()):
        started = _now()
        try:
            out = await agent.run(state)
            state.update(out)
            ok = out.get("ok", True)
            steps.append(
                {
                    "agent": agent.name,
                    "stage": "agent_run",
                    "status": "success" if ok else "failed",
                    "started_at": started,
                    "finished_at": _now(),
                    "summary": out.get("error") or f"{agent.name} completed",
                }
            )
            if ok is False and agent.name in {"EvidenceAgent", "RootCauseAgent"}:
                break
        except Exception as exc:  # noqa: BLE001
            steps.append(
                {
                    "agent": agent.name,
                    "stage": "agent_run",
                    "status": "failed",
                    "started_at": started,
                    "finished_at": _now(),
                    "summary": str(exc),
                }
            )
            if agent.name in {"EvidenceAgent", "RootCauseAgent"}:
                break

    return {
        "analysis_steps": steps,
        "root_cause": state.get("root_cause"),
        "root_cause_candidates": state.get("root_cause_candidates", []),
        "hypotheses": state.get("hypotheses", []),
        "winning_hypothesis": state.get("winning_hypothesis"),
        "counter_evidence_result": state.get("counter_evidence_result"),
        "conclusion_status": state.get("conclusion_status"),
        "evidence_sufficiency": state.get("evidence_sufficiency"),
        "contradictions": state.get("contradictions", []),
        "recommended_actions": state.get("recommended_actions", []),
        "evidences": state.get("evidence", []),
        "evidence_refs": state.get("evidence_refs", []),
        "topology": state.get("topology", {}),
        "knowledge_articles": state.get("articles", []),
        "alert_match": state.get("alert_match", {}),
        "alert_knowledge_ids": state.get("alert_knowledge_ids", []),
        "similar_cases": state.get("similar_cases", []),
        "similar_case_ids": state.get("similar_case_ids", []),
        "safe_actions": state.get("safe_actions", []),
        "approval_actions": state.get("approval_actions", []),
        "coverage": state.get("coverage"),
        "evidence_errors": state.get("errors", []),
    }
