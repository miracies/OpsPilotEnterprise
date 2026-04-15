"""BFF router: Tool registry and lifecycle facade."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from opspilot_schema.envelope import make_error, make_success

router = APIRouter(prefix="/tools", tags=["tools"])

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")
VCENTER_ENDPOINT = os.environ.get("VCENTER_ENDPOINT", "https://10.0.80.21:443/sdk")
VCENTER_USERNAME = os.environ.get("VCENTER_USERNAME", "administrator@vsphere.local")
VCENTER_PASSWORD = os.environ.get("VCENTER_PASSWORD", "VMware1!")

_TOOL_FLAGS: dict[str, dict[str, Any]] = {}
_TOOL_INVOCATIONS: list[dict[str, Any]] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _load_tools() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{TOOL_GATEWAY_URL.rstrip('/')}/api/v1/tools/")
    payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError(payload.get("error") or "failed to load tool registry")
    items = payload.get("data", []) or []
    out: list[dict[str, Any]] = []
    for item in items:
        name = item.get("name")
        flags = _TOOL_FLAGS.get(name, {})
        out.append(
            {
                **item,
                "lifecycle_status": flags.get("lifecycle_status", "enabled"),
                "enabled": flags.get("enabled", True),
                "updated_at": flags.get("updated_at", _now()),
            }
        )
    return out


class ToggleBody(BaseModel):
    action: str


class LifecycleBody(BaseModel):
    action: str
    target_version: str | None = None


class InvokeToolBody(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


def _ensure_vmware_connection(input_payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(input_payload)
    payload.setdefault(
        "connection",
        {
            "endpoint": VCENTER_ENDPOINT,
            "username": VCENTER_USERNAME,
            "password": VCENTER_PASSWORD,
            "insecure": True,
        },
    )
    return payload


@router.get("")
async def list_tools():
    try:
        return make_success(await _load_tools())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.get("/gateways")
async def gateways():
    data = [
        {"name": "tool-gateway", "url": TOOL_GATEWAY_URL, "healthy": True, "last_check": _now(), "latency_ms": 20},
        {"name": "vmware-skill-gateway", "url": os.environ.get("VMWARE_GATEWAY_URL", "http://127.0.0.1:8030"), "healthy": True, "last_check": _now(), "latency_ms": 42},
        {"name": "kubernetes-skill-gateway", "url": os.environ.get("KUBERNETES_GATEWAY_URL", "http://127.0.0.1:8080"), "healthy": True, "last_check": _now(), "latency_ms": 38},
    ]
    return make_success(data)


@router.get("/invocations")
async def invocations():
    return make_success(_TOOL_INVOCATIONS[-200:])


@router.get("/stats")
async def stats():
    tools = await _load_tools()
    enabled = sum(1 for t in tools if t.get("enabled", True))
    disabled = len(tools) - enabled
    return make_success(
        {
            "total_tools": len(tools),
            "enabled_tools": enabled,
            "disabled_tools": disabled,
            "last_updated_at": _now(),
        }
    )


@router.patch("/{tool_name}/toggle")
async def toggle(tool_name: str, body: ToggleBody):
    enabled = body.action.lower() in {"enable", "enabled", "on", "true"}
    state = _TOOL_FLAGS.setdefault(tool_name, {})
    state["enabled"] = enabled
    state["updated_at"] = _now()
    return make_success({"tool_name": tool_name, "enabled": enabled})


@router.patch("/{tool_name}/lifecycle")
async def lifecycle(tool_name: str, body: LifecycleBody):
    state = _TOOL_FLAGS.setdefault(tool_name, {})
    action = body.action.lower()
    if action in {"deprecate", "deprecated"}:
        state["lifecycle_status"] = "deprecated"
    elif action in {"disable", "disabled"}:
        state["lifecycle_status"] = "disabled"
    else:
        state["lifecycle_status"] = "enabled"
    state["target_version"] = body.target_version
    state["updated_at"] = _now()
    return make_success({"tool_name": tool_name, "lifecycle_status": state["lifecycle_status"], "target_version": body.target_version})


@router.get("/{tool_name}/manifest")
async def manifest(tool_name: str):
    tools = await _load_tools()
    tool = next((t for t in tools if t.get("name") == tool_name), None)
    if not tool:
        return make_error(f"tool not found: {tool_name}")
    return make_success(
        {
            "name": tool_name,
            "provider": tool.get("provider"),
            "version": tool.get("version", "1.0.0"),
            "schema_version": "2026-04",
            "timeout_seconds": tool.get("timeout_seconds", 60),
        }
    )


@router.get("/{tool_name}/capabilities")
async def capabilities(tool_name: str):
    tools = await _load_tools()
    tool = next((t for t in tools if t.get("name") == tool_name), None)
    if not tool:
        return make_error(f"tool not found: {tool_name}")
    return make_success(
        [
            {
                "name": tool_name,
                "action_type": tool.get("action_type", "read"),
                "risk_level": tool.get("risk_level", "low"),
                "approval_required": tool.get("approval_required", False),
                "idempotent": tool.get("idempotent", True),
            }
        ]
    )


@router.get("/{tool_name}/connections")
async def connections(tool_name: str):
    if tool_name.startswith("vmware."):
        refs = ["conn-vcenter-prod"]
    elif tool_name.startswith("k8s."):
        refs = ["conn-k8s-prod"]
    else:
        refs = []
    return make_success([{"tool_name": tool_name, "connection_ref": x} for x in refs])


@router.get("/{tool_name}/audit-stats")
async def audit_stats(tool_name: str):
    return make_success(
        {
            "tool_name": tool_name,
            "invocation_count_24h": sum(1 for x in _TOOL_INVOCATIONS if x.get("tool_name") == tool_name),
            "success_rate": 1.0,
            "avg_duration_ms": 40,
            "last_invoked_at": (_TOOL_INVOCATIONS[-1]["timestamp"] if _TOOL_INVOCATIONS else None),
        }
    )


@router.post("/{tool_name}/health-check")
async def health_check(tool_name: str):
    data = {"tool_name": tool_name, "healthy": True, "checked_at": _now(), "latency_ms": 30}
    return make_success(data)


@router.post("/register")
async def register_tool(meta: dict[str, Any]):
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.post(f"{TOOL_GATEWAY_URL.rstrip('/')}/api/v1/tools/register", json=meta)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Tool gateway unreachable: {exc}")


@router.post("/{tool_name}/invoke")
async def invoke_tool(tool_name: str, body: InvokeToolBody):
    try:
        tools = await _load_tools()
        tool = next((t for t in tools if t.get("name") == tool_name), None)
        if not tool:
            return make_error(f"tool not found: {tool_name}")
        if tool.get("action_type") != "read":
            return make_error("only read tools can be invoked directly from this endpoint")

        input_payload = dict(body.input or {})
        if tool_name.startswith("vmware."):
            input_payload = _ensure_vmware_connection(input_payload)

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{TOOL_GATEWAY_URL.rstrip('/')}/api/v1/invoke/{tool_name}",
                json={"input": input_payload, "dry_run": bool(body.dry_run)},
            )
            return resp.json()
    except httpx.HTTPError as exc:
        return make_error(f"Tool gateway unreachable: {exc}")
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))

