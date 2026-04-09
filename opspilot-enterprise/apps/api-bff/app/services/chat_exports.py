from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

EXPORT_TTL_SECONDS = 600
EXPORT_MIME_TYPE = "text/csv; charset=utf-8"


@dataclass
class ExportRecord:
    export_id: str
    file_path: Path
    file_name: str
    session_id: str | None
    created_at: datetime
    expires_at: datetime
    mime_type: str = EXPORT_MIME_TYPE

    def to_api_dict(self, download_url: str) -> dict:
        size = self.file_path.stat().st_size if self.file_path.exists() else 0
        return {
            "export_id": self.export_id,
            "file_name": self.file_name,
            "download_url": download_url,
            "expires_at": self.expires_at.isoformat(),
            "file_size_bytes": size,
            "mime_type": self.mime_type,
        }


_exports: dict[str, ExportRecord] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(record: ExportRecord) -> bool:
    return record.expires_at <= _now()


def cleanup_expired_exports() -> None:
    expired_ids = [export_id for export_id, rec in _exports.items() if _is_expired(rec)]
    for export_id in expired_ids:
        rec = _exports.pop(export_id, None)
        if rec and rec.file_path.exists():
            try:
                rec.file_path.unlink()
            except OSError:
                pass


def register_export(file_path: Path, file_name: str, session_id: str | None = None) -> ExportRecord:
    cleanup_expired_exports()
    export_id = f"exp-{uuid.uuid4().hex[:12]}"
    created_at = _now()
    record = ExportRecord(
        export_id=export_id,
        file_path=file_path,
        file_name=file_name,
        session_id=session_id,
        created_at=created_at,
        expires_at=created_at + timedelta(seconds=EXPORT_TTL_SECONDS),
    )
    _exports[export_id] = record
    return record


def get_export(export_id: str) -> ExportRecord | None:
    cleanup_expired_exports()
    rec = _exports.get(export_id)
    if not rec:
        return None
    if _is_expired(rec):
        _exports.pop(export_id, None)
        if rec.file_path.exists():
            try:
                rec.file_path.unlink()
            except OSError:
                pass
        return None
    return rec

