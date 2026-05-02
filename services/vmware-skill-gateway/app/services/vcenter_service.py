from __future__ import annotations

import asyncio
import os
import ssl
import time
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


def _safe_percent(used: Any, total: Any) -> float | None:
    try:
        used_f = float(used)
        total_f = float(total)
        if total_f <= 0:
            return None
        return round(used_f * 100 / total_f, 2)
    except (TypeError, ValueError):
        return None


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
    cpu_mhz = int(hardware.cpuMhz * hardware.numCpuCores)
    cpu_usage_mhz = int(getattr(quick, "overallCpuUsage", 0) or 0)
    memory_mb = int(hardware.memorySize / 1024 / 1024)
    memory_usage_mb = int(getattr(quick, "overallMemoryUsage", 0) or 0)
    return {
        "host_id": _moid(host),
        "name": host.name,
        "cluster_id": _moid(host.parent) if getattr(host, "parent", None) else None,
        "cpu_mhz": cpu_mhz,
        "cpu_usage_mhz": cpu_usage_mhz,
        "cpu_usage_percent": _safe_percent(cpu_usage_mhz, cpu_mhz),
        "memory_mb": memory_mb,
        "memory_usage_mb": memory_usage_mb,
        "memory_usage_percent": _safe_percent(memory_usage_mb, memory_mb),
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
    hosts = list(getattr(ds, "host", []) or [])
    host_refs = [getattr(item, "key", None) for item in hosts]
    host_ids = [_moid(host) for host in host_refs if host is not None]
    host_names = [getattr(host, "name", "") for host in host_refs if host is not None]
    capacity_gb = round((summary.capacity or 0) / 1024 / 1024 / 1024, 2)
    free_gb = round((summary.freeSpace or 0) / 1024 / 1024 / 1024, 2)
    return {
        "id": _moid(ds),
        "name": summary.name,
        "type": summary.type,
        "capacity_gb": capacity_gb,
        "free_gb": free_gb,
        "free_percent": _safe_percent(free_gb, capacity_gb),
        "host_ids": host_ids,
        "host_names": host_names,
        "vm_count": len(getattr(ds, "vm", []) or []),
    }


def _vm_inventory_summary(vm: Any) -> dict[str, Any]:
    runtime = vm.summary.runtime
    datastores = list(getattr(vm, "datastore", []) or [])
    return {
        "vm_id": _moid(vm),
        "name": vm.summary.config.name,
        "power_state": str(runtime.powerState),
        "host_id": _moid(runtime.host) if getattr(runtime, "host", None) else None,
        "host_name": runtime.host.name if getattr(runtime, "host", None) else None,
        "cluster_id": _moid(runtime.host.parent) if getattr(runtime, "host", None) and getattr(runtime.host, "parent", None) else None,
        "datastore_ids": [_moid(ds) for ds in datastores],
        "datastore_names": [ds.name for ds in datastores if getattr(ds, "name", None)],
    }


def _metric_unit(metric: str) -> str:
    return {
        "cpu_usage_percent": "percent",
        "cpu_capacity_mhz": "mhz",
        "memory_usage_percent": "percent",
        "memory_capacity_mb": "mb",
        "datastore_free_percent": "percent",
        "datastore_capacity_gb": "gb",
        "datastore_iops": "iops",
        "datastore_latency_ms": "ms",
        "datastore_throughput_mbps": "mbps",
        "cpu.usage": "mhz",
        "cpu.usage.average": "mhz",
        "memory.usage": "mb",
        "mem.usage.average": "mb",
    }.get(metric, "count")


def _metric_value_from_row(row: dict[str, Any], metric: str) -> float | None:
    try:
        if metric in {"cpu_usage_percent"}:
            if row.get("cpu_usage_percent") is not None:
                return round(float(row["cpu_usage_percent"]), 2)
            return _safe_percent(row.get("cpu_usage_mhz"), row.get("cpu_mhz"))
        if metric in {"cpu_capacity_mhz"}:
            return round(float(row.get("cpu_mhz")), 2)
        if metric in {"cpu.usage", "cpu.usage.average"}:
            return round(float(row.get("cpu_usage_mhz")), 2)
        if metric in {"memory_usage_percent"}:
            if row.get("memory_usage_percent") is not None:
                return round(float(row["memory_usage_percent"]), 2)
            return _safe_percent(row.get("memory_usage_mb"), row.get("memory_mb"))
        if metric in {"memory_capacity_mb"}:
            return round(float(row.get("memory_mb")), 2)
        if metric in {"memory.usage", "mem.usage.average"}:
            return round(float(row.get("memory_usage_mb")), 2)
        if metric == "datastore_free_percent":
            return _safe_percent(row.get("free_gb"), row.get("capacity_gb"))
        if metric == "datastore_capacity_gb":
            return round(float(row.get("capacity_gb")), 2)
        if row.get(metric) is not None:
            return round(float(row.get(metric)), 2)
    except (TypeError, ValueError):
        return None
    return None


def _perf_counter_keys(metric: str) -> list[str]:
    return {
        "cpu_usage_percent": ["cpu.usage.average"],
        "memory_usage_percent": ["mem.usage.average"],
        "datastore_iops": ["datastore.numberReadAveraged.average", "datastore.numberWriteAveraged.average"],
        "datastore_latency_ms": ["datastore.totalReadLatency.average", "datastore.totalWriteLatency.average"],
        "datastore_throughput_mbps": ["datastore.read.average", "datastore.write.average"],
    }.get(metric, [metric] if "." in metric else [])


def _perf_counter_map(perf_manager: Any) -> dict[str, int]:
    counters: dict[str, int] = {}
    for counter in getattr(perf_manager, "perfCounter", []) or []:
        group = getattr(getattr(counter, "groupInfo", None), "key", "")
        name = getattr(getattr(counter, "nameInfo", None), "key", "")
        rollup = getattr(counter, "rollupType", "")
        key = f"{group}.{name}.{rollup}"
        counters[key] = int(getattr(counter, "key", 0) or 0)
    return counters


def _normalize_perf_value(metric: str, value: Any) -> float:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return 0.0
    if metric in {"cpu_usage_percent", "memory_usage_percent"} and raw > 100:
        return raw / 100.0
    if metric == "datastore_throughput_mbps":
        # vCenter datastore read/write counters are commonly KBps.
        return raw / 1024.0
    return raw


def _dt(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return value.astimezone(UTC).isoformat()
    except Exception:
        return str(value)


def _fault_message(issue: Any) -> str:
    for attr in ("fullFormattedMessage", "localizedMessage", "msg"):
        value = getattr(issue, attr, None)
        if value:
            return str(value)
    fault = getattr(issue, "fault", None)
    return str(getattr(fault, "msg", "") or fault or issue)


def _snapshot_tree(nodes: list[Any], depth: int = 0) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in nodes or []:
        out.append(
            {
                "name": str(getattr(node, "name", "") or ""),
                "description": str(getattr(node, "description", "") or ""),
                "created_time": _dt(getattr(node, "createTime", None)),
                "state": str(getattr(node, "state", "") or ""),
                "depth": depth,
            }
        )
        out.extend(_snapshot_tree(list(getattr(node, "childSnapshotList", []) or []), depth + 1))
    return out


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
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            si = None
            try:
                si = _connect(connection)
                content = si.RetrieveContent()
                return handler(content, connection)
            except Exception as exc:
                last_exc = exc
                if attempt >= 3:
                    break
                # vCenter handshake may intermittently EOF; short retry improves stability.
                time.sleep(0.8 * attempt)
            finally:
                if si is not None:
                    try:
                        Disconnect(si)
                    except Exception:
                        pass
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("failed to connect vCenter")

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
            "virtual_machines": [_vm_inventory_summary(vm) for vm in vms],
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
                detail["connection_state"] = str(getattr(runtime, "connectionState", "") or "")
                detail["guest_heartbeat_status"] = str(getattr(getattr(vm.summary, "guest", None), "guestHeartbeatStatus", "") or "")
                detail["host_name"] = runtime.host.name if getattr(runtime, "host", None) else None
                datastores = list(getattr(vm, "datastore", []) or [])
                detail["datastore_ids"] = [_moid(ds) for ds in datastores]
                datastore_names = [ds.name for ds in datastores if getattr(ds, "name", None)]
                detail["datastore_name"] = datastore_names[0] if datastore_names else None
                detail["datastore_names"] = datastore_names
                storage = getattr(vm.summary, "storage", None)
                committed = float(getattr(storage, "committed", 0) or 0)
                uncommitted = float(getattr(storage, "uncommitted", 0) or 0)
                detail["used_gb"] = round(committed / 1024 / 1024 / 1024, 2) if committed else 0.0
                detail["provisioned_gb"] = round((committed + uncommitted) / 1024 / 1024 / 1024, 2) if (committed or uncommitted) else 0.0
                detail["uptime_seconds"] = int(getattr(vm.summary.quickStats, "uptimeSeconds", 0) or 0)
                detail["snapshot_count"] = len(getattr(getattr(vm, "snapshot", None), "rootSnapshotList", []) or [])
                return detail
        return None

    async def collect_vm_diagnosis_bundle(self, vm_id: str, hours: int = 4) -> dict[str, Any] | None:
        def _impl():
            return self._with_client(lambda content, _: self._collect_vm_diagnosis_bundle_sync(content, vm_id, hours))
        try:
            return await self._run(_impl)
        except Exception:
            if os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true":
                return mock_data.get_vm_diagnosis_bundle(vm_id, hours)
            raise

    def _collect_vm_diagnosis_bundle_sync(self, content: Any, vm_id: str, hours: int) -> dict[str, Any] | None:
        vm = self._find_vm_by_id(content, vm_id)
        if vm is None:
            return None
        detail = self._find_vm_detail(content, vm_id) or {}
        runtime = vm.summary.runtime
        guest = vm.summary.guest
        datastores = list(getattr(vm, "datastore", []) or [])
        networks = list(getattr(vm, "network", []) or [])
        events = self._query_events_sync(content, vm_id, hours)
        host = getattr(runtime, "host", None)
        host_status = _host_summary(host) if host is not None else None
        datastore_status = [_datastore_summary(ds) for ds in datastores]
        triggered_alarms: list[dict[str, Any]] = []
        for state in list(getattr(vm, "triggeredAlarmState", []) or []):
            alarm = getattr(state, "alarm", None)
            alarm_info = getattr(alarm, "info", None)
            triggered_alarms.append(
                {
                    "key": str(getattr(state, "key", "") or ""),
                    "alarm_name": str(getattr(alarm_info, "name", "") or _moid(alarm) or ""),
                    "alarm_id": _moid(alarm) if alarm is not None else None,
                    "entity_id": _moid(getattr(state, "entity", None)) or vm_id,
                    "entity_name": getattr(getattr(state, "entity", None), "name", detail.get("name")),
                    "status": str(getattr(state, "overallStatus", "") or ""),
                    "time": _dt(getattr(state, "time", None)),
                    "acknowledged": bool(getattr(state, "acknowledged", False)),
                    "acknowledged_by": getattr(state, "acknowledgedByUser", None),
                    "acknowledged_time": _dt(getattr(state, "acknowledgedTime", None)),
                    "event_key": getattr(state, "eventKey", None),
                    "disabled": bool(getattr(state, "disabled", False)),
                }
            )
        config_issues: list[dict[str, Any]] = []
        for issue in list(getattr(vm, "configIssue", []) or []):
            fault = getattr(issue, "fault", None)
            config_issues.append(
                {
                    "key": str(getattr(issue, "key", "") or ""),
                    "message": _fault_message(issue),
                    "fault_type": fault.__class__.__name__ if fault is not None else issue.__class__.__name__,
                    "created_time": _dt(getattr(issue, "createdTime", None)),
                }
            )
        snapshot = getattr(vm, "snapshot", None)
        root_snapshots = list(getattr(snapshot, "rootSnapshotList", []) or [])
        task_events = [
            item
            for item in events
            if "task" in str(item.get("event_type") or item.get("type") or item.get("message") or "").lower()
        ]
        same_host_unhealthy: list[dict[str, Any]] = []
        if host is not None:
            for peer in list(getattr(host, "vm", []) or []):
                if _moid(peer) != vm_id and _overall_status(peer) not in {"green", "gray"}:
                    same_host_unhealthy.append({"vm_id": _moid(peer), "name": peer.summary.config.name, "overall_status": _overall_status(peer)})
        same_datastore_unhealthy: list[dict[str, Any]] = []
        for ds in datastores:
            for peer in list(getattr(ds, "vm", []) or []):
                if _moid(peer) != vm_id and _overall_status(peer) not in {"green", "gray"}:
                    same_datastore_unhealthy.append({"vm_id": _moid(peer), "name": peer.summary.config.name, "overall_status": _overall_status(peer), "datastore_id": _moid(ds)})
        return {
            "vm_id": vm_id,
            "hours": hours,
            "basic_status": {
                "vm_id": vm_id,
                "name": detail.get("name"),
                "uuid": getattr(getattr(vm, "config", None), "uuid", None),
                "instance_uuid": getattr(getattr(vm, "config", None), "instanceUuid", None),
                "power_state": str(getattr(runtime, "powerState", "") or ""),
                "connection_state": str(getattr(runtime, "connectionState", "") or ""),
                "overall_status": _overall_status(vm),
                "guest_heartbeat_status": str(getattr(guest, "guestHeartbeatStatus", "") or ""),
                "tools_status": detail.get("tools_status"),
                "host_id": detail.get("host_id"),
                "host_name": detail.get("host_name"),
                "datastore_ids": detail.get("datastore_ids", []),
                "datastore_names": detail.get("datastore_names", []),
                "network_names": [getattr(net, "name", "") for net in networks if getattr(net, "name", None)],
            },
            "triggered_alarms": triggered_alarms,
            "config_issues": config_issues,
            "recent_events": events,
            "recent_tasks": task_events,
            "snapshot_status": {
                "snapshot_count": len(root_snapshots),
                "consolidation_needed": bool(getattr(runtime, "consolidationNeeded", False)),
                "snapshots": _snapshot_tree(root_snapshots),
            },
            "dependency_status": {
                "host": host_status,
                "datastores": datastore_status,
                "networks": [
                    {
                        "id": _moid(net),
                        "name": getattr(net, "name", ""),
                        "overall_status": _overall_status(net),
                    }
                    for net in networks
                ],
            },
            "performance_metrics": {
                "vm.cpu_usage_percent": self._latest_metric_series(vm, "vm", "cpu_usage_percent"),
                "vm.memory_usage_percent": self._latest_metric_series(vm, "vm", "memory_usage_percent"),
                "host.cpu_usage_percent": self._latest_metric_series(host, "host", "cpu_usage_percent") if host is not None else [],
                "host.memory_usage_percent": self._latest_metric_series(host, "host", "memory_usage_percent") if host is not None else [],
                "datastore.free_percent": [
                    {"datastore_id": _moid(ds), "series": self._latest_metric_series(ds, "datastore", "datastore_free_percent")}
                    for ds in datastores
                ],
            },
            "blast_radius": {
                "same_host_unhealthy_vms": same_host_unhealthy,
                "same_datastore_unhealthy_vms": same_datastore_unhealthy,
            },
        }

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
                data["vms"] = [{"vm_id": _moid(vm), "name": vm.summary.config.name} for vm in getattr(host, "vm", [])]
                datastores = list(getattr(host, "datastore", []) or [])
                data["datastores"] = [_datastore_summary(ds) for ds in datastores]
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

    async def query_metrics(
        self,
        object_id: str,
        metric: str,
        *,
        object_type: str | None = None,
        metrics: list[str] | None = None,
        range_minutes: int = 0,
        step_seconds: int = 300,
        source: str = "vcenter",
    ) -> dict[str, Any]:
        def _impl():
            return self._with_client(
                lambda content, _: self._query_metrics_sync(
                    content,
                    object_id,
                    metric,
                    object_type=object_type,
                    metrics=metrics,
                    range_minutes=range_minutes,
                    step_seconds=step_seconds,
                    source=source,
                )
            )
        try:
            return await self._run(_impl)
        except Exception:
            if os.environ.get("VMWARE_USE_MOCK_FALLBACK", "false").lower() == "true":
                metric_names = metrics or [metric]
                payload = {
                    name: {
                        "metric": name,
                        "unit": _metric_unit(name),
                        "series": mock_data.get_metric_series(object_id, name),
                    }
                    for name in metric_names
                    if name
                }
                first = metric_names[0] if metric_names else metric
                first_payload = payload.get(first, {"series": []})
                return {
                    "object_id": object_id,
                    "object_type": object_type,
                    "metric": first,
                    "unit": first_payload.get("unit", "count"),
                    "series": first_payload.get("series", []),
                    "metrics": payload,
                    "source": "mock",
                }
            raise

    def _query_metrics_sync(
        self,
        content: Any,
        object_id: str,
        metric: str,
        *,
        object_type: str | None = None,
        metrics: list[str] | None = None,
        range_minutes: int = 0,
        step_seconds: int = 300,
        source: str = "vcenter",
    ) -> dict[str, Any]:
        metric_names = [item for item in (metrics or [metric]) if item]
        if not metric_names:
            metric_names = [metric]
        target = None
        target_type = None
        vim_types = [(vim.HostSystem, "host"), (vim.VirtualMachine, "vm"), (vim.Datastore, "datastore")]
        if object_type:
            vim_types = [item for item in vim_types if item[1] == object_type] or vim_types
        for vim_type, label in vim_types:
            for obj in _get_objects(content, vim_type):
                if _moid(obj) == object_id:
                    target = obj
                    target_type = label
                    break
            if target:
                break
        if not target:
            return {"object_id": object_id, "metric": metric, "unit": "count", "series": []}

        metric_payload: dict[str, dict[str, Any]] = {}
        for metric_name in metric_names:
            if range_minutes > 0:
                series = self._query_perf_series(content, target, metric_name, range_minutes, step_seconds)
                if not series:
                    series = self._latest_metric_series(target, target_type, metric_name)
            else:
                series = self._latest_metric_series(target, target_type, metric_name)
            metric_payload[metric_name] = {
                "metric": metric_name,
                "unit": _metric_unit(metric_name),
                "series": series,
            }
        first = metric_names[0]
        first_payload = metric_payload[first]
        return {
            "object_id": object_id,
            "object_type": target_type,
            "metric": first,
            "unit": first_payload["unit"],
            "series": first_payload["series"],
            "metrics": metric_payload,
            "source": source or "vcenter",
        }

    def _latest_metric_series(self, target: Any, target_type: str | None, metric: str) -> list[dict[str, Any]]:
        timestamp = datetime.now(UTC).isoformat()
        if target_type == "host":
            data = _host_summary(target)
            value = _metric_value_from_row(data, metric)
        elif target_type == "vm":
            data = _vm_summary(target)
            value = _metric_value_from_row(data, metric)
        elif target_type == "datastore":
            data = _datastore_summary(target)
            value = _metric_value_from_row(data, metric)
        else:
            value = None
        return [{"timestamp": timestamp, "value": value}] if value is not None else []

    def _query_perf_series(self, content: Any, target: Any, metric: str, range_minutes: int, step_seconds: int) -> list[dict[str, Any]]:
        counter_keys = _perf_counter_keys(metric)
        if not counter_keys:
            return []
        perf_manager = content.perfManager
        counters = _perf_counter_map(perf_manager)
        counter_ids = [counters[key] for key in counter_keys if key in counters]
        if not counter_ids:
            return []
        start = datetime.now(UTC) - timedelta(minutes=max(1, range_minutes))
        end = datetime.now(UTC)
        interval = max(20, int(step_seconds or 300))
        spec = vim.PerformanceManager.QuerySpec(
            entity=target,
            metricId=[vim.PerformanceManager.MetricId(counterId=counter_id, instance="") for counter_id in counter_ids],
            startTime=start,
            endTime=end,
            intervalId=interval,
            maxSample=300,
        )
        try:
            results = perf_manager.QueryPerf(querySpec=[spec]) or []
        except Exception:
            return []
        if not results:
            return []
        sample_info = list(getattr(results[0], "sampleInfo", []) or [])
        if not sample_info:
            return []
        values_by_idx: dict[int, list[float]] = {}
        for series in getattr(results[0], "value", []) or []:
            for idx, raw in enumerate(getattr(series, "value", []) or []):
                values_by_idx.setdefault(idx, []).append(_normalize_perf_value(metric, raw))
        points: list[dict[str, Any]] = []
        for idx, info in enumerate(sample_info):
            values = values_by_idx.get(idx) or []
            if not values:
                continue
            ts = getattr(info, "timestamp", datetime.now(UTC))
            points.append({"timestamp": ts.astimezone(UTC).isoformat(), "value": round(sum(values) / len(values), 2)})
        return points

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

    async def create_snapshot(self, vm_id: str, name: str) -> dict[str, Any]:
        def _impl():
            return self._with_client(lambda content, _: self._create_snapshot_sync(content, vm_id, name))

        return await self._run(_impl)

    def _create_snapshot_sync(self, content: Any, vm_id: str, name: str) -> dict[str, Any]:
        vm = self._find_vm_by_id(content, vm_id)
        if vm is None:
            raise ValueError(f"Virtual machine not found: {vm_id}")
        task = vm.CreateSnapshot_Task(
            name=name,
            description="Created by OpsPilot",
            memory=False,
            quiesce=False,
        )
        return {
            "task_id": _moid(task) or f"task-{int(time.time())}",
            "status": "submitted",
            "vm_id": vm_id,
            "snapshot_name": name,
            "operation": "CreateSnapshot_Task",
        }

    async def vm_guest_restart(self, vm_id: str) -> dict[str, Any]:
        def _impl():
            return self._with_client(lambda content, _: self._vm_guest_restart_sync(content, vm_id))

        return await self._run(_impl)

    def _vm_guest_restart_sync(self, content: Any, vm_id: str) -> dict[str, Any]:
        vm = self._find_vm_by_id(content, vm_id)
        if vm is None:
            raise ValueError(f"Virtual machine not found: {vm_id}")
        vm.RebootGuest()
        return {
            "task_id": f"guest-restart-{int(time.time())}",
            "status": "submitted",
            "vm_id": vm_id,
            "operation": "RebootGuest",
        }

    async def vm_power_on(self, vm_id: str) -> dict[str, Any]:
        def _impl():
            return self._with_client(lambda content, _: self._vm_power_on_sync(content, vm_id))

        return await self._run(_impl)

    def _vm_power_on_sync(self, content: Any, vm_id: str) -> dict[str, Any]:
        vm = self._find_vm_by_id(content, vm_id)
        if vm is None:
            raise ValueError(f"Virtual machine not found: {vm_id}")
        before_state = str(vm.summary.runtime.powerState)
        if before_state.lower() in {"poweredon", "powered_on", "on"}:
            return {
                "task_id": None,
                "status": "already_on",
                "vm_id": vm_id,
                "operation": "PowerOnVM_Task",
                "power_state_before": before_state,
                "power_state_after": before_state,
            }
        task = vm.PowerOnVM_Task()
        result = self._wait_task(task, timeout_seconds=45)
        return {
            "task_id": _moid(task) or f"task-{int(time.time())}",
            "status": result["status"],
            "vm_id": vm_id,
            "operation": "PowerOnVM_Task",
            "power_state_before": before_state,
            "power_state_after": str(vm.summary.runtime.powerState),
            "task_message": result.get("message"),
        }

    async def vm_power_off(self, vm_id: str) -> dict[str, Any]:
        def _impl():
            return self._with_client(lambda content, _: self._vm_power_off_sync(content, vm_id))

        return await self._run(_impl)

    def _vm_power_off_sync(self, content: Any, vm_id: str) -> dict[str, Any]:
        vm = self._find_vm_by_id(content, vm_id)
        if vm is None:
            raise ValueError(f"Virtual machine not found: {vm_id}")
        before_state = str(vm.summary.runtime.powerState)
        if before_state.lower() in {"poweredoff", "powered_off", "off"}:
            return {
                "task_id": None,
                "status": "already_off",
                "vm_id": vm_id,
                "operation": "PowerOffVM_Task",
                "power_state_before": before_state,
                "power_state_after": before_state,
            }
        task = vm.PowerOffVM_Task()
        result = self._wait_task(task, timeout_seconds=45)
        return {
            "task_id": _moid(task) or f"task-{int(time.time())}",
            "status": result["status"],
            "vm_id": vm_id,
            "operation": "PowerOffVM_Task",
            "power_state_before": before_state,
            "power_state_after": str(vm.summary.runtime.powerState),
            "task_message": result.get("message"),
        }

    def _wait_task(self, task: Any, timeout_seconds: int = 45) -> dict[str, Any]:
        started = time.time()
        while time.time() - started < timeout_seconds:
            info = getattr(task, "info", None)
            if info is None:
                time.sleep(0.8)
                continue
            state = str(getattr(info, "state", "")).lower()
            if state == "success":
                return {"status": "success", "message": "task completed"}
            if state == "error":
                err = getattr(info, "error", None)
                msg = str(getattr(err, "msg", "task failed")) if err else "task failed"
                raise RuntimeError(msg)
            time.sleep(1.0)
        return {"status": "submitted", "message": "task still running"}

    def _find_vm_by_id(self, content: Any, vm_id: str):
        for vm in _get_objects(content, vim.VirtualMachine):
            if _moid(vm) == vm_id:
                return vm
        return None

    async def host_restart(self, host_id: str) -> dict[str, Any]:
        def _impl():
            return self._with_client(lambda content, _: self._host_restart_sync(content, host_id))

        return await self._run(_impl)

    def _host_restart_sync(self, content: Any, host_id: str) -> dict[str, Any]:
        host = self._find_host_by_id(content, host_id)
        if host is None:
            raise ValueError(f"Host not found: {host_id}")
        task = host.RebootHost_Task(force=True)
        result = self._wait_task(task, timeout_seconds=60)
        return {
            "task_id": _moid(task) or f"task-{int(time.time())}",
            "status": result["status"],
            "host_id": host_id,
            "operation": "RebootHost_Task",
            "task_message": result.get("message"),
        }

    def _find_host_by_id(self, content: Any, host_id: str):
        for host in _get_objects(content, vim.HostSystem):
            if _moid(host) == host_id:
                return host
        return None
