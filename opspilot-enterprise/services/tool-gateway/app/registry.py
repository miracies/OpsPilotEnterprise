from __future__ import annotations

from opspilot_schema import ToolMeta

_TOOLS: list[dict] = [
    ToolMeta(
        name="vmware.list_vms",
        display_name="List VMs",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="read",
        risk_level="low",
        approval_required=False,
        timeout_seconds=60,
        idempotent=True,
        version="1.0.0",
        tags=["vm", "inventory"],
    ).model_dump(),
    ToolMeta(
        name="vmware.get_vm",
        display_name="Get VM",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="read",
        risk_level="low",
        approval_required=False,
        timeout_seconds=30,
        idempotent=True,
        version="1.0.0",
        tags=["vm"],
    ).model_dump(),
    ToolMeta(
        name="vmware.power_on",
        display_name="Power on VM",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="write",
        risk_level="medium",
        approval_required=True,
        timeout_seconds=120,
        idempotent=False,
        version="1.0.0",
        tags=["vm", "power"],
    ).model_dump(),
    ToolMeta(
        name="vmware.power_off",
        display_name="Power off VM",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="write",
        risk_level="high",
        approval_required=True,
        timeout_seconds=120,
        idempotent=False,
        version="1.0.0",
        tags=["vm", "power"],
    ).model_dump(),
    ToolMeta(
        name="vmware.snapshot",
        display_name="Create snapshot",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="write",
        risk_level="medium",
        approval_required=True,
        timeout_seconds=300,
        idempotent=False,
        version="1.0.0",
        tags=["vm", "snapshot"],
    ).model_dump(),
    ToolMeta(
        name="vmware.clone",
        display_name="Clone VM",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="write",
        risk_level="high",
        approval_required=True,
        timeout_seconds=600,
        idempotent=False,
        version="1.0.0",
        tags=["vm", "clone"],
    ).model_dump(),
    ToolMeta(
        name="vmware.migrate",
        display_name="Migrate VM",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="write",
        risk_level="high",
        approval_required=True,
        timeout_seconds=900,
        idempotent=False,
        version="1.0.0",
        tags=["vm", "migrate"],
    ).model_dump(),
    ToolMeta(
        name="vmware.list_networks",
        display_name="List networks",
        category="network",
        domain="vmware",
        provider="vmware",
        action_type="read",
        risk_level="low",
        approval_required=False,
        timeout_seconds=45,
        idempotent=True,
        version="1.0.0",
        tags=["network"],
    ).model_dump(),
    ToolMeta(
        name="change_impact.analyze",
        display_name="Analyze change impact",
        category="change",
        domain="change_management",
        provider="change_impact",
        action_type="read",
        risk_level="low",
        approval_required=False,
        timeout_seconds=180,
        idempotent=True,
        version="1.0.0",
        tags=["change", "impact"],
    ).model_dump(),
]


def list_tools() -> list[dict]:
    return list(_TOOLS)


def get_tool(name: str) -> dict | None:
    for t in _TOOLS:
        if t["name"] == name:
            return t
    return None


def register_tool(meta: dict) -> dict:
    validated = ToolMeta(**meta).model_dump()
    unregister_tool(validated["name"])
    _TOOLS.append(validated)
    return validated


def unregister_tool(name: str) -> bool:
    for i, t in enumerate(_TOOLS):
        if t["name"] == name:
            del _TOOLS[i]
            return True
    return False
