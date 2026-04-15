from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.vcenter_service import VCenterService
from opspilot_schema.envelope import make_error, make_success

router = APIRouter(prefix="/execute", tags=["execute"])


class CreateSnapshotBody(BaseModel):
    vm_id: str
    name: str = Field(..., description="Snapshot display name")
    dry_run: bool = False
    connection: dict | None = None


class VmMigrateBody(BaseModel):
    vm_id: str
    target_host_id: str
    dry_run: bool = False
    connection: dict | None = None


class VmIdOnlyBody(BaseModel):
    vm_id: str
    dry_run: bool = False
    connection: dict | None = None


class HostIdOnlyBody(BaseModel):
    host_id: str
    dry_run: bool = False
    connection: dict | None = None


def _task_response(operation: str, vm_id: str) -> dict:
    tid = f"task-{uuid.uuid4().hex[:12]}"
    return {
        "task_id": tid,
        "status": "running",
        "operation": operation,
        "vm_id": vm_id,
        "message": f"Task queued for {operation}",
    }


@router.post("/create_snapshot")
async def create_snapshot(body: CreateSnapshotBody) -> dict:
    try:
        if body.dry_run:
            return make_success(
                {
                    "dry_run": True,
                    "vm_id": body.vm_id,
                    "name": body.name,
                    "action": "create_snapshot",
                }
            )
        result = await VCenterService(body.connection).create_snapshot(body.vm_id, body.name)
        return make_success(result)
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.post("/vm_migrate")
def vm_migrate(body: VmMigrateBody) -> dict:
    if body.dry_run:
        return make_success(
            {
                "dry_run": True,
                "vm_id": body.vm_id,
                "target_host_id": body.target_host_id,
                "compatibility": "unknown",
                "estimated_downtime_sec": 0,
                "warnings": ["dry-run only; migration execution path is not implemented in this release"],
            }
        )
    return make_error("vm_migrate execution is not implemented; use approval workflow")


@router.post("/vm_power_on")
async def vm_power_on(body: VmIdOnlyBody) -> dict:
    try:
        if body.dry_run:
            return make_success({"dry_run": True, "vm_id": body.vm_id, "action": "vm_power_on"})
        result = await VCenterService(body.connection).vm_power_on(body.vm_id)
        return make_success(result)
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.post("/vm_power_off")
async def vm_power_off(body: VmIdOnlyBody) -> dict:
    try:
        if body.dry_run:
            return make_success({"dry_run": True, "vm_id": body.vm_id, "action": "vm_power_off"})
        result = await VCenterService(body.connection).vm_power_off(body.vm_id)
        return make_success(result)
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.post("/vm_guest_restart")
async def vm_guest_restart(body: VmIdOnlyBody) -> dict:
    try:
        if body.dry_run:
            return make_success({"dry_run": True, "vm_id": body.vm_id, "action": "vm_guest_restart"})
        result = await VCenterService(body.connection).vm_guest_restart(body.vm_id)
        return make_success(result)
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@router.post("/host_restart")
async def host_restart(body: HostIdOnlyBody) -> dict:
    try:
        if body.dry_run:
            return make_success({"dry_run": True, "host_id": body.host_id, "action": "host_restart"})
        result = await VCenterService(body.connection).host_restart(body.host_id)
        return make_success(result)
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))
