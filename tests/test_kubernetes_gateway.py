import os
from fastapi.testclient import TestClient

from conftest import load_service_app

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "kubernetes-skill-gateway")
_app = load_service_app(SERVICE_DIR)
client = TestClient(_app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_capabilities():
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "k8s.get_workload_status" in body["data"]["tools"]
