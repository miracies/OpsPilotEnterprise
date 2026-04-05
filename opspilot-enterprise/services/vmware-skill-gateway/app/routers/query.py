from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from opspilot_schema.envelope import make_error, make_success

from app import mock_data

router = APIRouter(prefix="/query", tags=["query"])


class VmIdBody(BaseModel):
    vm_id: str = Field(..., description="Virtual machine MOID or mock id")


class HostIdBody(BaseModel):
    host_id: str = Field(..., description="Host MOID or mock id")


class ClusterIdBody(BaseModel):
    cluster_id: str = Field(..., description="Cluster MOID or mock id")


class QueryEventsBody(BaseModel):
    object_id: str
    hours: int = Field(24, ge=1, le=168)


class QueryMetricsBody(BaseModel):
    object_id: str
    metric: str = Field(..., description="Metric key, e.g. cpu.usage.average")


@router.post("/get_vcenter_inventory")
def get_vcenter_inventory() -> dict:
    return make_success(mock_data.get_inventory())


@router.post("/get_vm_detail")
def get_vm_detail(body: VmIdBody) -> dict:
    detail = mock_data.get_vm_detail(body.vm_id)
    if detail is None:
        return make_error(f"Virtual machine not found: {body.vm_id}")
    return make_success(detail)


@router.post("/get_host_detail")
def get_host_detail(body: HostIdBody) -> dict:
    detail = mock_data.get_host_detail(body.host_id)
    if detail is None:
        return make_error(f"Host not found: {body.host_id}")
    return make_success(detail)


@router.post("/get_cluster_detail")
def get_cluster_detail(body: ClusterIdBody) -> dict:
    detail = mock_data.get_cluster_detail(body.cluster_id)
    if detail is None:
        return make_error(f"Cluster not found: {body.cluster_id}")
    return make_success(detail)


@router.post("/query_events")
def query_events(body: QueryEventsBody) -> dict:
    events = mock_data.get_events_for_object(body.object_id, body.hours)
    return make_success({"object_id": body.object_id, "hours": body.hours, "events": events})


@router.post("/query_metrics")
def query_metrics(body: QueryMetricsBody) -> dict:
    series = mock_data.get_metric_series(body.object_id, body.metric)
    return make_success(
        {"object_id": body.object_id, "metric": body.metric, "unit": "percent", "series": series}
    )


@router.post("/query_alerts")
def query_alerts() -> dict:
    return make_success({"alerts": mock_data.ALERTS})


@router.post("/query_topology")
def query_topology() -> dict:
    return make_success({"nodes": mock_data.TOPOLOGY_NODES})
