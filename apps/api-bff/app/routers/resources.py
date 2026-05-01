from __future__ import annotations

import asyncio
import csv
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.routers.connections import resolve_connection_context
from app.services.chat_exports import register_export
from opspilot_schema.envelope import make_error, make_success

router = APIRouter(prefix="/resources", tags=["resources"])
logger = logging.getLogger(__name__)

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")
TOOL_GATEWAY_FALLBACK_URL = os.environ.get("TOOL_GATEWAY_FALLBACK_URL", "http://127.0.0.1:18020")
TOOL_GATEWAY_TIMEOUT_SECONDS = float(os.environ.get("TOOL_GATEWAY_TIMEOUT_SECONDS", "220"))
VMWARE_GATEWAY_URL = os.environ.get("VMWARE_GATEWAY_URL", "http://127.0.0.1:18030")
VMWARE_GATEWAY_FALLBACK_URL = os.environ.get("VMWARE_GATEWAY_FALLBACK_URL", "http://127.0.0.1:8030")
DOWNLOAD_BASE_URL = os.environ.get("DOWNLOAD_BASE_URL", "http://127.0.0.1:8000")
EXPORT_DIR = Path(os.environ.get("CHAT_EXPORT_DIR", "data/chat_exports"))
VM_DETAIL_CONCURRENCY = int(os.environ.get("VM_DETAIL_CONCURRENCY", "8"))
TOOL_GATEWAY_FAIL_CACHE_SECONDS = float(os.environ.get("TOOL_GATEWAY_FAIL_CACHE_SECONDS", "30"))
_tool_gateway_unavailable_until = 0.0


class VCenterInventoryExportBody(BaseModel):
    connection_id: str = "conn-vcenter-prod"
    format: str = "csv"
    session_id: str | None = None
    requested_columns: list[str] | None = None


EXPORT_COLUMN_ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "name": ("name",),
    "名称": ("name",),
    "vm name": ("name",),
    "ip": ("ip_address",),
    "ip地址": ("ip_address",),
    "ip address": ("ip_address",),
    "host": ("host_name",),
    "host name": ("host_name",),
    "esxi": ("host_name",),
    "所在esxi主机名": ("host_name",),
    "cpu": ("cpu_count",),
    "cpu核数": ("cpu_count",),
    "cpu数量": ("cpu_count",),
    "内存": ("memory_mb",),
    "memory": ("memory_mb",),
    "存储": ("provisioned_gb", "used_gb"),
    "storage": ("provisioned_gb", "used_gb"),
    "datastore": ("datastore_names",),
    "关联的datastore": ("datastore_names",),
    "关联datastore": ("datastore_names",),
}
SUPPORTED_EXPORT_COLUMNS = {
    "vm_id",
    "name",
    "power_state",
    "ip_address",
    "host_name",
    "cpu_count",
    "memory_mb",
    "provisioned_gb",
    "used_gb",
    "datastore_names",
}
DEFAULT_VM_EXPORT_COLUMNS = ["vm_id", "name", "power_state"]


def _connection_ref(connection: dict[str, Any]) -> dict[str, Any]:
    return {
        "connection_id": connection["id"],
        "connection_name": connection["display_name"],
        "connection_type": connection["type"],
        "endpoint": connection["endpoint"],
    }


def _build_vcenter_connection_input(connection: dict[str, Any], credentials: dict[str, Any] | None) -> dict[str, Any]:
    if not credentials:
        raise ValueError("vCenter connection is missing secret:// credentials")
    return {
        "endpoint": connection["endpoint"],
        "username": credentials["username"],
        "password": credentials["password"],
        "insecure": True,
    }


def _build_k8s_connection_input(connection: dict[str, Any], credentials: dict[str, Any] | None) -> dict[str, Any]:
    if not credentials:
        raise ValueError("kubernetes connection is missing secret:// credentials")
    if credentials.get("kubeconfig"):
        return {
            "kubeconfig": credentials["kubeconfig"],
            "namespace": connection.get("scope", ""),
        }
    return {
        "token": credentials.get("token"),
        "server": credentials.get("server") or connection["endpoint"],
        "ca_cert": credentials.get("ca_cert"),
        "namespace": credentials.get("namespace"),
    }


async def _invoke_tool(tool_name: str, input_payload: dict[str, Any]) -> dict[str, Any]:
    global _tool_gateway_unavailable_until
    if time.time() < _tool_gateway_unavailable_until:
        raise RuntimeError("tool gateway unavailable (cached)")

    tried_errors: list[str] = []
    gateway_urls = [TOOL_GATEWAY_URL]
    if TOOL_GATEWAY_FALLBACK_URL and TOOL_GATEWAY_FALLBACK_URL != TOOL_GATEWAY_URL:
        gateway_urls.append(TOOL_GATEWAY_FALLBACK_URL)

    async with httpx.AsyncClient(timeout=TOOL_GATEWAY_TIMEOUT_SECONDS) as client:
        for base in gateway_urls:
            url = f"{base.rstrip('/')}/api/v1/invoke/{tool_name}"
            try:
                response = await client.post(url, json={"input": input_payload, "dry_run": False})
                try:
                    data = response.json()
                except ValueError as exc:
                    body_preview = (response.text or "")[:240]
                    raise RuntimeError(
                        f"tool {tool_name} non-JSON response from {base} (status={response.status_code}): {body_preview}"
                    ) from exc
                if not data.get("success"):
                    raise RuntimeError(data.get("error") or f"tool failed: {tool_name}")
                return data["data"]
            except Exception as exc:
                tried_errors.append(f"{base}: {exc}")

    _tool_gateway_unavailable_until = time.time() + TOOL_GATEWAY_FAIL_CACHE_SECONDS
    raise RuntimeError("; ".join(tried_errors) if tried_errors else f"tool failed: {tool_name}")


async def _invoke_vmware_inventory_direct(connection_input: dict[str, Any]) -> dict[str, Any]:
    tried_errors: list[str] = []
    gateway_urls = [VMWARE_GATEWAY_URL]
    if VMWARE_GATEWAY_FALLBACK_URL and VMWARE_GATEWAY_FALLBACK_URL != VMWARE_GATEWAY_URL:
        gateway_urls.append(VMWARE_GATEWAY_FALLBACK_URL)

    async with httpx.AsyncClient(timeout=TOOL_GATEWAY_TIMEOUT_SECONDS) as client:
        for base in gateway_urls:
            url = f"{base.rstrip('/')}/api/v1/query/get_vcenter_inventory"
            try:
                response = await client.post(url, json={"connection": connection_input})
                try:
                    data = response.json()
                except ValueError as exc:
                    body_preview = (response.text or "")[:240]
                    raise RuntimeError(
                        f"direct vmware inventory non-JSON response (status={response.status_code}) from {url}: {body_preview}"
                    ) from exc
                if not data.get("success"):
                    raise RuntimeError(data.get("error") or "direct vmware inventory failed")
                return data["data"]
            except Exception as exc:
                tried_errors.append(f"{base}: {exc}")

    raise RuntimeError("; ".join(tried_errors) if tried_errors else "direct vmware inventory failed")


async def _invoke_vmware_vm_detail_direct(connection_input: dict[str, Any], vm_id: str) -> dict[str, Any]:
    tried_errors: list[str] = []
    gateway_urls = [VMWARE_GATEWAY_URL]
    if VMWARE_GATEWAY_FALLBACK_URL and VMWARE_GATEWAY_FALLBACK_URL != VMWARE_GATEWAY_URL:
        gateway_urls.append(VMWARE_GATEWAY_FALLBACK_URL)

    async with httpx.AsyncClient(timeout=TOOL_GATEWAY_TIMEOUT_SECONDS) as client:
        for base in gateway_urls:
            url = f"{base.rstrip('/')}/api/v1/query/get_vm_detail"
            try:
                response = await client.post(url, json={"connection": connection_input, "vm_id": vm_id})
                try:
                    data = response.json()
                except ValueError as exc:
                    body_preview = (response.text or "")[:240]
                    raise RuntimeError(
                        f"direct vm detail non-JSON response (status={response.status_code}) from {url}: {body_preview}"
                    ) from exc
                if not data.get("success"):
                    raise RuntimeError(data.get("error") or "direct vm detail failed")
                return data["data"]
            except Exception as exc:
                tried_errors.append(f"{base}: {exc}")

    raise RuntimeError("; ".join(tried_errors) if tried_errors else "direct vm detail failed")


async def _fetch_vcenter_inventory_data(connection_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    context = await resolve_connection_context(connection_id, "vcenter")
    if not context:
        raise RuntimeError("未找到可用的 vCenter 连接")
    connection = context["connection"]
    connection_input = _build_vcenter_connection_input(connection, context["credentials"])
    logger.info(
        "vcenter inventory fetch start connection_id=%s endpoint=%s tool_gateway=%s fallback=%s vmware_gateway=%s",
        connection_id or connection.get("id"),
        connection.get("endpoint"),
        TOOL_GATEWAY_URL,
        TOOL_GATEWAY_FALLBACK_URL,
        VMWARE_GATEWAY_URL,
    )
    try:
        inventory = await _invoke_tool("vmware.get_vcenter_inventory", {"connection": connection_input})
    except Exception:
        logger.exception("invoke tool vmware.get_vcenter_inventory failed, fallback direct gateway")
        inventory = await _invoke_vmware_inventory_direct(connection_input)
    inventory["connection"] = _connection_ref(connection)
    return inventory, connection_input


def _normalize_requested_columns(raw_columns: list[str] | None) -> tuple[list[str], list[str]]:
    if not raw_columns:
        return DEFAULT_VM_EXPORT_COLUMNS[:], []

    normalized: list[str] = []
    ignored: list[str] = []
    seen: set[str] = set()
    for item in raw_columns:
        token = (item or "").strip()
        if not token:
            continue
        lowered = token.lower()
        mapped: tuple[str, ...] = ()

        if lowered in SUPPORTED_EXPORT_COLUMNS:
            mapped = (lowered,)
        else:
            for alias, columns in sorted(EXPORT_COLUMN_ALIAS_MAP.items(), key=lambda kv: len(kv[0]), reverse=True):
                if alias in token or alias in lowered:
                    mapped = columns
                    break

        if not mapped:
            ignored.append(token)
            continue

        for col in mapped:
            if col in SUPPORTED_EXPORT_COLUMNS and col not in seen:
                normalized.append(col)
                seen.add(col)

    if not normalized:
        return DEFAULT_VM_EXPORT_COLUMNS[:], ignored
    return normalized, ignored


async def _fetch_vm_details(
    inventory: dict[str, Any],
    connection_input: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    vm_rows = inventory.get("virtual_machines", []) or []
    vm_ids = [row.get("vm_id") for row in vm_rows if isinstance(row, dict) and row.get("vm_id")]
    if not vm_ids:
        return {}

    # Keep bounded concurrency; configurable for export performance tuning.
    semaphore = asyncio.Semaphore(max(1, VM_DETAIL_CONCURRENCY))

    async def _one(vm_id: str) -> tuple[str, dict[str, Any]]:
        async with semaphore:
            for attempt in range(1, 4):
                try:
                    detail = await _invoke_tool(
                        "vmware.get_vm_detail",
                        {"connection": connection_input, "vm_id": vm_id},
                    )
                    return vm_id, detail
                except Exception:
                    try:
                        detail = await _invoke_vmware_vm_detail_direct(connection_input, vm_id)
                        return vm_id, detail
                    except Exception:
                        if attempt >= 3:
                            return vm_id, {}
                        await asyncio.sleep(0.4 * attempt)
            return vm_id, {}

    pairs = await asyncio.gather(*[_one(vm_id) for vm_id in vm_ids])
    return {vm_id: detail for vm_id, detail in pairs}


def _requires_vm_details(export_columns: list[str]) -> bool:
    detail_columns = {
        "ip_address",
        "host_name",
        "cpu_count",
        "memory_mb",
        "provisioned_gb",
        "used_gb",
        "datastore_names",
    }
    return any(col in detail_columns for col in export_columns)


def _as_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _build_export_row(
    vm: dict[str, Any],
    detail: dict[str, Any],
    export_columns: list[str],
) -> dict[str, Any]:
    ip_list = detail.get("ip_addresses")
    if isinstance(ip_list, list):
        ip_address = ",".join(str(ip) for ip in ip_list if ip)
    else:
        ip_address = detail.get("ip_address") or ""

    datastores = detail.get("datastore_names")
    if isinstance(datastores, list):
        datastore_names = ",".join(str(ds) for ds in datastores if ds)
    else:
        datastore_names = detail.get("datastore_name") or ""

    row = {
        "vm_id": vm.get("vm_id", ""),
        "name": detail.get("name") or vm.get("name", ""),
        "power_state": detail.get("power_state") or vm.get("power_state", ""),
        "ip_address": ip_address,
        "host_name": detail.get("host_name", ""),
        "cpu_count": detail.get("cpu_count", ""),
        "memory_mb": detail.get("memory_mb", ""),
        "provisioned_gb": (
            _as_number(detail.get("provisioned_gb"))
            if detail.get("provisioned_gb") is not None else ""
        ),
        "used_gb": _as_number(detail.get("used_gb")) if detail.get("used_gb") is not None else "",
        "datastore_names": datastore_names,
    }
    return {key: row.get(key, "") for key in export_columns}


def _build_csv_for_vms(
    inventory: dict[str, Any],
    details_by_vm_id: dict[str, dict[str, Any]],
    connection_id: str,
    export_columns: list[str],
) -> tuple[Path, str]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    file_name = f"vcenter-{connection_id}-vms-{now.strftime('%Y%m%dT%H%M%SZ')}.csv"
    file_path = EXPORT_DIR / file_name
    rows = inventory.get("virtual_machines", []) or []
    with file_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=export_columns)
        writer.writeheader()
        for row in rows:
            vm_id = row.get("vm_id")
            detail = details_by_vm_id.get(vm_id, {}) if vm_id else {}
            writer.writerow(_build_export_row(row, detail, export_columns))
    return file_path, file_name


@router.get("/vcenter/overview")
async def get_vcenter_overview(connection_id: str | None = Query(None)):
    try:
        inventory, _ = await _fetch_vcenter_inventory_data(connection_id)
        hosts = inventory.get("hosts", [])
        vms = inventory.get("virtual_machines", [])
        result = {
            "connection": inventory.get("connection"),
            "vcenter": inventory.get("vcenter"),
            "generated_at": inventory.get("generated_at"),
            "summary": {
                **inventory.get("summary", {}),
                "powered_off_vm_count": sum(1 for vm in vms if vm.get("power_state") != "poweredOn"),
                "unhealthy_host_count": sum(1 for host in hosts if host.get("overall_status") not in {"green", "gray", None}),
                "unhealthy_vm_count": sum(1 for vm in vms if vm.get("power_state") != "poweredOn"),
            },
            "datacenters": inventory.get("datacenters", []),
            "clusters": inventory.get("clusters", []),
            "hosts": hosts,
        }
        return make_success(result)
    except Exception as exc:
        return make_error(f"获取 vCenter 概览失败: {exc}")


@router.get("/vcenter/inventory")
async def get_vcenter_inventory(connection_id: str | None = Query(None)):
    try:
        inventory, _ = await _fetch_vcenter_inventory_data(connection_id)
        return make_success(inventory)
    except Exception as exc:
        return make_error(f"获取 vCenter 清单失败: {exc}")


@router.post("/vcenter/inventory/export")
async def export_vcenter_inventory(body: VCenterInventoryExportBody):
    try:
        export_format = (body.format or "csv").lower()
        if export_format != "csv":
            return make_error("仅支持 csv 导出格式")
        export_columns, ignored_columns = _normalize_requested_columns(body.requested_columns)
        inventory, connection_input = await _fetch_vcenter_inventory_data(body.connection_id)
        vm_details: dict[str, dict[str, Any]] = {}
        if _requires_vm_details(export_columns):
            vm_details = await _fetch_vm_details(inventory, connection_input)
        file_path, file_name = _build_csv_for_vms(
            inventory=inventory,
            details_by_vm_id=vm_details,
            connection_id=body.connection_id,
            export_columns=export_columns,
        )
        record = register_export(file_path=file_path, file_name=file_name, session_id=body.session_id)
        download_path = f"/api/v1/chat/exports/{record.export_id}/download"
        payload = record.to_api_dict(download_url=f"{DOWNLOAD_BASE_URL.rstrip('/')}{download_path}")
        payload["export_columns"] = export_columns
        payload["ignored_columns"] = ignored_columns
        return make_success(
            payload
        )
    except Exception as exc:
        return make_error(f"导出 vCenter 虚拟机列表失败: {exc}")


@router.get("/k8s/overview")
async def get_k8s_overview(connection_id: str | None = Query(None)):
    try:
        context = await resolve_connection_context(connection_id, "kubeconfig")
        if not context:
            return make_error("未找到可用的 Kubernetes 连接")
        connection = context["connection"]
        connection_input = {"connection": _build_k8s_connection_input(connection, context["credentials"])}
        workloads = await _invoke_tool("k8s.get_workload_status", connection_input)
        namespaces = await _invoke_tool("k8s.list_namespaces", connection_input)
        nodes = workloads.get("nodes", [])
        pods = workloads.get("pods", [])
        result = {
            "connection": _connection_ref(connection),
            "cluster_version": workloads.get("cluster_version"),
            "namespace": workloads.get("namespace"),
            "summary": {
                **workloads.get("summary", {}),
                "unhealthy_node_count": sum(1 for node in nodes if not node.get("ready")),
                "unhealthy_pod_count": sum(1 for pod in pods if not pod.get("ready")),
            },
            "namespaces": namespaces.get("namespaces", []),
            "nodes": nodes,
        }
        return make_success(result)
    except Exception as exc:
        return make_error(f"获取 K8s 概览失败: {exc}")


@router.get("/k8s/workloads")
async def get_k8s_workloads(
    connection_id: str | None = Query(None),
    namespace: str | None = Query(None),
):
    try:
        context = await resolve_connection_context(connection_id, "kubeconfig")
        if not context:
            return make_error("未找到可用的 Kubernetes 连接")
        connection = context["connection"]
        connection_input = {
            "connection": _build_k8s_connection_input(connection, context["credentials"]),
            "namespace": namespace,
        }
        workloads = await _invoke_tool("k8s.get_workload_status", connection_input)
        namespaces = await _invoke_tool(
            "k8s.list_namespaces",
            {"connection": _build_k8s_connection_input(connection, context["credentials"])}
        )
        workloads["connection"] = _connection_ref(connection)
        workloads["namespaces"] = namespaces.get("namespaces", [])
        workloads["summary"] = {
            **workloads.get("summary", {}),
            "unhealthy_node_count": sum(1 for node in workloads.get("nodes", []) if not node.get("ready")),
            "unhealthy_pod_count": sum(1 for pod in workloads.get("pods", []) if not pod.get("ready")),
        }
        return make_success(workloads)
    except Exception as exc:
        return make_error(f"获取 K8s 工作负载失败: {exc}")
