from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from opspilot_schema.envelope import make_success

from app.api import router, service

app = FastAPI(title="OpsPilot Memory Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
service.init()


@app.on_event("startup")
async def startup() -> None:
    service.init()


@app.get("/health")
async def health():
    return make_success(
        {
            "status": "ok",
            "service": "memory-service",
            "storage_backend": "postgres" if service.store.pg_enabled() else "sqlite",
            "graph_backend": "neo4j" if service.graph.enabled() else "degraded",
        }
    )
