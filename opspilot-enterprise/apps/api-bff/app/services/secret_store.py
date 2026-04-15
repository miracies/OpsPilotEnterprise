"""Simple SQLite-backed secret store used by API BFF."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

_LOCK = asyncio.Lock()
UTC = timezone.utc


def _now() -> str:
    return datetime.now(UTC).isoformat()


_DEFAULT_DB_PATH = Path(__file__).resolve().parents[4] / "data" / "secrets.db"
DB_PATH: Path = Path(os.environ.get("OPSPILOT_SECRET_DB", str(_DEFAULT_DB_PATH)))

_DDL = """
CREATE TABLE IF NOT EXISTS secrets (
    id            TEXT PRIMARY KEY,
    name          TEXT UNIQUE NOT NULL,
    display_name  TEXT NOT NULL DEFAULT '',
    secret_type   TEXT NOT NULL DEFAULT 'generic',
    plain_val     TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    tags          TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute(_DDL)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(secrets)").fetchall()]
    if "plain_val" not in cols:
        conn.execute("ALTER TABLE secrets ADD COLUMN plain_val TEXT NOT NULL DEFAULT ''")
        conn.commit()
    conn.commit()
    return conn


def _table_columns(conn: sqlite3.Connection) -> set[str]:
    return {r["name"] for r in conn.execute("PRAGMA table_info(secrets)").fetchall()}


def _row_to_meta(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "display_name": row["display_name"],
        "secret_type": row["secret_type"],
        "description": row["description"],
        "tags": json.loads(row["tags"] or "[]"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


_SEED_SECRETS: list[dict[str, str]] = [
    {
        "name": "vcenter-prod",
        "display_name": "vCenter 生产环境凭据",
        "secret_type": "vcenter",
        "value": json.dumps({"username": "administrator@vsphere.local", "password": "VMware1!"}, ensure_ascii=False),
        "description": "vCenter production credentials",
    },
    {
        "name": "vcenter-dr",
        "display_name": "vCenter 灾备环境凭据",
        "secret_type": "vcenter",
        "value": json.dumps({"username": "administrator@vsphere.local", "password": "ChangeMe-DR!"}, ensure_ascii=False),
        "description": "vCenter DR credentials",
    },
    {
        "name": "k8s-prod",
        "display_name": "K8s 生产集群 kubeconfig",
        "secret_type": "kubeconfig",
        "value": os.environ.get("K8S_KUBECONFIG_PATH", r"C:\Users\mirac\.kube\config"),
        "description": "Kubernetes production kubeconfig path",
    },
]


async def init_db() -> None:
    async with _LOCK:
        conn = _get_conn()
        try:
            cols = _table_columns(conn)
            for item in _SEED_SECRETS:
                exists = conn.execute("SELECT 1 FROM secrets WHERE name = ?", (item["name"],)).fetchone()
                if exists:
                    continue
                now = _now()
                payload: dict[str, Any] = {
                    "id": f"sec-{uuid.uuid4().hex[:8]}",
                    "name": item["name"],
                    "display_name": item["display_name"],
                    "secret_type": item["secret_type"],
                    "plain_val": item["value"],
                    "description": item["description"],
                    "tags": json.dumps(["seed"]),
                    "created_at": now,
                    "updated_at": now,
                }
                if "encrypted_val" in cols:
                    payload["encrypted_val"] = b"seed"
                if "iv" in cols:
                    payload["iv"] = b"seed"
                if "salt" in cols:
                    payload["salt"] = b"seed"
                keys = [k for k in payload.keys() if k in cols]
                q = f"INSERT INTO secrets({','.join(keys)}) VALUES({','.join(['?'] * len(keys))})"
                conn.execute(q, tuple(payload[k] for k in keys))
            conn.commit()
        finally:
            conn.close()


async def list_secrets() -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM secrets ORDER BY updated_at DESC").fetchall()
        return [_row_to_meta(r) for r in rows]
    finally:
        conn.close()


async def get_secret_meta(name: str) -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM secrets WHERE name = ?", (name,)).fetchone()
        return _row_to_meta(row) if row else None
    finally:
        conn.close()


async def create_secret(
    name: str,
    plaintext_value: str,
    display_name: str = "",
    secret_type: str = "generic",
    description: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    async with _LOCK:
        conn = _get_conn()
        try:
            now = _now()
            sid = f"sec-{uuid.uuid4().hex[:8]}"
            cols = _table_columns(conn)
            payload: dict[str, Any] = {
                "id": sid,
                "name": name,
                "display_name": display_name,
                "secret_type": secret_type,
                "plain_val": plaintext_value,
                "description": description,
                "tags": json.dumps(tags or []),
                "created_at": now,
                "updated_at": now,
            }
            if "encrypted_val" in cols:
                payload["encrypted_val"] = b"user"
            if "iv" in cols:
                payload["iv"] = b"user"
            if "salt" in cols:
                payload["salt"] = b"user"
            keys = [k for k in payload.keys() if k in cols]
            q = f"INSERT INTO secrets({','.join(keys)}) VALUES({','.join(['?'] * len(keys))})"
            conn.execute(q, tuple(payload[k] for k in keys))
            conn.commit()
            row = conn.execute("SELECT * FROM secrets WHERE name = ?", (name,)).fetchone()
            return _row_to_meta(row)
        finally:
            conn.close()


async def update_secret(
    name: str,
    plaintext_value: str | None = None,
    display_name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any] | None:
    async with _LOCK:
        conn = _get_conn()
        try:
            row = conn.execute("SELECT * FROM secrets WHERE name = ?", (name,)).fetchone()
            if not row:
                return None

            sets: list[str] = []
            params: list[Any] = []
            if plaintext_value is not None:
                sets.append("plain_val = ?")
                params.append(plaintext_value)
                cols = _table_columns(conn)
                if "encrypted_val" in cols:
                    sets.append("encrypted_val = ?")
                    params.append(b"upd")
                if "iv" in cols:
                    sets.append("iv = ?")
                    params.append(b"upd")
                if "salt" in cols:
                    sets.append("salt = ?")
                    params.append(b"upd")
            if display_name is not None:
                sets.append("display_name = ?")
                params.append(display_name)
            if description is not None:
                sets.append("description = ?")
                params.append(description)
            if tags is not None:
                sets.append("tags = ?")
                params.append(json.dumps(tags))
            sets.append("updated_at = ?")
            params.append(_now())
            params.append(name)

            conn.execute(f"UPDATE secrets SET {', '.join(sets)} WHERE name = ?", params)
            conn.commit()
            row2 = conn.execute("SELECT * FROM secrets WHERE name = ?", (name,)).fetchone()
            return _row_to_meta(row2)
        finally:
            conn.close()


async def delete_secret(name: str) -> bool:
    async with _LOCK:
        conn = _get_conn()
        try:
            cur = conn.execute("DELETE FROM secrets WHERE name = ?", (name,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


async def reveal_secret(name: str) -> str | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT plain_val FROM secrets WHERE name = ?", (name,)).fetchone()
        return row["plain_val"] if row else None
    finally:
        conn.close()


def parse_secret_payload(secret_type: str, raw: str) -> dict[str, Any]:
    if secret_type == "vcenter":
        parsed = json.loads(raw)
        username = parsed.get("username")
        password = parsed.get("password")
        if not username or not password:
            raise ValueError("vcenter secret requires username/password")
        return parsed
    if secret_type == "kubeconfig":
        try:
            parsed = yaml.safe_load(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        # allow kubeconfig path string
        if raw.strip():
            return {"kubeconfig_path": raw.strip()}
        raise ValueError("invalid kubeconfig secret payload")
    if secret_type == "generic":
        return {"value": raw}
    try:
        return json.loads(raw)
    except Exception:
        return {"value": raw}


async def get_secret_payload(name: str) -> dict[str, Any] | None:
    val = await reveal_secret(name)
    if val is None:
        return None
    meta = await get_secret_meta(name)
    if not meta:
        return None
    return parse_secret_payload(meta["secret_type"], val)


async def resolve_credential(credential_ref: str) -> dict[str, Any] | None:
    if not credential_ref:
        return None
    if credential_ref.startswith("secret://"):
        secret_name = credential_ref[len("secret://") :]
        try:
            payload = await get_secret_payload(secret_name)
            if payload is not None:
                return payload
        except Exception:
            payload = None
        if secret_name == "vcenter-prod":
            return {
                "username": os.environ.get("VCENTER_USERNAME", "administrator@vsphere.local"),
                "password": os.environ.get("VCENTER_PASSWORD", "VMware1!"),
            }
        return None
    return None
