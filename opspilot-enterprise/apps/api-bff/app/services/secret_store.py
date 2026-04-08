"""
Self-hosted secret store — AES-256-GCM encryption + SQLite persistence.

Every secret is encrypted with a unique (salt, iv) pair.
The encryption key is derived from a master passphrase via PBKDF2-HMAC-SHA256.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── AES-256-GCM via cryptography ─────────────────────────────

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KDF_ITERATIONS = 480_000
_SALT_BYTES = 16
_IV_BYTES = 12
_KEY_BYTES = 32  # AES-256

_MASTER_PASSPHRASE: str = os.environ.get(
    "OPSPILOT_SECRET_KEY", "opspilot-dev-default-key-change-me"
)

DB_PATH: Path = Path(
    os.environ.get("OPSPILOT_SECRET_DB", "data/secrets.db")
)


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode(), salt, _KDF_ITERATIONS, dklen=_KEY_BYTES
    )


def _encrypt(plaintext: str) -> tuple[bytes, bytes, bytes]:
    """Return (encrypted_data, iv, salt)."""
    salt = os.urandom(_SALT_BYTES)
    iv = os.urandom(_IV_BYTES)
    key = _derive_key(_MASTER_PASSPHRASE, salt)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(iv, plaintext.encode(), None)
    return ct, iv, salt


def _decrypt(ct: bytes, iv: bytes, salt: bytes) -> str:
    key = _derive_key(_MASTER_PASSPHRASE, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ct, None).decode()


# ── SQLite helpers ────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS secrets (
    id            TEXT PRIMARY KEY,
    name          TEXT UNIQUE NOT NULL,
    display_name  TEXT NOT NULL DEFAULT '',
    secret_type   TEXT NOT NULL DEFAULT 'generic',
    encrypted_val BLOB NOT NULL,
    iv            BLOB NOT NULL,
    salt          BLOB NOT NULL,
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
    conn.commit()
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_meta(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a DB row to a metadata dict (no decrypted value)."""
    return {
        "id": row["id"],
        "name": row["name"],
        "display_name": row["display_name"],
        "secret_type": row["secret_type"],
        "description": row["description"],
        "tags": json.loads(row["tags"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ── Public async API (wraps sync sqlite3 via to_thread) ──────

async def init_db() -> None:
    """Ensure the DB and table exist (called at app startup)."""
    await asyncio.to_thread(_get_conn)


async def list_secrets() -> list[dict[str, Any]]:
    def _run():
        conn = _get_conn()
        rows = conn.execute("SELECT * FROM secrets ORDER BY updated_at DESC").fetchall()
        conn.close()
        return [_row_to_meta(r) for r in rows]
    return await asyncio.to_thread(_run)


async def get_secret_meta(name: str) -> dict[str, Any] | None:
    def _run():
        conn = _get_conn()
        row = conn.execute("SELECT * FROM secrets WHERE name = ?", (name,)).fetchone()
        conn.close()
        return _row_to_meta(row) if row else None
    return await asyncio.to_thread(_run)


async def create_secret(
    name: str,
    plaintext_value: str,
    display_name: str = "",
    secret_type: str = "generic",
    description: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    def _run():
        ct, iv, salt = _encrypt(plaintext_value)
        now = _now()
        sid = f"sec-{uuid.uuid4().hex[:8]}"
        conn = _get_conn()
        conn.execute(
            "INSERT INTO secrets (id, name, display_name, secret_type, encrypted_val, iv, salt, description, tags, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, name, display_name or name, secret_type, ct, iv, salt, description, json.dumps(tags or []), now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM secrets WHERE id = ?", (sid,)).fetchone()
        conn.close()
        return _row_to_meta(row)
    return await asyncio.to_thread(_run)


async def update_secret(
    name: str,
    plaintext_value: str | None = None,
    display_name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any] | None:
    def _run():
        conn = _get_conn()
        row = conn.execute("SELECT * FROM secrets WHERE name = ?", (name,)).fetchone()
        if not row:
            conn.close()
            return None

        sets: list[str] = []
        params: list[Any] = []

        if plaintext_value is not None:
            ct, iv, salt = _encrypt(plaintext_value)
            sets += ["encrypted_val = ?", "iv = ?", "salt = ?"]
            params += [ct, iv, salt]

        if display_name is not None:
            sets.append("display_name = ?")
            params.append(display_name)

        if description is not None:
            sets.append("description = ?")
            params.append(description)

        if tags is not None:
            sets.append("tags = ?")
            params.append(json.dumps(tags))

        if sets:
            sets.append("updated_at = ?")
            params.append(_now())
            params.append(name)
            conn.execute(f"UPDATE secrets SET {', '.join(sets)} WHERE name = ?", params)
            conn.commit()

        row = conn.execute("SELECT * FROM secrets WHERE name = ?", (name,)).fetchone()
        conn.close()
        return _row_to_meta(row) if row else None
    return await asyncio.to_thread(_run)


async def delete_secret(name: str) -> bool:
    def _run():
        conn = _get_conn()
        cur = conn.execute("DELETE FROM secrets WHERE name = ?", (name,))
        conn.commit()
        conn.close()
        return cur.rowcount > 0
    return await asyncio.to_thread(_run)


async def reveal_secret(name: str) -> str | None:
    """Decrypt and return the plaintext value of a secret."""
    def _run():
        conn = _get_conn()
        row = conn.execute("SELECT encrypted_val, iv, salt FROM secrets WHERE name = ?", (name,)).fetchone()
        conn.close()
        if not row:
            return None
        return _decrypt(bytes(row["encrypted_val"]), bytes(row["iv"]), bytes(row["salt"]))
    return await asyncio.to_thread(_run)


async def resolve_credential(ref: str) -> dict[str, str] | None:
    """
    Resolve a credential_ref to a dict of credentials.

    Supported formats:
      - secret://<name>  → look up in local secret store
      - vault://...      → not implemented (placeholder)

    The stored plaintext is expected to be JSON, e.g.:
      {"username": "admin", "password": "***"}
    or:
      {"api_key": "sk-***"}

    Returns the parsed dict, or None if not found / not resolvable.
    """
    if ref.startswith("secret://"):
        secret_name = ref[len("secret://"):]
        raw = await reveal_secret(secret_name)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"value": raw}
    return None
