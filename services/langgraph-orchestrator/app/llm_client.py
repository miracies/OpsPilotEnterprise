"""Zhipu AI (GLM) LLM client via OpenAI-compatible API."""
from __future__ import annotations

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

LLM_API_BASE = os.environ.get(
    "LLM_API_BASE", "https://open.bigmodel.cn/api/paas/v4"
)
LLM_API_KEY = os.environ.get(
    "LLM_API_KEY", "6125e19580834f158c14c0b245fcca0c.D7bUeGnGVUaYhRP1"
)
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-5-turbo")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "4096"))
LLM_ENABLED = os.environ.get("LLM_ENABLED", "true").lower() in ("true", "1", "yes")

SYSTEM_PROMPT = """你是 OpsPilot，一个企业级 AIOps 智能运维助手。你的职责包括：

1. **故障诊断**：分析告警、日志、指标，定位根因，给出置信度评估
2. **变更影响分析**：评估变更操作的风险和影响范围
3. **运维知识问答**：回答基础设施、中间件、应用运维相关问题
4. **操作建议**：给出可执行的修复建议和最佳实践

回答规范：
- 使用简洁清晰的中文回答
- 涉及诊断时，按「现象 → 证据 → 根因 → 建议」的结构组织
- 给出具体可操作的建议，而非笼统描述
- 如果涉及高风险操作，明确提醒需要审批
- 使用 Markdown 格式让内容结构清晰

你所处的平台环境：
- 管理 VMware vSphere 私有化基础设施
- 有 Tool Gateway 可调用 VMware API 查询主机、VM、指标、事件
- 有证据聚合服务可汇总多源证据
- 有变更影响分析服务评估操作风险
- 有审批中心管理高风险操作"""

DIAGNOSIS_SYSTEM_PROMPT = """你是 OpsPilot 的 RCA（根因分析）Agent。用户描述了一个运维问题，你需要基于以下采集到的证据进行分析。

请按以下结构回答：

## 诊断结论

简述分析结果。

### 根因候选
列出 1-3 个根因候选项，按置信度排序，格式：
1. **根因描述** (置信度 XX%)
2. **根因描述** (置信度 XX%)

### 建议动作
给出 2-4 条具体可执行的修复建议。

保持简洁专业，直接给出结论，不要冗长铺垫。"""


async def chat_completion(
    messages: list[dict],
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Optional[str]:
    """Call Zhipu AI chat completions API. Returns assistant content or None on failure."""
    if not LLM_ENABLED:
        return None

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    payload = {
        "model": LLM_MODEL,
        "messages": full_messages,
        "temperature": temperature or LLM_TEMPERATURE,
        "max_tokens": max_tokens or LLM_MAX_TOKENS,
    }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{LLM_API_BASE}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            reasoning = msg.get("reasoning_content") or ""
            result = content if content.strip() else reasoning
            logger.info(
                "LLM response: model=%s, tokens=%s",
                LLM_MODEL,
                data.get("usage", {}),
            )
            return result
    except httpx.HTTPStatusError as exc:
        logger.error("LLM API HTTP error: %s - %s", exc.response.status_code, exc.response.text[:500])
        return None
    except Exception as exc:
        logger.error("LLM API error: %s", exc)
        return None


async def check_llm_health() -> dict:
    """Quick health check for the LLM connection."""
    if not LLM_ENABLED:
        return {"status": "disabled", "model": LLM_MODEL}
    try:
        result = await chat_completion(
            [{"role": "user", "content": "请回复：pong"}],
            system_prompt="用一个词回复",
            max_tokens=50,
        )
        return {
            "status": "connected" if result else "error",
            "model": LLM_MODEL,
            "api_base": LLM_API_BASE,
        }
    except Exception as exc:
        return {"status": "error", "model": LLM_MODEL, "error": str(exc)}
