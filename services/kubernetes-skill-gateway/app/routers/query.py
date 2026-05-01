from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from opspilot_schema.envelope import make_success

from app.services.k8s_service import KubernetesService

router = APIRouter(prefix="/query", tags=["query"])


class ConnectionBody(BaseModel):
    connection: dict | None = None


class NamespaceBody(BaseModel):
    namespace: str | None = None
    connection: dict | None = None


class PodLogsBody(BaseModel):
    namespace: str
    pod_name: str
    container: str | None = None
    tail_lines: int = Field(200, ge=1, le=2000)
    connection: dict | None = None


@router.post("/list_nodes")
async def list_nodes(body: ConnectionBody | None = None) -> dict:
    data = await KubernetesService(body.connection if body else None).list_nodes()
    return make_success({"nodes": data})


@router.post("/list_namespaces")
async def list_namespaces(body: ConnectionBody | None = None) -> dict:
    data = await KubernetesService(body.connection if body else None).list_namespaces()
    return make_success({"namespaces": data})


@router.post("/list_pods")
async def list_pods(body: NamespaceBody) -> dict:
    data = await KubernetesService(body.connection).list_pods(body.namespace)
    return make_success({"pods": data, "namespace": body.namespace})


@router.post("/get_pod_logs")
async def get_pod_logs(body: PodLogsBody) -> dict:
    data = await KubernetesService(body.connection).get_pod_logs(
        namespace=body.namespace,
        pod_name=body.pod_name,
        container=body.container,
        tail_lines=body.tail_lines,
    )
    return make_success(data)


@router.post("/get_workload_status")
async def get_workload_status(body: NamespaceBody) -> dict:
    data = await KubernetesService(body.connection).get_workload_status(body.namespace)
    return make_success(data)
