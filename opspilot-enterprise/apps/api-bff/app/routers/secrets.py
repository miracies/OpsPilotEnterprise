"""Secret management endpoints — CRUD + reveal."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from opspilot_schema.envelope import make_success, make_error
from app.services import secret_store

router = APIRouter(prefix="/secrets", tags=["secrets"])


# ── Request models ────────────────────────────────────────────

class CreateSecretBody(BaseModel):
    name: str
    display_name: str = ""
    secret_type: str = "generic"
    value: str
    description: str = ""
    tags: list[str] = []


class UpdateSecretBody(BaseModel):
    display_name: Optional[str] = None
    value: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None


class RevealBody(BaseModel):
    """Require explicit confirmation to reveal secret value."""
    confirm: bool = False


class ResolveRefBody(BaseModel):
    credential_ref: str


# ── Routes ────────────────────────────────────────────────────

@router.get("")
async def list_secrets_route():
    secrets = await secret_store.list_secrets()
    return make_success(secrets)


@router.get("/stats")
async def secret_stats():
    secrets = await secret_store.list_secrets()
    total = len(secrets)
    by_type: dict[str, int] = {}
    for s in secrets:
        t = s["secret_type"]
        by_type[t] = by_type.get(t, 0) + 1
    return make_success({"total": total, "by_type": by_type})


@router.post("")
async def create_secret_route(body: CreateSecretBody):
    try:
        meta = await secret_store.create_secret(
            name=body.name,
            plaintext_value=body.value,
            display_name=body.display_name,
            secret_type=body.secret_type,
            description=body.description,
            tags=body.tags,
        )
        return make_success(meta)
    except Exception as exc:
        if "UNIQUE constraint" in str(exc):
            return make_error(f"密钥名称 '{body.name}' 已存在")
        return make_error(str(exc))


@router.get("/{name}")
async def get_secret_route(name: str):
    meta = await secret_store.get_secret_meta(name)
    if not meta:
        return make_error(f"密钥 '{name}' 不存在")
    return make_success(meta)


@router.put("/{name}")
async def update_secret_route(name: str, body: UpdateSecretBody):
    result = await secret_store.update_secret(
        name=name,
        plaintext_value=body.value,
        display_name=body.display_name,
        description=body.description,
        tags=body.tags,
    )
    if not result:
        return make_error(f"密钥 '{name}' 不存在")
    return make_success(result)


@router.delete("/{name}")
async def delete_secret_route(name: str):
    deleted = await secret_store.delete_secret(name)
    if not deleted:
        return make_error(f"密钥 '{name}' 不存在")
    return make_success({"deleted": True, "name": name})


@router.post("/{name}/reveal")
async def reveal_secret_route(name: str, body: RevealBody):
    """Decrypt and return the plaintext. Requires confirm=true."""
    if not body.confirm:
        return make_error("请确认解密操作 (confirm: true)")
    value = await secret_store.reveal_secret(name)
    if value is None:
        return make_error(f"密钥 '{name}' 不存在")
    return make_success({"name": name, "value": value})


@router.post("/resolve")
async def resolve_ref_route(body: ResolveRefBody):
    """Resolve a credential_ref to its credentials dict (for internal use)."""
    creds = await secret_store.resolve_credential(body.credential_ref)
    if creds is None:
        return make_error(f"无法解析凭据引用: {body.credential_ref}")
    return make_success(creds)
