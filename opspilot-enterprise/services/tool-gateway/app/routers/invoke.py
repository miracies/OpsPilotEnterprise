from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, unquote
from uuid import uuid4

import httpx
from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from opspilot_schema import make_error, make_success
from app import registry

router = APIRouter(prefix="/invoke")

VMWARE_GATEWAY_URL = os.environ.get("VMWARE_GATEWAY_URL", "http://localhost:8030")
VMWARE_GATEWAY_FALLBACK_URL = os.environ.get("VMWARE_GATEWAY_FALLBACK_URL", "http://127.0.0.1:18030")
KUBERNETES_GATEWAY_URL = os.environ.get("KUBERNETES_GATEWAY_URL", "http://localhost:8080")
CHANGE_IMPACT_URL = os.environ.get("CHANGE_IMPACT_URL", "http://localhost:8040")
GOVERNANCE_SERVICE_URL = os.environ.get("GOVERNANCE_SERVICE_URL", "http://127.0.0.1:8071").rstrip("/")
STRICT_SCHEMA_VALIDATION = os.environ.get("STRICT_SCHEMA_VALIDATION", "true").lower() == "true"


class InvokeBody(BaseModel):
    input: Any = Field(default_factory=dict)
    dry_run: bool = False


def _schema_error(code: str, message: str, field_errors: list[dict[str, str]] | None = None) -> dict:
    return {
        "code": code,
        "message": message,
        "field_errors": field_errors or [],
    }


def _validate_type(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True


def _validate_json_schema(payload: Any, schema: dict[str, Any] | None, strict: bool = True) -> list[dict[str, str]]:
    if not schema:
        return []
    errors: list[dict[str, str]] = []
    root_type = schema.get("type")
    if root_type and not _validate_type(payload, root_type):
        return [{"path": "$", "message": f"expected {root_type}, got {type(payload).__name__}"}]
    if root_type != "object" or not isinstance(payload, dict):
        return errors

    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    for req in required:
        if req not in payload:
            errors.append({"path": f"$.{req}", "message": "is required"})

    for key, value in payload.items():
        prop_schema = props.get(key)
        if prop_schema is None:
            if strict:
                errors.append({"path": f"$.{key}", "message": "unknown field"})
            continue
        expected_type = prop_schema.get("type")
        if expected_type and not _validate_type(value, expected_type):
            errors.append({"path": f"$.{key}", "message": f"expected {expected_type}, got {type(value).__name__}"})

    return errors


async def _evaluate_policy(tool: dict[str, Any], body: InvokeBody) -> tuple[bool, str]:
    action_type = str(tool.get("action_type") or "read")
    risk_level = str(tool.get("risk_level") or "low")
    context = {
        "tool_name": tool.get("name"),
        "action_type": action_type,
        "risk_level": risk_level,
        "risk_score": {"low": 20, "medium": 50, "high": 75, "critical": 90}.get(risk_level, 30),
        "environment": body.input.get("environment", "prod") if isinstance(body.input, dict) else "prod",
        "approved": bool(body.input.get("approved")) if isinstance(body.input, dict) else False,
        "requester": body.input.get("requester", "ops-user") if isinstance(body.input, dict) else "ops-user",
        "approver": body.input.get("approver", ""),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{GOVERNANCE_SERVICE_URL}/policies/evaluate", json=context)
        result = resp.json()
        if not result.get("success"):
            return False, result.get("error") or "policy evaluation failed"
        data = result.get("data") or {}
        allowed = bool(data.get("allowed"))
        require_approval = bool(data.get("require_approval"))
        reason = str(data.get("reason") or "")
        if require_approval and not body.dry_run:
            return False, reason or "approval required"
        return allowed or body.dry_run, reason
    except Exception as exc:  # noqa: BLE001
        return False, f"policy service unavailable: {exc}"


@router.post("/{tool_name}")
async def invoke_tool(tool_name: str, body: InvokeBody, response: Response) -> dict:
    request_id = str(uuid4())
    trace_id = str(uuid4())
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Trace-Id"] = trace_id

    tool = registry.get_tool(tool_name)
    if not tool:
        return make_error(
            error=f"unsupported tool: {tool_name}",
            data=_schema_error("TOOL_NOT_FOUND", "tool_name not registered"),
            request_id=request_id,
            trace_id=trace_id,
        )

    input_schema = tool.get("input_schema") if isinstance(tool, dict) else None
    field_errors = _validate_json_schema(body.input, input_schema, strict=STRICT_SCHEMA_VALIDATION)
    if field_errors:
        return make_error(
            error="invalid tool input",
            data=_schema_error("INPUT_SCHEMA_VALIDATION_FAILED", "input schema validation failed", field_errors),
            request_id=request_id,
            trace_id=trace_id,
        )

    allowed, deny_reason = await _evaluate_policy(tool, body)
    if not allowed:
        return make_error(
            error=f"policy denied: {deny_reason}",
            data=_schema_error("POLICY_DENIED", deny_reason or "policy denied"),
            request_id=request_id,
            trace_id=trace_id,
        )

    payload = {"input": body.input, "dry_run": body.dry_run}
    safe_path = quote(tool_name, safe="")

    if tool_name.startswith("vmware."):
        url = f"{VMWARE_GATEWAY_URL.rstrip('/')}/api/v1/invoke/{safe_path}"
        return await _forward_or_fail(url, payload, request_id, trace_id)

    if tool_name.startswith("k8s."):
        url = f"{KUBERNETES_GATEWAY_URL.rstrip('/')}/api/v1/invoke/{safe_path}"
        return await _forward_or_fail(url, payload, request_id, trace_id)

    if tool_name.startswith("change_impact."):
        url = f"{CHANGE_IMPACT_URL.rstrip('/')}/api/v1/invoke/{safe_path}"
        return await _forward_or_fail(url, payload, request_id, trace_id)

    return make_error(
        error=f"unsupported routing for tool: {tool_name}",
        data=_schema_error("UNSUPPORTED_TOOL_ROUTE", "tool route not configured"),
        request_id=request_id,
        trace_id=trace_id,
    )


async def _forward_or_fail(
    url: str,
    payload: dict[str, Any],
    request_id: str,
    trace_id: str,
) -> dict:
    headers = {
        "X-Request-Id": request_id,
        "X-Trace-Id": trace_id,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as e:
        if "/invoke/vmware." in url and VMWARE_GATEWAY_FALLBACK_URL:
            fallback_url = url.replace(
                VMWARE_GATEWAY_URL.rstrip("/"),
                VMWARE_GATEWAY_FALLBACK_URL.rstrip("/"),
                1,
            )
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    r = await client.post(fallback_url, json=payload, headers=headers)
            except httpx.RequestError:
                return make_error(
                    error=f"upstream request failed: {e}",
                    request_id=request_id,
                    trace_id=trace_id,
                )
        else:
            return make_error(
                error=f"upstream request failed: {e}",
                request_id=request_id,
                trace_id=trace_id,
            )

    try:
        body = r.json()
    except ValueError:
        if "/invoke/vmware." in url and VMWARE_GATEWAY_FALLBACK_URL:
            fallback_url = url.replace(
                VMWARE_GATEWAY_URL.rstrip("/"),
                VMWARE_GATEWAY_FALLBACK_URL.rstrip("/"),
                1,
            )
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    r2 = await client.post(fallback_url, json=payload, headers=headers)
                body2 = r2.json()
                if isinstance(body2, dict) and all(
                    k in body2 for k in ("request_id", "success", "message", "timestamp")
                ):
                    body2 = {**body2, "request_id": request_id, "trace_id": trace_id}
                    return body2
                if r2.is_success:
                    return make_success(
                        data=body2 if body2 is not None else {},
                        request_id=request_id,
                        trace_id=trace_id,
                    )
                return make_error(
                    error=body2.get("error") if isinstance(body2, dict) else str(body2),
                    request_id=request_id,
                    trace_id=trace_id,
                )
            except Exception:
                pass
        upstream_preview = (r.text or "").strip()[:1024]
        return make_error(
            error=(
                f"upstream returned non-JSON (status {r.status_code}); "
                f"body_preview={upstream_preview!r}"
            ),
            request_id=request_id,
            trace_id=trace_id,
        )

    if isinstance(body, dict) and all(
        k in body for k in ("request_id", "success", "message", "timestamp")
    ):
        body = {**body, "request_id": request_id, "trace_id": trace_id}
        return body

    if r.is_success:
        tool_name = unquote(url.rsplit("/invoke/", 1)[-1])
        tool = registry.get_tool(tool_name)
        output_schema = tool.get("output_schema") if isinstance(tool, dict) else None
        out_data = body if body is not None else {}
        out_field_errors = _validate_json_schema(out_data, output_schema, strict=False)
        if out_field_errors:
            return make_error(
                error="invalid tool output",
                data=_schema_error(
                    "OUTPUT_SCHEMA_VALIDATION_FAILED",
                    "output schema validation failed",
                    out_field_errors,
                ),
                request_id=request_id,
                trace_id=trace_id,
            )
        return make_success(
            data=out_data,
            request_id=request_id,
            trace_id=trace_id,
        )

    return make_error(
        error=body.get("error") if isinstance(body, dict) else str(body),
        request_id=request_id,
        trace_id=trace_id,
    )
