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
        "k8s.list_nodes": lambda: query.list_nodes(query.ConnectionBody(connection=body.input.get("connection"))),
        "k8s.list_namespaces": lambda: query.list_namespaces(query.ConnectionBody(connection=body.input.get("connection"))),
        "k8s.list_pods": lambda: query.list_pods(
            query.NamespaceBody(namespace=body.input.get("namespace"), connection=body.input.get("connection"))
        ),
        "k8s.get_pod_logs": lambda: query.get_pod_logs(
            query.PodLogsBody(
                namespace=body.input["namespace"],
                pod_name=body.input["pod_name"],
                container=body.input.get("container"),
                tail_lines=body.input.get("tail_lines", 200),
                connection=body.input.get("connection"),
            )
        ),
        "k8s.get_workload_status": lambda: query.get_workload_status(
            query.NamespaceBody(namespace=body.input.get("namespace"), connection=body.input.get("connection"))
        ),
        "k8s.restart_deployment": lambda: execute.restart_deployment(
            execute.RestartDeploymentBody(
                namespace=body.input["namespace"],
                deployment_name=body.input["deployment_name"],
                dry_run=body.dry_run or body.input.get("dry_run", False),
                connection=body.input.get("connection"),
            )
        ),
        "k8s.scale_deployment": lambda: execute.scale_deployment(
            execute.ScaleDeploymentBody(
                namespace=body.input["namespace"],
                deployment_name=body.input["deployment_name"],
                replicas=int(body.input["replicas"]),
                dry_run=body.dry_run or body.input.get("dry_run", False),
                connection=body.input.get("connection"),
            )
        ),
    }
    handler = tool_map.get(tool_name)
    if not handler:
        return make_error(f"unsupported kubernetes tool: {tool_name}")
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result
