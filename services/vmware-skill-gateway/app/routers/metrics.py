from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Response

from app.services.vcenter_service import VCenterService

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _label(value: Any) -> str:
    return str(value or "").replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _line(name: str, labels: dict[str, Any], value: Any) -> str | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    rendered = ",".join(f'{key}="{_label(val)}"' for key, val in labels.items() if val is not None)
    return f"{name}{{{rendered}}} {number}"


def _free_percent(row: dict[str, Any]) -> float | None:
    if row.get("free_percent") is not None:
        try:
            return float(row["free_percent"])
        except (TypeError, ValueError):
            return None
    try:
        capacity = float(row.get("capacity_gb") or 0)
        free = float(row.get("free_gb") or 0)
        return round(free * 100 / capacity, 2) if capacity > 0 else None
    except (TypeError, ValueError):
        return None


def _host_labels(connection_id: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "connection_id": connection_id,
        "host_id": row.get("host_id"),
        "host_name": row.get("name"),
        "cluster_id": row.get("cluster_id"),
    }


def _datastore_labels(connection_id: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "connection_id": connection_id,
        "datastore_id": row.get("id"),
        "datastore_name": row.get("name"),
        "type": row.get("type"),
    }


def _format_metrics(inventory: dict[str, Any], connection_id: str) -> str:
    lines = [
        "# HELP opspilot_vmware_host_cpu_usage_percent VMware host CPU usage percentage.",
        "# TYPE opspilot_vmware_host_cpu_usage_percent gauge",
        "# HELP opspilot_vmware_host_memory_usage_percent VMware host memory usage percentage.",
        "# TYPE opspilot_vmware_host_memory_usage_percent gauge",
        "# HELP opspilot_vmware_datastore_free_percent VMware datastore free capacity percentage.",
        "# TYPE opspilot_vmware_datastore_free_percent gauge",
    ]
    for host in inventory.get("hosts", []) or []:
        if not isinstance(host, dict):
            continue
        labels = _host_labels(connection_id, host)
        cpu_total = host.get("cpu_mhz")
        mem_total = host.get("memory_mb")
        cpu_usage_percent = host.get("cpu_usage_percent")
        memory_usage_percent = host.get("memory_usage_percent")
        if cpu_usage_percent is None and cpu_total:
            cpu_usage_percent = round(float(host.get("cpu_usage_mhz") or 0) * 100 / float(cpu_total), 2)
        if memory_usage_percent is None and mem_total:
            memory_usage_percent = round(float(host.get("memory_usage_mb") or 0) * 100 / float(mem_total), 2)
        for item in (
            _line("opspilot_vmware_host_cpu_usage_percent", labels, cpu_usage_percent),
            _line("opspilot_vmware_host_cpu_capacity_mhz", labels, cpu_total),
            _line("opspilot_vmware_host_memory_usage_percent", labels, memory_usage_percent),
            _line("opspilot_vmware_host_memory_capacity_mb", labels, mem_total),
        ):
            if item:
                lines.append(item)
    for ds in inventory.get("datastores", []) or []:
        if not isinstance(ds, dict):
            continue
        labels = _datastore_labels(connection_id, ds)
        for item in (
            _line("opspilot_vmware_datastore_free_percent", labels, _free_percent(ds)),
            _line("opspilot_vmware_datastore_capacity_gb", labels, ds.get("capacity_gb")),
            _line("opspilot_vmware_datastore_free_gb", labels, ds.get("free_gb")),
        ):
            if item:
                lines.append(item)
        for metric in ("datastore_iops", "datastore_latency_ms", "datastore_throughput_mbps"):
            if ds.get(metric) is not None:
                line = _line(f"opspilot_vmware_{metric}", labels, ds.get(metric))
                if line:
                    lines.append(line)
    return "\n".join(lines) + "\n"


@router.get("/vmware")
async def vmware_metrics() -> Response:
    connection_id = os.environ.get("VCENTER_CONNECTION_ID", "conn-vcenter-prod")
    try:
        inventory = await VCenterService(None).get_inventory()
    except Exception as exc:  # noqa: BLE001
        return Response(f"# VMware metrics unavailable: {exc}\n", media_type="text/plain; version=0.0.4", status_code=503)
    return Response(_format_metrics(inventory, connection_id), media_type="text/plain; version=0.0.4")
