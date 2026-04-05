"""BFF router: Case archive."""
from __future__ import annotations
from fastapi import APIRouter
from opspilot_schema.envelope import make_success

router = APIRouter(tags=["cases"])

_CASES = [
    {"id": "CASE-20260320", "title": "Java GC 风暴导致主机 CPU 飙升（已结）", "summary": "2026-03-20 app-server-03 Java 进程 Full GC 频率过高，导致 esxi-node02 CPU 利用率飙升至 96%。", "category": "performance", "status": "archived", "severity": "high", "tags": ["jvm", "cpu", "gc"], "incident_refs": ["INC-20260320-001"], "root_cause_summary": "JVM 堆内存设置过小，频繁触发 Full GC。", "resolution_summary": "扩展 JVM 堆内存至 4GB，启用 G1GC。", "lessons_learned": "JVM 参数纳入标准化部署模板。", "author": "zhangsan", "created_at": "2026-03-20T18:00:00Z", "archived_at": "2026-03-21T09:00:00Z", "similarity_score": 0.82, "hit_count": 3, "knowledge_refs": ["KB-001"]},
    {"id": "CASE-20260315", "title": "NFS 存储快照堆积导致容量告警", "summary": "2026-03-15 ds-nfs-staging01 快照未按策略清理，导致可用空间降至 5%。", "category": "capacity", "status": "archived", "severity": "medium", "tags": ["nfs", "snapshot", "capacity"], "incident_refs": ["INC-20260315-003"], "root_cause_summary": "快照保留策略配置错误，7 天保留期未生效。", "resolution_summary": "修正策略，批量删除过期快照共 24 个，释放 1.2TB。", "lessons_learned": "容量预警应在 15% 时提前处理。", "author": "lisi", "created_at": "2026-03-15T14:00:00Z", "archived_at": "2026-03-16T10:00:00Z", "similarity_score": 0.91, "hit_count": 5, "knowledge_refs": ["KB-003"]},
    {"id": "CASE-20260228", "title": "esxi-node05 HA 切换后 VM 启动顺序异常", "summary": "2026-02-28 HA 切换后部分 VM 按错误顺序启动，导致连接超时。", "category": "availability", "status": "archived", "severity": "critical", "tags": ["ha", "vmware", "boot-order"], "incident_refs": ["INC-20260228-002"], "root_cause_summary": "VM 启动顺序组未正确配置。", "resolution_summary": "重新配置 VM 启动顺序组，数据库延迟 120s 后启动应用层。", "lessons_learned": "HA 环境下必须明确定义 VM 启动顺序。", "author": "wangwu", "created_at": "2026-02-28T22:00:00Z", "archived_at": "2026-03-01T09:00:00Z", "similarity_score": None, "hit_count": 2, "knowledge_refs": ["KB-002"]},
]


@router.get("/cases")
async def list_cases(category: str | None = None, status: str | None = None):
    data = _CASES
    if category:
        data = [c for c in data if c["category"] == category]
    if status:
        data = [c for c in data if c["status"] == status]
    return make_success({"items": data, "total": len(data)})


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    item = next((c for c in _CASES if c["id"] == case_id), None)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Case not found")
    return make_success(item)
