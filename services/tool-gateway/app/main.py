from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import invoke, tools
from opspilot_schema import make_success

app = FastAPI(title="OpsPilot Tool Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api/v1")

api.include_router(tools.router, tags=["tools"])
api.include_router(invoke.router, tags=["invoke"])


@api.get("/health")
def health() -> dict:
    return make_success(
        data={"status": "ok", "service": "tool-gateway"},
        request_id=str(uuid4()),
        trace_id=str(uuid4()),
    )


app.include_router(api)
