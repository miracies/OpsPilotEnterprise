from __future__ import annotations

import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import httpx
from fastapi import FastAPI, HTTPException

from opspilot_schema.envelope import make_error, make_success
from opspilot_schema.logs import (
    LogContextGroup,
    LogContextResponse,
    LogEvidenceRequest,
    LogExternalLink,
    LogItem,
    LogSearchRequest,
    LogSearchResponse,
    LogSourceConfig,
    LogSourcePublic,
    LogSourceUpsert,
    VMwareLogContextQuery,
)


DB_PATH = Path(os.environ.get("LOG_GATEWAY_DB", "data/log_gateway.db"))
DEFAULT_OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "").strip()
DEFAULT_OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX_PATTERN", "opspilot-vmware-*").strip()
DEFAULT_LOG_WEB_URL = os.environ.get("OPENSEARCH_WEB_URL", os.environ.get("LOG_PLATFORM_URL", "")).strip()
DEFAULT_OPENSEARCH_USERNAME = os.environ.get("OPENSEARCH_USERNAME", "").strip()
DEFAULT_OPENSEARCH_PASSWORD = os.environ.get("OPENSEARCH_PASSWORD", "").strip()
DEFAULT_OPENSEARCH_TLS_VERIFY = os.environ.get("OPENSEARCH_TLS_VERIFY", "true").strip().lower() not in {"0", "false", "no"}

app = FastAPI(title="OpsPilot Log Gateway", version="0.1.0")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_window(minutes: int) -> tuple[str, str]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=max(minutes, 1))
    return start.isoformat(), end.isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except ValueError:
        return default


def _public_source(config: LogSourceConfig) -> LogSourcePublic:
    return LogSourcePublic(
        id=config.id,
        name=config.name,
        backend_type=config.backend_type,
        endpoint=config.endpoint,
        auth_type=config.auth_type,
        username=config.username,
        index_pattern=config.index_pattern,
        tenant=config.tenant,
        tls_verify=config.tls_verify,
        default_time_window=config.default_time_window,
        max_result_limit=config.max_result_limit,
        enabled=config.enabled,
        web_url=config.web_url,
        has_secret=bool(config.password or config.token),
    )


class LogRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.init()

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS log_sources (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS log_evidence_refs (
                    evidence_ref TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    log_id TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    comment TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    def list_sources(self, include_disabled: bool = True) -> list[LogSourceConfig]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT payload FROM log_sources ORDER BY updated_at DESC").fetchall()
        items = [LogSourceConfig.model_validate(_loads(row[0], {})) for row in rows]
        if not include_disabled:
            items = [item for item in items if item.enabled]
        return items

    def get_source(self, source_id: str) -> LogSourceConfig | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT payload FROM log_sources WHERE id = ?", (source_id,)).fetchone()
        if not row:
            return None
        return LogSourceConfig.model_validate(_loads(row[0], {}))

    def upsert_source(self, body: LogSourceUpsert) -> LogSourceConfig:
        existing = self.get_source(body.id) if body.id else None
        source_id = body.id or f"logsrc-{uuid.uuid4().hex[:10]}"
        payload = body.model_dump()
        if existing and payload.get("password") is None:
            payload["password"] = existing.password
        if existing and payload.get("token") is None:
            payload["token"] = existing.token
        config = LogSourceConfig.model_validate({**payload, "id": source_id})
        now = _now()
        with sqlite3.connect(self.db_path) as conn:
            exists = conn.execute("SELECT 1 FROM log_sources WHERE id = ?", (source_id,)).fetchone()
            if exists:
                conn.execute("UPDATE log_sources SET payload = ?, updated_at = ? WHERE id = ?", (_json(config.model_dump()), now, source_id))
            else:
                conn.execute(
                    "INSERT INTO log_sources(id, payload, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (source_id, _json(config.model_dump()), now, now),
                )
        return config

    def delete_source(self, source_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM log_sources WHERE id = ?", (source_id,))
            return cur.rowcount > 0

    def add_evidence_refs(self, incident_id: str, log_ids: list[str], evidence_type: str, comment: str | None) -> list[str]:
        refs: list[str] = []
        now = _now()
        with sqlite3.connect(self.db_path) as conn:
            for log_id in log_ids:
                ref = f"evidence-log-{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO log_evidence_refs(evidence_ref, incident_id, log_id, evidence_type, comment, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (ref, incident_id, log_id, evidence_type, comment, now),
                )
                refs.append(ref)
        return refs


repo = LogRepository(DB_PATH)


class LogBackend(ABC):
    def __init__(self, config: LogSourceConfig) -> None:
        self.config = config

    @abstractmethod
    async def search(self, query: LogSearchRequest) -> LogSearchResponse:
        raise NotImplementedError

    @abstractmethod
    async def get_raw(self, log_id: str) -> LogItem:
        raise NotImplementedError

    @abstractmethod
    async def test_connection(self) -> dict[str, Any]:
        raise NotImplementedError


def _terms_clause(fields: list[str], value: Any) -> dict[str, Any] | None:
    if value in (None, "", []):
        return None
    values = value if isinstance(value, list) else [value]
    values = [item for item in values if item not in (None, "")]
    if not values:
        return None
    should: list[dict[str, Any]] = []
    for field in fields:
        should.append({"terms": {field: values}})
        should.append({"terms": {f"{field}.keyword": values}})
        for item in values:
            should.append({"match_phrase": {field: item}})
    if len(should) == 1:
        return should[0]
    return {"bool": {"should": should, "minimum_should_match": 1}}


def _filter_clause(key: str, value: Any) -> dict[str, Any] | None:
    aliases = {
        "host": ["host.name", "hostname", "source_host", "source"],
        "hostname": ["hostname", "host.name", "source_host", "source"],
        "source_host": ["source_host", "hostname", "host.name", "source"],
        "vm_name": ["vm_name", "object_name"],
        "object_name": ["object_name", "vm_name"],
        "vm_moid": ["vm_moid", "object_moid"],
        "object_moid": ["object_moid", "vm_moid"],
        "datastore": ["datastore", "datastore_name"],
        "component": ["component"],
        "severity": ["severity", "level"],
        "product": ["product"],
        "vcenter": ["vcenter"],
    }
    return _terms_clause(aliases.get(key, [key]), value)


def build_opensearch_dsl(query: LogSearchRequest, config: LogSourceConfig) -> dict[str, Any]:
    filters = query.filters or {}
    must: list[dict[str, Any]] = []
    filter_clauses: list[dict[str, Any]] = []
    if query.time_range and (query.time_range.from_ or query.time_range.to):
        range_body: dict[str, str] = {}
        if query.time_range.from_:
            range_body["gte"] = query.time_range.from_
        if query.time_range.to:
            range_body["lte"] = query.time_range.to
        filter_clauses.append({"range": {"@timestamp": range_body}})
    elif config.default_time_window:
        start, end = _utc_window(config.default_time_window)
        filter_clauses.append({"range": {"@timestamp": {"gte": start, "lte": end}}})

    for key, value in filters.items():
        if value in (None, "", []):
            continue
        clause = _filter_clause(key, value)
        if clause:
            filter_clauses.append(clause)

    if query.query:
        must.append(
            {
                "query_string": {
                    "query": query.query,
                    "fields": [
                        "message",
                        "raw_message",
                        "component",
                        "source",
                        "source_host",
                        "hostname",
                        "host.name",
                        "object_name",
                        "object_moid",
                        "vm_name",
                        "vm_moid",
                        "datastore",
                        "datastore_name",
                        "vcenter",
                        "event_type",
                        "task_id",
                    ],
                    "default_operator": "OR",
                }
            }
        )

    return {
        "size": min(max(query.limit, 1), config.max_result_limit),
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {"bool": {"must": must or [{"match_all": {}}], "filter": filter_clauses}},
    }


class OpenSearchLogBackend(LogBackend):
    def _auth(self) -> httpx.Auth | None:
        if self.config.auth_type == "basic" and self.config.username is not None:
            return httpx.BasicAuth(self.config.username, self.config.password or "")
        return None

    def _headers(self) -> dict[str, str]:
        if self.config.auth_type == "token" and self.config.token:
            return {"Authorization": f"Bearer {self.config.token}"}
        return {}

    def _link(self, query_text: str | None, log_id: str | None = None) -> list[LogExternalLink]:
        if not self.config.web_url:
            return []
        q = query_text or log_id or ""
        url = self.config.web_url.rstrip("/")
        if q:
            url = f"{url}?q={quote(q)}"
        if self.config.backend_type == "opensearch" and "/app/discover" in url:
            parsed = urlsplit(url)
            next_url = parsed.path
            if parsed.query:
                next_url = f"{next_url}?{parsed.query}"
            url = urlunsplit((parsed.scheme, parsed.netloc, "/auth/anonymous", f"nextUrl={quote(next_url, safe='')}", ""))
        return [LogExternalLink(provider="opensearch", title="OpenSearch Dashboards", url=url, query=q or None, kind="search")]

    def _normalize_hit(self, hit: dict[str, Any], query_text: str | None = None) -> LogItem:
        src = hit.get("_source") if isinstance(hit.get("_source"), dict) else {}
        index = str(hit.get("_index") or "")
        doc_id = str(hit.get("_id") or "")
        raw = str(src.get("raw_message") or src.get("message") or json.dumps(src, ensure_ascii=False))
        message = str(src.get("message") or src.get("raw_message") or raw)
        timestamp = str(src.get("@timestamp") or src.get("timestamp") or _now())
        host_value = src.get("host")
        host_name = host_value.get("name") if isinstance(host_value, dict) else host_value
        source = str(src.get("source") or src.get("hostname") or src.get("source_host") or host_name or "log")
        log_id = f"opensearch:{index}:{doc_id}"
        return LogItem(
            log_id=log_id,
            timestamp=timestamp,
            source=source,
            product=src.get("product") or src.get("source_type"),
            component=src.get("component"),
            severity=src.get("severity") or src.get("level"),
            message=message,
            raw_message=raw,
            fields=src,
            backend="opensearch",
            index=index,
            document_id=doc_id,
            external_links=self._link(query_text, log_id),
        )

    async def search(self, query: LogSearchRequest) -> LogSearchResponse:
        dsl = build_opensearch_dsl(query, self.config)
        url = f"{self.config.endpoint.rstrip('/')}/{self.config.index_pattern}/_search"
        async with httpx.AsyncClient(timeout=30.0, verify=self.config.tls_verify) as client:
            resp = await client.post(url, json=dsl, auth=self._auth(), headers=self._headers())
        resp.raise_for_status()
        body = resp.json()
        hits_body = body.get("hits") if isinstance(body, dict) else {}
        total_raw = hits_body.get("total", 0) if isinstance(hits_body, dict) else 0
        total = int(total_raw.get("value", 0) if isinstance(total_raw, dict) else total_raw or 0)
        items = [self._normalize_hit(hit, query.query) for hit in (hits_body.get("hits") or [])]
        return LogSearchResponse(total=total, items=items, backend="opensearch", source_id=self.config.id)

    async def get_raw(self, log_id: str) -> LogItem:
        parts = log_id.split(":", 2)
        if len(parts) != 3 or parts[0] != "opensearch":
            raise ValueError("invalid opensearch log_id")
        _, index, doc_id = parts
        url = f"{self.config.endpoint.rstrip('/')}/{quote(index, safe='')}/_doc/{quote(doc_id, safe='')}"
        async with httpx.AsyncClient(timeout=20.0, verify=self.config.tls_verify) as client:
            resp = await client.get(url, auth=self._auth(), headers=self._headers())
        resp.raise_for_status()
        return self._normalize_hit(resp.json(), log_id)

    async def test_connection(self) -> dict[str, Any]:
        url = f"{self.config.endpoint.rstrip('/')}/_cluster/health"
        async with httpx.AsyncClient(timeout=10.0, verify=self.config.tls_verify) as client:
            resp = await client.get(url, auth=self._auth(), headers=self._headers())
        resp.raise_for_status()
        return resp.json()


class UnsupportedLogBackend(LogBackend):
    async def search(self, query: LogSearchRequest) -> LogSearchResponse:
        raise RuntimeError(f"{self.config.backend_type} backend is not implemented in this release")

    async def get_raw(self, log_id: str) -> LogItem:
        raise RuntimeError(f"{self.config.backend_type} backend is not implemented in this release")

    async def test_connection(self) -> dict[str, Any]:
        raise RuntimeError(f"{self.config.backend_type} backend is not implemented in this release")


def _backend(config: LogSourceConfig) -> LogBackend:
    if config.backend_type == "opensearch":
        return OpenSearchLogBackend(config)
    return UnsupportedLogBackend(config)


def _enabled_source(source_id: str | None = None, backend: str | None = None) -> LogSourceConfig | None:
    if source_id:
        config = repo.get_source(source_id)
        return config if config and config.enabled else None
    sources = repo.list_sources(include_disabled=False)
    if backend:
        sources = [src for src in sources if src.backend_type == backend]
    return sources[0] if sources else None


def _seed_default_source() -> None:
    if repo.list_sources() or not DEFAULT_OPENSEARCH_URL:
        return
    repo.upsert_source(
        LogSourceUpsert(
            id="default-opensearch",
            name="Default OpenSearch",
            backend_type="opensearch",
            endpoint=DEFAULT_OPENSEARCH_URL,
            index_pattern=DEFAULT_OPENSEARCH_INDEX,
            web_url=DEFAULT_LOG_WEB_URL or None,
            enabled=True,
            auth_type="basic" if DEFAULT_OPENSEARCH_USERNAME or DEFAULT_OPENSEARCH_PASSWORD else "none",
            username=DEFAULT_OPENSEARCH_USERNAME or None,
            password=DEFAULT_OPENSEARCH_PASSWORD or None,
            tls_verify=DEFAULT_OPENSEARCH_TLS_VERIFY,
        )
    )


def _component_query(name: str, components: list[str], keywords: list[str], ctx: VMwareLogContextQuery) -> tuple[str, LogSearchRequest]:
    terms = [x for x in [ctx.vm_name, ctx.vm_moid, ctx.host, ctx.datastore, *keywords] if x]
    filters: dict[str, Any] = {"component": components}
    if ctx.vcenter:
        filters["vcenter"] = ctx.vcenter
    if ctx.host:
        filters["host"] = ctx.host
    if ctx.vm_name:
        filters["vm_name"] = ctx.vm_name
    if ctx.vm_moid:
        filters["vm_moid"] = ctx.vm_moid
    if ctx.datastore:
        filters["datastore"] = ctx.datastore
    query = " OR ".join(str(term) for term in terms)
    minutes = ctx.time_window.before_minutes + ctx.time_window.after_minutes
    start, end = _utc_window(minutes)
    if ctx.timestamp:
        try:
            center = datetime.fromisoformat(ctx.timestamp.replace("Z", "+00:00"))
            start = (center - timedelta(minutes=ctx.time_window.before_minutes)).isoformat()
            end = (center + timedelta(minutes=ctx.time_window.after_minutes)).isoformat()
        except ValueError:
            pass
    return name, LogSearchRequest(time_range={"from": start, "to": end}, filters=filters, query=query, limit=ctx.limit)


def _vmware_templates(ctx: VMwareLogContextQuery) -> list[tuple[str, LogSearchRequest]]:
    templates = {
        "vm_overall_status_red": [
            ("vm_related_logs", ["hostd", "vpxa", "vpxd", "vpxd-alert"], ["inaccessible", "orphaned", "invalid", "Failed"]),
            ("storage_related_logs", ["vmkernel", "hostd", "sps"], ["APD", "PDL", "NMP", "snapshot", "consolidation", "No space left"]),
            ("vcenter_task_event_logs", ["vpxd", "vpxd-alert"], ["triggered", "alarm", "Task", "Event"]),
        ],
        "host_disconnected": [
            ("host_connectivity_logs", ["vpxa", "hostd", "vmkernel", "vmksummary", "vpxd"], ["disconnected", "not responding", "heartbeat", "SSL", "timeout"]),
        ],
        "vmotion_failed": [
            ("vmotion_logs", ["hostd", "vpxa", "vmkernel", "vpxd"], ["vMotion", "Migration", "Relocate", "Timed out", "EVC", "NFC"]),
        ],
        "datastore_snapshot_issue": [
            ("datastore_snapshot_logs", ["vmkernel", "hostd", "vpxd", "sps"], ["APD", "PDL", "NMP", "naa.", "timeout", "snapshot", "delta", "consolidation"]),
        ],
        "ha_failover": [
            ("ha_failover_logs", ["fdm", "hostd", "vmkernel", "vpxd"], ["FDM", "HA", "failover", "restart", "isolation", "heartbeat datastore"]),
        ],
    }
    selected = templates.get(ctx.scenario, templates["vm_overall_status_red"])
    return [_component_query(name, components, keywords, ctx) for name, components, keywords in selected]


@app.on_event("startup")
async def startup() -> None:
    repo.init()
    _seed_default_source()


@app.get("/health")
async def health() -> dict[str, Any]:
    return make_success({"status": "ok", "service": "log-gateway", "version": "0.1.0"})


@app.get("/api/v1/logs/sources")
async def list_sources() -> dict[str, Any]:
    return make_success({"items": [_public_source(src).model_dump() for src in repo.list_sources()]})


@app.post("/api/v1/logs/sources")
async def upsert_source(body: LogSourceUpsert) -> dict[str, Any]:
    try:
        src = repo.upsert_source(body)
        return make_success(_public_source(src).model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.delete("/api/v1/logs/sources/{source_id}")
async def delete_source(source_id: str) -> dict[str, Any]:
    if not repo.delete_source(source_id):
        return make_error("log source not found")
    return make_success({"deleted": True})


@app.post("/api/v1/logs/sources/test")
async def test_source(body: dict[str, Any]) -> dict[str, Any]:
    try:
        if body.get("source_id"):
            config = repo.get_source(str(body["source_id"]))
            if not config:
                return make_error("log source not found")
        else:
            config = LogSourceConfig.model_validate({**body, "id": body.get("id") or "test-source", "name": body.get("name") or "Test Source"})
        result = await _backend(config).test_connection()
        return make_success({"ok": True, "backend": config.backend_type, "result": result})
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.post("/api/v1/logs/search")
async def search_logs(body: LogSearchRequest) -> dict[str, Any]:
    try:
        config = _enabled_source(body.source_id, body.backend)
        if not config:
            return make_success(LogSearchResponse(total=0, items=[], backend=body.backend, source_id=body.source_id).model_dump())
        result = await _backend(config).search(body)
        return make_success(result.model_dump())
    except httpx.HTTPStatusError as exc:
        return make_error(f"log backend returned {exc.response.status_code}: {exc.response.text[:300]}")
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.get("/api/v1/logs/raw/{log_id:path}")
async def get_raw(log_id: str) -> dict[str, Any]:
    try:
        backend_name = log_id.split(":", 1)[0]
        config = _enabled_source(backend=backend_name)
        if not config:
            raise HTTPException(status_code=404, detail="log source not configured")
        item = await _backend(config).get_raw(log_id)
        return make_success(item.model_dump())
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))


@app.post("/api/v1/logs/context")
async def context_logs(body: VMwareLogContextQuery) -> dict[str, Any]:
    config = _enabled_source()
    queries = _vmware_templates(body)
    if not config:
        response = LogContextResponse(incident_id=body.incident_id, queries_executed=[name for name, _ in queries], groups=[])
        return make_success(response.model_dump())
    groups: list[LogContextGroup] = []
    executed: list[str] = []
    for name, req in queries:
        executed.append(name)
        try:
            result = await _backend(config).search(req)
            groups.append(LogContextGroup(name=name, count=result.total, items=result.items))
        except Exception as exc:  # noqa: BLE001
            groups.append(LogContextGroup(name=name, count=0, items=[]))
            executed.append(f"{name} failed: {exc}")
    return make_success(LogContextResponse(incident_id=body.incident_id, queries_executed=executed, groups=groups).model_dump())


@app.post("/api/v1/logs/evidence")
async def add_log_evidence(body: LogEvidenceRequest) -> dict[str, Any]:
    refs = repo.add_evidence_refs(body.incident_id, body.log_ids, body.evidence_type, body.comment)
    return make_success({"evidence_refs": refs})
