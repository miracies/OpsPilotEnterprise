"""BFF router: Upgrade management."""
from __future__ import annotations
from fastapi import APIRouter
from opspilot_schema.envelope import make_success

router = APIRouter(tags=["upgrades"])

_PACKAGES = [
    {"id": "PKG-001", "version": "0.2.0", "release_name": "Arctic Fox", "description": "OpsPilot P1 版本，新增审批中心、知识管理、策略管理等模块。", "changelog": ["新增审批中心、值班通知、审计中心", "新增知识管理与知识导入流程", "新增策略管理（OPA 接口预留）", "新增 SubAgent 运行视图", "UI 全面 polish"], "status": "ready", "target": "all-services", "package_size_mb": 128.4, "requires_restart": True, "requires_approval": True, "risk_level": "low", "released_at": "2026-04-05T00:00:00Z", "deployed_at": None, "deployed_by": None, "rollback_version": "0.1.0", "environment": "production"},
    {"id": "PKG-002", "version": "0.1.1", "release_name": "Patch Hotfix", "description": "修复 P0 中 evidence-aggregator 高负载下连接超时问题。", "changelog": ["修复 evidence-aggregator httpx 连接池配置", "增加 BFF /health 接口超时重试"], "status": "deployed", "target": "api-bff", "package_size_mb": 8.2, "requires_restart": False, "requires_approval": False, "risk_level": "low", "released_at": "2026-04-02T10:00:00Z", "deployed_at": "2026-04-02T14:30:00Z", "deployed_by": "ops-lead", "rollback_version": "0.1.0", "environment": "production"},
    {"id": "PKG-003", "version": "0.3.0-beta", "release_name": "Blue Glacier", "description": "P2 Beta，接入真实 VMware vCenter SDK，移除 mock 层。", "changelog": ["接入 PyVmomi vCenter SDK", "实现真实 VMware 指标查询"], "status": "available", "target": "vmware-skill-gateway", "package_size_mb": 54.8, "requires_restart": True, "requires_approval": True, "risk_level": "medium", "released_at": "2026-04-04T08:00:00Z", "deployed_at": None, "deployed_by": None, "rollback_version": "0.2.0", "environment": "staging"},
]

_DEPLOYMENTS = [
    {"id": "DEP-001", "package_id": "PKG-002", "package_version": "0.1.1", "status": "deployed", "environment": "production", "deployed_by": "ops-lead", "started_at": "2026-04-02T14:28:00Z", "completed_at": "2026-04-02T14:30:00Z", "log_summary": ["拉取镜像 opspilot/api-bff:0.1.1", "健康检查通过", "滚动更新完成，0 中断"], "rollback_available": True},
]


@router.get("/upgrades")
async def list_upgrade_packages(environment: str | None = None):
    data = _PACKAGES if not environment else [p for p in _PACKAGES if p["environment"] == environment]
    return make_success({"items": data, "total": len(data)})


@router.get("/upgrades/{package_id}")
async def get_upgrade_package(package_id: str):
    item = next((p for p in _PACKAGES if p["id"] == package_id), None)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Package not found")
    return make_success(item)


@router.get("/upgrades/deployments/history")
async def list_deployment_history():
    return make_success({"items": _DEPLOYMENTS})


@router.post("/upgrades/{package_id}/deploy")
async def deploy_package(package_id: str):
    return make_success({"package_id": package_id, "status": "deploying", "message": "Deployment started (mock)"})
