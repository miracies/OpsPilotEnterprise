from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opspilot_schema.envelope import make_success

from app.routers import execute, query

CAPABILITY_TOOLS = [
    "get_vcenter_inventory",
    "get_vm_detail",
    "get_host_detail",
    "get_cluster_detail",
    "query_events",
    "query_metrics",
    "query_alerts",
    "query_topology",
    "create_snapshot",
    "vm_migrate",
    "vm_power_on",
    "vm_power_off",
    "vm_guest_restart",
]

app = FastAPI(title="OpsPilot VMware Skill Gateway (Mock)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_v1 = APIRouter(prefix="/api/v1")


@api_v1.get("/health")
def health() -> dict:
    return make_success({"status": "healthy", "service": "vmware-skill-gateway"})


@api_v1.get("/capabilities")
def capabilities() -> dict:
    return make_success({"tools": CAPABILITY_TOOLS})


app.include_router(api_v1)
app.include_router(query.router, prefix="/api/v1")
app.include_router(execute.router, prefix="/api/v1")
