"""Smoke tests for Knowledge & Cases BFF routes."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "shared-schema", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))

from fastapi.testclient import TestClient


def _get_client():
    from app.main import app
    return TestClient(app)


def test_list_knowledge_articles():
    client = _get_client()
    resp = client.get("/api/v1/knowledge/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    items = data["data"]["items"]
    assert len(items) > 0


def test_list_knowledge_articles_filter_status():
    client = _get_client()
    resp = client.get("/api/v1/knowledge/articles?status=published")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert all(i["status"] == "published" for i in items)


def test_get_article_detail():
    client = _get_client()
    resp = client.get("/api/v1/knowledge/articles/KB-001")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "KB-001"
    assert "confidence_score" in data


def test_list_import_jobs():
    client = _get_client()
    resp = client.get("/api/v1/knowledge/import-jobs")
    assert resp.status_code == 200
    jobs = resp.json()["data"]["items"]
    assert len(jobs) > 0


def test_list_cases():
    client = _get_client()
    resp = client.get("/api/v1/cases")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) > 0


def test_get_case_detail():
    client = _get_client()
    resp = client.get("/api/v1/cases/CASE-20260320")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "CASE-20260320"
    assert "root_cause_summary" in data
