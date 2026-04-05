"""OpsPilot API BFF - aggregation layer for the frontend."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, incidents, change_impact, tools

app = FastAPI(title="OpsPilot API BFF", version="0.1.0")

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

app.include_router(chat.router, prefix="/api/v1")
app.include_router(incidents.router, prefix="/api/v1")
app.include_router(change_impact.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")


@app.get("/health")
async def health():
    from opspilot_schema.envelope import make_success
    return make_success({"status": "ok", "service": "api-bff"})
