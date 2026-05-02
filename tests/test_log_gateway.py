"""Tests for Log Gateway."""
import os
import sys

from conftest import load_service_app
from fastapi.testclient import TestClient

SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "log-gateway")
_app = load_service_app(SERVICE_DIR)
LOG_MAIN = sys.modules["app.main"]
client = TestClient(_app)


def test_opensearch_dsl_contains_filters_and_keywords():
    config = LOG_MAIN.LogSourceConfig(
        id="src-test",
        name="Test",
        backend_type="opensearch",
        endpoint="http://opensearch:9200",
        index_pattern="opspilot-vmware-*",
    )
    req = LOG_MAIN.LogSearchRequest(
        time_range={"from": "2026-05-01T00:00:00Z", "to": "2026-05-01T01:00:00Z"},
        filters={"component": ["hostd", "vmkernel"], "severity": ["warning", "error"], "host": "esxi-01"},
        query="APD OR PDL OR vm-123",
        limit=50,
    )
    dsl = LOG_MAIN.build_opensearch_dsl(req, config)
    assert dsl["size"] == 50
    bool_query = dsl["query"]["bool"]
    filters_text = str(bool_query["filter"])
    assert "'component': ['hostd', 'vmkernel']" in filters_text
    assert "'component.keyword': ['hostd', 'vmkernel']" in filters_text
    assert "'severity': ['warning', 'error']" in filters_text
    assert "'level.keyword': ['warning', 'error']" in filters_text
    assert "'host.name.keyword': ['esxi-01']" in filters_text
    assert "'source_host.keyword': ['esxi-01']" in filters_text
    assert "'match_phrase': {'hostname': 'esxi-01'}" in filters_text
    assert bool_query["must"][0]["query_string"]["query"] == "APD OR PDL OR vm-123"
    fields = bool_query["must"][0]["query_string"]["fields"]
    assert "raw_message" in fields
    assert "host.name" in fields
    assert "vm_moid" in fields


def test_opensearch_dsl_supports_vmware_alias_filters():
    config = LOG_MAIN.LogSourceConfig(
        id="src-test",
        name="Test",
        backend_type="opensearch",
        endpoint="https://opensearch:9200",
        index_pattern="opspilot-vmware-*",
    )
    req = LOG_MAIN.LogSearchRequest(
        filters={
            "vm_name": "app-01",
            "vm_moid": "vm-123",
            "datastore": "ds-prod-01",
            "vcenter": "vcsa-01",
            "product": "esxi",
        },
        query="overallStatus red",
    )
    filters = LOG_MAIN.build_opensearch_dsl(req, config)["query"]["bool"]["filter"]
    filters_text = str(filters)
    assert "'vm_name.keyword': ['app-01']" in filters_text
    assert "'object_name.keyword': ['app-01']" in filters_text
    assert "'vm_moid.keyword': ['vm-123']" in filters_text
    assert "'object_moid.keyword': ['vm-123']" in filters_text
    assert "'datastore.keyword': ['ds-prod-01']" in filters_text
    assert "'datastore_name.keyword': ['ds-prod-01']" in filters_text
    assert "'vcenter.keyword': ['vcsa-01']" in filters_text
    assert "'product.keyword': ['esxi']" in filters_text


def test_default_source_seed_uses_basic_auth_env(monkeypatch):
    monkeypatch.setattr(LOG_MAIN, "DEFAULT_OPENSEARCH_URL", "https://opensearch:9200")
    monkeypatch.setattr(LOG_MAIN, "DEFAULT_OPENSEARCH_INDEX", "opspilot-vmware-*")
    monkeypatch.setattr(LOG_MAIN, "DEFAULT_LOG_WEB_URL", "http://logs.example/app/discover")
    monkeypatch.setattr(LOG_MAIN, "DEFAULT_OPENSEARCH_USERNAME", "admin")
    monkeypatch.setattr(LOG_MAIN, "DEFAULT_OPENSEARCH_PASSWORD", "secret")
    monkeypatch.setattr(LOG_MAIN, "DEFAULT_OPENSEARCH_TLS_VERIFY", False)

    class FakeRepo:
        def __init__(self):
            self.source = None

        def list_sources(self):
            return []

        def upsert_source(self, body):
            self.source = body

    fake_repo = FakeRepo()
    monkeypatch.setattr(LOG_MAIN, "repo", fake_repo)
    LOG_MAIN._seed_default_source()
    assert fake_repo.source.auth_type == "basic"
    assert fake_repo.source.username == "admin"
    assert fake_repo.source.password == "secret"
    assert fake_repo.source.tls_verify is False


def test_opensearch_dashboard_links_use_anonymous_entrypoint():
    config = LOG_MAIN.LogSourceConfig(
        id="src-test",
        name="Test",
        backend_type="opensearch",
        endpoint="https://opensearch:9200",
        index_pattern="opspilot-vmware-*",
        web_url="http://logs.example/app/discover",
    )
    backend = LOG_MAIN.OpenSearchLogBackend(config)
    link = backend._link("overallStatus OR hostd")[0]
    assert link.url.startswith("http://logs.example/auth/anonymous?nextUrl=")
    assert "%2Fapp%2Fdiscover%3Fq%3DoverallStatus%2520OR%2520hostd" in link.url


def test_sources_and_evidence_refs_api():
    source_id = "logsrc-pytest"
    client.delete(f"/api/v1/logs/sources/{source_id}")
    resp = client.post(
        "/api/v1/logs/sources",
        json={
            "id": source_id,
            "name": "Pytest OpenSearch",
            "backend_type": "opensearch",
            "endpoint": "http://opensearch.local:9200",
            "auth_type": "basic",
            "username": "ops",
            "password": "secret",
            "index_pattern": "opspilot-vmware-*",
            "web_url": "http://opensearch.local/app/discover",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == source_id
    assert data["has_secret"] is True
    assert "password" not in data

    listed = client.get("/api/v1/logs/sources").json()["data"]["items"]
    assert any(item["id"] == source_id for item in listed)

    ev_resp = client.post(
        "/api/v1/logs/evidence",
        json={"incident_id": "inc-logs", "log_ids": ["opensearch:index:doc"], "comment": "APD evidence"},
    )
    assert ev_resp.status_code == 200
    assert ev_resp.json()["data"]["evidence_refs"][0].startswith("evidence-log-")


def test_context_templates_without_source_are_non_fatal(monkeypatch):
    monkeypatch.setattr(LOG_MAIN, "_enabled_source", lambda source_id=None, backend=None: None)
    resp = client.post(
        "/api/v1/logs/context",
        json={
            "incident_id": "inc-vmotion",
            "host": "esxi-03",
            "vm_name": "app-01",
            "vm_moid": "vm-123",
            "scenario": "vmotion_failed",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["groups"] == []
    assert "vmotion_logs" in body["data"]["queries_executed"]


def test_search_and_raw_with_fake_backend(monkeypatch):
    source_id = "logsrc-fake-backend"
    client.post(
        "/api/v1/logs/sources",
        json={
            "id": source_id,
            "name": "Fake OpenSearch",
            "backend_type": "opensearch",
            "endpoint": "http://opensearch.local:9200",
            "index_pattern": "opspilot-vmware-*",
            "web_url": "http://opensearch.local/app/discover",
        },
    )

    class FakeBackend:
        def __init__(self, config):
            self.config = config

        async def search(self, query):
            item = LOG_MAIN.LogItem(
                log_id="opensearch:opspilot-vmware-2026.05.01:abc123",
                timestamp="2026-05-01T09:32:15Z",
                source="esxi-03",
                product="esxi",
                component="vmkernel",
                severity="warning",
                message="NMP APD detected",
                raw_message="2026-05-01T09:32:15Z esxi-03 vmkernel: NMP APD detected",
                fields={"datastore": "ds-prod-01"},
                backend="opensearch",
                index="opspilot-vmware-2026.05.01",
                document_id="abc123",
                external_links=[{"provider": "opensearch", "title": "OpenSearch Dashboards", "url": "http://logs/q"}],
            )
            return LOG_MAIN.LogSearchResponse(total=1, items=[item], backend="opensearch", source_id=self.config.id)

        async def get_raw(self, log_id):
            result = await self.search(LOG_MAIN.LogSearchRequest())
            return result.items[0]

        async def test_connection(self):
            return {"status": "green"}

    monkeypatch.setattr(LOG_MAIN, "_backend", lambda config: FakeBackend(config))
    search = client.post("/api/v1/logs/search", json={"source_id": source_id, "query": "APD"}).json()["data"]
    assert search["total"] == 1
    assert search["items"][0]["raw_message"].endswith("NMP APD detected")
    assert search["items"][0]["external_links"][0]["url"] == "http://logs/q"

    raw = client.get("/api/v1/logs/raw/opensearch:opspilot-vmware-2026.05.01:abc123").json()["data"]
    assert raw["document_id"] == "abc123"
