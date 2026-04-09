from __future__ import annotations

from opspilot_schema import ToolMeta

_TOOLS: list[dict] = [
    ToolMeta(name="vmware.get_vcenter_inventory", display_name="Get vCenter inventory", category="inventory", domain="vmware", provider="vmware", action_type="read", risk_level="low", approval_required=False, timeout_seconds=60, idempotent=True, version="1.0.0", tags=["inventory", "cluster", "host", "vm"]).model_dump(),
    ToolMeta(name="vmware.get_vm_detail", display_name="Get VM detail", category="compute", domain="vmware", provider="vmware", action_type="read", risk_level="low", approval_required=False, timeout_seconds=30, idempotent=True, version="1.0.0", tags=["vm", "detail"]).model_dump(),
    ToolMeta(name="vmware.get_host_detail", display_name="Get host detail", category="compute", domain="vmware", provider="vmware", action_type="read", risk_level="low", approval_required=False, timeout_seconds=30, idempotent=True, version="1.0.0", tags=["host", "detail"]).model_dump(),
    ToolMeta(name="vmware.get_cluster_detail", display_name="Get cluster detail", category="compute", domain="vmware", provider="vmware", action_type="read", risk_level="low", approval_required=False, timeout_seconds=30, idempotent=True, version="1.0.0", tags=["cluster", "detail"]).model_dump(),
    ToolMeta(name="vmware.query_events", display_name="Query events", category="observability", domain="vmware", provider="vmware", action_type="read", risk_level="low", approval_required=False, timeout_seconds=60, idempotent=True, version="1.0.0", tags=["event"]).model_dump(),
    ToolMeta(name="vmware.query_metrics", display_name="Query metrics", category="observability", domain="vmware", provider="vmware", action_type="read", risk_level="low", approval_required=False, timeout_seconds=60, idempotent=True, version="1.0.0", tags=["metric"]).model_dump(),
    ToolMeta(name="vmware.query_alerts", display_name="Query alerts", category="observability", domain="vmware", provider="vmware", action_type="read", risk_level="low", approval_required=False, timeout_seconds=60, idempotent=True, version="1.0.0", tags=["alert"]).model_dump(),
    ToolMeta(name="vmware.query_topology", display_name="Query topology", category="inventory", domain="vmware", provider="vmware", action_type="read", risk_level="low", approval_required=False, timeout_seconds=60, idempotent=True, version="1.0.0", tags=["topology"]).model_dump(),
    ToolMeta(name="vmware.create_snapshot", display_name="Create snapshot", category="compute", domain="vmware", provider="vmware", action_type="write", risk_level="medium", approval_required=True, timeout_seconds=300, idempotent=False, version="1.0.0", tags=["vm", "snapshot"]).model_dump(),
    ToolMeta(name="vmware.vm_migrate", display_name="Migrate VM", category="compute", domain="vmware", provider="vmware", action_type="write", risk_level="high", approval_required=True, timeout_seconds=900, idempotent=False, version="1.0.0", tags=["vm", "migrate"]).model_dump(),
    ToolMeta(name="vmware.vm_power_on", display_name="Power on VM", category="compute", domain="vmware", provider="vmware", action_type="write", risk_level="medium", approval_required=True, timeout_seconds=120, idempotent=False, version="1.0.0", tags=["vm", "power"]).model_dump(),
    ToolMeta(name="vmware.vm_power_off", display_name="Power off VM", category="compute", domain="vmware", provider="vmware", action_type="write", risk_level="high", approval_required=True, timeout_seconds=120, idempotent=False, version="1.0.0", tags=["vm", "power"]).model_dump(),
    ToolMeta(name="vmware.vm_guest_restart", display_name="Restart guest OS", category="compute", domain="vmware", provider="vmware", action_type="write", risk_level="medium", approval_required=True, timeout_seconds=120, idempotent=False, version="1.0.0", tags=["vm", "guest"]).model_dump(),
    ToolMeta(name="k8s.list_nodes", display_name="List nodes", category="cluster", domain="kubernetes", provider="kubernetes", action_type="read", risk_level="low", approval_required=False, timeout_seconds=30, idempotent=True, version="1.0.0", tags=["k8s", "node"]).model_dump(),
    ToolMeta(name="k8s.list_namespaces", display_name="List namespaces", category="cluster", domain="kubernetes", provider="kubernetes", action_type="read", risk_level="low", approval_required=False, timeout_seconds=30, idempotent=True, version="1.0.0", tags=["k8s", "namespace"]).model_dump(),
    ToolMeta(name="k8s.list_pods", display_name="List pods", category="workload", domain="kubernetes", provider="kubernetes", action_type="read", risk_level="low", approval_required=False, timeout_seconds=30, idempotent=True, version="1.0.0", tags=["k8s", "pod"]).model_dump(),
    ToolMeta(name="k8s.get_pod_logs", display_name="Get pod logs", category="workload", domain="kubernetes", provider="kubernetes", action_type="read", risk_level="low", approval_required=False, timeout_seconds=60, idempotent=True, version="1.0.0", tags=["k8s", "log"]).model_dump(),
    ToolMeta(name="k8s.get_workload_status", display_name="Get workload status", category="workload", domain="kubernetes", provider="kubernetes", action_type="read", risk_level="low", approval_required=False, timeout_seconds=60, idempotent=True, version="1.0.0", tags=["k8s", "deployment"]).model_dump(),
    ToolMeta(name="k8s.restart_deployment", display_name="Restart deployment", category="workload", domain="kubernetes", provider="kubernetes", action_type="write", risk_level="medium", approval_required=True, timeout_seconds=180, idempotent=False, version="1.0.0", tags=["k8s", "deployment"]).model_dump(),
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
