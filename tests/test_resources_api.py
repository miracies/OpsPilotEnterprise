import os
import sys
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared-schema", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))

from fastapi.testclient import TestClient


def _get_client():
    to_remove = [k for k in sys.modules if k == "app" or k.startswith("app.")]
    for key in to_remove:
        del sys.modules[key]
    import app.main
    importlib.reload(app.main)
    return TestClient(app.main.app)


def test_vcenter_overview_resource_api(monkeypatch):
    async def fake_context(connection_id=None, conn_type=None):
        return {
            "connection": {
                "id": "conn-vcenter-prod",
                "display_name": "vCenter 生产环境",
                "type": "vcenter",
                "endpoint": "https://vc.example.local/sdk",
            },
            "credentials": {"username": "admin", "password": "secret"},
        }

    async def fake_invoke(tool_name, input_payload):
        assert tool_name == "vmware.get_vcenter_inventory"
        return {
            "vcenter": "vc.example.local",
            "generated_at": "2026-04-05T09:00:00Z",
            "summary": {"datacenter_count": 1, "cluster_count": 2, "host_count": 4, "vm_count": 20, "datastore_count": 3},
            "datacenters": [{"id": "dc-1", "name": "DC-1"}],
            "clusters": [{"cluster_id": "cluster-1", "name": "Cluster-1", "host_count": 4, "overall_status": "green"}],
            "hosts": [{"host_id": "host-1", "name": "esxi-01", "overall_status": "green", "cpu_usage_mhz": 1000, "memory_usage_mb": 2048}],
            "virtual_machines": [{"vm_id": "vm-1", "name": "app-01", "power_state": "poweredOn"}],
            "datastores": [],
        }

    client = _get_client()
    import app.routers.resources as resources_router

    monkeypatch.setattr(resources_router, "resolve_connection_context", fake_context)
    monkeypatch.setattr(resources_router, "_invoke_tool", fake_invoke)

    response = client.get("/api/v1/resources/vcenter/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["summary"]["cluster_count"] == 2


def test_k8s_workloads_resource_api(monkeypatch):
    async def fake_context(connection_id=None, conn_type=None):
        return {
            "connection": {
                "id": "conn-k8s-staging",
                "display_name": "K8s 测试集群",
                "type": "kubeconfig",
                "endpoint": "https://k8s.example.local:6443",
            },
            "credentials": {"kubeconfig": {"apiVersion": "v1", "clusters": [], "contexts": [], "users": []}},
        }

    async def fake_invoke(tool_name, input_payload):
        if tool_name == "k8s.list_namespaces":
            return {"namespaces": [{"name": "default", "phase": "Active"}]}
        return {
            "cluster_version": "v1.30.1",
            "namespace": "default",
            "summary": {"node_count": 3, "namespace_count": 1, "pod_count": 8, "deployment_count": 2, "ready_node_count": 3, "running_pod_count": 7},
            "nodes": [{"node_name": "node-1", "ready": True}],
            "pods": [{"namespace": "default", "pod_name": "web-0", "ready": False, "restart_count": 1}],
            "deployments": [{"namespace": "default", "name": "web", "ready": False, "replicas_desired": 2, "replicas_available": 1}],
        }

    client = _get_client()
    import app.routers.resources as resources_router

    monkeypatch.setattr(resources_router, "resolve_connection_context", fake_context)
    monkeypatch.setattr(resources_router, "_invoke_tool", fake_invoke)

    response = client.get("/api/v1/resources/k8s/workloads")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["summary"]["pod_count"] == 8
    assert body["data"]["summary"]["unhealthy_pod_count"] == 1
