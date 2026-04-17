from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI
from opspilot_schema import TopologyEdge, TopologyGraph, TopologyNode
from opspilot_schema.envelope import make_error, make_success

UTC = timezone.utc

app = FastAPI(title="OpsPilot Topology Service")

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020").rstrip("/")
EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060").rstrip("/")
VCENTER_ENDPOINT = os.environ.get("VCENTER_ENDPOINT", "https://10.0.80.21:443/sdk")
VCENTER_USERNAME = os.environ.get("VCENTER_USERNAME", "administrator@vsphere.local")
VCENTER_PASSWORD = os.environ.get("VCENTER_PASSWORD", "VMware1!")
VCENTER_CONNECTION_ID = os.environ.get("VCENTER_CONNECTION_ID", "conn-vcenter-prod")
TOPOLOGY_INVENTORY_TIMEOUT_SEC = float(os.environ.get("TOPOLOGY_INVENTORY_TIMEOUT_SEC", "45"))

_LAST_INVENTORY: dict[str, Any] | None = None
_LAST_INVENTORY_AT: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _vcenter_connection_input() -> dict[str, Any]:
    return {
        "endpoint": VCENTER_ENDPOINT,
        "username": VCENTER_USERNAME,
        "password": VCENTER_PASSWORD,
        "insecure": True,
    }


async def _invoke_tool(tool_name: str, payload: dict[str, Any], timeout_sec: float = TOPOLOGY_INVENTORY_TIMEOUT_SEC) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        resp = await client.post(
            f"{TOOL_GATEWAY_URL}/api/v1/invoke/{tool_name}",
            json={"input": payload, "dry_run": False},
        )
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error") or f"tool invoke failed: {tool_name}")
    return body.get("data", {}) or {}


async def _get_inventory_prefer_fresh() -> tuple[dict[str, Any], bool]:
    global _LAST_INVENTORY, _LAST_INVENTORY_AT
    try:
        inventory = await _invoke_tool(
            "vmware.get_vcenter_inventory",
            {"connection": _vcenter_connection_input()},
            timeout_sec=TOPOLOGY_INVENTORY_TIMEOUT_SEC,
        )
        if isinstance(inventory, dict) and inventory:
            _LAST_INVENTORY = inventory
            _LAST_INVENTORY_AT = _now()
        return inventory, False
    except Exception:
        if _LAST_INVENTORY:
            return _LAST_INVENTORY, True
        raise


async def _fetch_incident(incident_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{EVENT_INGESTION_URL}/api/v1/incidents/{incident_id}")
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error") or f"incident not found: {incident_id}")
    return body.get("data", {}) or {}


async def _enrich_vms_with_detail(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    vms = inventory.get("virtual_machines", []) if isinstance(inventory.get("virtual_machines"), list) else []
    if not vms:
        return []

    datastore_name_to_id: dict[str, str] = {}
    datastores = inventory.get("datastores", []) if isinstance(inventory.get("datastores"), list) else []
    fallback_ds: dict[str, Any] | None = None
    for ds in datastores:
        dsid = str(ds.get("datastore_id") or ds.get("id") or "")
        name = str(ds.get("name") or "").strip()
        if dsid and name:
            datastore_name_to_id[name] = dsid
            if fallback_ds is None:
                fallback_ds = {"datastore_id": dsid, "name": name}

    sem = asyncio.Semaphore(4)

    async def _load_one(vm: dict[str, Any]) -> dict[str, Any]:
        vm_id = str(vm.get("vm_id") or "")
        if not vm_id:
            return vm
        try:
            async with sem:
                detail = await _invoke_tool(
                    "vmware.get_vm_detail",
                    {"connection": _vcenter_connection_input(), "vm_id": vm_id},
                    timeout_sec=10.0,
                )
            if isinstance(detail, dict):
                enriched = dict(vm)
                enriched["host_id"] = detail.get("host_id") or enriched.get("host_id")
                enriched["cluster_id"] = detail.get("cluster_id") or enriched.get("cluster_id")
                enriched["power_state"] = detail.get("power_state") or enriched.get("power_state")

                datastore_names = detail.get("datastore_names") if isinstance(detail.get("datastore_names"), list) else []
                mapped_datastores: list[dict[str, Any]] = []
                for ds_name in datastore_names:
                    ds_name_s = str(ds_name)
                    ds_id = datastore_name_to_id.get(ds_name_s)
                    if ds_id:
                        mapped_datastores.append({"datastore_id": ds_id, "name": ds_name_s})
                if not mapped_datastores and fallback_ds:
                    mapped_datastores = [fallback_ds]
                enriched["datastores"] = mapped_datastores
                return enriched
        except Exception:
            if fallback_ds:
                fallback_vm = dict(vm)
                fallback_vm["datastores"] = [fallback_ds]
                return fallback_vm
            return vm
        if fallback_ds:
            fallback_vm = dict(vm)
            fallback_vm["datastores"] = [fallback_ds]
            return fallback_vm
        return vm

    return await asyncio.gather(*[_load_one(vm) for vm in vms])


async def _inventory_to_nodes(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    clusters = inventory.get("clusters", []) if isinstance(inventory.get("clusters"), list) else []
    default_cluster_id = str(clusters[0].get("cluster_id") or "") if clusters else ""
    hosts = inventory.get("hosts", []) if isinstance(inventory.get("hosts"), list) else []
    vms = await _enrich_vms_with_detail(inventory)
    datastores = inventory.get("datastores", []) if isinstance(inventory.get("datastores"), list) else []

    for c in clusters:
        cid = str(c.get("cluster_id") or "")
        if not cid:
            continue
        nodes.append(
            {
                "id": cid,
                "name": c.get("name") or cid,
                "type": "cluster",
                "status": c.get("overall_status", "unknown"),
                "parent_id": None,
            }
        )

    for h in hosts:
        hid = str(h.get("host_id") or "")
        if not hid:
            continue
        nodes.append(
            {
                "id": hid,
                "name": h.get("name") or hid,
                "type": "host",
                "status": h.get("overall_status", "unknown"),
                "parent_id": str(h.get("cluster_id") or "") or None,
            }
        )

    for vm in vms:
        vid = str(vm.get("vm_id") or "")
        if not vid:
            continue
        parent_id = str(vm.get("host_id") or vm.get("cluster_id") or default_cluster_id or "") or None
        nodes.append(
            {
                "id": vid,
                "name": vm.get("name") or vid,
                "type": "vm",
                "status": vm.get("power_state", "unknown"),
                "parent_id": parent_id,
                "datastores": vm.get("datastores", []),
            }
        )

    for ds in datastores:
        dsid = str(ds.get("datastore_id") or ds.get("id") or "")
        if not dsid:
            continue
        nodes.append(
            {
                "id": dsid,
                "name": ds.get("name") or dsid,
                "type": "datastore",
                "status": ds.get("overall_status", "unknown"),
                "parent_id": None,
            }
        )

    return nodes


def _build_graph(
    *,
    connection_id: str,
    nodes_data: list[dict[str, Any]],
    object_id: str | None,
    depth: int,
) -> TopologyGraph:
    nodes: list[TopologyNode] = []
    edges: list[TopologyEdge] = []
    by_id: dict[str, dict[str, Any]] = {}
    children: dict[str, list[str]] = {}

    for raw in nodes_data:
        nid = str(raw.get("id") or "")
        if not nid:
            continue
        by_id[nid] = raw
        pid = str(raw.get("parent_id") or "")
        if pid:
            children.setdefault(pid, []).append(nid)

    selected_ids: set[str] = set()
    roots: list[str] = []
    if object_id and object_id in by_id:
        roots = [object_id]
    elif object_id:
        roots = [nid for nid, item in by_id.items() if object_id.lower() in str(item.get("name", "")).lower()][:1]
    if not roots:
        roots = [nid for nid, item in by_id.items() if str(item.get("type", "")).lower() == "cluster"][:5]
        if not roots:
            roots = list(by_id.keys())[:5]

    def walk(node_id: str, d: int) -> None:
        if d > depth or node_id in selected_ids:
            return
        selected_ids.add(node_id)
        for child in children.get(node_id, []):
            walk(child, d + 1)

    for root in roots:
        walk(root, 0)

    # Keep datastore nodes visible in global view for capacity context.
    for nid, item in by_id.items():
        if str(item.get("type", "")).lower() == "datastore":
            selected_ids.add(nid)

    for nid in selected_ids:
        item = by_id[nid]
        nodes.append(
            TopologyNode(
                id=nid,
                name=str(item.get("name") or nid),
                type=str(item.get("type") or "unknown"),
                status=str(item.get("status") or "unknown"),
                metadata={
                    "parent_id": item.get("parent_id"),
                    "raw_type": item.get("type"),
                },
            )
        )

    for nid in selected_ids:
        item = by_id[nid]
        pid = str(item.get("parent_id") or "")
        if pid and pid in selected_ids:
            edges.append(
                TopologyEdge(
                    id=f"edge-{pid}-{nid}",
                    source=pid,
                    target=nid,
                    relation="contains",
                    metadata={},
                )
            )
        datastores = item.get("datastores", []) if isinstance(item.get("datastores"), list) else []
        for ds in datastores:
            dsid = str(ds.get("id") or ds.get("datastore_id") or "")
            if dsid and dsid in selected_ids:
                edges.append(
                    TopologyEdge(
                        id=f"edge-{nid}-{dsid}",
                        source=nid,
                        target=dsid,
                        relation="attached_to_datastore",
                        metadata={},
                    )
                )

    return TopologyGraph(
        graph_id=f"graph-{uuid.uuid4().hex[:10]}",
        connection_id=connection_id,
        generated_at=_now(),
        nodes=nodes,
        edges=edges,
        metadata={
            "root_object_id": object_id,
            "depth": depth,
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
    )


@app.get("/health")
async def health() -> dict:
    return make_success({"status": "ok", "service": "topology-service"})


@app.get("/api/v1/topology/graph")
async def get_topology_graph(connection_id: str = VCENTER_CONNECTION_ID, object_id: str | None = None, depth: int = 3) -> dict:
    try:
        inventory, from_cache = await _get_inventory_prefer_fresh()
        graph = _build_graph(
            connection_id=connection_id,
            nodes_data=await _inventory_to_nodes(inventory if isinstance(inventory, dict) else {}),
            object_id=object_id,
            depth=max(1, min(depth, 5)),
        )
        payload = graph.model_dump()
        if from_cache:
            payload["metadata"]["warning"] = f"using cached inventory from {_LAST_INVENTORY_AT}"
        return make_success(payload)
    except Exception as exc:  # noqa: BLE001
        fallback_nodes: list[TopologyNode] = []
        if object_id:
            fallback_nodes.append(
                TopologyNode(
                    id=object_id,
                    name=object_id,
                    type="unknown",
                    status="unknown",
                    metadata={},
                )
            )
        graph = TopologyGraph(
            graph_id=f"graph-{uuid.uuid4().hex[:10]}",
            connection_id=connection_id,
            generated_at=_now(),
            nodes=fallback_nodes,
            edges=[],
            metadata={
                "root_object_id": object_id,
                "depth": depth,
                "node_count": len(fallback_nodes),
                "edge_count": 0,
                "warning": f"inventory unavailable: {exc}",
            },
        )
        return make_success(graph.model_dump())


@app.get("/api/v1/topology/incidents/{incident_id}")
async def get_incident_topology(incident_id: str, depth: int = 2) -> dict:
    try:
        incident = await _fetch_incident(incident_id)
        details = incident.get("details") or {}
        object_id = details.get("object_id")
        if not object_id:
            affected = incident.get("affected_objects") or []
            if affected:
                object_id = affected[0].get("object_id")

        inventory, from_cache = await _get_inventory_prefer_fresh()
        graph = _build_graph(
            connection_id=VCENTER_CONNECTION_ID,
            nodes_data=await _inventory_to_nodes(inventory if isinstance(inventory, dict) else {}),
            object_id=str(object_id) if object_id else None,
            depth=max(1, min(depth, 4)),
        )
        payload = graph.model_dump()
        payload["metadata"]["incident_id"] = incident_id
        if from_cache:
            payload["metadata"]["warning"] = f"using cached inventory from {_LAST_INVENTORY_AT}"
        return make_success(payload)
    except Exception as exc:  # noqa: BLE001
        fallback_object_id = str(object_id) if "object_id" in locals() and object_id else f"incident:{incident_id}"
        graph = TopologyGraph(
            graph_id=f"graph-{uuid.uuid4().hex[:10]}",
            connection_id=VCENTER_CONNECTION_ID,
            generated_at=_now(),
            nodes=[
                TopologyNode(
                    id=fallback_object_id,
                    name=fallback_object_id,
                    type="unknown",
                    status="unknown",
                    metadata={},
                )
            ],
            edges=[],
            metadata={
                "incident_id": incident_id,
                "root_object_id": fallback_object_id,
                "depth": depth,
                "node_count": 1,
                "edge_count": 0,
                "warning": f"inventory unavailable: {exc}",
            },
        )
        return make_success(graph.model_dump())
