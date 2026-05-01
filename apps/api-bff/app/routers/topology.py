"""BFF router: topology (proxy to topology-service)."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from opspilot_schema.envelope import make_error

router = APIRouter(prefix="/topology", tags=["topology"])

TOPOLOGY_SERVICE_URL = os.environ.get("TOPOLOGY_SERVICE_URL", "http://127.0.0.1:8090")


@router.get("/graph")
async def get_graph(connection_id: str = "conn-vcenter-prod", object_id: str | None = None, depth: int = 3):
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            params = {"connection_id": connection_id, "depth": max(1, min(depth, 5))}
            if object_id:
                params["object_id"] = object_id
            resp = await client.get(f"{TOPOLOGY_SERVICE_URL}/api/v1/topology/graph", params=params)
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Topology service unreachable: {exc}")


@router.get("/incidents/{incident_id}")
async def get_incident_graph(incident_id: str, depth: int = 2):
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            resp = await client.get(
                f"{TOPOLOGY_SERVICE_URL}/api/v1/topology/incidents/{incident_id}",
                params={"depth": max(1, min(depth, 4))},
            )
            return resp.json()
        except httpx.HTTPError as exc:
            return make_error(f"Topology service unreachable: {exc}")
