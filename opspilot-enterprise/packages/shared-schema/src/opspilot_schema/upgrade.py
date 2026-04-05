from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class UpgradePackage(BaseModel):
    id: str
    version: str
    release_name: str
    description: str
    changelog: list[str] = []
    status: str
    target: str
    package_size_mb: float
    requires_restart: bool
    requires_approval: bool
    risk_level: str
    released_at: str
    deployed_at: Optional[str] = None
    deployed_by: Optional[str] = None
    rollback_version: Optional[str] = None
    environment: str


class UpgradeDeploymentRecord(BaseModel):
    id: str
    package_id: str
    package_version: str
    status: str
    environment: str
    deployed_by: str
    started_at: str
    completed_at: Optional[str] = None
    log_summary: list[str] = []
    rollback_available: bool = False
