from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

try:
    from kubernetes import client
    from kubernetes.config.kube_config import KubeConfigLoader
except Exception:  # pragma: no cover - optional runtime dependency
    client = None
    KubeConfigLoader = None


@dataclass
class KubernetesConnection:
    kubeconfig: dict[str, Any] | None = None
    token: str | None = None
    server: str | None = None
    ca_cert: str | None = None
    namespace: str | None = None

    @classmethod
    def from_input(cls, connection: dict[str, Any] | None = None) -> "KubernetesConnection":
        payload = connection or {}
        if payload.get("kubeconfig"):
            kubeconfig = payload["kubeconfig"]
            if not isinstance(kubeconfig, dict):
                raise ValueError("kubeconfig 必须为对象")
            return cls(kubeconfig=kubeconfig, namespace=payload.get("namespace"))
        token = payload.get("token") or os.environ.get("K8S_TOKEN")
        server = payload.get("server") or os.environ.get("K8S_API_SERVER")
        ca_cert = payload.get("ca_cert") or os.environ.get("K8S_CA_CERT")
        namespace = payload.get("namespace") or os.environ.get("K8S_NAMESPACE")
        if not token or not server:
            raise ValueError("missing kubeconfig or token/server")
        return cls(token=token, server=server, ca_cert=ca_cert, namespace=namespace)


def _to_api_client(connection: KubernetesConnection) -> client.ApiClient:
    if client is None or KubeConfigLoader is None:
        raise RuntimeError("kubernetes python client is not installed")
    configuration = client.Configuration()
    if connection.kubeconfig:
        loader = KubeConfigLoader(config_dict=connection.kubeconfig)
        loader.load_and_set(configuration)
        return client.ApiClient(configuration)

    configuration.host = connection.server
    configuration.verify_ssl = bool(connection.ca_cert)
    if connection.ca_cert:
        configuration.ssl_ca_cert = connection.ca_cert
    else:
        configuration.verify_ssl = False
    configuration.api_key = {"authorization": connection.token or ""}
    configuration.api_key_prefix = {"authorization": "Bearer"}
    return client.ApiClient(configuration)


def _node_summary(node: client.V1Node) -> dict[str, Any]:
    conditions = {cond.type: cond.status for cond in (node.status.conditions or [])}
    return {
        "node_name": node.metadata.name,
        "labels": node.metadata.labels or {},
        "kubelet_version": node.status.node_info.kubelet_version if node.status and node.status.node_info else "",
        "os_image": node.status.node_info.os_image if node.status and node.status.node_info else "",
        "ready": conditions.get("Ready") == "True",
        "unschedulable": bool(node.spec.unschedulable) if node.spec else False,
        "pod_cidr": node.spec.pod_cidr if node.spec else None,
    }


def _pod_summary(pod: client.V1Pod) -> dict[str, Any]:
    statuses = pod.status.container_statuses or []
    ready = all(status.ready for status in statuses) if statuses else False
    restarts = sum(status.restart_count for status in statuses)
    return {
        "namespace": pod.metadata.namespace,
        "pod_name": pod.metadata.name,
        "phase": pod.status.phase,
        "node_name": pod.spec.node_name if pod.spec else None,
        "pod_ip": pod.status.pod_ip if pod.status else None,
        "ready": ready,
        "restart_count": restarts,
        "start_time": pod.status.start_time.isoformat() if pod.status and pod.status.start_time else None,
    }


def _deployment_summary(dep: client.V1Deployment) -> dict[str, Any]:
    status = dep.status
    spec = dep.spec
    desired = spec.replicas or 0
    available = status.available_replicas or 0
    updated = status.updated_replicas or 0
    return {
        "namespace": dep.metadata.namespace,
        "name": dep.metadata.name,
        "ready": available >= desired and desired > 0,
        "replicas_desired": desired,
        "replicas_available": available,
        "replicas_updated": updated,
    }


class KubernetesService:
    def __init__(self, connection: dict[str, Any] | None = None):
        self._connection_input = connection

    async def _run(self, func):
        return await asyncio.to_thread(func)

    def _with_clients(self, handler):
        connection = KubernetesConnection.from_input(self._connection_input)
        api_client = _to_api_client(connection)
        core = client.CoreV1Api(api_client)
        apps = client.AppsV1Api(api_client)
        version = client.VersionApi(api_client)
        return handler(core, apps, version, connection)

    async def list_nodes(self) -> list[dict[str, Any]]:
        return await self._run(lambda: self._with_clients(self._list_nodes_sync))

    def _list_nodes_sync(self, core: client.CoreV1Api, apps: client.AppsV1Api, version: client.VersionApi, connection: KubernetesConnection) -> list[dict[str, Any]]:
        return [_node_summary(node) for node in core.list_node().items]

    async def list_namespaces(self) -> list[dict[str, Any]]:
        return await self._run(lambda: self._with_clients(self._list_namespaces_sync))

    def _list_namespaces_sync(self, core: client.CoreV1Api, apps: client.AppsV1Api, version: client.VersionApi, connection: KubernetesConnection) -> list[dict[str, Any]]:
        return [
            {
                "name": ns.metadata.name,
                "phase": ns.status.phase if ns.status else None,
                "labels": ns.metadata.labels or {},
            }
            for ns in core.list_namespace().items
        ]

    async def list_pods(self, namespace: str | None = None) -> list[dict[str, Any]]:
        return await self._run(lambda: self._with_clients(lambda core, apps, version, connection: self._list_pods_sync(core, connection, namespace)))

    def _list_pods_sync(self, core: client.CoreV1Api, connection: KubernetesConnection, namespace: str | None) -> list[dict[str, Any]]:
        ns = namespace or connection.namespace
        if ns:
            items = core.list_namespaced_pod(ns).items
        else:
            items = core.list_pod_for_all_namespaces().items
        return [_pod_summary(pod) for pod in items]

    async def get_pod_logs(
        self,
        namespace: str,
        pod_name: str,
        container: str | None = None,
        tail_lines: int = 200,
    ) -> dict[str, Any]:
        return await self._run(
            lambda: self._with_clients(
                lambda core, apps, version, connection: {
                    "namespace": namespace,
                    "pod_name": pod_name,
                    "container": container,
                    "tail_lines": tail_lines,
                    "logs": core.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=namespace,
                        container=container,
                        tail_lines=tail_lines,
                    ),
                }
            )
        )

    async def get_workload_status(self, namespace: str | None = None) -> dict[str, Any]:
        return await self._run(
            lambda: self._with_clients(lambda core, apps, version, connection: self._get_workload_status_sync(core, apps, version, connection, namespace))
        )

    def _get_workload_status_sync(
        self,
        core: client.CoreV1Api,
        apps: client.AppsV1Api,
        version: client.VersionApi,
        connection: KubernetesConnection,
        namespace: str | None,
    ) -> dict[str, Any]:
        ns = namespace or connection.namespace
        version_info = version.get_code()
        nodes = core.list_node().items
        pods = core.list_namespaced_pod(ns).items if ns else core.list_pod_for_all_namespaces().items
        deployments = apps.list_namespaced_deployment(ns).items if ns else apps.list_deployment_for_all_namespaces().items
        namespaces = core.list_namespace().items if not ns else []
        return {
            "cluster_version": version_info.git_version,
            "namespace": ns,
            "summary": {
                "node_count": len(nodes),
                "namespace_count": len(namespaces) if not ns else 1,
                "pod_count": len(pods),
                "deployment_count": len(deployments),
                "ready_node_count": sum(1 for node in nodes if any(cond.type == "Ready" and cond.status == "True" for cond in (node.status.conditions or []))),
                "running_pod_count": sum(1 for pod in pods if pod.status and pod.status.phase == "Running"),
            },
            "nodes": [_node_summary(node) for node in nodes],
            "pods": [_pod_summary(pod) for pod in pods],
            "deployments": [_deployment_summary(dep) for dep in deployments],
        }
