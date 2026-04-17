from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from opspilot_schema.envelope import make_error

from app.routers import execute, query

router = APIRouter(prefix="/invoke", tags=["invoke"])


class InvokeBody(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


@router.post("/{tool_name}")
async def invoke(tool_name: str, body: InvokeBody) -> dict:
    def _required(key: str) -> Any:
        val = body.input.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            raise ValueError(f"missing required input: {key}")
        return val

    try:
        if tool_name == "vmware.vm.power":
            vm_id = str(_required("vm_id"))
            action = str(_required("action")).lower()
            if action in {"on", "power_on", "start"}:
                return await execute.vm_power_on(
                    execute.VmIdOnlyBody(
                        vm_id=vm_id,
                        dry_run=body.dry_run or body.input.get("dry_run", False),
                        connection=body.input.get("connection"),
                    )
                )
            if action in {"off", "power_off", "stop"}:
                return await execute.vm_power_off(
                    execute.VmIdOnlyBody(
                        vm_id=vm_id,
                        dry_run=body.dry_run or body.input.get("dry_run", False),
                        connection=body.input.get("connection"),
                    )
                )
            return make_error("unsupported action for vmware.vm.power, expected on/off")
        if tool_name == "vmware.vm.create":
            return make_error("not_supported: vmware.vm.create is not implemented in this release")
        if tool_name == "vmware.vm.delete":
            return make_error("not_supported: vmware.vm.delete is not implemented in this release")
        if tool_name == "vmware.vm.migrate":
            return execute.vm_migrate(
                execute.VmMigrateBody(
                    vm_id=str(_required("vm_id")),
                    target_host_id=str(_required("target_host_id")),
                    dry_run=body.dry_run or body.input.get("dry_run", False),
                )
            )
        if tool_name == "vmware.cluster.balance":
            return make_error("not_supported: vmware.cluster.balance is not implemented in this release")
        if tool_name == "vmware.vm.metrics":
            return await query.query_metrics(
                query.QueryMetricsBody(
                    object_id=str(_required("vm_id")),
                    metric=str(_required("metric")),
                    connection=body.input.get("connection"),
                )
            )
        if tool_name == "vmware.host.metrics":
            return await query.query_metrics(
                query.QueryMetricsBody(
                    object_id=str(_required("host_id")),
                    metric=str(_required("metric")),
                    connection=body.input.get("connection"),
                )
            )
        if tool_name == "vmware.vsan.health":
            alerts = await query.query_alerts(query.ConnectionBody(connection=body.input.get("connection")))
            return alerts
        if tool_name == "vmware.datastore.usage":
            inventory = await query.get_vcenter_inventory(query.ConnectionBody(connection=body.input.get("connection")))
            return inventory
        if tool_name == "vmware.get_vcenter_inventory":
            return await query.get_vcenter_inventory(query.ConnectionBody(connection=body.input.get("connection")))
        if tool_name == "vmware.get_vm_detail":
            return await query.get_vm_detail(
                query.VmIdBody(vm_id=str(_required("vm_id")), connection=body.input.get("connection"))
            )
        if tool_name == "vmware.get_host_detail":
            return await query.get_host_detail(
                query.HostIdBody(host_id=str(_required("host_id")), connection=body.input.get("connection"))
            )
        if tool_name == "vmware.get_cluster_detail":
            return await query.get_cluster_detail(
                query.ClusterIdBody(cluster_id=str(_required("cluster_id")), connection=body.input.get("connection"))
            )
        if tool_name == "vmware.query_events":
            return await query.query_events(
                query.QueryEventsBody(
                    object_id=str(_required("object_id")),
                    hours=body.input.get("hours", 24),
                    connection=body.input.get("connection"),
                )
            )
        if tool_name == "vmware.query_metrics":
            return await query.query_metrics(
                query.QueryMetricsBody(
                    object_id=str(_required("object_id")),
                    metric=str(_required("metric")),
                    connection=body.input.get("connection"),
                )
            )
        if tool_name == "vmware.query_alerts":
            return await query.query_alerts(query.ConnectionBody(connection=body.input.get("connection")))
        if tool_name == "vmware.query_topology":
            return await query.query_topology(query.ConnectionBody(connection=body.input.get("connection")))
        if tool_name == "vmware.create_snapshot":
            return await execute.create_snapshot(
                execute.CreateSnapshotBody(
                    vm_id=str(_required("vm_id")),
                    name=str(_required("name")),
                    dry_run=body.dry_run or body.input.get("dry_run", False),
                    connection=body.input.get("connection"),
                )
            )
        if tool_name == "vmware.vm_migrate":
            return execute.vm_migrate(
                execute.VmMigrateBody(
                    vm_id=str(_required("vm_id")),
                    target_host_id=str(_required("target_host_id")),
                    dry_run=body.dry_run or body.input.get("dry_run", False),
                )
            )
        if tool_name == "vmware.vm_power_on":
            return await execute.vm_power_on(
                execute.VmIdOnlyBody(
                    vm_id=str(_required("vm_id")),
                    dry_run=body.dry_run or body.input.get("dry_run", False),
                    connection=body.input.get("connection"),
                )
            )
        if tool_name == "vmware.vm_power_off":
            return await execute.vm_power_off(
                execute.VmIdOnlyBody(
                    vm_id=str(_required("vm_id")),
                    dry_run=body.dry_run or body.input.get("dry_run", False),
                    connection=body.input.get("connection"),
                )
            )
        if tool_name == "vmware.vm_guest_restart":
            return await execute.vm_guest_restart(
                execute.VmIdOnlyBody(
                    vm_id=str(_required("vm_id")),
                    dry_run=body.dry_run or body.input.get("dry_run", False),
                    connection=body.input.get("connection"),
                )
            )
        if tool_name == "vmware.host_restart":
            return await execute.host_restart(
                execute.HostIdOnlyBody(
                    host_id=str(_required("host_id")),
                    dry_run=body.dry_run or body.input.get("dry_run", False),
                    connection=body.input.get("connection"),
                )
            )
        return make_error(f"unsupported vmware tool: {tool_name}")
    except ValueError as exc:
        return make_error(str(exc))
