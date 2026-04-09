from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, Query

from opspilot_schema.envelope import make_error, make_success
from app.routers.connections import resolve_connection_context

router = APIRouter(prefix="/resources", tags=["resources"])

# #region agent log
import json as _json_dbg; open(r"E:\work\git\OpsPilot\debug-ef9114.log","a").write(_json_dbg.dumps({"sessionId":"ef9114","hypothesisId":"H2","location":"resources.py:module_load","message":"resources router module loaded successfully","timestamp":__import__("time").time()})+"\n")
# #endregion

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")
TOOL_GATEWAY_FALLBACK_URL = os.environ.get("TOOL_GATEWAY_FALLBACK_URL", "http://127.0.0.1:18020")
TOOL_GATEWAY_TIMEOUT_SECONDS = float(os.environ.get("TOOL_GATEWAY_TIMEOUT_SECONDS", "220"))
VMWARE_GATEWAY_URL = os.environ.get("VMWARE_GATEWAY_URL", "http://127.0.0.1:18030")


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
    # Try primary tool-gateway first, then fallback gateway to reduce impact of
    # one broken local process/port mapping.
    tried_errors: list[str] = []
    gateway_urls = [TOOL_GATEWAY_URL]
    if TOOL_GATEWAY_FALLBACK_URL and TOOL_GATEWAY_FALLBACK_URL != TOOL_GATEWAY_URL:
        gateway_urls.append(TOOL_GATEWAY_FALLBACK_URL)

    async with httpx.AsyncClient(timeout=TOOL_GATEWAY_TIMEOUT_SECONDS) as client:
        for base in gateway_urls:
            url = f"{base.rstrip('/')}/api/v1/invoke/{tool_name}"
            try:
                response = await client.post(url, json={"input": input_payload, "dry_run": False})
                data = response.json()
                if not data.get("success"):
                    raise RuntimeError(data.get("error") or f"tool failed: {tool_name}")
                return data["data"]
            except Exception as exc:
                tried_errors.append(f"{base}: {exc}")

    raise RuntimeError("; ".join(tried_errors) if tried_errors else f"tool failed: {tool_name}")


async def _invoke_vmware_inventory_direct(connection_input: dict[str, Any]) -> dict[str, Any]:
    url = f"{VMWARE_GATEWAY_URL.rstrip('/')}/api/v1/query/get_vcenter_inventory"
    async with httpx.AsyncClient(timeout=TOOL_GATEWAY_TIMEOUT_SECONDS) as client:
        response = await client.post(url, json={"connection": connection_input})
    data = response.json()
    if not data.get("success"):
        raise RuntimeError(data.get("error") or "direct vmware inventory failed")
    return data["data"]


@router.get("/vcenter/overview")
async def get_vcenter_overview(connection_id: str | None = Query(None)):
    # #region agent log
    import json as _json_dbg3; open(r"E:\work\git\OpsPilot\debug-ef9114.log","a").write(_json_dbg3.dumps({"sessionId":"ef9114","hypothesisId":"H3","location":"resources.py:get_vcenter_overview","message":"vcenter overview endpoint hit","data":{"connection_id":connection_id},"timestamp":__import__("time").time()})+"\n")
    # #endregion
    try:
        context = await resolve_connection_context(connection_id, "vcenter")
        if not context:
            return make_error("未找到可用的 vCenter 连接")
        connection = context["connection"]
        connection_input = _build_vcenter_connection_input(connection, context["credentials"])
        input_payload = {"connection": connection_input}
        try:
            inventory = await _invoke_tool("vmware.get_vcenter_inventory", input_payload)
        except Exception:
            inventory = await _invoke_vmware_inventory_direct(connection_input)
        hosts = inventory.get("hosts", [])
        vms = inventory.get("virtual_machines", [])
        result = {
            "connection": _connection_ref(connection),
            "vcenter": inventory.get("vcenter", connection["endpoint"]),
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
        context = await resolve_connection_context(connection_id, "vcenter")
        if not context:
            return make_error("未找到可用的 vCenter 连接")
        connection = context["connection"]
        connection_input = _build_vcenter_connection_input(connection, context["credentials"])
        try:
            inventory = await _invoke_tool(
                "vmware.get_vcenter_inventory",
                {"connection": connection_input},
            )
        except Exception:
            inventory = await _invoke_vmware_inventory_direct(connection_input)
        inventory["connection"] = _connection_ref(connection)
        return make_success(inventory)
    except Exception as exc:
        return make_error(f"获取 vCenter 清单失败: {exc}")


@router.get("/k8s/overview")
async def get_k8s_overview(connection_id: str | None = Query(None)):
    # #region agent log
    import json as _json_dbg4; open(r"E:\work\git\OpsPilot\debug-ef9114.log","a").write(_json_dbg4.dumps({"sessionId":"ef9114","hypothesisId":"K8S","location":"resources.py:get_k8s_overview","message":"k8s overview endpoint hit","data":{"connection_id":connection_id},"timestamp":__import__("time").time()})+"\n")
    # #endregion
    try:
        context = await resolve_connection_context(connection_id, "kubeconfig")
        if not context:
            return make_error("未找到可用的 Kubernetes 连接")
        connection = context["connection"]
        # #region agent log
        open(r"E:\work\git\OpsPilot\debug-ef9114.log","a").write(_json_dbg4.dumps({"sessionId":"ef9114","hypothesisId":"K8S","location":"resources.py:get_k8s_overview:context","message":"resolved connection context","data":{"conn_id":connection.get("id"),"has_creds":context.get("credentials") is not None,"cred_keys":list((context.get("credentials") or {}).keys())},"timestamp":__import__("time").time()})+"\n")
        # #endregion
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
        # #region agent log
        open(r"E:\work\git\OpsPilot\debug-ef9114.log","a").write(_json_dbg4.dumps({"sessionId":"ef9114","hypothesisId":"K8S","location":"resources.py:get_k8s_overview:error","message":"k8s overview failed","data":{"error":str(exc),"type":type(exc).__name__},"timestamp":__import__("time").time()})+"\n")
        # #endregion
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
        connection_input = {"connection": _build_k8s_connection_input(connection, context["credentials"]), "namespace": namespace}
        workloads = await _invoke_tool("k8s.get_workload_status", connection_input)
        namespaces = await _invoke_tool(
            "k8s.list_namespaces",
            {"connection": _build_k8s_connection_input(connection, context["credentials"])},
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
