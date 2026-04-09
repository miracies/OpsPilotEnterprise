"""Mock VMware vCenter–style data for the skill gateway."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


NOW = datetime.now(UTC)

DATASTORES = [
    {"id": "ds-vsan-prod-a", "name": "vsanDatastore-prod-a", "type": "vSAN", "capacity_gb": 20480, "free_gb": 6120},
    {"id": "ds-nfs-backup-01", "name": "nfs-backup-vol01", "type": "NFS", "capacity_gb": 10240, "free_gb": 3890},
    {"id": "ds-vmfs-mgmt", "name": "VMFS-MGMT-LUN01", "type": "VMFS", "capacity_gb": 4096, "free_gb": 1120},
    {"id": "ds-vsan-dr", "name": "vsanDatastore-dr", "type": "vSAN", "capacity_gb": 8192, "free_gb": 2410},
]

CLUSTERS = [
    {
        "cluster_id": "cluster-prod-01",
        "name": "PROD-COMPUTE-01",
        "drs_enabled": True,
        "ha_enabled": True,
        "host_count": 4,
        "vm_count": 16,
        "overall_status": "green",
        "datacenter": "DC-PRIMARY",
    },
    {
        "cluster_id": "cluster-mgmt-01",
        "name": "MGMT-INFRA-01",
        "drs_enabled": True,
        "ha_enabled": True,
        "host_count": 2,
        "vm_count": 8,
        "overall_status": "yellow",
        "datacenter": "DC-PRIMARY",
    },
]

HOSTS = [
    {
        "host_id": "host-esxi01",
        "name": "esxi-node01.corp.local",
        "cluster_id": "cluster-prod-01",
        "cpu_mhz": 46080,
        "cpu_usage_mhz": 28120,
        "memory_mb": 786432,
        "memory_usage_mb": 498200,
        "vm_count": 4,
        "connection_state": "connected",
        "power_state": "poweredOn",
        "version": "8.0.2",
        "build": "22380479",
    },
    {
        "host_id": "host-esxi02",
        "name": "esxi-node02.corp.local",
        "cluster_id": "cluster-prod-01",
        "cpu_mhz": 46080,
        "cpu_usage_mhz": 30210,
        "memory_mb": 786432,
        "memory_usage_mb": 521100,
        "vm_count": 4,
        "connection_state": "connected",
        "power_state": "poweredOn",
        "version": "8.0.2",
        "build": "22380479",
    },
    {
        "host_id": "host-esxi03",
        "name": "esxi-node03.corp.local",
        "cluster_id": "cluster-prod-01",
        "cpu_mhz": 46080,
        "cpu_usage_mhz": 26540,
        "memory_mb": 786432,
        "memory_usage_mb": 455000,
        "vm_count": 4,
        "connection_state": "connected",
        "power_state": "poweredOn",
        "version": "8.0.2",
        "build": "22380479",
    },
    {
        "host_id": "host-esxi04",
        "name": "esxi-node04.corp.local",
        "cluster_id": "cluster-prod-01",
        "cpu_mhz": 46080,
        "cpu_usage_mhz": 29400,
        "memory_mb": 786432,
        "memory_usage_mb": 488900,
        "vm_count": 4,
        "connection_state": "connected",
        "power_state": "poweredOn",
        "version": "8.0.2",
        "build": "22380479",
    },
    {
        "host_id": "host-esxi05",
        "name": "esxi-node05.corp.local",
        "cluster_id": "cluster-mgmt-01",
        "cpu_mhz": 23040,
        "cpu_usage_mhz": 8120,
        "memory_mb": 393216,
        "memory_usage_mb": 142200,
        "vm_count": 4,
        "connection_state": "connected",
        "power_state": "poweredOn",
        "version": "8.0.2",
        "build": "22380479",
    },
    {
        "host_id": "host-esxi06",
        "name": "esxi-node06.corp.local",
        "cluster_id": "cluster-mgmt-01",
        "cpu_mhz": 23040,
        "cpu_usage_mhz": 7680,
        "memory_mb": 393216,
        "memory_usage_mb": 138400,
        "vm_count": 4,
        "connection_state": "connected",
        "power_state": "poweredOn",
        "version": "8.0.2",
        "build": "22380479",
    },
]

# 24 VMs with realistic names
_VM_SPECS: list[tuple[str, str, str, str, str, int, int, str, str]] = [
    ("vm-001", "app-server-01", "host-esxi01", "ds-vsan-prod-a", "cluster-prod-01", 8, 32768, "poweredOn", "other3xLinux64Guest"),
    ("vm-002", "app-server-02", "host-esxi01", "ds-vsan-prod-a", "cluster-prod-01", 8, 32768, "poweredOn", "other3xLinux64Guest"),
    ("vm-003", "app-server-03", "host-esxi02", "ds-vsan-prod-a", "cluster-prod-01", 8, 32768, "poweredOn", "other3xLinux64Guest"),
    ("vm-004", "app-server-04", "host-esxi02", "ds-vsan-prod-a", "cluster-prod-01", 8, 32768, "poweredOn", "other3xLinux64Guest"),
    ("vm-005", "db-server-01", "host-esxi03", "ds-vsan-prod-a", "cluster-prod-01", 16, 131072, "poweredOn", "other3xLinux64Guest"),
    ("vm-006", "db-server-02", "host-esxi03", "ds-vsan-prod-a", "cluster-prod-01", 16, 131072, "poweredOn", "other3xLinux64Guest"),
    ("vm-007", "web-tier-01", "host-esxi04", "ds-vsan-prod-a", "cluster-prod-01", 4, 16384, "poweredOn", "other3xLinux64Guest"),
    ("vm-008", "web-tier-02", "host-esxi04", "ds-vsan-prod-a", "cluster-prod-01", 4, 16384, "poweredOn", "other3xLinux64Guest"),
    ("vm-009", "web-tier-03", "host-esxi01", "ds-vsan-prod-a", "cluster-prod-01", 4, 16384, "poweredOn", "other3xLinux64Guest"),
    ("vm-010", "web-tier-04", "host-esxi02", "ds-vsan-prod-a", "cluster-prod-01", 4, 16384, "poweredOn", "other3xLinux64Guest"),
    ("vm-011", "batch-worker-01", "host-esxi03", "ds-vsan-prod-a", "cluster-prod-01", 4, 65536, "poweredOn", "other3xLinux64Guest"),
    ("vm-012", "batch-worker-02", "host-esxi04", "ds-vsan-prod-a", "cluster-prod-01", 4, 65536, "poweredOn", "other3xLinux64Guest"),
    ("vm-013", "cache-redis-01", "host-esxi01", "ds-vsan-prod-a", "cluster-prod-01", 4, 65536, "poweredOn", "other3xLinux64Guest"),
    ("vm-014", "cache-redis-02", "host-esxi02", "ds-vsan-prod-a", "cluster-prod-01", 4, 65536, "poweredOn", "other3xLinux64Guest"),
    ("vm-015", "mq-broker-01", "host-esxi03", "ds-vsan-prod-a", "cluster-prod-01", 4, 32768, "poweredOn", "other3xLinux64Guest"),
    ("vm-016", "mq-broker-02", "host-esxi04", "ds-vsan-prod-a", "cluster-prod-01", 4, 32768, "poweredOn", "other3xLinux64Guest"),
    ("vm-017", "jump-box-01", "host-esxi05", "ds-vmfs-mgmt", "cluster-mgmt-01", 2, 8192, "poweredOn", "windows2019srv_64Guest"),
    ("vm-018", "jump-box-02", "host-esxi05", "ds-vmfs-mgmt", "cluster-mgmt-01", 2, 8192, "poweredOn", "windows2019srv_64Guest"),
    ("vm-019", "vcenter-proxy-01", "host-esxi06", "ds-vmfs-mgmt", "cluster-mgmt-01", 4, 16384, "poweredOn", "other3xLinux64Guest"),
    ("vm-020", "vcenter-proxy-02", "host-esxi06", "ds-vmfs-mgmt", "cluster-mgmt-01", 4, 16384, "poweredOn", "other3xLinux64Guest"),
    ("vm-021", "infra-dns-01", "host-esxi05", "ds-vmfs-mgmt", "cluster-mgmt-01", 2, 4096, "poweredOn", "other3xLinux64Guest"),
    ("vm-022", "infra-dns-02", "host-esxi06", "ds-vmfs-mgmt", "cluster-mgmt-01", 2, 4096, "poweredOn", "other3xLinux64Guest"),
    ("vm-023", "monitoring-01", "host-esxi05", "ds-nfs-backup-01", "cluster-mgmt-01", 8, 32768, "poweredOn", "other3xLinux64Guest"),
    ("vm-024", "monitoring-02", "host-esxi06", "ds-nfs-backup-01", "cluster-mgmt-01", 8, 32768, "poweredOn", "other3xLinux64Guest"),
]

VMS = [
    {
        "vm_id": vid,
        "name": name,
        "host_id": hid,
        "datastore_id": ds,
        "cluster_id": cid,
        "cpu_count": cpu,
        "memory_mb": mem,
        "power_state": pwr,
        "guest_os": gos,
        "folder": "/PROD/Applications" if "mgmt" not in cid else "/MGMT/Infrastructure",
        "tools_status": "toolsOk",
        "ip_addresses": [f"10.{120 + i // 8}.{20 + (i % 8)}.{100 + (i % 20)}"],
        "annotation": f"Mock workload VM — {name}",
    }
    for i, (vid, name, hid, ds, cid, cpu, mem, pwr, gos) in enumerate(_VM_SPECS)
]

VM_BY_ID = {v["vm_id"]: v for v in VMS}
HOST_BY_ID = {h["host_id"]: h for h in HOSTS}
CLUSTER_BY_ID = {c["cluster_id"]: c for c in CLUSTERS}
DS_BY_ID = {d["id"]: d for d in DATASTORES}


def get_inventory() -> dict:
    return {
        "vcenter": "vc01.corp.local",
        "generated_at": _iso(NOW),
        "summary": {
            "cluster_count": len(CLUSTERS),
            "host_count": len(HOSTS),
            "vm_count": len(VMS),
            "datastore_count": len(DATASTORES),
        },
        "clusters": CLUSTERS,
        "hosts": HOSTS,
        "virtual_machines": [{"vm_id": v["vm_id"], "name": v["name"], "power_state": v["power_state"]} for v in VMS],
        "datastores": DATASTORES,
    }


def get_vm_detail(vm_id: str) -> dict | None:
    v = VM_BY_ID.get(vm_id)
    if not v:
        return None
    h = HOST_BY_ID.get(v["host_id"], {})
    ds = DS_BY_ID.get(v["datastore_id"], {})
    return {
        **v,
        "host_name": h.get("name"),
        "datastore_name": ds.get("name"),
        "datastore_names": [ds.get("name")] if ds.get("name") else [],
        "used_gb": round((v["memory_mb"] / 1024) * 8.5, 2),
        "provisioned_gb": round((v["memory_mb"] / 1024) * 11.0, 2),
        "cpu_usage_mhz": v["cpu_count"] * 2200,
        "memory_usage_mb": int(v["memory_mb"] * 0.72),
        "uptime_seconds": 86400 * 14 + 3600 * 3,
        "snapshot_count": 2 if v["vm_id"] in ("vm-005", "vm-006") else 0,
    }


def get_host_detail(host_id: str) -> dict | None:
    h = HOST_BY_ID.get(host_id)
    if not h:
        return None
    vms_on_host = [v for v in VMS if v["host_id"] == host_id]
    return {
        **h,
        "cpu_usage_percent": round(100 * h["cpu_usage_mhz"] / h["cpu_mhz"], 2),
        "memory_usage_percent": round(100 * h["memory_usage_mb"] / h["memory_mb"], 2),
        "vms": [{"vm_id": v["vm_id"], "name": v["name"]} for v in vms_on_host],
    }


def get_cluster_detail(cluster_id: str) -> dict | None:
    c = CLUSTER_BY_ID.get(cluster_id)
    if not c:
        return None
    hosts_in = [h for h in HOSTS if h["cluster_id"] == cluster_id]
    vms_in = [v for v in VMS if v["cluster_id"] == cluster_id]
    return {
        **c,
        "hosts": [{"host_id": h["host_id"], "name": h["name"]} for h in hosts_in],
        "virtual_machines": [{"vm_id": v["vm_id"], "name": v["name"]} for v in vms_in],
    }


def get_events_for_object(object_id: str, hours: int) -> list[dict]:
    base = NOW - timedelta(hours=min(hours, 72))
    templates = [
        ("info", "com.vmware.vc.vm.VmPoweredOnEvent", "Virtual machine powered on"),
        ("warning", "com.vmware.vc.HA.DasHostFailedEvent", "Host connectivity lost — remediation started"),
        ("info", "com.vmware.vc.vm.VmGuestRebootEvent", "Guest OS reboot initiated for vm"),
        ("error", "com.vmware.vc.vm.VmFailedToPowerOnEvent", "Insufficient resources to power on VM"),
        ("info", "com.vmware.vc.vm.VmReconfiguredEvent", "VM configuration updated (CPU/Memory)"),
    ]
    out = []
    for i, (level, etype, msg) in enumerate(templates[:5]):
        ts = base + timedelta(minutes=15 * i)
        out.append(
            {
                "event_id": f"evt-{object_id}-{i}",
                "timestamp": _iso(ts),
                "type": etype,
                "severity": level,
                "object_id": object_id,
                "message": f"{msg} (object={object_id})",
                "username": "vpxuser@corp.local",
            }
        )
    return out


def get_metric_series(object_id: str, metric: str) -> list[dict]:
    points = []
    base_val = hash(f"{object_id}:{metric}") % 5000 + 1000
    for i in range(12):
        ts = NOW - timedelta(minutes=5 * (11 - i))
        noise = (i * 17 + base_val) % 200
        points.append({"timestamp": _iso(ts), "value": round(base_val * 0.001 + noise, 3)})
    return points


ALERTS = [
    {
        "alert_id": "al-1001",
        "severity": "warning",
        "status": "active",
        "object_type": "HostSystem",
        "object_name": "esxi-node03.corp.local",
        "message": "Memory usage above 85% for 15 minutes",
        "raised_at": _iso(NOW - timedelta(minutes=22)),
    },
    {
        "alert_id": "al-1002",
        "severity": "info",
        "status": "acknowledged",
        "object_type": "VirtualMachine",
        "object_name": "db-server-01",
        "message": "VMware Tools upgrade available",
        "raised_at": _iso(NOW - timedelta(hours=3)),
    },
    {
        "alert_id": "al-1003",
        "severity": "critical",
        "status": "active",
        "object_type": "Datastore",
        "object_name": "nfs-backup-vol01",
        "message": "Datastore free space below 20%",
        "raised_at": _iso(NOW - timedelta(minutes=45)),
    },
    {
        "alert_id": "al-1004",
        "severity": "warning",
        "status": "active",
        "object_type": "ClusterComputeResource",
        "object_name": "MGMT-INFRA-01",
        "message": "DRS recommendation: migrate 2 VMs for load balancing",
        "raised_at": _iso(NOW - timedelta(minutes=8)),
    },
]

TOPOLOGY_NODES = [
    {"id": "dc-primary", "type": "Datacenter", "name": "DC-PRIMARY", "parent": None},
    {"id": "folder-compute", "type": "Folder", "name": "Compute", "parent": "dc-primary"},
    {"id": "cluster-prod-01", "type": "ClusterComputeResource", "name": "PROD-COMPUTE-01", "parent": "folder-compute"},
    {"id": "cluster-mgmt-01", "type": "ClusterComputeResource", "name": "MGMT-INFRA-01", "parent": "folder-compute"},
    {"id": "host-esxi01", "type": "HostSystem", "name": "esxi-node01.corp.local", "parent": "cluster-prod-01"},
    {"id": "host-esxi02", "type": "HostSystem", "name": "esxi-node02.corp.local", "parent": "cluster-prod-01"},
    {"id": "host-esxi03", "type": "HostSystem", "name": "esxi-node03.corp.local", "parent": "cluster-prod-01"},
    {"id": "host-esxi04", "type": "HostSystem", "name": "esxi-node04.corp.local", "parent": "cluster-prod-01"},
    {"id": "host-esxi05", "type": "HostSystem", "name": "esxi-node05.corp.local", "parent": "cluster-mgmt-01"},
    {"id": "host-esxi06", "type": "HostSystem", "name": "esxi-node06.corp.local", "parent": "cluster-mgmt-01"},
    {"id": "vm-005", "type": "VirtualMachine", "name": "db-server-01", "parent": "host-esxi03"},
    {"id": "vm-007", "type": "VirtualMachine", "name": "web-tier-01", "parent": "host-esxi04"},
    {"id": "ds-vsan-prod-a", "type": "Datastore", "name": "vsanDatastore-prod-a", "parent": "dc-primary"},
]
