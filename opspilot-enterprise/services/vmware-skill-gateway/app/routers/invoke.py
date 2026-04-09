from __future__ import annotations

import inspect
from typing import Any, Callable

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
    tool_map: dict[str, Callable[[], Any]] = {
        "vmware.get_vcenter_inventory": lambda: query.get_vcenter_inventory(
            query.ConnectionBody(connection=body.input.get("connection"))
        ),
        "vmware.get_vm_detail": lambda: query.get_vm_detail(
            query.VmIdBody(vm_id=body.input["vm_id"], connection=body.input.get("connection"))
        ),
        "vmware.get_host_detail": lambda: query.get_host_detail(
            query.HostIdBody(host_id=body.input["host_id"], connection=body.input.get("connection"))
        ),
        "vmware.get_cluster_detail": lambda: query.get_cluster_detail(
            query.ClusterIdBody(cluster_id=body.input["cluster_id"], connection=body.input.get("connection"))
        ),
        "vmware.query_events": lambda: query.query_events(
            query.QueryEventsBody(
                object_id=body.input["object_id"],
                hours=body.input.get("hours", 24),
                connection=body.input.get("connection"),
            )
        ),
        "vmware.query_metrics": lambda: query.query_metrics(
            query.QueryMetricsBody(
                object_id=body.input["object_id"],
                metric=body.input["metric"],
                connection=body.input.get("connection"),
            )
        ),
        "vmware.query_alerts": lambda: query.query_alerts(
            query.ConnectionBody(connection=body.input.get("connection"))
        ),
        "vmware.query_topology": lambda: query.query_topology(
            query.ConnectionBody(connection=body.input.get("connection"))
        ),
        "vmware.create_snapshot": lambda: execute.create_snapshot(
            execute.CreateSnapshotBody(vm_id=body.input["vm_id"], name=body.input["name"])
        ),
        "vmware.vm_migrate": lambda: execute.vm_migrate(
            execute.VmMigrateBody(
                vm_id=body.input["vm_id"],
                target_host_id=body.input["target_host_id"],
                dry_run=body.dry_run or body.input.get("dry_run", False),
            )
        ),
        "vmware.vm_power_on": lambda: execute.vm_power_on(execute.VmIdOnlyBody(vm_id=body.input["vm_id"])),
        "vmware.vm_power_off": lambda: execute.vm_power_off(execute.VmIdOnlyBody(vm_id=body.input["vm_id"])),
        "vmware.vm_guest_restart": lambda: execute.vm_guest_restart(
            execute.VmIdOnlyBody(vm_id=body.input["vm_id"])
        ),
    }
    handler = tool_map.get(tool_name)
    if not handler:
        return make_error(f"unsupported vmware tool: {tool_name}")
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result
