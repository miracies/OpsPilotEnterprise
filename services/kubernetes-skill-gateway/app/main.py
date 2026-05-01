from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opspilot_schema.envelope import make_success

from app.routers import execute, invoke, query

CAPABILITY_TOOLS = [
    "k8s.list_nodes",
    "k8s.list_namespaces",
    "k8s.list_pods",
    "k8s.get_pod_logs",
    "k8s.get_workload_status",
    "k8s.restart_deployment",
    "k8s.scale_deployment",
]

app = FastAPI(title="OpsPilot Kubernetes Skill Gateway")

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
    return make_success({"status": "healthy", "service": "kubernetes-skill-gateway"})


@api_v1.get("/capabilities")
def capabilities() -> dict:
    return make_success({"tools": CAPABILITY_TOOLS})


app.include_router(api_v1)
app.include_router(invoke.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")
app.include_router(execute.router, prefix="/api/v1")
