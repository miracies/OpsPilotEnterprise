"""Smoke tests for Auth BFF routes."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared-schema", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))

from fastapi.testclient import TestClient


def _get_client():
    from app.main import app
    return TestClient(app)


def test_login_success():
    client = _get_client()
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["username"] == "admin"
    assert data["data"]["display_name"] == "管理员"
    assert data["data"]["role"] == "admin"
    assert "token" in data["data"]
    assert "opspilot_token" in resp.cookies


def test_login_failure():
    client = _get_client()
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_me_unauthenticated():
    client = _get_client()
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_authenticated():
    client = _get_client()
    login_resp = client.post("/api/v1/auth/login", json={"username": "zhangsan", "password": "ops123"})
    assert login_resp.status_code == 200

    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["username"] == "zhangsan"
    assert data["data"]["display_name"] == "张三"


def test_logout():
    client = _get_client()
    client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})

    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401
