from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field
from opspilot_schema.envelope import make_error, make_success

from app import mock_data

router = APIRouter(prefix="/execute", tags=["execute"])


class CreateSnapshotBody(BaseModel):
    vm_id: str
    name: str = Field(..., description="Snapshot display name")


class VmMigrateBody(BaseModel):
    vm_id: str
    target_host_id: str
    dry_run: bool = False


class VmIdOnlyBody(BaseModel):
    vm_id: str


def _task_response(operation: str, vm_id: str) -> dict:
    tid = f"task-{uuid.uuid4().hex[:12]}"
    return {
        "task_id": tid,
        "status": "running",
        "operation": operation,
        "vm_id": vm_id,
        "message": f"Mock async task queued for {operation}",
    }


@router.post("/create_snapshot")
def create_snapshot(body: CreateSnapshotBody) -> dict:
    if body.vm_id not in mock_data.VM_BY_ID:
        return make_error(f"Virtual machine not found: {body.vm_id}")
    return make_success(
        {
            "task_id": f"snap-task-{uuid.uuid4().hex[:10]}",
            "status": "queued",
            "vm_id": body.vm_id,
            "snapshot_name": body.name,
        }
    )


@router.post("/vm_migrate")
def vm_migrate(body: VmMigrateBody) -> dict:
    if body.vm_id not in mock_data.VM_BY_ID:
        return make_error(f"Virtual machine not found: {body.vm_id}")
    if body.target_host_id not in mock_data.HOST_BY_ID:
        return make_error(f"Target host not found: {body.target_host_id}")
    vm = mock_data.VM_BY_ID[body.vm_id]
    target = mock_data.HOST_BY_ID[body.target_host_id]
    if body.dry_run:
        return make_success(
            {
                "dry_run": True,
                "vm_id": body.vm_id,
                "vm_name": vm["name"],
                "source_host_id": vm["host_id"],
                "target_host_id": body.target_host_id,
                "target_host_name": target["name"],
                "compatibility": "compatible",
                "estimated_downtime_sec": 0,
                "warnings": [],
            }
        )
    return make_success(_task_response("RelocateVM_Task", body.vm_id))


@router.post("/vm_power_on")
def vm_power_on(body: VmIdOnlyBody) -> dict:
    if body.vm_id not in mock_data.VM_BY_ID:
        return make_error(f"Virtual machine not found: {body.vm_id}")
    return make_success(_task_response("PowerOnVM_Task", body.vm_id))


@router.post("/vm_power_off")
def vm_power_off(body: VmIdOnlyBody) -> dict:
    if body.vm_id not in mock_data.VM_BY_ID:
        return make_error(f"Virtual machine not found: {body.vm_id}")
    return make_success(_task_response("PowerOffVM_Task", body.vm_id))


@router.post("/vm_guest_restart")
def vm_guest_restart(body: VmIdOnlyBody) -> dict:
    if body.vm_id not in mock_data.VM_BY_ID:
        return make_error(f"Virtual machine not found: {body.vm_id}")
    return make_success(_task_response("RestartGuest_Task", body.vm_id))
