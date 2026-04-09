"""Tool Gateway management endpoints."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

from opspilot_schema.envelope import make_success, make_error

router = APIRouter(prefix="/tools", tags=["tools"])

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Extended mock data ───────────────────────────────────────
MOCK_GATEWAYS = [
    {
        "id": "gw-vmware",
        "name": "vmware-skill-gateway",
        "display_name": "VMware Skill Gateway",
        "domain": "vmware",
        "url": "http://127.0.0.1:8030",
        "status": "healthy",
        "tool_count": 9,
        "last_heartbeat": _now(),
        "latency_ms": 45,
        "version": "1.0.0",
    },
    {
        "id": "gw-change",
        "name": "change-impact-service",
        "display_name": "Change Impact Service",
        "domain": "platform",
        "url": "http://127.0.0.1:8040",
        "status": "healthy",
        "tool_count": 1,
        "last_heartbeat": _now(),
        "latency_ms": 32,
        "version": "1.0.0",
    },
    {
        "id": "gw-evidence",
        "name": "evidence-aggregator",
        "display_name": "Evidence Aggregator",
        "domain": "platform",
        "url": "http://127.0.0.1:8050",
        "status": "healthy",
        "tool_count": 2,
        "last_heartbeat": _now(),
        "latency_ms": 28,
        "version": "1.0.0",
    },
    {
        "id": "gw-k8s",
        "name": "kubernetes-skill-gateway",
        "display_name": "Kubernetes Skill Gateway",
        "domain": "kubernetes",
        "url": "http://127.0.0.1:8080",
        "status": "healthy",
        "tool_count": 6,
        "last_heartbeat": _now(),
        "latency_ms": 36,
        "version": "1.0.0",
    },
    {
        "id": "gw-rag",
        "name": "rag-service",
        "display_name": "RAG Knowledge Service",
        "domain": "knowledge",
        "url": "http://127.0.0.1:8060",
        "status": "degraded",
        "tool_count": 2,
        "last_heartbeat": "2026-04-05T08:30:00Z",
        "latency_ms": 820,
        "version": "1.0.0",
    },
]

MOCK_TOOLS_EXTENDED: list[dict[str, Any]] = [
    {"name": "vmware.get_vcenter_inventory", "display_name": "查询 vCenter 清单", "description": "获取 vCenter 下的完整资源清单，包括集群、主机、虚拟机、数据存储等", "category": "vmware", "domain": "vmware", "provider": "vmware-skill-gateway", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 30, "idempotent": True, "version": "1.2.0", "tags": ["vmware", "inventory"], "lifecycle_status": "enabled", "connection_ref": "conn-vcenter-prod", "supported_connection_types": ["vcenter"], "registered_at": "2026-03-01T10:00:00Z", "updated_at": "2026-04-01T08:00:00Z"},
    {"name": "vmware.get_vm_detail", "display_name": "查询虚拟机详情", "description": "获取指定虚拟机的详细信息，包括 CPU、内存、磁盘、网络配置", "category": "vmware", "domain": "vmware", "provider": "vmware-skill-gateway", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 30, "idempotent": True, "version": "1.2.0", "tags": ["vmware", "inventory"], "lifecycle_status": "enabled", "connection_ref": "conn-vcenter-prod", "supported_connection_types": ["vcenter"], "registered_at": "2026-03-01T10:00:00Z", "updated_at": "2026-04-01T08:00:00Z"},
    {"name": "vmware.get_host_detail", "display_name": "查询主机详情", "description": "获取 ESXi 主机详细信息，包括硬件规格、运行状态、VM 数量", "category": "vmware", "domain": "vmware", "provider": "vmware-skill-gateway", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 30, "idempotent": True, "version": "1.2.0", "tags": ["vmware", "inventory"], "lifecycle_status": "enabled", "connection_ref": "conn-vcenter-prod", "supported_connection_types": ["vcenter"], "registered_at": "2026-03-01T10:00:00Z", "updated_at": "2026-04-01T08:00:00Z"},
    {"name": "vmware.query_events", "display_name": "查询事件", "description": "查询 vCenter 事件日志，支持按时间范围和对象 ID 过滤", "category": "vmware", "domain": "vmware", "provider": "vmware-skill-gateway", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 30, "idempotent": True, "version": "1.2.0", "tags": ["vmware", "event"], "lifecycle_status": "enabled", "connection_ref": "conn-vcenter-prod", "supported_connection_types": ["vcenter"], "registered_at": "2026-03-01T10:00:00Z", "updated_at": "2026-04-01T08:00:00Z"},
    {"name": "vmware.query_metrics", "display_name": "查询性能指标", "description": "查询 ESXi 主机或虚拟机的性能指标（CPU、内存、磁盘、网络）", "category": "vmware", "domain": "vmware", "provider": "vmware-skill-gateway", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 60, "idempotent": True, "version": "1.2.0", "tags": ["vmware", "metric"], "lifecycle_status": "enabled", "connection_ref": "conn-vcenter-prod", "supported_connection_types": ["vcenter"], "registered_at": "2026-03-01T10:00:00Z", "updated_at": "2026-04-01T08:00:00Z"},
    {"name": "vmware.vm_migrate", "display_name": "迁移虚拟机", "description": "执行 vMotion 迁移虚拟机到目标主机，支持 Storage vMotion", "category": "vmware", "domain": "vmware", "provider": "vmware-skill-gateway", "action_type": "write", "risk_level": "high", "approval_required": True, "timeout_seconds": 300, "idempotent": False, "version": "1.2.0", "tags": ["vmware", "execution"], "lifecycle_status": "enabled", "connection_ref": "conn-vcenter-prod", "supported_connection_types": ["vcenter"], "registered_at": "2026-03-01T10:00:00Z", "updated_at": "2026-04-01T08:00:00Z"},
    {"name": "vmware.create_snapshot", "display_name": "创建快照", "description": "为指定虚拟机创建快照，支持内存快照和静默快照", "category": "vmware", "domain": "vmware", "provider": "vmware-skill-gateway", "action_type": "write", "risk_level": "medium", "approval_required": False, "timeout_seconds": 120, "idempotent": False, "version": "1.2.0", "tags": ["vmware", "snapshot"], "lifecycle_status": "enabled", "connection_ref": "conn-vcenter-prod", "supported_connection_types": ["vcenter"], "registered_at": "2026-03-01T10:00:00Z", "updated_at": "2026-04-01T08:00:00Z"},
    {"name": "vmware.power_off", "display_name": "关闭虚拟机电源", "description": "强制关闭虚拟机电源（硬关机），高风险操作", "category": "vmware", "domain": "vmware", "provider": "vmware-skill-gateway", "action_type": "dangerous", "risk_level": "critical", "approval_required": True, "timeout_seconds": 60, "idempotent": True, "version": "1.2.0", "tags": ["vmware", "power"], "lifecycle_status": "enabled", "connection_ref": "conn-vcenter-prod", "supported_connection_types": ["vcenter"], "registered_at": "2026-03-01T10:00:00Z", "updated_at": "2026-04-01T08:00:00Z"},
    {"name": "vmware.delete_snapshot", "display_name": "删除快照", "description": "删除指定虚拟机的快照（不可恢复）", "category": "vmware", "domain": "vmware", "provider": "vmware-skill-gateway", "action_type": "write", "risk_level": "high", "approval_required": True, "timeout_seconds": 180, "idempotent": False, "version": "1.2.0", "tags": ["vmware", "snapshot"], "lifecycle_status": "disabled", "connection_ref": "conn-vcenter-prod", "supported_connection_types": ["vcenter"], "registered_at": "2026-03-01T10:00:00Z", "updated_at": "2026-04-03T14:00:00Z"},
    {"name": "change_impact.analyze", "display_name": "变更影响分析", "description": "分析变更操作对基础设施的影响范围、风险评分和依赖关系", "category": "analysis", "domain": "platform", "provider": "change-impact-service", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 60, "idempotent": True, "version": "1.0.0", "tags": ["analysis", "change"], "lifecycle_status": "enabled", "connection_ref": None, "supported_connection_types": [], "registered_at": "2026-03-01T10:00:00Z", "updated_at": "2026-04-01T08:00:00Z"},
    {"name": "evidence.aggregate", "display_name": "证据聚合", "description": "从多个数据源聚合证据，生成统一证据包", "category": "analysis", "domain": "platform", "provider": "evidence-aggregator", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 45, "idempotent": True, "version": "1.0.0", "tags": ["evidence", "aggregation"], "lifecycle_status": "enabled", "connection_ref": None, "supported_connection_types": [], "registered_at": "2026-03-15T10:00:00Z", "updated_at": "2026-04-01T08:00:00Z"},
    {"name": "evidence.search", "display_name": "证据检索", "description": "从证据存储中按条件检索历史证据", "category": "analysis", "domain": "platform", "provider": "evidence-aggregator", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 30, "idempotent": True, "version": "1.0.0", "tags": ["evidence", "search"], "lifecycle_status": "enabled", "connection_ref": None, "supported_connection_types": [], "registered_at": "2026-03-15T10:00:00Z", "updated_at": "2026-04-01T08:00:00Z"},
    {"name": "k8s.list_nodes", "display_name": "查询节点列表", "description": "获取集群节点清单、Ready 状态、调度状态和版本信息", "category": "kubernetes", "domain": "kubernetes", "provider": "kubernetes-skill-gateway", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 30, "idempotent": True, "version": "1.0.0", "tags": ["k8s", "node"], "lifecycle_status": "enabled", "connection_ref": "conn-k8s-staging", "supported_connection_types": ["kubeconfig"], "registered_at": "2026-04-05T06:00:00Z", "updated_at": _now()},
    {"name": "k8s.list_namespaces", "display_name": "查询命名空间列表", "description": "获取集群命名空间及生命周期状态", "category": "kubernetes", "domain": "kubernetes", "provider": "kubernetes-skill-gateway", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 30, "idempotent": True, "version": "1.0.0", "tags": ["k8s", "namespace"], "lifecycle_status": "enabled", "connection_ref": "conn-k8s-staging", "supported_connection_types": ["kubeconfig"], "registered_at": "2026-04-05T06:00:00Z", "updated_at": _now()},
    {"name": "k8s.list_pods", "display_name": "查询 Pod 列表", "description": "获取指定命名空间下的 Pod 列表及状态", "category": "kubernetes", "domain": "kubernetes", "provider": "kubernetes-skill-gateway", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 30, "idempotent": True, "version": "1.0.0", "tags": ["k8s", "pod"], "lifecycle_status": "enabled", "connection_ref": "conn-k8s-staging", "supported_connection_types": ["kubeconfig"], "registered_at": "2026-04-05T06:00:00Z", "updated_at": _now()},
    {"name": "k8s.get_pod_logs", "display_name": "查询 Pod 日志", "description": "获取指定 Pod 容器的实时日志", "category": "kubernetes", "domain": "kubernetes", "provider": "kubernetes-skill-gateway", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 60, "idempotent": True, "version": "1.0.0", "tags": ["k8s", "log"], "lifecycle_status": "enabled", "connection_ref": "conn-k8s-staging", "supported_connection_types": ["kubeconfig"], "registered_at": "2026-04-05T06:00:00Z", "updated_at": _now()},
    {"name": "k8s.get_workload_status", "display_name": "查询工作负载状态", "description": "获取 Deployment、Pod、Node 的健康与副本状态摘要", "category": "kubernetes", "domain": "kubernetes", "provider": "kubernetes-skill-gateway", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 45, "idempotent": True, "version": "1.0.0", "tags": ["k8s", "deployment"], "lifecycle_status": "enabled", "connection_ref": "conn-k8s-staging", "supported_connection_types": ["kubeconfig"], "registered_at": "2026-04-05T06:00:00Z", "updated_at": _now()},
    {"name": "k8s.restart_deployment", "display_name": "重启 Deployment", "description": "滚动重启指定 Deployment 的所有 Pod", "category": "kubernetes", "domain": "kubernetes", "provider": "kubernetes-skill-gateway", "action_type": "write", "risk_level": "medium", "approval_required": True, "timeout_seconds": 180, "idempotent": False, "version": "1.0.0", "tags": ["k8s", "deployment"], "lifecycle_status": "enabled", "connection_ref": "conn-k8s-staging", "supported_connection_types": ["kubeconfig"], "registered_at": "2026-04-05T06:00:00Z", "updated_at": _now()},
    {"name": "rag.knowledge_search", "display_name": "知识库检索", "description": "基于 RAG 的知识库向量检索，返回相关文档片段", "category": "knowledge", "domain": "knowledge", "provider": "rag-service", "action_type": "read", "risk_level": "low", "approval_required": False, "timeout_seconds": 15, "idempotent": True, "version": "1.0.0", "tags": ["rag", "knowledge", "search"], "lifecycle_status": "degraded", "connection_ref": "conn-milvus-prod", "supported_connection_types": ["milvus", "elasticsearch"], "registered_at": "2026-03-10T10:00:00Z", "updated_at": "2026-04-04T08:00:00Z"},
    {"name": "rag.document_ingest", "display_name": "文档导入", "description": "将文档分段并写入向量存储，支持 PDF/Markdown/DOCX", "category": "knowledge", "domain": "knowledge", "provider": "rag-service", "action_type": "write", "risk_level": "medium", "approval_required": False, "timeout_seconds": 300, "idempotent": False, "version": "1.0.0", "tags": ["rag", "knowledge", "ingest"], "lifecycle_status": "degraded", "connection_ref": "conn-milvus-prod", "supported_connection_types": ["milvus", "elasticsearch"], "registered_at": "2026-03-10T10:00:00Z", "updated_at": "2026-04-04T08:00:00Z"},
]

MOCK_INVOCATIONS = [
    {"id": "inv-001", "tool_name": "vmware.get_host_detail", "caller": "RCAAgent", "caller_type": "agent", "input_summary": '{"host_id": "host-33"}', "output_summary": "CPU: 97.3%, Memory: 82.1%, VMs: 12", "status": "success", "duration_ms": 320, "dry_run": False, "policy_result": "allow", "timestamp": "2026-04-05T08:20:06Z", "trace_id": "trace-abc123"},
    {"id": "inv-002", "tool_name": "vmware.query_metrics", "caller": "RCAAgent", "caller_type": "agent", "input_summary": '{"host_id": "host-33", "metric": "cpu.usage"}', "output_summary": "1h trend: 72% → 97%", "status": "success", "duration_ms": 450, "dry_run": False, "policy_result": "allow", "timestamp": "2026-04-05T08:20:07Z", "trace_id": "trace-abc123"},
    {"id": "inv-003", "tool_name": "vmware.query_events", "caller": "RCAAgent", "caller_type": "agent", "input_summary": '{"host_id": "host-33", "hours": 4}', "output_summary": "3 events found", "status": "success", "duration_ms": 280, "dry_run": False, "policy_result": "allow", "timestamp": "2026-04-05T08:20:08Z", "trace_id": "trace-abc123"},
    {"id": "inv-004", "tool_name": "vmware.vm_migrate", "caller": "zhangsan", "caller_type": "user", "input_summary": '{"vm_id": "vm-201", "target_host": "host-34"}', "output_summary": "Denied: approval required", "status": "denied", "duration_ms": 15, "dry_run": False, "policy_result": "approval_required", "timestamp": "2026-04-05T08:25:10Z", "trace_id": "trace-def456"},
    {"id": "inv-005", "tool_name": "change_impact.analyze", "caller": "ChangeCorrelationAgent", "caller_type": "agent", "input_summary": '{"target": "vm-201", "action": "vm_migrate"}', "output_summary": "risk_score: 45, risk_level: medium", "status": "success", "duration_ms": 520, "dry_run": False, "policy_result": "allow", "timestamp": "2026-04-05T08:25:06Z", "trace_id": "trace-ghi789"},
    {"id": "inv-006", "tool_name": "evidence.aggregate", "caller": "EvidenceCollectionAgent", "caller_type": "agent", "input_summary": '{"context": "esxi-node03 CPU alert"}', "output_summary": "Aggregated 4 evidence items", "status": "success", "duration_ms": 180, "dry_run": False, "policy_result": "allow", "timestamp": "2026-04-05T08:21:00Z", "trace_id": "trace-abc123"},
    {"id": "inv-007", "tool_name": "vmware.power_off", "caller": "admin", "caller_type": "user", "input_summary": '{"vm_id": "vm-205"}', "output_summary": "Policy denied: critical operation", "status": "denied", "duration_ms": 8, "dry_run": False, "policy_result": "deny", "timestamp": "2026-04-05T07:10:00Z", "trace_id": "trace-jkl012"},
    {"id": "inv-008", "tool_name": "vmware.create_snapshot", "caller": "Orchestrator", "caller_type": "agent", "input_summary": '{"vm_id": "vm-201", "name": "pre-migrate"}', "output_summary": "Snapshot created: snap-1234", "status": "success", "duration_ms": 3200, "dry_run": False, "policy_result": "allow", "timestamp": "2026-04-05T08:30:00Z", "trace_id": "trace-mno345"},
    {"id": "inv-009", "tool_name": "rag.knowledge_search", "caller": "MemoryAgent", "caller_type": "agent", "input_summary": '{"query": "ESXi host CPU高"}', "output_summary": "Timeout: vector DB slow", "status": "error", "duration_ms": 15000, "dry_run": False, "policy_result": "allow", "timestamp": "2026-04-05T08:35:00Z", "trace_id": "trace-pqr678"},
    {"id": "inv-010", "tool_name": "vmware.get_vcenter_inventory", "caller": "Orchestrator", "caller_type": "agent", "input_summary": '{"datacenter": "DC-01"}', "output_summary": "3 clusters, 12 hosts, 87 VMs", "status": "success", "duration_ms": 680, "dry_run": False, "policy_result": "allow", "timestamp": "2026-04-05T08:40:00Z", "trace_id": "trace-stu901"},
]

# ── Mock manifests (per tool) ────────────────────────────────
_MANIFESTS: dict[str, dict] = {
    "vmware.get_vcenter_inventory": {
        "tool_name": "vmware.get_vcenter_inventory",
        "version": "1.2.0",
        "author": "OpsPilot Core Team",
        "license": "Proprietary",
        "min_platform_version": "0.2.0",
        "dependencies": ["vmware-skill-gateway>=1.0.0"],
        "capabilities": [
            {"name": "list_clusters", "description": "列出所有计算集群", "action_type": "read", "parameters": ["datacenter"]},
            {"name": "list_hosts", "description": "列出所有 ESXi 主机", "action_type": "read", "parameters": ["cluster"]},
            {"name": "list_vms", "description": "列出所有虚拟机", "action_type": "read", "parameters": ["host", "folder"]},
            {"name": "list_datastores", "description": "列出所有数据存储", "action_type": "read", "parameters": ["datacenter"]},
        ],
        "supported_connection_types": ["vcenter"],
        "input_schema": {"type": "object", "properties": {"datacenter": {"type": "string"}, "cluster": {"type": "string"}, "host": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"clusters": {"type": "array"}, "hosts": {"type": "array"}, "vms": {"type": "array"}, "datastores": {"type": "array"}}},
        "changelog": "v1.2.0: 增加数据存储列举\nv1.1.0: 优化分页\nv1.0.0: 初始版本",
    },
    "vmware.vm_migrate": {
        "tool_name": "vmware.vm_migrate",
        "version": "1.2.0",
        "author": "OpsPilot Core Team",
        "license": "Proprietary",
        "min_platform_version": "0.2.0",
        "dependencies": ["vmware-skill-gateway>=1.0.0"],
        "capabilities": [
            {"name": "vmotion", "description": "计算 vMotion 迁移", "action_type": "write", "parameters": ["vm_id", "target_host"]},
            {"name": "storage_vmotion", "description": "存储 vMotion 迁移", "action_type": "write", "parameters": ["vm_id", "target_datastore"]},
        ],
        "supported_connection_types": ["vcenter"],
        "input_schema": {"type": "object", "required": ["vm_id", "target_host"], "properties": {"vm_id": {"type": "string"}, "target_host": {"type": "string"}, "priority": {"type": "string", "enum": ["low", "default", "high"]}}},
        "output_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "status": {"type": "string"}, "duration_seconds": {"type": "number"}}},
        "changelog": "v1.2.0: 增加 priority 参数\nv1.1.0: 支持 Storage vMotion\nv1.0.0: 初始版本",
    },
    "vmware.power_off": {
        "tool_name": "vmware.power_off",
        "version": "1.2.0",
        "author": "OpsPilot Core Team",
        "license": "Proprietary",
        "min_platform_version": "0.2.0",
        "dependencies": ["vmware-skill-gateway>=1.0.0"],
        "capabilities": [
            {"name": "hard_power_off", "description": "强制关闭虚拟机电源", "action_type": "dangerous", "parameters": ["vm_id"]},
        ],
        "supported_connection_types": ["vcenter"],
        "input_schema": {"type": "object", "required": ["vm_id"], "properties": {"vm_id": {"type": "string"}, "force": {"type": "boolean", "default": True}}},
        "output_schema": {"type": "object", "properties": {"status": {"type": "string"}, "powered_off_at": {"type": "string"}}},
        "changelog": "v1.2.0: 增加 force 参数\nv1.0.0: 初始版本",
    },
    "rag.knowledge_search": {
        "tool_name": "rag.knowledge_search",
        "version": "1.0.0",
        "author": "OpsPilot Core Team",
        "license": "Proprietary",
        "min_platform_version": "0.2.0",
        "dependencies": ["rag-service>=1.0.0", "milvus-client>=2.3.0"],
        "capabilities": [
            {"name": "vector_search", "description": "向量相似度检索", "action_type": "read", "parameters": ["query", "top_k", "threshold"]},
            {"name": "hybrid_search", "description": "混合检索（向量+关键词）", "action_type": "read", "parameters": ["query", "filters"]},
        ],
        "supported_connection_types": ["milvus", "elasticsearch"],
        "input_schema": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "default": 5}, "threshold": {"type": "number", "default": 0.7}}},
        "output_schema": {"type": "object", "properties": {"results": {"type": "array"}, "total": {"type": "integer"}}},
        "changelog": "v1.0.0: 初始版本，支持向量检索和混合检索",
    },
}

# ── Mock connection bindings ─────────────────────────────────
_CONNECTIONS: dict[str, list[dict]] = {
    "conn-vcenter-prod": [
        {"connection_id": "conn-vcenter-prod", "connection_name": "vCenter 生产环境", "connection_type": "vcenter", "target_url": "https://vcenter-prod.corp.local:443/sdk", "status": "active", "bound_at": "2026-03-01T10:00:00Z", "last_used": "2026-04-05T08:40:00Z"},
    ],
    "conn-milvus-prod": [
        {"connection_id": "conn-milvus-prod", "connection_name": "Milvus 向量库", "connection_type": "milvus", "target_url": "milvus-prod.corp.local:19530", "status": "error", "bound_at": "2026-03-10T10:00:00Z", "last_used": "2026-04-05T08:35:00Z"},
    ],
}

# ── Mock audit stats (per tool) ──────────────────────────────
def _make_audit_stats(tool_name: str, total: int, success: int, error: int, denied: int, avg_ms: int, p95_ms: int, today: int, week: int) -> dict:
    return {
        "tool_name": tool_name,
        "total_invocations": total,
        "success_count": success,
        "error_count": error,
        "denied_count": denied,
        "avg_duration_ms": avg_ms,
        "p95_duration_ms": p95_ms,
        "last_invoked": "2026-04-05T08:40:00Z",
        "invocations_today": today,
        "invocations_7d": week,
        "top_callers": [
            {"caller": "RCAAgent", "count": int(total * 0.4)},
            {"caller": "Orchestrator", "count": int(total * 0.3)},
            {"caller": "zhangsan", "count": int(total * 0.2)},
        ],
        "daily_trend": [
            {"date": f"2026-03-{30+i:02d}" if 30+i <= 31 else f"2026-04-{30+i-31:02d}", "count": max(5, today + i * 2 - 7), "success": max(4, today + i * 2 - 8)}
            for i in range(7)
        ],
    }


_AUDIT_STATS: dict[str, dict] = {
    "vmware.get_vcenter_inventory": _make_audit_stats("vmware.get_vcenter_inventory", 342, 338, 2, 2, 680, 1200, 12, 82),
    "vmware.get_vm_detail": _make_audit_stats("vmware.get_vm_detail", 1205, 1198, 5, 2, 240, 520, 45, 310),
    "vmware.get_host_detail": _make_audit_stats("vmware.get_host_detail", 890, 884, 4, 2, 320, 680, 32, 220),
    "vmware.query_events": _make_audit_stats("vmware.query_events", 562, 558, 3, 1, 280, 560, 18, 140),
    "vmware.query_metrics": _make_audit_stats("vmware.query_metrics", 780, 772, 5, 3, 450, 980, 28, 195),
    "vmware.vm_migrate": _make_audit_stats("vmware.vm_migrate", 23, 18, 1, 4, 12000, 28000, 2, 8),
    "vmware.create_snapshot": _make_audit_stats("vmware.create_snapshot", 156, 150, 4, 2, 3200, 8500, 5, 38),
    "vmware.power_off": _make_audit_stats("vmware.power_off", 8, 3, 0, 5, 800, 1200, 1, 3),
    "vmware.delete_snapshot": _make_audit_stats("vmware.delete_snapshot", 42, 40, 2, 0, 4500, 12000, 0, 2),
    "change_impact.analyze": _make_audit_stats("change_impact.analyze", 267, 262, 3, 2, 520, 1100, 8, 65),
    "evidence.aggregate": _make_audit_stats("evidence.aggregate", 445, 440, 3, 2, 180, 420, 15, 110),
    "evidence.search": _make_audit_stats("evidence.search", 890, 886, 2, 2, 120, 280, 35, 220),
    "rag.knowledge_search": _make_audit_stats("rag.knowledge_search", 320, 240, 78, 2, 850, 15000, 10, 80),
    "rag.document_ingest": _make_audit_stats("rag.document_ingest", 45, 38, 7, 0, 8500, 45000, 2, 12),
}


# ── Request models ───────────────────────────────────────────

class ToggleToolBody(BaseModel):
    action: str  # "enable" | "disable"


class LifecycleBody(BaseModel):
    action: str  # "retire" | "upgrade" | "rollback" | "validate"
    target_version: Optional[str] = None


class RegisterToolBody(BaseModel):
    name: str
    display_name: str
    description: str
    domain: str
    provider: str
    action_type: str
    risk_level: str
    version: str
    tags: list[str] = []


# ── Routes ───────────────────────────────────────────────────

@router.get("")
async def list_tools(
    domain: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    lifecycle_status: Optional[str] = Query(None),
    version: Optional[str] = Query(None),
):
    tools = list(MOCK_TOOLS_EXTENDED)
    if domain:
        tools = [t for t in tools if t["domain"] == domain]
    if action_type:
        tools = [t for t in tools if t["action_type"] == action_type]
    if risk_level:
        tools = [t for t in tools if t["risk_level"] == risk_level]
    if lifecycle_status:
        tools = [t for t in tools if t["lifecycle_status"] == lifecycle_status]
    if version:
        tools = [t for t in tools if t["version"] == version]
    return make_success(tools)


@router.get("/health")
async def tools_health():
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{TOOL_GATEWAY_URL}/api/v1/tools/health")
            return resp.json()
        except Exception:
            statuses = [
                {"name": t["provider"], "provider": t["provider"], "healthy": t["lifecycle_status"] in ("enabled", "degraded"), "last_check": _now(), "latency_ms": 30 + i * 5, "error_message": None if t["lifecycle_status"] == "enabled" else "Service degraded or unavailable"}
                for i, t in enumerate(MOCK_TOOLS_EXTENDED)
            ]
            seen: set[str] = set()
            unique = []
            for s in statuses:
                if s["name"] not in seen:
                    seen.add(s["name"])
                    unique.append(s)
            return make_success(unique)


@router.get("/gateways")
async def list_gateways():
    return make_success(MOCK_GATEWAYS)


@router.get("/invocations")
async def list_invocations(
    tool_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50),
):
    invocations = list(MOCK_INVOCATIONS)
    if tool_name:
        invocations = [i for i in invocations if i["tool_name"] == tool_name]
    if status:
        invocations = [i for i in invocations if i["status"] == status]
    return make_success(invocations[:limit])


@router.get("/stats")
async def tool_stats():
    tools = MOCK_TOOLS_EXTENDED
    total = len(tools)
    enabled = sum(1 for t in tools if t["lifecycle_status"] == "enabled")
    disabled = sum(1 for t in tools if t["lifecycle_status"] == "disabled")
    draft = sum(1 for t in tools if t["lifecycle_status"] == "draft")
    degraded = sum(1 for t in tools if t["lifecycle_status"] == "degraded")
    read_count = sum(1 for t in tools if t["action_type"] == "read")
    write_count = sum(1 for t in tools if t["action_type"] in ("write", "dangerous"))
    high_risk = sum(1 for t in tools if t["risk_level"] in ("high", "critical"))
    gateways_healthy = sum(1 for g in MOCK_GATEWAYS if g["status"] == "healthy")
    gateways_total = len(MOCK_GATEWAYS)

    domains: dict[str, int] = {}
    for t in tools:
        d = t["domain"]
        domains[d] = domains.get(d, 0) + 1

    versions: dict[str, int] = {}
    for t in tools:
        v = t["version"]
        versions[v] = versions.get(v, 0) + 1

    invocation_success = sum(1 for i in MOCK_INVOCATIONS if i["status"] == "success")
    invocation_total = len(MOCK_INVOCATIONS)

    return make_success({
        "total_tools": total,
        "enabled": enabled,
        "disabled": disabled,
        "draft": draft,
        "degraded": degraded,
        "read_tools": read_count,
        "write_tools": write_count,
        "high_risk_tools": high_risk,
        "gateways_healthy": gateways_healthy,
        "gateways_total": gateways_total,
        "domains": domains,
        "versions": versions,
        "invocation_success_rate": round(invocation_success / max(invocation_total, 1) * 100, 1),
        "total_invocations": invocation_total,
    })


@router.get("/{tool_name}")
async def get_tool(tool_name: str):
    for t in MOCK_TOOLS_EXTENDED:
        if t["name"] == tool_name:
            return make_success(t)
    return make_error(f"Tool {tool_name} not found")


@router.get("/{tool_name}/manifest")
async def get_tool_manifest(tool_name: str):
    manifest = _MANIFESTS.get(tool_name)
    if not manifest:
        base = next((t for t in MOCK_TOOLS_EXTENDED if t["name"] == tool_name), None)
        if not base:
            return make_error(f"Tool {tool_name} not found")
        manifest = {
            "tool_name": tool_name,
            "version": base["version"],
            "author": "OpsPilot Core Team",
            "license": "Proprietary",
            "min_platform_version": "0.2.0",
            "dependencies": [f"{base['provider']}>=1.0.0"] if base["provider"] else [],
            "capabilities": [
                {"name": base["name"].split(".")[-1], "description": base.get("description", ""), "action_type": base["action_type"], "parameters": []},
            ],
            "supported_connection_types": base.get("supported_connection_types", []),
            "input_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "changelog": f"v{base['version']}: 初始版本",
        }
    return make_success(manifest)


@router.get("/{tool_name}/capabilities")
async def get_tool_capabilities(tool_name: str):
    manifest = _MANIFESTS.get(tool_name)
    if manifest:
        return make_success(manifest["capabilities"])
    base = next((t for t in MOCK_TOOLS_EXTENDED if t["name"] == tool_name), None)
    if not base:
        return make_error(f"Tool {tool_name} not found")
    return make_success([
        {"name": base["name"].split(".")[-1], "description": base.get("description", ""), "action_type": base["action_type"], "parameters": []},
    ])


@router.get("/{tool_name}/connections")
async def get_tool_connections(tool_name: str):
    base = next((t for t in MOCK_TOOLS_EXTENDED if t["name"] == tool_name), None)
    if not base:
        return make_error(f"Tool {tool_name} not found")
    ref = base.get("connection_ref")
    if not ref:
        return make_success([])
    return make_success(_CONNECTIONS.get(ref, []))


@router.get("/{tool_name}/audit-stats")
async def get_tool_audit_stats(tool_name: str):
    stats = _AUDIT_STATS.get(tool_name)
    if not stats:
        return make_success({
            "tool_name": tool_name, "total_invocations": 0, "success_count": 0,
            "error_count": 0, "denied_count": 0, "avg_duration_ms": 0,
            "p95_duration_ms": 0, "last_invoked": None, "invocations_today": 0,
            "invocations_7d": 0, "top_callers": [], "daily_trend": [],
        })
    return make_success(stats)


@router.post("/{tool_name}/health-check")
async def run_health_check(tool_name: str):
    base = next((t for t in MOCK_TOOLS_EXTENDED if t["name"] == tool_name), None)
    if not base:
        return make_error(f"Tool {tool_name} not found")

    healthy = base["lifecycle_status"] in ("enabled", "ready")
    checks = [
        {"name": "gateway_reachable", "passed": base["lifecycle_status"] != "draft", "message": "网关可达" if base["lifecycle_status"] != "draft" else "网关未部署"},
        {"name": "schema_valid", "passed": True, "message": "输入/输出 schema 校验通过"},
        {"name": "connection_active", "passed": bool(base.get("connection_ref")), "message": f"连接 {base.get('connection_ref', 'N/A')} 活跃" if base.get("connection_ref") else "无绑定连接"},
        {"name": "latency_acceptable", "passed": healthy, "message": f"响应延迟 {45 if healthy else 0}ms（阈值 1000ms）"},
    ]
    return make_success({
        "tool_name": tool_name,
        "healthy": healthy and all(c["passed"] for c in checks),
        "latency_ms": 45 if healthy else 0,
        "checked_at": _now(),
        "checks": checks,
    })


@router.patch("/{tool_name}/toggle")
async def toggle_tool(tool_name: str, body: ToggleToolBody):
    for t in MOCK_TOOLS_EXTENDED:
        if t["name"] == tool_name:
            if body.action == "enable":
                t["lifecycle_status"] = "enabled"
            elif body.action == "disable":
                t["lifecycle_status"] = "disabled"
            t["updated_at"] = _now()
            return make_success(t)
    return make_error(f"Tool {tool_name} not found")


@router.patch("/{tool_name}/lifecycle")
async def lifecycle_action(tool_name: str, body: LifecycleBody):
    for t in MOCK_TOOLS_EXTENDED:
        if t["name"] == tool_name:
            if body.action == "retire":
                t["lifecycle_status"] = "retired"
            elif body.action == "upgrade" and body.target_version:
                t["lifecycle_status"] = "enabled"
                t["version"] = body.target_version
            elif body.action == "rollback":
                t["lifecycle_status"] = "enabled"
            elif body.action == "validate":
                t["lifecycle_status"] = "ready"
            t["updated_at"] = _now()
            return make_success(t)
    return make_error(f"Tool {tool_name} not found")


@router.post("/register")
async def register_tool(body: RegisterToolBody):
    new_tool = {
        "name": body.name,
        "display_name": body.display_name,
        "description": body.description,
        "category": body.domain,
        "domain": body.domain,
        "provider": body.provider,
        "action_type": body.action_type,
        "risk_level": body.risk_level,
        "approval_required": body.risk_level in ("high", "critical"),
        "timeout_seconds": 60,
        "idempotent": body.action_type == "read",
        "version": body.version,
        "tags": body.tags,
        "lifecycle_status": "draft",
        "connection_ref": None,
        "supported_connection_types": [],
        "registered_at": _now(),
        "updated_at": _now(),
    }
    MOCK_TOOLS_EXTENDED.append(new_tool)
    return make_success(new_tool)
