import asyncio
import importlib
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))


def _load_incidents_router():
    to_remove = [key for key in sys.modules if key == "app" or key.startswith("app.")]
    for key in to_remove:
        del sys.modules[key]
    import app.routers.incidents as incidents_router

    importlib.reload(incidents_router)
    return incidents_router


def test_bff_incident_list_forwards_query_params(monkeypatch):
    incidents_router = _load_incidents_router()
    captured = {}

    class _FakeResp:
        def json(self):
            return {"success": True, "data": {"incidents": [], "view": "detail", "limit": 12}}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, **kwargs):
            captured["url"] = url
            captured["params"] = kwargs.get("params")
            return _FakeResp()

    monkeypatch.setattr(incidents_router.httpx, "AsyncClient", _FakeAsyncClient)

    payload = asyncio.run(incidents_router.list_incidents(view="detail", limit=12))

    assert payload["success"] is True
    assert captured["url"].endswith("/api/v1/incidents")
    assert captured["params"] == {"view": "detail", "limit": 12}
