from __future__ import annotations

import asyncio
import os
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from app import mock_data

try:
    from pyVim.connect import Disconnect, SmartConnect
    try:
        from pyVim.connect import SmartConnectNoSSL
    except Exception:
        SmartConnectNoSSL = None
    from pyVmomi import vim
except Exception:  # pragma: no cover - optional runtime dependency
    Disconnect = SmartConnect = SmartConnectNoSSL = None
    vim = None


UTC = timezone.utc


@dataclass
class VCenterConnection:
    endpoint: str
    username: str
    password: str
    insecure: bool = True
    port: int = 443

    @classmethod
    def from_input(cls, connection: dict[str, Any] | None = None) -> "VCenterConnection":
        payload = connection or {}
        endpoint = payload.get("endpoint") or os.environ.get("VCENTER_ENDPOINT", "")
        username = payload.get("username") or os.environ.get("VCENTER_USERNAME", "")
        password = payload.get("password") or os.environ.get("VCENTER_PASSWORD", "")
        insecure = bool(payload.get("insecure", True))
        parsed = urlparse(endpoint)
        port = parsed.port or 443
        if not endpoint or not username or not password:
            raise ValueError("missing vCenter endpoint or credentials")
        return cls(endpoint=endpoint, username=username, password=password, insecure=insecure, port=port)

    @property
    def host(self) -> str:
        parsed = urlparse(self.endpoint)
        return parsed.hostname or self.endpoint


def _moid(obj: Any) -> str:
    return getattr(obj, "_moId", "")


def _overall_status(obj: Any) -> str:
    status = getattr(obj, "overallStatus", None)
    return str(status) if status is not None else "gray"


def _connect(connection: VCenterConnection):
    if SmartConnect is None:
        raise RuntimeError("pyVmomi is not installed")
    if connection.insecure:
        if SmartConnectNoSSL is not None:
            return SmartConnectNoSSL(
                host=connection.host,
                user=connection.username,
                pwd=connection.password,
                port=connection.port,
            )
        # pyVmomi variants may not expose SmartConnectNoSSL; use an
        # unverified SSL context for the same behavior.
        insecure_ctx = ssl._create_unverified_context()
        return SmartConnect(
            host=connection.host,
            user=connection.username,
            pwd=connection.password,
            port=connection.port,
            sslContext=insecure_ctx,
        )
    ctx = ssl.create_default_context()
    return SmartConnect(
        host=connection.host,
        user=connection.username,
        pwd=connection.password,
        port=connection.port,
        sslContext=ctx,
    )


def _get_objects(content: Any, vim_type: Any) -> list[Any]:
    view = content.viewManager.CreateContainerView(content.rootFolder, [vim_type], True)
    try:
        return list(view.view)
    finally:
        view.Destroy()


def _host_summary(host: Any) -> dict[str, Any]:
    summary = host.summary
    hardware = summary.hardware
    quick = summary.quickStats
    return {
        "host_id": _moid(host),
        "name": host.name,
        "cluster_id": _moid(host.parent) if getattr(host, "parent", None) else None,
        "cpu_mhz": int(hardware.cpuMhz * hardware.numCpuCores),
        "cpu_usage_mhz": int(getattr(quick, "overallCpuUsage", 0) or 0),
        "memory_mb": int(hardware.memorySize / 1024 / 1024),
        "memory_usage_mb": int(getattr(quick, "overallMemoryUsage", 0) or 0),
        "vm_count": len(getattr(host, "vm", [])),
        "connection_state": str(summary.runtime.connectionState),
        "power_state": str(summary.runtime.powerState),
        "version": getattr(summary.config.product, "version", ""),
        "build": getattr(summary.config.product, "build", ""),
        "overall_status": _overall_status(host),
    }


def _vm_summary(vm: Any) -> dict[str, Any]:
    summary = vm.summary
    config = summary.config
    runtime = summary.runtime
    guest = summary.guest
    quick = summary.quickStats
    return {
        "vm_id": _moid(vm),
        "name": config.name,
        "host_id": _moid(runtime.host) if getattr(runtime, "host", None) else None,
        "cluster_id": _moid(runtime.host.parent) if getattr(runtime, "host", None) and getattr(runtime.host, "parent", None) else None,
        "cpu_count": int(getattr(config, "numCpu", 0) or 0),
        "memory_mb": int(getattr(config, "memorySizeMB", 0) or 0),
        "power_state": str(runtime.powerState),
        "guest_os": getattr(config, "guestFullName", "") or getattr(config, "guestId", ""),
        "ip_addresses": [guest.ipAddress] if getattr(guest, "ipAddress", None) else [],
        "annotation": getattr(config, "annotation", "") or "",
        "tools_status": str(getattr(guest, "toolsRunningStatus", "") or getattr(guest, "toolsStatus", "")),
        "cpu_usage_mhz": int(getattr(quick, "overallCpuUsage", 0) or 0),
        "memory_usage_mb": int(getattr(quick, "guestMemoryUsage", 0) or 0),
        "overall_status": _overall_status(vm),
    }


def _cluster_summary(cluster: Any) -> dict[str, Any]:
    summary = cluster.summary
    return {
        "cluster_id": _moid(cluster),
        "name": cluster.name,
        "drs_enabled": bool(getattr(cluster.configuration.drsConfig, "enabled", False)),
        "ha_enabled": bool(getattr(cluster.configuration.dasConfig, "enabled", False)),
        "host_count": int(getattr(summary, "numHosts", 0) or len(getattr(cluster, "host", []))),
        "vm_count": int(getattr(summary, "numVmotions", 0) or sum(len(getattr(h, "vm", [])) for h in getattr(cluster, "host", []))),
        "overall_status": _overall_status(cluster),
        "datacenter": getattr(getattr(getattr(cluster, "parent", None), "parent", None), "name", ""),
    }


def _datastore_summary(ds: Any) -> dict[str, Any]:
    summary = ds.summary
    return {
        "id": _moid(ds),
        "name": summary.name,
        "type": summary.type,
        "capacity_gb": round((summary.capacity or 0) / 1024 / 1024 / 1024, 2),
        "free_gb": round((summary.freeSpace or 0) / 1024 / 1024 / 1024, 2),
    }


class VCenterService:
    def __init__(self, connection: dict[str, Any] | None = None):
        self._connection_input = connection

    async def _run(self, func):
        try:
            return await asyncio.to_thread(func)
        except Exception:
            if os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true":
                raise
            raise

    def _with_client(self, handler):
        connection = VCenterConnection.from_input(self._connection_input)
        si = _connect(connection)
        try:
            content = si.RetrieveContent()
            return handler(content, connection)
        finally:
            Disconnect(si)

    async def get_inventory(self) -> dict[str, Any]:
        def _impl():
            return self._with_client(self._get_inventory_sync)

        try:
            return await self._run(_impl)
        except Exception:
            if os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true":
                return mock_data.get_inventory()
            raise

    def _get_inventory_sync(self, content: Any, connection: VCenterConnection) -> dict[str, Any]:
        datacenters = _get_objects(content, vim.Datacenter)
        clusters = _get_objects(content, vim.ClusterComputeResource)
        hosts = _get_objects(content, vim.HostSystem)
        vms = _get_objects(content, vim.VirtualMachine)
        datastores = _get_objects(content, vim.Datastore)
        return {
            "vcenter": connection.host,
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {
                "datacenter_count": len(datacenters),
                "cluster_count": len(clusters),
                "host_count": len(hosts),
                "vm_count": len(vms),
                "datastore_count": len(datastores),
            },
            "datacenters": [{"id": _moid(dc), "name": dc.name} for dc in datacenters],
            "clusters": [_cluster_summary(cluster) for cluster in clusters],
            "hosts": [_host_summary(host) for host in hosts],
            "virtual_machines": [
                {"vm_id": _moid(vm), "name": vm.summary.config.name, "power_state": str(vm.summary.runtime.powerState)}
                for vm in vms
            ],
            "datastores": [_datastore_summary(ds) for ds in datastores],
        }

    async def get_vm_detail(self, vm_id: str) -> dict[str, Any] | None:
        def _impl():
            return self._with_client(lambda content, _: self._find_vm_detail(content, vm_id))
        try:
            return await self._run(_impl)
        except Exception:
            if os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true":
                return mock_data.get_vm_detail(vm_id)
            raise

    def _find_vm_detail(self, content: Any, vm_id: str) -> dict[str, Any] | None:
        for vm in _get_objects(content, vim.VirtualMachine):
            if _moid(vm) == vm_id:
                detail = _vm_summary(vm)
                runtime = vm.summary.runtime
                detail["host_name"] = runtime.host.name if getattr(runtime, "host", None) else None
                detail["datastore_name"] = vm.datastore[0].name if getattr(vm, "datastore", None) else None
                detail["uptime_seconds"] = int(getattr(vm.summary.quickStats, "uptimeSeconds", 0) or 0)
                detail["snapshot_count"] = len(getattr(getattr(vm, "snapshot", None), "rootSnapshotList", []) or [])
                return detail
        return None

    async def get_host_detail(self, host_id: str) -> dict[str, Any] | None:
        def _impl():
            return self._with_client(lambda content, _: self._find_host_detail(content, host_id))
        try:
            return await self._run(_impl)
        except Exception:
            if os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true":
                return mock_data.get_host_detail(host_id)
            raise

    def _find_host_detail(self, content: Any, host_id: str) -> dict[str, Any] | None:
        for host in _get_objects(content, vim.HostSystem):
            if _moid(host) == host_id:
                data = _host_summary(host)
                data["cpu_usage_percent"] = round(100 * data["cpu_usage_mhz"] / data["cpu_mhz"], 2) if data["cpu_mhz"] else 0
                data["memory_usage_percent"] = round(100 * data["memory_usage_mb"] / data["memory_mb"], 2) if data["memory_mb"] else 0
                data["vms"] = [{"vm_id": _moid(vm), "name": vm.summary.config.name} for vm in getattr(host, "vm", [])]
                return data
        return None

    async def get_cluster_detail(self, cluster_id: str) -> dict[str, Any] | None:
        def _impl():
            return self._with_client(lambda content, _: self._find_cluster_detail(content, cluster_id))
        try:
            return await self._run(_impl)
        except Exception:
            if os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true":
                return mock_data.get_cluster_detail(cluster_id)
            raise

    def _find_cluster_detail(self, content: Any, cluster_id: str) -> dict[str, Any] | None:
        for cluster in _get_objects(content, vim.ClusterComputeResource):
            if _moid(cluster) == cluster_id:
                data = _cluster_summary(cluster)
                hosts = list(getattr(cluster, "host", []) or [])
                data["hosts"] = [{"host_id": _moid(host), "name": host.name} for host in hosts]
                data["virtual_machines"] = [
                    {"vm_id": _moid(vm), "name": vm.summary.config.name}
                    for host in hosts for vm in getattr(host, "vm", [])
                ]
                return data
        return None

    async def query_events(self, object_id: str, hours: int) -> list[dict[str, Any]]:
        def _impl():
            return self._with_client(lambda content, _: self._query_events_sync(content, object_id, hours))
        try:
            return await self._run(_impl)
        except Exception:
            if os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true":
                return mock_data.get_events_for_object(object_id, hours)
            raise

    def _query_events_sync(self, content: Any, object_id: str, hours: int) -> list[dict[str, Any]]:
        event_manager = content.eventManager
        begin = datetime.now(UTC) - timedelta(hours=hours)
        entity = None
        for vim_type in (vim.VirtualMachine, vim.HostSystem, vim.ClusterComputeResource, vim.Datacenter):
            for obj in _get_objects(content, vim_type):
                if _moid(obj) == object_id:
                    entity = obj
                    break
            if entity:
                break
        filter_spec = vim.event.EventFilterSpec()
        filter_spec.time = vim.event.EventFilterSpec.ByTime(beginTime=begin)
        if entity:
            filter_spec.entity = vim.event.EventFilterSpec.ByEntity(entity=entity, recursion="self")
        events = event_manager.QueryEvents(filter_spec) or []
        return [
            {
                "event_id": _moid(event) or f"evt-{idx}",
                "event_type": event.__class__.__name__,
                "level": str(getattr(event, "severity", "info")),
                "message": getattr(event, "fullFormattedMessage", ""),
                "created_time": getattr(event, "createdTime", datetime.now(UTC)).astimezone(UTC).isoformat(),
            }
            for idx, event in enumerate(events[:50])
        ]

    async def query_metrics(self, object_id: str, metric: str) -> dict[str, Any]:
        def _impl():
            return self._with_client(lambda content, _: self._query_metrics_sync(content, object_id, metric))
        try:
            return await self._run(_impl)
        except Exception:
            if os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true":
                return {"object_id": object_id, "metric": metric, "unit": "percent", "series": mock_data.get_metric_series(object_id, metric)}
            raise

    def _query_metrics_sync(self, content: Any, object_id: str, metric: str) -> dict[str, Any]:
        target = None
        target_type = None
        for vim_type, label in ((vim.HostSystem, "host"), (vim.VirtualMachine, "vm")):
            for obj in _get_objects(content, vim_type):
                if _moid(obj) == object_id:
                    target = obj
                    target_type = label
                    break
            if target:
                break
        if not target:
            return {"object_id": object_id, "metric": metric, "unit": "count", "series": []}

        summary = target.summary
        quick = summary.quickStats
        unit = "count"
        value = 0
        if target_type == "host" and metric in {"cpu.usage", "cpu.usage.average"}:
            unit = "mhz"
            value = int(getattr(quick, "overallCpuUsage", 0) or 0)
        elif target_type == "host" and metric in {"memory.usage", "mem.usage.average"}:
            unit = "mb"
            value = int(getattr(quick, "overallMemoryUsage", 0) or 0)
        elif target_type == "vm" and metric in {"cpu.usage", "cpu.usage.average"}:
            unit = "mhz"
            value = int(getattr(quick, "overallCpuUsage", 0) or 0)
        elif target_type == "vm" and metric in {"memory.usage", "mem.usage.average"}:
            unit = "mb"
            value = int(getattr(quick, "guestMemoryUsage", 0) or 0)
        return {
            "object_id": object_id,
            "metric": metric,
            "unit": unit,
            "series": [{"timestamp": datetime.now(UTC).isoformat(), "value": value}],
        }

    async def query_alerts(self) -> list[dict[str, Any]]:
        def _impl():
            return self._with_client(self._query_alerts_sync)
        try:
            return await self._run(_impl)
        except Exception:
            if os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true":
                return mock_data.ALERTS
            raise

    def _query_alerts_sync(self, content: Any, _: VCenterConnection) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        for host in _get_objects(content, vim.HostSystem):
            status = _overall_status(host)
            if status not in {"green", "gray"}:
                alerts.append(
                    {
                        "object_id": _moid(host),
                        "object_name": host.name,
                        "severity": status,
                        "summary": f"Host {host.name} overallStatus = {status}",
                    }
                )
        for vm in _get_objects(content, vim.VirtualMachine):
            status = _overall_status(vm)
            if status not in {"green", "gray"}:
                alerts.append(
                    {
                        "object_id": _moid(vm),
                        "object_name": vm.summary.config.name,
                        "severity": status,
                        "summary": f"VM {vm.summary.config.name} overallStatus = {status}",
                    }
                )
        return alerts

    async def query_topology(self) -> list[dict[str, Any]]:
        def _impl():
            return self._with_client(self._query_topology_sync)
        try:
            return await self._run(_impl)
        except Exception:
            if os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true":
                return mock_data.TOPOLOGY_NODES
            raise

    def _query_topology_sync(self, content: Any, _: VCenterConnection) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        for cluster in _get_objects(content, vim.ClusterComputeResource):
            cluster_id = _moid(cluster)
            nodes.append({"id": cluster_id, "name": cluster.name, "type": "cluster", "parent_id": None})
            for host in getattr(cluster, "host", []) or []:
                host_id = _moid(host)
                nodes.append({"id": host_id, "name": host.name, "type": "host", "parent_id": cluster_id})
                for vm in getattr(host, "vm", []) or []:
                    nodes.append(
                        {
                            "id": _moid(vm),
                            "name": vm.summary.config.name,
                            "type": "vm",
                            "parent_id": host_id,
                        }
                    )
        return nodes
