"""Resource Connection Center endpoints."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from opspilot_schema.envelope import make_success, make_error
from app.services.secret_store import resolve_credential

router = APIRouter(prefix="/connections", tags=["connections"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_connection(conn_id: str) -> dict[str, Any] | None:
    return next((c for c in MOCK_CONNECTIONS if c["id"] == conn_id), None)


def _get_default_connection(conn_type: str) -> dict[str, Any] | None:
    return next((c for c in MOCK_CONNECTIONS if c["type"] == conn_type), None)


async def resolve_connection_context(
    conn_id: str | None = None,
    conn_type: str | None = None,
) -> dict[str, Any] | None:
    conn = _get_connection(conn_id) if conn_id else (_get_default_connection(conn_type) if conn_type else None)
    if not conn:
        return None
    resolved_creds = None
    cred_ref = conn.get("credential_ref", "")
    if cred_ref.startswith("secret://"):
        resolved_creds = await resolve_credential(cred_ref)
    return {
        "connection": conn,
        "credentials": resolved_creds,
    }


# ── Category labels ──────────────────────────────────────────
CATEGORIES = {
    "vcenter": "VMware vCenter",
    "kubeconfig": "Kubernetes",
    "network_device": "网络设备",
    "storage_array": "存储阵列",
    "milvus": "Milvus 向量库",
    "elasticsearch": "Elasticsearch",
    "opa": "OPA 策略引擎",
    "n8n": "n8n 工作流",
    "rag_index": "RAG 索引",
    "llm": "大语言模型",
    "itsm": "ITSM 工单",
    "notification": "通知渠道",
}

# ── Mock connections ─────────────────────────────────────────
VCENTER_ENDPOINT = os.environ.get("VCENTER_ENDPOINT", "https://192.168.1.16:443/sdk")
VCENTER_DR_ENDPOINT = os.environ.get("VCENTER_DR_ENDPOINT", "https://vcenter-dr.corp.local:443/sdk")

MOCK_CONNECTIONS: list[dict[str, Any]] = [
    {
        "id": "conn-vcenter-prod",
        "name": "vcenter-prod",
        "display_name": "vCenter 生产环境",
        "type": "vcenter",
        "category": "VMware vCenter",
        "endpoint": VCENTER_ENDPOINT,
        "scope": "Datacenter: DC-01, DC-02",
        "credential_ref": "secret://vcenter-prod",
        "proxy_config": None,
        "status": "active",
        "enabled": True,
        "version": "vSphere 8.0",
        "description": "生产环境 vCenter Server，管理 DC-01 和 DC-02 两个数据中心",
        "created_at": "2026-02-15T10:00:00Z",
        "updated_at": "2026-04-01T08:00:00Z",
        "last_tested": "2026-04-05T08:50:00Z",
        "last_test_result": "pass",
        "last_test_latency_ms": 45,
        "bound_tools": ["vmware.get_vcenter_inventory", "vmware.get_vm_detail", "vmware.get_host_detail", "vmware.query_events", "vmware.query_metrics", "vmware.vm_migrate", "vmware.create_snapshot", "vmware.power_off", "vmware.delete_snapshot"],
        "tags": ["production", "vmware", "core"],
    },
    {
        "id": "conn-vcenter-dr",
        "name": "vcenter-dr",
        "display_name": "vCenter 灾备环境",
        "type": "vcenter",
        "category": "VMware vCenter",
        "endpoint": VCENTER_DR_ENDPOINT,
        "scope": "Datacenter: DC-DR",
        "credential_ref": "secret://vcenter-dr",
        "proxy_config": "jumphost: bastion-dr.corp.local:22",
        "status": "active",
        "enabled": True,
        "version": "vSphere 8.0",
        "description": "灾备 vCenter Server，通过跳板机访问",
        "created_at": "2026-02-20T10:00:00Z",
        "updated_at": "2026-03-28T14:00:00Z",
        "last_tested": "2026-04-05T08:50:00Z",
        "last_test_result": "pass",
        "last_test_latency_ms": 120,
        "bound_tools": ["vmware.get_vcenter_inventory", "vmware.get_vm_detail"],
        "tags": ["dr", "vmware"],
    },
    {
        "id": "conn-milvus-prod",
        "name": "milvus-prod",
        "display_name": "Milvus 向量库",
        "type": "milvus",
        "category": "Milvus 向量库",
        "endpoint": "milvus-prod.corp.local:19530",
        "scope": "Collection: opspilot_kb",
        "credential_ref": "vault://secret/milvus/prod",
        "proxy_config": None,
        "status": "error",
        "enabled": True,
        "version": "Milvus 2.4",
        "description": "知识库向量存储，当前响应延迟异常",
        "created_at": "2026-03-10T10:00:00Z",
        "updated_at": "2026-04-04T08:00:00Z",
        "last_tested": "2026-04-05T08:35:00Z",
        "last_test_result": "fail",
        "last_test_latency_ms": 15200,
        "bound_tools": ["rag.knowledge_search", "rag.document_ingest"],
        "tags": ["rag", "vector", "knowledge"],
    },
    {
        "id": "conn-opa-prod",
        "name": "opa-prod",
        "display_name": "OPA 策略引擎",
        "type": "opa",
        "category": "OPA 策略引擎",
        "endpoint": "http://opa-prod.corp.local:8181",
        "scope": "Bundle: opspilot/v1",
        "credential_ref": "vault://secret/opa/token",
        "proxy_config": None,
        "status": "active",
        "enabled": True,
        "version": "OPA v0.62",
        "description": "策略决策引擎，负责工具调用权限和审批策略判定",
        "created_at": "2026-02-15T10:00:00Z",
        "updated_at": "2026-04-01T08:00:00Z",
        "last_tested": "2026-04-05T08:50:00Z",
        "last_test_result": "pass",
        "last_test_latency_ms": 8,
        "bound_tools": [],
        "tags": ["policy", "security", "core"],
    },
    {
        "id": "conn-n8n-prod",
        "name": "n8n-prod",
        "display_name": "n8n 工作流引擎",
        "type": "n8n",
        "category": "n8n 工作流",
        "endpoint": "https://n8n-prod.corp.local:5678",
        "scope": "Webhook: /approval, /notification",
        "credential_ref": "vault://secret/n8n/api-key",
        "proxy_config": None,
        "status": "active",
        "enabled": True,
        "version": "n8n 1.32",
        "description": "工作流引擎，处理审批流、通知流和工单集成",
        "created_at": "2026-02-15T10:00:00Z",
        "updated_at": "2026-04-01T08:00:00Z",
        "last_tested": "2026-04-05T08:50:00Z",
        "last_test_result": "pass",
        "last_test_latency_ms": 32,
        "bound_tools": [],
        "tags": ["workflow", "approval", "notification"],
    },
    {
        "id": "conn-llm-zhipu",
        "name": "llm-zhipu",
        "display_name": "智谱 GLM 大模型",
        "type": "llm",
        "category": "大语言模型",
        "endpoint": "https://open.bigmodel.cn/api/paas/v4",
        "scope": "Model: glm-5-turbo",
        "credential_ref": "vault://secret/llm/zhipu-api-key",
        "proxy_config": None,
        "status": "active",
        "enabled": True,
        "version": "GLM-5-turbo",
        "description": "智谱 AI 大语言模型，用于对话和诊断推理",
        "created_at": "2026-04-01T10:00:00Z",
        "updated_at": "2026-04-05T08:00:00Z",
        "last_tested": "2026-04-05T08:45:00Z",
        "last_test_result": "pass",
        "last_test_latency_ms": 680,
        "bound_tools": [],
        "tags": ["llm", "ai", "core"],
    },
    {
        "id": "conn-rag-index",
        "name": "rag-index-prod",
        "display_name": "RAG 索引服务",
        "type": "rag_index",
        "category": "RAG 索引",
        "endpoint": "http://rag-service.corp.local:8060",
        "scope": "Index: opspilot_docs, opspilot_runbooks",
        "credential_ref": "vault://secret/rag/service-token",
        "proxy_config": None,
        "status": "active",
        "enabled": True,
        "version": "1.0.0",
        "description": "RAG 索引服务，管理知识文档分段、嵌入和检索",
        "created_at": "2026-03-10T10:00:00Z",
        "updated_at": "2026-04-04T08:00:00Z",
        "last_tested": "2026-04-05T08:50:00Z",
        "last_test_result": "pass",
        "last_test_latency_ms": 55,
        "bound_tools": ["rag.knowledge_search", "rag.document_ingest"],
        "tags": ["rag", "knowledge"],
    },
    {
        "id": "conn-es-logs",
        "name": "es-logs",
        "display_name": "Elasticsearch 日志",
        "type": "elasticsearch",
        "category": "Elasticsearch",
        "endpoint": "https://es-prod.corp.local:9200",
        "scope": "Index: opspilot-logs-*, opspilot-events-*",
        "credential_ref": "vault://secret/es/api-key",
        "proxy_config": None,
        "status": "active",
        "enabled": True,
        "version": "ES 8.12",
        "description": "日志和事件存储引擎",
        "created_at": "2026-02-15T10:00:00Z",
        "updated_at": "2026-03-20T14:00:00Z",
        "last_tested": "2026-04-05T08:50:00Z",
        "last_test_result": "pass",
        "last_test_latency_ms": 18,
        "bound_tools": ["evidence.search"],
        "tags": ["logs", "events", "search"],
    },
    {
        "id": "conn-k8s-staging",
        "name": "k8s-staging",
        "display_name": "K8s 测试集群",
        "type": "kubeconfig",
        "category": "Kubernetes",
        "endpoint": "https://k8s-staging.corp.local:6443",
        "scope": "Namespace: opspilot-test, default",
        "credential_ref": "secret://k8s-staging",
        "proxy_config": None,
        "status": "inactive",
        "enabled": False,
        "version": "K8s 1.29",
        "description": "测试环境 Kubernetes 集群（尚未启用）",
        "created_at": "2026-04-05T06:00:00Z",
        "updated_at": "2026-04-05T06:00:00Z",
        "last_tested": None,
        "last_test_result": None,
        "last_test_latency_ms": None,
        "bound_tools": ["k8s.list_pods", "k8s.get_pod_logs", "k8s.restart_deployment"],
        "tags": ["k8s", "staging"],
    },
    {
        "id": "conn-notify-email",
        "name": "notify-email",
        "display_name": "邮件通知渠道",
        "type": "notification",
        "category": "通知渠道",
        "endpoint": "smtp://mail.corp.local:587",
        "scope": "From: opspilot@corp.local",
        "credential_ref": "vault://secret/smtp/credentials",
        "proxy_config": None,
        "status": "active",
        "enabled": True,
        "version": None,
        "description": "企业邮件通知渠道",
        "created_at": "2026-02-20T10:00:00Z",
        "updated_at": "2026-03-01T14:00:00Z",
        "last_tested": "2026-04-05T08:50:00Z",
        "last_test_result": "pass",
        "last_test_latency_ms": 320,
        "bound_tools": [],
        "tags": ["notification", "email"],
    },
]

# ── Mock key rotation records ────────────────────────────────
MOCK_ROTATIONS: list[dict[str, Any]] = [
    {"id": "rot-001", "connection_id": "conn-vcenter-prod", "rotated_by": "admin", "old_credential_ref": "vault://secret/vcenter/prod@v2", "new_credential_ref": "vault://secret/vcenter/prod@v3", "rotated_at": "2026-04-01T02:00:00Z", "status": "success", "note": "季度密钥轮换"},
    {"id": "rot-002", "connection_id": "conn-vcenter-prod", "rotated_by": "admin", "old_credential_ref": "vault://secret/vcenter/prod@v1", "new_credential_ref": "vault://secret/vcenter/prod@v2", "rotated_at": "2026-01-01T02:00:00Z", "status": "success", "note": "季度密钥轮换"},
    {"id": "rot-003", "connection_id": "conn-llm-zhipu", "rotated_by": "admin", "old_credential_ref": "vault://secret/llm/zhipu-api-key@v1", "new_credential_ref": "vault://secret/llm/zhipu-api-key@v2", "rotated_at": "2026-04-01T10:00:00Z", "status": "success", "note": "API Key 更新"},
    {"id": "rot-004", "connection_id": "conn-milvus-prod", "rotated_by": "system", "old_credential_ref": "vault://secret/milvus/prod@v1", "new_credential_ref": "vault://secret/milvus/prod@v2", "rotated_at": "2026-03-15T02:00:00Z", "status": "failed", "note": "自动轮换失败：连接超时"},
]

# ── Mock audit records ───────────────────────────────────────
MOCK_AUDITS: list[dict[str, Any]] = [
    {"id": "caud-001", "connection_id": "conn-vcenter-prod", "action": "connectivity_test", "actor": "admin", "detail": "连通性测试通过，延迟 45ms", "timestamp": "2026-04-05T08:50:00Z", "ip": "10.0.1.50"},
    {"id": "caud-002", "connection_id": "conn-milvus-prod", "action": "connectivity_test", "actor": "admin", "detail": "连通性测试失败，延迟 15200ms（超时）", "timestamp": "2026-04-05T08:35:00Z", "ip": "10.0.1.50"},
    {"id": "caud-003", "connection_id": "conn-vcenter-prod", "action": "credential_rotation", "actor": "admin", "detail": "密钥轮换成功 v2→v3", "timestamp": "2026-04-01T02:00:00Z", "ip": "10.0.1.50"},
    {"id": "caud-004", "connection_id": "conn-k8s-staging", "action": "created", "actor": "admin", "detail": "创建连接 Profile", "timestamp": "2026-04-05T06:00:00Z", "ip": "10.0.1.50"},
    {"id": "caud-005", "connection_id": "conn-llm-zhipu", "action": "updated", "actor": "admin", "detail": "更新 endpoint 和 API Key", "timestamp": "2026-04-01T10:00:00Z", "ip": "10.0.1.50"},
    {"id": "caud-006", "connection_id": "conn-opa-prod", "action": "connectivity_test", "actor": "system", "detail": "自动健康检查通过", "timestamp": "2026-04-05T08:50:00Z", "ip": "10.0.1.1"},
    {"id": "caud-007", "connection_id": "conn-n8n-prod", "action": "enabled", "actor": "admin", "detail": "启用连接", "timestamp": "2026-02-15T10:30:00Z", "ip": "10.0.1.50"},
]

# ── Retention config ─────────────────────────────────────────
MOCK_RETENTION = {
    "audit_retention_days": 365,
    "connection_test_history_days": 90,
    "key_rotation_history_days": 730,
}


# ── Request models ───────────────────────────────────────────

class CreateConnectionBody(BaseModel):
    name: str
    display_name: str
    type: str
    endpoint: str
    scope: str = ""
    credential_ref: str = ""
    proxy_config: str = ""
    description: str = ""
    tags: list[str] = []


class UpdateConnectionBody(BaseModel):
    display_name: Optional[str] = None
    endpoint: Optional[str] = None
    scope: Optional[str] = None
    credential_ref: Optional[str] = None
    proxy_config: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None


class TestConnectionBody(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None


class ToggleConnectionBody(BaseModel):
    enabled: bool


class RetentionBody(BaseModel):
    audit_retention_days: int
    connection_test_history_days: int
    key_rotation_history_days: int


# ── Routes ───────────────────────────────────────────────────

def _validate_connection_payload(conn_type: str, credential_ref: str) -> str | None:
    if conn_type in {"vcenter", "kubeconfig"} and credential_ref and not credential_ref.startswith("secret://"):
        return f"{conn_type} 连接必须使用 secret:// 凭据引用"
    return None

@router.get("")
async def list_connections(
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
):
    conns = list(MOCK_CONNECTIONS)
    if type:
        conns = [c for c in conns if c["type"] == type]
    if status:
        conns = [c for c in conns if c["status"] == status]
    if enabled is not None:
        conns = [c for c in conns if c["enabled"] == enabled]
    return make_success(conns)


@router.get("/stats")
async def connection_stats():
    total = len(MOCK_CONNECTIONS)
    active = sum(1 for c in MOCK_CONNECTIONS if c["status"] == "active")
    error_count = sum(1 for c in MOCK_CONNECTIONS if c["status"] == "error")
    inactive = sum(1 for c in MOCK_CONNECTIONS if c["status"] == "inactive")
    types: dict[str, int] = {}
    for c in MOCK_CONNECTIONS:
        types[c["type"]] = types.get(c["type"], 0) + 1
    return make_success({
        "total": total,
        "active": active,
        "error": error_count,
        "inactive": inactive,
        "types": types,
    })


@router.get("/categories")
async def list_categories():
    return make_success(CATEGORIES)


@router.get("/retention")
async def get_retention():
    return make_success(MOCK_RETENTION)


@router.put("/retention")
async def update_retention(body: RetentionBody):
    MOCK_RETENTION.update(body.model_dump())
    return make_success(MOCK_RETENTION)


@router.get("/rotations")
async def list_rotations(connection_id: Optional[str] = Query(None)):
    recs = MOCK_ROTATIONS
    if connection_id:
        recs = [r for r in recs if r["connection_id"] == connection_id]
    return make_success(recs)


@router.get("/audits")
async def list_audits(connection_id: Optional[str] = Query(None), limit: int = Query(50)):
    recs = MOCK_AUDITS
    if connection_id:
        recs = [r for r in recs if r["connection_id"] == connection_id]
    return make_success(recs[:limit])


@router.get("/{conn_id}")
async def get_connection(conn_id: str):
    for c in MOCK_CONNECTIONS:
        if c["id"] == conn_id:
            return make_success(c)
    return make_error(f"Connection {conn_id} not found")


@router.post("")
async def create_connection(body: CreateConnectionBody):
    err = _validate_connection_payload(body.type, body.credential_ref)
    if err:
        return make_error(err)
    new_id = f"conn-{body.name}"
    conn = {
        "id": new_id,
        "name": body.name,
        "display_name": body.display_name,
        "type": body.type,
        "category": CATEGORIES.get(body.type, body.type),
        "endpoint": body.endpoint,
        "scope": body.scope,
        "credential_ref": body.credential_ref,
        "proxy_config": body.proxy_config or None,
        "status": "inactive",
        "enabled": False,
        "version": None,
        "description": body.description,
        "created_at": _now(),
        "updated_at": _now(),
        "last_tested": None,
        "last_test_result": None,
        "last_test_latency_ms": None,
        "bound_tools": [],
        "tags": body.tags,
    }
    MOCK_CONNECTIONS.append(conn)
    MOCK_AUDITS.insert(0, {"id": f"caud-{len(MOCK_AUDITS)+1:03d}", "connection_id": new_id, "action": "created", "actor": "admin", "detail": f"创建连接 Profile: {body.display_name}", "timestamp": _now(), "ip": "10.0.1.50"})
    return make_success(conn)


@router.patch("/{conn_id}/toggle")
async def toggle_connection(conn_id: str, body: ToggleConnectionBody):
    for c in MOCK_CONNECTIONS:
        if c["id"] == conn_id:
            c["enabled"] = body.enabled
            c["status"] = "active" if body.enabled and c["status"] != "error" else ("inactive" if not body.enabled else c["status"])
            c["updated_at"] = _now()
            action = "enabled" if body.enabled else "disabled"
            MOCK_AUDITS.insert(0, {"id": f"caud-{len(MOCK_AUDITS)+1:03d}", "connection_id": conn_id, "action": action, "actor": "admin", "detail": f"{'启用' if body.enabled else '停用'}连接", "timestamp": _now(), "ip": "10.0.1.50"})
            return make_success(c)
    return make_error(f"Connection {conn_id} not found")


@router.post("/{conn_id}/test")
async def test_connection(conn_id: str, body: Optional[TestConnectionBody] = None):
    conn = _get_connection(conn_id)
    if not conn:
        return make_error(f"Connection {conn_id} not found")

    conn_type = conn.get("type", "")

    # Auto-resolve credentials from secret store
    cred_ref = conn.get("credential_ref", "")
    resolved_creds: dict | None = None
    if cred_ref.startswith("secret://"):
        resolved_creds = await resolve_credential(cred_ref)

    if conn_type == "vcenter":
        from app.services.connectivity_tester import test_vcenter_connection

        username = body.username if body else None
        password = body.password if body else None

        if not username and not password and resolved_creds:
            username = resolved_creds.get("username")
            password = resolved_creds.get("password")

        checks = await test_vcenter_connection(conn["endpoint"], username, password)
        is_ok = all(c["passed"] for c in checks)
        latency = sum(c["duration_ms"] for c in checks)
    elif conn_type == "kubeconfig":
        from app.services.connectivity_tester import test_k8s_connection

        kubeconfig_json = resolved_creds

        checks = await test_k8s_connection(conn["endpoint"], kubeconfig_json)
        is_ok = all(c["passed"] for c in checks)
        latency = sum(c["duration_ms"] for c in checks)
    else:
        # Other types: mock result
        is_ok = conn["status"] != "error" and conn["enabled"]
        latency = 45 if is_ok else 15200
        checks = [
            {"name": "dns_resolve", "passed": True, "message": "DNS 解析成功", "duration_ms": 2},
            {"name": "tcp_connect", "passed": True, "message": "TCP 连接成功", "duration_ms": 8},
            {"name": "auth", "passed": is_ok, "message": "认证成功" if is_ok else "认证失败：凭据无效或过期", "duration_ms": 15 if is_ok else 100},
            {"name": "api_health", "passed": is_ok, "message": f"API 健康检查{'通过' if is_ok else '超时'}", "duration_ms": latency},
        ]

    conn["last_tested"] = _now()
    conn["last_test_result"] = "pass" if is_ok else "fail"
    conn["last_test_latency_ms"] = latency
    if is_ok and not conn["enabled"]:
        pass
    elif is_ok:
        conn["status"] = "active"
    else:
        conn["status"] = "error"

    MOCK_AUDITS.insert(0, {"id": f"caud-{len(MOCK_AUDITS)+1:03d}", "connection_id": conn_id, "action": "connectivity_test", "actor": "admin", "detail": f"连通性测试{'通过' if is_ok else '失败'}，延迟 {latency}ms", "timestamp": _now(), "ip": "10.0.1.50"})

    return make_success({
        "connection_id": conn_id,
        "success": is_ok,
        "latency_ms": latency,
        "tested_at": _now(),
        "checks": checks,
    })


@router.put("/{conn_id}")
async def update_connection(conn_id: str, body: UpdateConnectionBody):
    for c in MOCK_CONNECTIONS:
        if c["id"] == conn_id:
            next_type = c["type"]
            next_ref = body.credential_ref if body.credential_ref is not None else c.get("credential_ref", "")
            err = _validate_connection_payload(next_type, next_ref)
            if err:
                return make_error(err)
            changes: list[str] = []
            for field in ("display_name", "endpoint", "scope", "credential_ref", "proxy_config", "description", "tags"):
                val = getattr(body, field, None)
                if val is not None:
                    old = c.get(field)
                    c[field] = val if field != "proxy_config" else (val or None)
                    if old != c[field]:
                        changes.append(field)
            c["updated_at"] = _now()
            MOCK_AUDITS.insert(0, {
                "id": f"caud-{len(MOCK_AUDITS)+1:03d}",
                "connection_id": conn_id,
                "action": "updated",
                "actor": "admin",
                "detail": f"编辑连接: {', '.join(changes) if changes else '无变更'}",
                "timestamp": _now(),
                "ip": "10.0.1.50",
            })
            return make_success(c)
    return make_error(f"Connection {conn_id} not found")


@router.delete("/{conn_id}")
async def delete_connection(conn_id: str):
    for i, c in enumerate(MOCK_CONNECTIONS):
        if c["id"] == conn_id:
            removed = MOCK_CONNECTIONS.pop(i)
            MOCK_AUDITS.insert(0, {
                "id": f"caud-{len(MOCK_AUDITS)+1:03d}",
                "connection_id": conn_id,
                "action": "deleted",
                "actor": "admin",
                "detail": f"删除连接: {removed['display_name']}",
                "timestamp": _now(),
                "ip": "10.0.1.50",
            })
            return make_success({"deleted": True, "id": conn_id})
    return make_error(f"Connection {conn_id} not found")
