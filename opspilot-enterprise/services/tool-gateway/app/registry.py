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
    ToolMeta(name="vmware.host_restart", display_name="Restart host", category="compute", domain="vmware", provider="vmware", action_type="dangerous", risk_level="high", approval_required=True, timeout_seconds=300, idempotent=False, version="1.0.0", tags=["host", "restart", "reboot"]).model_dump(),
    ToolMeta(name="k8s.list_nodes", display_name="List nodes", category="cluster", domain="kubernetes", provider="kubernetes", action_type="read", risk_level="low", approval_required=False, timeout_seconds=30, idempotent=True, version="1.0.0", tags=["k8s", "node"]).model_dump(),
    ToolMeta(name="k8s.list_namespaces", display_name="List namespaces", category="cluster", domain="kubernetes", provider="kubernetes", action_type="read", risk_level="low", approval_required=False, timeout_seconds=30, idempotent=True, version="1.0.0", tags=["k8s", "namespace"]).model_dump(),
    ToolMeta(name="k8s.list_pods", display_name="List pods", category="workload", domain="kubernetes", provider="kubernetes", action_type="read", risk_level="low", approval_required=False, timeout_seconds=30, idempotent=True, version="1.0.0", tags=["k8s", "pod"]).model_dump(),
    ToolMeta(name="k8s.get_pod_logs", display_name="Get pod logs", category="workload", domain="kubernetes", provider="kubernetes", action_type="read", risk_level="low", approval_required=False, timeout_seconds=60, idempotent=True, version="1.0.0", tags=["k8s", "log"]).model_dump(),
    ToolMeta(name="k8s.get_workload_status", display_name="Get workload status", category="workload", domain="kubernetes", provider="kubernetes", action_type="read", risk_level="low", approval_required=False, timeout_seconds=60, idempotent=True, version="1.0.0", tags=["k8s", "deployment"]).model_dump(),
    ToolMeta(name="k8s.restart_deployment", display_name="Restart deployment", category="workload", domain="kubernetes", provider="kubernetes", action_type="write", risk_level="medium", approval_required=True, timeout_seconds=180, idempotent=False, version="1.0.0", tags=["k8s", "deployment"]).model_dump(),
    ToolMeta(name="k8s.scale_deployment", display_name="Scale deployment", category="workload", domain="kubernetes", provider="kubernetes", action_type="write", risk_level="medium", approval_required=True, timeout_seconds=180, idempotent=False, version="1.0.0", tags=["k8s", "deployment", "scale"]).model_dump(),
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
    ToolMeta(
        name="vmware.vm.power",
        display_name="VM Power Operation",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="write",
        risk_level="medium",
        approval_required=True,
        timeout_seconds=120,
        idempotent=False,
        version="2.0.0",
        tags=["vm", "power", "v2"],
    ).model_dump(),
    ToolMeta(
        name="vmware.vm.create",
        display_name="Create VM",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="dangerous",
        risk_level="high",
        approval_required=True,
        timeout_seconds=300,
        idempotent=False,
        version="2.0.0",
        tags=["vm", "create", "v2"],
    ).model_dump(),
    ToolMeta(
        name="vmware.vm.delete",
        display_name="Delete VM",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="dangerous",
        risk_level="critical",
        approval_required=True,
        timeout_seconds=300,
        idempotent=False,
        version="2.0.0",
        tags=["vm", "delete", "v2"],
    ).model_dump(),
    ToolMeta(
        name="vmware.vm.migrate",
        display_name="Migrate VM (V2)",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="write",
        risk_level="high",
        approval_required=True,
        timeout_seconds=900,
        idempotent=False,
        version="2.0.0",
        tags=["vm", "migrate", "v2"],
    ).model_dump(),
    ToolMeta(
        name="vmware.cluster.balance",
        display_name="Cluster Balance",
        category="compute",
        domain="vmware",
        provider="vmware",
        action_type="write",
        risk_level="high",
        approval_required=True,
        timeout_seconds=900,
        idempotent=False,
        version="2.0.0",
        tags=["cluster", "drs", "balance", "v2"],
    ).model_dump(),
    ToolMeta(
        name="vmware.vm.metrics",
        display_name="VM Metrics",
        category="observability",
        domain="vmware",
        provider="vmware",
        action_type="read",
        risk_level="low",
        approval_required=False,
        timeout_seconds=60,
        idempotent=True,
        version="2.0.0",
        tags=["vm", "metrics", "v2"],
    ).model_dump(),
    ToolMeta(
        name="vmware.host.metrics",
        display_name="Host Metrics",
        category="observability",
        domain="vmware",
        provider="vmware",
        action_type="read",
        risk_level="low",
        approval_required=False,
        timeout_seconds=60,
        idempotent=True,
        version="2.0.0",
        tags=["host", "metrics", "v2"],
    ).model_dump(),
    ToolMeta(
        name="vmware.vsan.health",
        display_name="vSAN Health",
        category="storage",
        domain="vmware",
        provider="vmware",
        action_type="read",
        risk_level="low",
        approval_required=False,
        timeout_seconds=60,
        idempotent=True,
        version="2.0.0",
        tags=["vsan", "health", "v2"],
    ).model_dump(),
    ToolMeta(
        name="vmware.datastore.usage",
        display_name="Datastore Usage",
        category="storage",
        domain="vmware",
        provider="vmware",
        action_type="read",
        risk_level="low",
        approval_required=False,
        timeout_seconds=60,
        idempotent=True,
        version="2.0.0",
        tags=["datastore", "usage", "v2"],
    ).model_dump(),
]

_DEFAULT_IO_SCHEMA: dict | None = None
_INPUT_SCHEMAS: dict[str, dict] = {
    "vmware.vm.power": {
        "type": "object",
        "properties": {"vm_id": {"type": "string"}, "action": {"type": "string"}},
        "required": ["vm_id", "action"],
    },
    "vmware.vm.create": {
        "type": "object",
        "properties": {"name": {"type": "string"}, "cpu_count": {"type": "integer"}, "memory_mb": {"type": "integer"}},
        "required": ["name", "cpu_count", "memory_mb"],
    },
    "vmware.vm.delete": {
        "type": "object",
        "properties": {"vm_id": {"type": "string"}},
        "required": ["vm_id"],
    },
    "vmware.vm.migrate": {
        "type": "object",
        "properties": {"vm_id": {"type": "string"}, "target_host_id": {"type": "string"}},
        "required": ["vm_id", "target_host_id"],
    },
    "vmware.vm.metrics": {
        "type": "object",
        "properties": {"vm_id": {"type": "string"}, "metric": {"type": "string"}},
        "required": ["vm_id", "metric"],
    },
    "vmware.host.metrics": {
        "type": "object",
        "properties": {"host_id": {"type": "string"}, "metric": {"type": "string"}},
        "required": ["host_id", "metric"],
    },
}
for tool in _TOOLS:
    name = tool.get("name")
    tool["input_schema"] = _INPUT_SCHEMAS.get(name, _DEFAULT_IO_SCHEMA)
    tool["output_schema"] = _DEFAULT_IO_SCHEMA


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
