from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from opspilot_schema.envelope import make_error, make_success

from app.services.vcenter_service import VCenterService

router = APIRouter(prefix="/query", tags=["query"])


class ConnectionBody(BaseModel):
    connection: dict | None = None


class VmIdBody(BaseModel):
    vm_id: str = Field(..., description="Virtual machine MOID or mock id")
    connection: dict | None = None


class HostIdBody(BaseModel):
    host_id: str = Field(..., description="Host MOID or mock id")
    connection: dict | None = None


class ClusterIdBody(BaseModel):
    cluster_id: str = Field(..., description="Cluster MOID or mock id")
    connection: dict | None = None


class QueryEventsBody(BaseModel):
    object_id: str
    hours: int = Field(24, ge=1, le=168)
    connection: dict | None = None


class QueryMetricsBody(BaseModel):
    object_id: str
    metric: str = Field(..., description="Metric key, e.g. cpu.usage.average")
    connection: dict | None = None


@router.post("/get_vcenter_inventory")
async def get_vcenter_inventory(body: ConnectionBody | None = None) -> dict:
    data = await VCenterService(body.connection if body else None).get_inventory()
    return make_success(data)


@router.post("/get_vm_detail")
async def get_vm_detail(body: VmIdBody) -> dict:
    detail = await VCenterService(body.connection).get_vm_detail(body.vm_id)
    if detail is None:
        return make_error(f"Virtual machine not found: {body.vm_id}")
    return make_success(detail)


@router.post("/get_host_detail")
async def get_host_detail(body: HostIdBody) -> dict:
    detail = await VCenterService(body.connection).get_host_detail(body.host_id)
    if detail is None:
        return make_error(f"Host not found: {body.host_id}")
    return make_success(detail)


@router.post("/get_cluster_detail")
async def get_cluster_detail(body: ClusterIdBody) -> dict:
    detail = await VCenterService(body.connection).get_cluster_detail(body.cluster_id)
    if detail is None:
        return make_error(f"Cluster not found: {body.cluster_id}")
    return make_success(detail)


@router.post("/query_events")
async def query_events(body: QueryEventsBody) -> dict:
    events = await VCenterService(body.connection).query_events(body.object_id, body.hours)
    return make_success({"object_id": body.object_id, "hours": body.hours, "events": events})


@router.post("/query_metrics")
async def query_metrics(body: QueryMetricsBody) -> dict:
    data = await VCenterService(body.connection).query_metrics(body.object_id, body.metric)
    return make_success(data)


@router.post("/query_alerts")
async def query_alerts(body: ConnectionBody | None = None) -> dict:
    alerts = await VCenterService(body.connection if body else None).query_alerts()
    return make_success({"alerts": alerts})


@router.post("/query_topology")
async def query_topology(body: ConnectionBody | None = None) -> dict:
    nodes = await VCenterService(body.connection if body else None).query_topology()
    return make_success({"nodes": nodes})
