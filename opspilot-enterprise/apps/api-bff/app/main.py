"""OpsPilot API BFF - aggregation layer for the frontend."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth, chat, incidents, change_impact, tools, connections, secrets,
    approvals, notifications, audit, knowledge, policies, cases, agent_runs, upgrades,
)

app = FastAPI(title="OpsPilot API BFF", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8010")
TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")
EVENT_INGESTION_URL = os.environ.get("EVENT_INGESTION_URL", "http://127.0.0.1:8060")

# Auth (no prefix - lives at /api/v1/auth/*)
app.include_router(auth.router,          prefix="/api/v1")

# P0 routes
app.include_router(chat.router,          prefix="/api/v1")
app.include_router(incidents.router,     prefix="/api/v1")
app.include_router(change_impact.router, prefix="/api/v1")
app.include_router(tools.router,         prefix="/api/v1")
app.include_router(connections.router,   prefix="/api/v1")
app.include_router(secrets.router,      prefix="/api/v1")

# P1 routes
app.include_router(approvals.router,     prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(audit.router,         prefix="/api/v1")
app.include_router(knowledge.router,     prefix="/api/v1")
app.include_router(policies.router,      prefix="/api/v1")
app.include_router(cases.router,         prefix="/api/v1")
app.include_router(agent_runs.router,    prefix="/api/v1")
app.include_router(upgrades.router,      prefix="/api/v1")


@app.on_event("startup")
async def _startup():
    from app.services.secret_store import init_db
    await init_db()


@app.get("/health")
async def health():
    from opspilot_schema.envelope import make_success
    return make_success({"status": "ok", "service": "api-bff", "version": "0.2.0"})
