"""OpsPilot Knowledge Service - articles, alert knowledge, import jobs, feedback."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

from opspilot_schema.envelope import make_error, make_success
from opspilot_schema.knowledge import (
    AlertKnowledge,
    AlertKnowledgeAutomation,
    AlertKnowledgeBulkImportBody,
    AlertKnowledgeSource,
    AlertMatchRequest,
    KnowledgeImportValidateBody,
    KnowledgeFeedbackBody,
)

UTC = timezone.utc


def _now() -> str:
    return datetime.now(UTC).isoformat()


BASE_DIR = Path(__file__).resolve().parents[2]


def _find_repo_dir() -> Path:
    candidates: list[Path] = []
    env_dir = os.environ.get("OPSPILOT_REPO_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    resolved = Path(__file__).resolve()
    candidates.extend(resolved.parents)
    candidates.extend([Path.cwd(), Path("/")])
    for candidate in candidates:
        if (candidate / "fixtures" / "knowledge" / "vmware_alerts" / "vmware_alert_knowledge.jsonl").exists():
            return candidate
    return BASE_DIR


REPO_DIR = _find_repo_dir()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("KNOWLEDGE_DB_PATH", str(DATA_DIR / "knowledge.db")))

app = FastAPI(title="OpsPilot Knowledge Service", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_ARTICLES = [
    {
        "id": "KB-001",
        "title": "Java Full GC storm on VMware VM",
        "content_summary": "Runbook for diagnosing JVM Full GC storms that surface as high VM CPU.",
        "source": "runbook",
        "status": "published",
        "tags": ["java", "jvm", "cpu", "vmware"],
        "categories": ["performance", "vmware"],
        "author": "ops-team",
        "version": "1.2.0",
        "hit_count": 23,
        "confidence_score": 0.92,
        "created_at": "2026-01-10T09:00:00Z",
        "updated_at": "2026-03-20T14:30:00Z",
        "related_incident_ids": ["INC-20260405-001"],
    },
    {
        "id": "KB-002",
        "title": "VMware HA isolation response runbook",
        "content_summary": "Checks for HA admission control, isolation response, host network, and VM restart behavior.",
        "source": "runbook",
        "status": "published",
        "tags": ["vmware", "ha", "network", "host"],
        "categories": ["availability", "vmware"],
        "author": "ops-team",
        "version": "2.0.1",
        "hit_count": 15,
        "confidence_score": 0.88,
        "created_at": "2025-11-05T10:00:00Z",
        "updated_at": "2026-02-14T11:00:00Z",
        "related_incident_ids": ["INC-20260404-005"],
    },
    {
        "id": "KB-003",
        "title": "NFS datastore snapshot capacity management",
        "content_summary": "Best practices for snapshot growth, datastore usage alarms, and consolidation risk.",
        "source": "confluence",
        "status": "published",
        "tags": ["vmware", "nfs", "snapshot", "datastore"],
        "categories": ["capacity", "storage"],
        "author": "storage-team",
        "version": "1.0.3",
        "hit_count": 31,
        "confidence_score": 0.95,
        "created_at": "2025-08-20T08:00:00Z",
        "updated_at": "2026-01-08T16:00:00Z",
        "related_incident_ids": ["INC-20260405-002"],
    },
]

_CASES = [
    {
        "id": "CASE-20260320",
        "title": "VM CPU pressure caused by Java GC storm",
        "summary": "High VM CPU and high application GC pause time on a production JVM.",
        "category": "performance",
        "status": "archived",
        "severity": "high",
        "tags": ["vmware", "cpu", "jvm"],
        "incident_refs": ["INC-20260320-001"],
        "root_cause_summary": "Application GC storm saturated VM CPU.",
        "resolution_summary": "Tuned JVM heap and moved noisy VM away from a hot host.",
        "lessons_learned": "Check guest process CPU before host capacity changes.",
        "author": "system",
        "created_at": "2026-03-20T08:00:00Z",
        "archived_at": "2026-03-21T09:00:00Z",
        "similarity_score": 0.82,
        "hit_count": 3,
        "knowledge_refs": ["AK-VMWARE-RESOURCE-001"],
    },
    {
        "id": "CASE-20260315",
        "title": "Datastore snapshot chain caused capacity alarm",
        "summary": "Snapshot chain grew after backup failure and triggered datastore usage alarm.",
        "category": "capacity",
        "status": "archived",
        "severity": "medium",
        "tags": ["vmware", "snapshot", "datastore"],
        "incident_refs": ["INC-20260315-001"],
        "root_cause_summary": "Backup job left a long snapshot chain.",
        "resolution_summary": "Consolidated snapshots after free-space verification.",
        "lessons_learned": "Pair datastore alarms with backup job status.",
        "author": "system",
        "created_at": "2026-03-15T08:00:00Z",
        "archived_at": "2026-03-16T10:00:00Z",
        "similarity_score": 0.91,
        "hit_count": 5,
        "knowledge_refs": ["AK-VMWARE-STORAGE-002"],
    },
]


class KnowledgeArticleCreateBody(BaseModel):
    title: str
    content_summary: str
    source: str = "manual"
    status: str = "published"
    tags: list[str] = Field(default_factory=list)
    author: str = "memory-service"
    steps: list[str] = Field(default_factory=list)


class PrometheusRulesImportBody(BaseModel):
    content: str
    source_url: str | None = None
    publish: bool = False
    upsert: bool = True


class CaseSimilarBody(BaseModel):
    title: str | None = None
    summary: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    root_cause_summary: str | None = None
    knowledge_refs: list[str] = Field(default_factory=list)
    limit: int = 5


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _exec(sql: str, params: tuple[Any, ...] = ()) -> None:
    conn = _connect()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _query_all(sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    conn = _connect()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _query_one(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    conn = _connect()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _row_get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def _init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS alert_knowledge (
                id TEXT PRIMARY KEY,
                alert_name TEXT NOT NULL,
                vendor TEXT NOT NULL,
                domain TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                aliases_json TEXT NOT NULL DEFAULT '[]',
                symptoms_json TEXT NOT NULL DEFAULT '[]',
                possible_causes_json TEXT NOT NULL DEFAULT '[]',
                diagnostic_steps_json TEXT NOT NULL DEFAULT '[]',
                decision_tree_json TEXT NOT NULL DEFAULT '[]',
                evidence_required_json TEXT NOT NULL DEFAULT '[]',
                evidence_optional_json TEXT NOT NULL DEFAULT '[]',
                remediation_json TEXT NOT NULL DEFAULT '[]',
                automation_json TEXT NOT NULL DEFAULT '{}',
                source_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL,
                version TEXT NOT NULL,
                trust_score REAL NOT NULL DEFAULT 0.8,
                hit_count INTEGER NOT NULL DEFAULT 0,
                case_refs_json TEXT NOT NULL DEFAULT '[]',
                knowledge_refs_json TEXT NOT NULL DEFAULT '[]',
                tags_json TEXT NOT NULL DEFAULT '[]',
                match_keywords_json TEXT NOT NULL DEFAULT '[]',
                negative_keywords_json TEXT NOT NULL DEFAULT '[]',
                owner TEXT,
                reviewer TEXT,
                review_notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(alert_name, vendor, category)
            );
            CREATE INDEX IF NOT EXISTS idx_alert_knowledge_status ON alert_knowledge(status);
            CREATE INDEX IF NOT EXISTS idx_alert_knowledge_vendor_category ON alert_knowledge(vendor, category);
            CREATE TABLE IF NOT EXISTS knowledge_import_jobs (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_url TEXT,
                status TEXT NOT NULL,
                articles_imported INTEGER NOT NULL DEFAULT 0,
                articles_failed INTEGER NOT NULL DEFAULT 0,
                created INTEGER NOT NULL DEFAULT 0,
                updated INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                total INTEGER NOT NULL DEFAULT 0,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS knowledge_feedback (
                id TEXT PRIMARY KEY,
                alert_knowledge_id TEXT,
                incident_id TEXT,
                match_correct INTEGER NOT NULL,
                actual_root_cause TEXT,
                missing_evidence_json TEXT NOT NULL DEFAULT '[]',
                accepted_actions_json TEXT NOT NULL DEFAULT '[]',
                comment TEXT,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        _ensure_columns(
            conn,
            "alert_knowledge",
            {
                "evidence_optional_json": "TEXT NOT NULL DEFAULT '[]'",
                "match_keywords_json": "TEXT NOT NULL DEFAULT '[]'",
                "negative_keywords_json": "TEXT NOT NULL DEFAULT '[]'",
                "owner": "TEXT",
                "reviewer": "TEXT",
                "review_notes": "TEXT",
            },
        )
        _ensure_columns(
            conn,
            "knowledge_import_jobs",
            {
                "created": "INTEGER NOT NULL DEFAULT 0",
                "updated": "INTEGER NOT NULL DEFAULT 0",
                "failed": "INTEGER NOT NULL DEFAULT 0",
                "total": "INTEGER NOT NULL DEFAULT 0",
            },
        )
        conn.commit()
    finally:
        conn.close()


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _row_to_alert(row: sqlite3.Row) -> AlertKnowledge:
    return AlertKnowledge(
        id=row["id"],
        alert_name=row["alert_name"],
        vendor=row["vendor"],
        domain=row["domain"],
        category=row["category"],
        severity=row["severity"],
        aliases=_loads(row["aliases_json"], []),
        symptoms=_loads(row["symptoms_json"], []),
        possible_causes=_loads(row["possible_causes_json"], []),
        diagnostic_steps=_loads(row["diagnostic_steps_json"], []),
        decision_tree=_loads(row["decision_tree_json"], []),
        evidence_required=_loads(row["evidence_required_json"], []),
        evidence_optional=_loads(_row_get(row, "evidence_optional_json"), []),
        remediation=_loads(row["remediation_json"], []),
        automation=_loads(row["automation_json"], {}),
        source=_loads(row["source_json"], {}),
        status=row["status"],
        version=row["version"],
        trust_score=float(row["trust_score"]),
        hit_count=int(row["hit_count"]),
        case_refs=_loads(row["case_refs_json"], []),
        knowledge_refs=_loads(row["knowledge_refs_json"], []),
        tags=_loads(row["tags_json"], []),
        match_keywords=_loads(_row_get(row, "match_keywords_json"), []),
        negative_keywords=_loads(_row_get(row, "negative_keywords_json"), []),
        owner=_row_get(row, "owner"),
        reviewer=_row_get(row, "reviewer"),
        review_notes=_row_get(row, "review_notes"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _upsert_alert(item: AlertKnowledge, *, upsert: bool) -> tuple[AlertKnowledge, bool]:
    existing = _query_one(
        "SELECT * FROM alert_knowledge WHERE id=? OR (alert_name=? AND vendor=? AND category=?)",
        (item.id, item.alert_name, item.vendor, item.category),
    )
    if existing and not upsert:
        raise HTTPException(status_code=409, detail="AlertKnowledge already exists")

    created = item.created_at
    hit_count = item.hit_count
    if existing:
        created = existing["created_at"]
        hit_count = int(existing["hit_count"])
        _exec(
            """
            UPDATE alert_knowledge SET
                alert_name=?, vendor=?, domain=?, category=?, severity=?, aliases_json=?,
                symptoms_json=?, possible_causes_json=?, diagnostic_steps_json=?, decision_tree_json=?,
                evidence_required_json=?, evidence_optional_json=?, remediation_json=?, automation_json=?, source_json=?,
                status=?, version=?, trust_score=?, hit_count=?, case_refs_json=?, knowledge_refs_json=?,
                tags_json=?, match_keywords_json=?, negative_keywords_json=?, owner=?, reviewer=?, review_notes=?, updated_at=?
            WHERE id=?
            """,
            (
                item.alert_name,
                item.vendor,
                item.domain,
                item.category,
                item.severity,
                _json(item.aliases),
                _json(item.symptoms),
                _json(item.possible_causes),
                _json(item.diagnostic_steps),
                _json([rule.model_dump() for rule in item.decision_tree]),
                _json(item.evidence_required),
                _json(item.evidence_optional),
                _json(item.remediation),
                _json(item.automation.model_dump()),
                _json(item.source.model_dump()),
                item.status,
                item.version,
                item.trust_score,
                hit_count,
                _json(item.case_refs),
                _json(item.knowledge_refs),
                _json(item.tags),
                _json(item.match_keywords),
                _json(item.negative_keywords),
                item.owner,
                item.reviewer,
                item.review_notes,
                _now(),
                existing["id"],
            ),
        )
        row = _query_one("SELECT * FROM alert_knowledge WHERE id=?", (existing["id"],))
        if not row:
            raise RuntimeError("updated alert knowledge not found")
        return _row_to_alert(row), False

    _exec(
        """
        INSERT INTO alert_knowledge(
            id,alert_name,vendor,domain,category,severity,aliases_json,symptoms_json,
            possible_causes_json,diagnostic_steps_json,decision_tree_json,evidence_required_json,
            evidence_optional_json,remediation_json,automation_json,source_json,status,version,trust_score,hit_count,
            case_refs_json,knowledge_refs_json,tags_json,match_keywords_json,negative_keywords_json,owner,reviewer,review_notes,created_at,updated_at
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            item.id,
            item.alert_name,
            item.vendor,
            item.domain,
            item.category,
            item.severity,
            _json(item.aliases),
            _json(item.symptoms),
            _json(item.possible_causes),
            _json(item.diagnostic_steps),
            _json([rule.model_dump() for rule in item.decision_tree]),
            _json(item.evidence_required),
            _json(item.evidence_optional),
            _json(item.remediation),
            _json(item.automation.model_dump()),
            _json(item.source.model_dump()),
            item.status,
            item.version,
            item.trust_score,
            hit_count,
            _json(item.case_refs),
            _json(item.knowledge_refs),
            _json(item.tags),
            _json(item.match_keywords),
            _json(item.negative_keywords),
            item.owner,
            item.reviewer,
            item.review_notes,
            created,
            item.updated_at,
        ),
    )
    row = _query_one("SELECT * FROM alert_knowledge WHERE id=?", (item.id,))
    if not row:
        raise RuntimeError("created alert knowledge not found")
    return _row_to_alert(row), True


def _make_seed(
    idx: int,
    name: str,
    category: str,
    severity: str,
    aliases: list[str],
    causes: list[str],
    evidence: list[str],
    safe: list[str],
    approval: list[str],
) -> AlertKnowledge:
    category_no = {
        "resource": 1,
        "ha_cluster": 2,
        "vmotion_drs": 3,
        "storage": 4,
        "network": 5,
        "vm_level": 6,
    }.get(category, 9)
    now = "2026-04-30T00:00:00Z"
    symptom = f"{name} observed in vCenter or related monitoring source"
    granular_required = {
        "Virtual machine CPU usage": ["vm.cpu.usage", "vm.cpu.ready", "host.cpu.usage", "vm.cpu.config", "recent.vmotion.events"],
        "Host Memory Usage": ["host.memory.usage", "host.memory.active", "host.memory.balloon", "host.memory.swap", "vm.memory.config"],
        "Insufficient HA failover resources": ["cluster.ha.config", "cluster.host.state", "vm.reservations", "maintenance.events"],
        "vMotion compatibility failure": ["vmotion.events", "vmk.config", "network.mtu.path", "cluster.evc", "host.cpu.compatibility"],
        "vMotion switchover timeout": ["vmotion.events", "vmk.config", "network.mtu.path", "packet_loss_test", "datastore.latency"],
        "Datastore usage on disk": ["datastore.usage", "datastore.free_space", "vm.snapshot.tree", "recent.backup.jobs"],
        "Virtual Machine Consolidation Needed": ["datastore.usage", "datastore.free_space", "vm.snapshot.tree", "vm.consolidation.status", "recent.backup.jobs"],
        "Host connection and power state": ["host.connection.events", "management.network.reachability", "hostd.logs", "vpxa.logs", "host.power.state"],
        "Host not responding": ["host.connection.events", "management.network.reachability", "hostd.logs", "vpxa.logs", "network.topology"],
    }.get(name, evidence)
    return AlertKnowledge(
        id=f"AK-VMWARE-{category_no:02d}-{idx:03d}",
        alert_name=name,
        vendor="vmware",
        domain="virtualization",
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        aliases=aliases,
        symptoms=[symptom, f"Object reports {severity} severity or repeated warning state"],
        possible_causes=causes,
        diagnostic_steps=[
            "Confirm alert scope, object identity, and first-seen timestamp.",
            "Collect required metrics, events, object detail, topology, and recent changes.",
            "Compare current evidence with the decision tree before recommending write actions.",
        ],
        decision_tree=[
            "if required evidence is missing -> request evidence before high-confidence RCA",
            "if metric and event evidence agree -> prioritize the matching cause branch",
            "if contradictions exist -> mark conclusion as insufficient_evidence",
        ],
        evidence_required=granular_required,
        evidence_optional=[ev for ev in evidence if ev not in granular_required],
        remediation=[
            "Run read-only collection first.",
            "Apply low-risk configuration guidance when evidence is sufficient.",
            "Use approval workflow for migration, restart, consolidation, or balancing actions.",
        ],
        automation=AlertKnowledgeAutomation(safe_actions=safe, approval_actions=approval),
        source=AlertKnowledgeSource(type="seed", title="VMware alert golden knowledge seed", trust_score=0.86),
        status="published",
        version="1.0.0",
        trust_score=0.86,
        hit_count=0,
        case_refs=[],
        knowledge_refs=["KB-001"] if category == "resource" else ["KB-002"] if category == "ha_cluster" else ["KB-003"],
        tags=["vmware", category, *aliases[:3]],
        match_keywords=[name.lower(), category, *aliases, *[str(c).lower() for c in causes[:2]]],
        negative_keywords=["hardware sensor", "temperature", "fan", "power supply"],
        owner="ops-team",
        reviewer="vmware-sme",
        created_at=now,
        updated_at=now,
    )


def _seed_alerts() -> list[AlertKnowledge]:
    rows = [
        ("Virtual machine CPU usage", "resource", "critical", ["vm cpu high", "cpu usage"], ["Guest workload spike", "CPU ready caused by host contention", "CPU limit or vCPU oversizing"], ["event", "metric", "detail", "topology", "change", "kb"], ["collect_vm_metrics", "collect_host_metrics", "query_recent_events"], ["vmware.vm_migrate", "vmware.cluster_balance"]),
        ("Host CPU usage", "resource", "warning", ["host cpu high", "esxi cpu"], ["Many busy VMs on one host", "DRS imbalance", "Recent migration concentrated workload"], ["metric", "detail", "topology", "change"], ["collect_host_metrics", "query_top_vms"], ["vmware.cluster_balance"]),
        ("Host Memory Usage", "resource", "warning", ["host memory high", "memory usage"], ["Configured memory overcommit", "Ballooning or swapping", "Active memory differs from consumed memory"], ["metric", "detail", "topology", "change"], ["collect_host_metrics", "collect_vm_metrics"], ["vmware.vm_migrate"]),
        ("VM memory ballooning", "resource", "warning", ["balloon", "swap"], ["Host memory pressure", "VM memory reservation too low", "Guest memory pressure"], ["metric", "detail", "event"], ["collect_vm_metrics", "collect_host_metrics"], ["vmware.vm_migrate"]),
        ("CPU ready high", "resource", "critical", ["cpu ready", "rdy"], ["Host CPU contention", "Too many vCPU assigned", "Co-stop pressure"], ["metric", "detail", "topology"], ["collect_vm_metrics", "query_top_vms"], ["vmware.vm_migrate"]),
        ("Insufficient HA failover resources", "ha_cluster", "warning", ["ha resources", "admission control"], ["Admission control cannot satisfy failover target", "Host count too low", "VM reservations too high"], ["event", "detail", "topology", "change"], ["collect_cluster_ha_config", "summarize_reservations"], []),
        ("vSphere HA virtual machine failed to failover", "ha_cluster", "critical", ["ha failover failed"], ["Destination hosts lack capacity", "VM files locked", "HA agent issue"], ["event", "detail", "topology", "change"], ["collect_cluster_ha_config", "query_recent_events"], ["vmware.vm_power_on"]),
        ("HA host isolation detected", "ha_cluster", "critical", ["host isolation", "isolation response"], ["Management network partition", "Datastore heartbeat lost", "Isolation response policy triggered"], ["event", "alert", "detail", "topology", "log"], ["collect_host_detail", "query_recent_events"], ["vmware.host_restart"]),
        ("HA agent unreachable", "ha_cluster", "warning", ["fdm agent", "ha agent"], ["FDM agent stopped", "Management network issue", "vCenter to host communication failure"], ["event", "detail", "log"], ["collect_host_detail", "query_recent_events"], ["vmware.host_restart"]),
        ("Admission control disabled", "ha_cluster", "warning", ["ha admission disabled"], ["HA policy drift", "Recent cluster configuration change", "Maintenance window setting left behind"], ["detail", "change", "event"], ["collect_cluster_ha_config", "query_recent_events"], []),
        ("vMotion compatibility failure", "vmotion_drs", "critical", ["compatibility check", "vmotion failed"], ["EVC or CPU mismatch", "Device compatibility issue", "VMkernel network mismatch"], ["event", "detail", "topology", "change"], ["collect_vmotion_config", "query_recent_events"], ["vmware.vm_migrate"]),
        ("vMotion switchover timeout", "vmotion_drs", "critical", ["100 second timeout", "vmotion timeout"], ["Network packet loss", "MTU mismatch", "Storage latency"], ["event", "metric", "detail", "topology"], ["collect_vmotion_config", "run_vmkping_check"], ["vmware.vm_migrate"]),
        ("DRS recommendation not applied", "vmotion_drs", "warning", ["drs recommendation"], ["DRS automation level manual", "Affinity rule conflict", "Host capacity constraints"], ["event", "detail", "topology"], ["collect_drs_config", "query_recent_events"], ["vmware.cluster_balance"]),
        ("EVC incompatibility", "vmotion_drs", "warning", ["evc", "cpu family"], ["Host CPU generation mismatch", "EVC baseline too high", "VM power state blocks migration"], ["detail", "topology", "event"], ["collect_cluster_evc_config"], ["vmware.vm_migrate"]),
        ("vMotion VMkernel misconfigured", "vmotion_drs", "critical", ["vmkernel", "vmk"], ["Missing vMotion VMkernel", "Duplicate IP", "VLAN mismatch"], ["detail", "topology", "event"], ["collect_vmotion_config", "run_vmkping_check"], []),
        ("Datastore usage on disk", "storage", "warning", ["datastore usage", "disk usage"], ["Normal capacity growth", "Snapshot accumulation", "Thin provisioning burst"], ["metric", "detail", "event", "topology"], ["collect_datastore_usage", "query_snapshot_tree"], ["vmware.storage_vmotion"]),
        ("Virtual Machine Consolidation Needed", "storage", "warning", ["consolidation needed"], ["Snapshot chain left by backup", "Previous consolidation failed", "Datastore free space low"], ["event", "detail", "metric"], ["query_snapshot_tree", "collect_datastore_usage"], ["vmware.vm_consolidate"]),
        ("Snapshot consolidation failed", "storage", "critical", ["snapshot failed", "consolidate failed"], ["File lock", "Insufficient free space", "Backup proxy still attached"], ["event", "detail", "log", "metric"], ["query_snapshot_tree", "collect_datastore_usage"], ["vmware.vm_consolidate"]),
        ("vSAN capacity health", "storage", "warning", ["vsan capacity"], ["Capacity threshold exceeded", "Resync consuming space", "Policy overhead increased"], ["metric", "detail", "topology"], ["collect_vsan_health", "collect_datastore_usage"], []),
        ("Datastore latency high", "storage", "critical", ["storage latency", "datastore latency"], ["Backend array latency", "Noisy VM", "Pathing issue"], ["metric", "detail", "topology", "event"], ["collect_datastore_latency", "query_top_vms"], ["vmware.storage_vmotion"]),
        ("Host connection and power state", "network", "critical", ["host connection", "power state"], ["vCenter to ESXi API failure", "Management vmkernel issue", "Host powered off"], ["alert", "detail", "event", "topology", "log"], ["collect_host_detail", "query_recent_events"], ["vmware.host_restart"]),
        ("Host not responding", "network", "critical", ["not responding", "disconnected"], ["Management network partition", "hostd or vpxa issue", "Physical network failure"], ["alert", "detail", "event", "log", "topology"], ["collect_host_detail", "query_recent_events"], ["vmware.host_restart"]),
        ("vDS out of sync", "network", "warning", ["vds sync", "distributed switch"], ["Host proxy switch drift", "vCenter network config mismatch", "Recent DVS change"], ["event", "detail", "change"], ["collect_network_config", "query_recent_events"], []),
        ("Management vmkernel packet loss", "network", "critical", ["vmk0 packet loss", "heartbeat loss"], ["Physical NIC issue", "Switch trunk problem", "MTU or VLAN mismatch"], ["metric", "log", "detail", "topology"], ["collect_network_config", "run_vmkping_check"], []),
        ("Physical NIC link down", "network", "critical", ["pnic down", "uplink down"], ["Cable or switch port failure", "NIC driver issue", "Redundant uplink missing"], ["alert", "detail", "event", "topology"], ["collect_network_config", "query_recent_events"], []),
        ("VMware Tools not running", "vm_level", "warning", ["tools not running", "guest tools"], ["Guest service stopped", "VMware Tools outdated", "Guest OS hung"], ["detail", "event", "log"], ["collect_vm_detail", "query_recent_events"], ["vmware.vm_guest_restart"]),
        ("Guest OS heartbeat lost", "vm_level", "critical", ["guest heartbeat", "vm monitoring"], ["Guest OS hung", "VMware Tools failure", "HA VM monitoring restart"], ["detail", "event", "metric"], ["collect_vm_detail", "query_recent_events"], ["vmware.vm_guest_restart"]),
        ("VM powered off unexpectedly", "vm_level", "critical", ["powered off", "unexpected power off"], ["Manual power operation", "Guest shutdown", "HA or host failure"], ["event", "detail", "change"], ["collect_vm_detail", "query_recent_events"], ["vmware.vm_power_on"]),
        ("VM snapshot age high", "vm_level", "warning", ["old snapshot", "snapshot age"], ["Backup snapshot retained", "Manual snapshot forgotten", "Consolidation risk"], ["detail", "event", "metric"], ["query_snapshot_tree", "collect_datastore_usage"], ["vmware.vm_consolidate"]),
        ("VM disk latency high", "vm_level", "critical", ["vm disk latency", "guest disk latency"], ["Datastore contention", "Snapshot chain overhead", "Backend storage issue"], ["metric", "detail", "topology", "event"], ["collect_vm_metrics", "collect_datastore_latency"], ["vmware.storage_vmotion"]),
    ]
    return [_make_seed(i + 1, *row) for i, row in enumerate(rows)]


def _fixture_seed_alerts() -> list[AlertKnowledge]:
    path = REPO_DIR / "fixtures" / "knowledge" / "vmware_alerts" / "vmware_alert_knowledge.jsonl"
    if not path.exists():
        return []
    items: list[AlertKnowledge] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(AlertKnowledge(**json.loads(line)))
    return items


def _seed_if_empty() -> None:
    count = _query_one("SELECT COUNT(*) AS c FROM alert_knowledge")
    if count and int(count["c"]) > 0:
        return
    imported = 0
    seed_items = _fixture_seed_alerts()
    existing_ids = {item.id for item in seed_items}
    existing_keys = {(item.alert_name.lower(), item.vendor.lower(), item.category.lower()) for item in seed_items}
    seed_items.extend(
        [
            item
            for item in _seed_alerts()
            if item.id not in existing_ids and (item.alert_name.lower(), item.vendor.lower(), item.category.lower()) not in existing_keys
        ]
    )
    for item in seed_items:
        _upsert_alert(item, upsert=True)
        imported += 1
    job_id = "KIJ-SEED-VMWARE"
    now = _now()
    _exec(
        """
        INSERT OR REPLACE INTO knowledge_import_jobs(id,source_type,source_url,status,articles_imported,articles_failed,created,updated,failed,total,started_at,completed_at,error)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (job_id, "seed", "vmware-golden-alerts", "completed", imported, 0, imported, 0, 0, imported, now, now, None),
    )


def _terms(text: str) -> list[str]:
    return [x for x in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if len(x) >= 2]


def _evidence_source_type(evidence_name: str) -> str:
    value = evidence_name.lower()
    if value in {"event", "metric", "detail", "topology", "change", "kb", "log", "alert"}:
        return value
    if any(token in value for token in ("cpu", "memory", "usage", "latency", "balloon", "swap", "packet_loss", "free_space")):
        return "metric"
    if any(token in value for token in ("alarm", "alert")):
        return "alert"
    if any(token in value for token in ("event", "task", "backup", "maintenance", "vmotion")):
        return "event"
    if any(token in value for token in ("log", "hostd", "vpxa")):
        return "log"
    if any(token in value for token in ("topology", "network", "reachability", "state", "config", "evc", "vmk", "reservation", "snapshot", "consolidation")):
        return "detail"
    return "detail"


def _evidence_missing(required: list[str], present: set[str]) -> tuple[list[str], list[str]]:
    missing_detail: list[str] = []
    missing_types: set[str] = set()
    present_l = {item.lower() for item in present}
    for required_item in required:
        source_type = _evidence_source_type(required_item)
        if required_item.lower() not in present_l and source_type not in present_l:
            missing_detail.append(required_item)
            missing_types.add(source_type)
    return missing_detail, sorted(missing_types)


def _alert_blob(item: AlertKnowledge) -> str:
    return " ".join(
        [
            item.alert_name,
            item.vendor,
            item.domain,
            item.category,
            item.severity,
            " ".join(item.aliases),
            " ".join(item.symptoms),
            " ".join(item.possible_causes),
            " ".join(item.evidence_required),
            " ".join(item.evidence_optional),
            " ".join(item.tags),
            " ".join(item.match_keywords),
            " ".join(item.negative_keywords),
        ]
    ).lower()


def _score_alert(item: AlertKnowledge, body: AlertMatchRequest) -> tuple[float, str, list[str]]:
    query = " ".join(
        [
            body.alert_name or "",
            body.summary or "",
            body.description or "",
            body.severity or "",
            body.category or "",
            " ".join(f"{k} {v}" for k, v in body.labels.items()),
        ]
    ).strip()
    query_l = query.lower()
    blob = _alert_blob(item)
    score = item.trust_score * 0.45
    reasons: list[str] = []
    matched_fields: list[str] = []
    if body.vendor and body.vendor.lower() == item.vendor.lower():
        score += 0.08
        reasons.append("vendor matched")
        matched_fields.append("vendor")
    if body.category and body.category.lower() == item.category.lower():
        score += 0.12
        reasons.append("category matched")
        matched_fields.append("category")
    if body.severity and body.severity.lower() == item.severity.lower():
        score += 0.04
        reasons.append("severity matched")
        matched_fields.append("severity")
    if body.alert_name and body.alert_name.lower() == item.alert_name.lower():
        score += 0.35
        reasons.append("exact alert name matched")
        matched_fields.append("alert_name")
    elif body.alert_name and body.alert_name.lower() in blob:
        score += 0.22
        reasons.append("alert name matched knowledge text")
        matched_fields.append("alert_name")
    alias_hits = [a for a in item.aliases if a.lower() in query_l]
    if alias_hits:
        score += min(0.24, 0.08 * len(alias_hits))
        reasons.append(f"aliases matched: {', '.join(alias_hits[:3])}")
        matched_fields.append("aliases")
    keyword_hits = [kw for kw in item.match_keywords if kw and kw.lower() in query_l]
    if keyword_hits:
        score += min(0.24, 0.06 * len(keyword_hits))
        reasons.append(f"keywords matched: {', '.join(keyword_hits[:3])}")
        matched_fields.append("match_keywords")
    negative_hits = [kw for kw in item.negative_keywords if kw and kw.lower() in query_l]
    if negative_hits:
        score -= min(0.35, 0.12 * len(negative_hits))
        reasons.append(f"negative keywords matched: {', '.join(negative_hits[:3])}")
        matched_fields.append("negative_keywords")
    tag_hits = [tag for tag in item.tags if tag and tag.lower() in query_l]
    if tag_hits:
        score += min(0.12, 0.03 * len(tag_hits))
        reasons.append(f"tags matched: {', '.join(tag_hits[:3])}")
        matched_fields.append("tags")
    matched_terms = [term for term in _terms(query) if term in blob]
    if matched_terms:
        score += min(0.22, 0.025 * len(set(matched_terms)))
        reasons.append(f"terms matched: {len(set(matched_terms))}")
        matched_fields.append("text_terms")
    return round(max(0.0, min(score, 0.99)), 3), "; ".join(reasons) or "baseline trust score", list(dict.fromkeys(matched_fields))


def _list_alerts(
    status: str | None = None,
    vendor: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    tag: str | None = None,
    source_type: str | None = None,
    q: str | None = None,
) -> list[AlertKnowledge]:
    sql = "SELECT * FROM alert_knowledge WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND lower(status)=?"
        params.append(status.lower())
    if vendor:
        sql += " AND lower(vendor)=?"
        params.append(vendor.lower())
    if category:
        sql += " AND lower(category)=?"
        params.append(category.lower())
    if severity:
        sql += " AND lower(severity)=?"
        params.append(severity.lower())
    sql += " ORDER BY updated_at DESC, id ASC"
    items = [_row_to_alert(row) for row in _query_all(sql, tuple(params))]
    if tag:
        tag_l = tag.lower()
        items = [item for item in items if tag_l in {t.lower() for t in item.tags}]
    if source_type:
        items = [item for item in items if item.source.type.lower() == source_type.lower()]
    if q:
        q_l = q.lower()
        items = [item for item in items if q_l in _alert_blob(item)]
    return items


def _score_article(item: dict, q: str | None, domain: str | None, environment: str | None) -> tuple[float, str]:
    score = float(item.get("confidence_score") or 0.5)
    reasons: list[str] = []
    blob = f"{item.get('title', '')} {item.get('content_summary', '')} {' '.join(item.get('tags', []))}".lower()
    if q:
        matched = sum(1 for t in _terms(q) if t in blob)
        if matched:
            score += 0.07 * matched
            reasons.append(f"matched {matched} query terms")
    if domain and domain.lower() in blob:
        score += 0.08
        reasons.append(f"matched domain {domain}")
    if environment and environment.lower() in {"prod", "production"} and item.get("source") == "runbook":
        score += 0.03
        reasons.append("production runbook preferred")
    return min(score, 0.99), "; ".join(reasons) or "baseline relevance"


def _case_terms(text: str) -> set[str]:
    return {term for term in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if len(term) >= 2}


def _similar_cases_local(body: CaseSimilarBody) -> list[dict[str, Any]]:
    query_text = " ".join(
        [
            body.title or "",
            body.summary or "",
            body.category or "",
            body.root_cause_summary or "",
            " ".join(body.tags),
            " ".join(body.knowledge_refs),
        ]
    )
    query_terms = _case_terms(query_text)
    scored: list[dict[str, Any]] = []
    if not query_terms:
        return []
    for case in _CASES:
        fields = {
            "title": str(case.get("title") or ""),
            "summary": str(case.get("summary") or ""),
            "category": str(case.get("category") or ""),
            "root_cause_summary": str(case.get("root_cause_summary") or ""),
            "tags": " ".join(str(x) for x in case.get("tags") or []),
            "knowledge_refs": " ".join(str(x) for x in case.get("knowledge_refs") or []),
        }
        matched_fields: list[str] = []
        overlap = 0
        for field, value in fields.items():
            terms = _case_terms(value)
            if query_terms & terms:
                matched_fields.append(field)
                overlap += len(query_terms & terms)
        score = overlap / max(len(query_terms), 1)
        if body.category and body.category == case.get("category"):
            score += 0.18
            matched_fields.append("category")
        if set(body.knowledge_refs or []) & set(case.get("knowledge_refs") or []):
            score += 0.25
            matched_fields.append("knowledge_refs")
        if set(body.tags or []) & set(case.get("tags") or []):
            score += 0.12
            matched_fields.append("tags")
        if score <= 0:
            continue
        item = dict(case)
        item["similarity_score"] = round(min(score, 0.99), 3)
        item["matched_fields"] = list(dict.fromkeys(matched_fields))
        scored.append(item)
    scored.sort(key=lambda item: (item.get("similarity_score") or 0.0, item.get("hit_count") or 0), reverse=True)
    return scored[: max(1, min(int(body.limit or 5), 20))]


def _parse_prometheus_rules(content: str, source_url: str | None, publish: bool) -> list[AlertKnowledge]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency should be present in runtime
        raise HTTPException(status_code=500, detail="PyYAML is required for Prometheus rule import") from exc
    parsed = yaml.safe_load(content) or {}
    groups = parsed.get("groups") if isinstance(parsed, dict) else []
    items: list[AlertKnowledge] = []
    for group in groups or []:
        for rule in group.get("rules", []) or []:
            alert = str(rule.get("alert") or "").strip()
            if not alert:
                continue
            labels = rule.get("labels") if isinstance(rule.get("labels"), dict) else {}
            annotations = rule.get("annotations") if isinstance(rule.get("annotations"), dict) else {}
            severity = str(labels.get("severity") or "warning").lower()
            if severity not in {"info", "warning", "critical"}:
                severity = "critical" if severity in {"high", "page"} else "warning"
            summary = str(annotations.get("summary") or annotations.get("description") or alert)
            expr = str(rule.get("expr") or "")
            rule_id = re.sub(r"[^A-Za-z0-9]+", "-", alert).strip("-").lower() or uuid.uuid4().hex[:8]
            now = _now()
            items.append(
                AlertKnowledge(
                    id=f"AK-RULE-{rule_id}",
                    alert_name=alert,
                    vendor="prometheus",
                    domain="observability",
                    category="other",
                    severity=severity,  # type: ignore[arg-type]
                    aliases=[alert.lower()],
                    symptoms=[summary, f"Prometheus expression firing: {expr}"],
                    possible_causes=["Metric threshold crossed", "Service or infrastructure behavior changed"],
                    diagnostic_steps=["Inspect firing labels.", "Query the source metric around the firing window."],
                    decision_tree=["if source metric is still firing -> keep incident active", "if metric recovered -> check alert clear event"],
                    evidence_required=["metric", "alert", "event"],
                    remediation=["Follow linked runbook or service owner guidance."],
                    automation=AlertKnowledgeAutomation(safe_actions=["query_prometheus_metric"], approval_actions=[]),
                    source=AlertKnowledgeSource(
                        type="rule",
                        title=str(annotations.get("runbook_url") or source_url or "Prometheus rule"),
                        url=source_url,
                        trust_score=0.72,
                    ),
                    status="published" if publish else "draft",
                    version="1.0.0",
                    trust_score=0.72,
                    created_at=now,
                    updated_at=now,
                    tags=["prometheus", "rule", str(group.get("name") or "default")],
                )
            )
    return items


def _parse_import_content(body: KnowledgeImportValidateBody) -> tuple[list[AlertKnowledge], list[str]]:
    errors: list[str] = []
    raw_items: list[Any] = []
    if body.content_type == "prometheus_rules":
        try:
            return _parse_prometheus_rules(body.content, None, body.publish), []
        except Exception as exc:  # noqa: BLE001
            return [], [str(exc)]
    if body.content_type == "json":
        try:
            parsed = json.loads(body.content)
            raw_items = parsed.get("items", []) if isinstance(parsed, dict) and "items" in parsed else parsed
            if isinstance(raw_items, dict):
                raw_items = [raw_items]
        except json.JSONDecodeError as exc:
            return [], [f"invalid JSON: {exc}"]
    else:
        for idx, line in enumerate(body.content.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw_items.append(json.loads(line))
            except json.JSONDecodeError as exc:
                errors.append(f"line {idx}: {exc}")
    items: list[AlertKnowledge] = []
    for idx, raw in enumerate(raw_items, start=1):
        try:
            items.append(AlertKnowledge(**raw))
        except ValidationError as exc:
            errors.append(f"item {idx}: {exc.errors()}")
    return items, errors


def _job_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source_type": row["source_type"],
        "source_url": row["source_url"],
        "status": row["status"],
        "articles_imported": row["articles_imported"],
        "articles_failed": row["articles_failed"],
        "created": _row_get(row, "created", row["articles_imported"]),
        "updated": _row_get(row, "updated", 0),
        "failed": _row_get(row, "failed", row["articles_failed"]),
        "total": _row_get(row, "total", row["articles_imported"] + row["articles_failed"]),
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "error": row["error"],
    }


class AlertKnowledgeRepository:
    def upsert(self, item: AlertKnowledge, *, upsert: bool = True) -> tuple[AlertKnowledge, bool]:
        return _upsert_alert(item, upsert=upsert)

    def get(self, item_id: str) -> AlertKnowledge | None:
        row = _query_one("SELECT * FROM alert_knowledge WHERE id=?", (item_id,))
        return _row_to_alert(row) if row else None

    def list(self, filters: dict[str, Any]) -> list[AlertKnowledge]:
        return _list_alerts(**filters)

    def deprecate(self, item_id: str) -> AlertKnowledge | None:
        _exec("UPDATE alert_knowledge SET status='deprecated', updated_at=? WHERE id=?", (_now(), item_id))
        return self.get(item_id)


repository = AlertKnowledgeRepository()


@app.on_event("startup")
async def _startup() -> None:
    _init_db()
    _seed_if_empty()


_init_db()
_seed_if_empty()


@app.get("/health")
async def health() -> dict:
    return make_success({"status": "ok", "service": "knowledge-service", "version": "0.3.0"})


@app.get("/knowledge/articles")
async def list_articles(status: Optional[str] = None, q: Optional[str] = None, domain: Optional[str] = None, environment: Optional[str] = None) -> dict:
    data = _ARTICLES
    if status:
        data = [a for a in data if a["status"] == status]
    ranked: list[dict] = []
    for item in data:
        score, why = _score_article(item, q, domain, environment)
        enriched = dict(item)
        enriched["relevance_score"] = round(score, 3)
        enriched["why_selected"] = why
        enriched["citations"] = [{"article_id": item["id"], "title": item["title"], "relevance_score": round(score, 3), "why_selected": why}]
        ranked.append(enriched)
    ranked.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return make_success({"items": ranked, "total": len(ranked)})


@app.get("/knowledge/articles/{article_id}")
async def get_article(article_id: str) -> dict:
    item = next((a for a in _ARTICLES if a["id"] == article_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Article not found")
    return make_success(item)


@app.post("/knowledge/articles")
async def create_article(body: KnowledgeArticleCreateBody) -> dict:
    article = {
        "id": f"KB-MEM-{len(_ARTICLES) + 1:03d}",
        "title": body.title,
        "content_summary": body.content_summary,
        "source": body.source,
        "status": body.status,
        "tags": body.tags,
        "categories": [],
        "author": body.author,
        "version": "1.0.0",
        "hit_count": 0,
        "confidence_score": 0.8,
        "created_at": _now(),
        "updated_at": _now(),
        "related_incident_ids": [],
        "steps": body.steps,
    }
    _ARTICLES.append(article)
    return make_success(article)


@app.get("/knowledge/stats")
async def knowledge_stats() -> dict:
    items = _list_alerts()
    feedback_rows = _query_all("SELECT match_correct, created_at FROM knowledge_feedback")
    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for item in items:
        by_status[item.status] = by_status.get(item.status, 0) + 1
        by_category[item.category] = by_category.get(item.category, 0) + 1
    return make_success(
        {
            "total": len(items),
            "by_status": by_status,
            "by_category": by_category,
            "vmware_alert_knowledge": len([item for item in items if item.vendor.lower() == "vmware"]),
            "hit_count_total": sum(item.hit_count for item in items),
            "negative_feedback_total": len([row for row in feedback_rows if int(row["match_correct"]) == 0]),
        }
    )


@app.get("/knowledge/alert-items")
async def list_alert_items(
    status: str | None = None,
    vendor: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    tag: str | None = None,
    source_type: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    all_items = _list_alerts(status=status, vendor=vendor, category=category, severity=severity, tag=tag, source_type=source_type, q=q)
    safe_page = max(1, int(page or 1))
    safe_size = max(1, min(int(page_size or 50), 200))
    start = (safe_page - 1) * safe_size
    items = [item.model_dump() for item in all_items[start : start + safe_size]]
    return make_success({"items": items, "total": len(all_items), "page": safe_page, "page_size": safe_size})


@app.post("/knowledge/alert-items/{item_id}:deprecate")
@app.post("/knowledge/alert-items/{item_id}/deprecate")
async def deprecate_alert_item(item_id: str) -> dict:
    item = repository.deprecate(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="AlertKnowledge not found")
    return make_success({"item": item.model_dump()})


@app.get("/knowledge/alert-items/{item_id}")
async def get_alert_item(item_id: str) -> dict:
    row = _query_one("SELECT * FROM alert_knowledge WHERE id=?", (item_id,))
    if not row:
        raise HTTPException(status_code=404, detail="AlertKnowledge not found")
    return make_success(_row_to_alert(row).model_dump())


@app.post("/knowledge/alert-items")
async def upsert_alert_item(body: AlertKnowledge, upsert: bool = True) -> dict:
    item, created = _upsert_alert(body, upsert=upsert)
    return make_success({"item": item.model_dump(), "created": created})


@app.post("/knowledge/alert-items:bulk-import")
async def bulk_import_alert_items(body: AlertKnowledgeBulkImportBody) -> dict:
    job_id = f"KIJ-{uuid.uuid4().hex[:8].upper()}"
    started = _now()
    created_count = 0
    updated_count = 0
    failed = 0
    errors: list[str] = []
    for item in body.items:
        try:
            if not body.dry_run:
                _, created = repository.upsert(item, upsert=body.upsert)
            else:
                created = not repository.get(item.id)
            if created:
                created_count += 1
            else:
                updated_count += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append(f"{item.id}: {exc}")
    completed = _now()
    imported = created_count + updated_count
    status = "completed" if failed == 0 else "failed" if imported == 0 else "completed"
    if not body.dry_run:
        _exec(
            """
            INSERT INTO knowledge_import_jobs(id,source_type,source_url,status,articles_imported,articles_failed,created,updated,failed,total,started_at,completed_at,error)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                job_id,
                body.source_type,
                body.source_url,
                status,
                imported,
                failed,
                created_count,
                updated_count,
                failed,
                len(body.items),
                started,
                completed,
                "; ".join(errors[:3]) or None,
            ),
        )
    return make_success(
        {
            "id": job_id,
            "job_id": job_id,
            "status": "validated" if body.dry_run else status,
            "articles_imported": imported,
            "articles_failed": failed,
            "created": created_count,
            "updated": updated_count,
            "failed": failed,
            "total": len(body.items),
            "errors": errors,
        }
    )


@app.get("/knowledge/import-jobs")
async def list_import_jobs() -> dict:
    rows = _query_all("SELECT * FROM knowledge_import_jobs ORDER BY started_at DESC LIMIT 100")
    items = [_job_row(row) for row in rows]
    return make_success({"items": items, "total": len(items)})


@app.get("/knowledge/import-jobs/{job_id}")
async def get_import_job(job_id: str) -> dict:
    row = _query_one("SELECT * FROM knowledge_import_jobs WHERE id=?", (job_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Import job not found")
    return make_success(_job_row(row))


@app.post("/knowledge/import/validate")
async def validate_import(body: KnowledgeImportValidateBody) -> dict:
    items, errors = _parse_import_content(body)
    return make_success(
        {
            "valid": not errors,
            "items": [item.model_dump() for item in items[:50]],
            "total": len(items),
            "errors": errors,
            "created": len([item for item in items if repository.get(item.id) is None]),
            "updated": len([item for item in items if repository.get(item.id) is not None]),
        }
    )


@app.post("/knowledge/alert-match")
async def alert_match(body: AlertMatchRequest) -> dict:
    candidates = _list_alerts(status="published", vendor=body.vendor, category=body.category)
    scored: list[dict[str, Any]] = []
    present = set(body.evidence_present or [])
    for item in candidates:
        score, why, matched_fields = _score_alert(item, body)
        if score < 0.18:
            continue
        missing_detail, missing_types = _evidence_missing(item.evidence_required, present)
        missing = list(dict.fromkeys([*missing_detail, *missing_types]))
        scored.append(
            {
                "item": item,
                "relevance_score": score,
                "why_selected": why,
                "matched_fields": matched_fields,
                "missing_evidence": missing,
                "missing_critical_evidence": missing_detail,
            }
        )
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    top_k = max(1, min(int(body.top_k or 5), 20))
    top = scored[:top_k]
    for hit in top:
        _exec("UPDATE alert_knowledge SET hit_count=hit_count+1, updated_at=? WHERE id=?", (_now(), hit["item"].id))
    required = sorted({_evidence_source_type(ev) for hit in top[:3] for ev in hit["item"].evidence_required})
    missing_all = sorted({ev for hit in top[:3] for ev in hit["missing_evidence"]})
    missing_critical = sorted({ev for hit in top[:3] for ev in hit["missing_critical_evidence"]})
    diagnostic_steps = list(dict.fromkeys(step for hit in top[:3] for step in hit["item"].diagnostic_steps))[:12]
    safe_actions = list(dict.fromkeys(action for hit in top[:3] for action in hit["item"].automation.safe_actions))
    approval_actions = list(dict.fromkeys(action for hit in top[:3] for action in hit["item"].automation.approval_actions))
    why = "; ".join(hit["why_selected"] for hit in top[:2]) if top else "no published alert knowledge matched"
    similar_cases = _similar_cases_local(
        CaseSimilarBody(
            title=body.alert_name,
            summary=body.summary or body.description,
            category=top[0]["item"].category if top else body.category,
            tags=["vmware", *(top[0]["item"].tags if top else [])],
            knowledge_refs=[hit["item"].id for hit in top[:3]],
            limit=5,
        )
    )
    return make_success(
        {
            "matches": [
                {
                    "item": hit["item"].model_dump(),
                    "relevance_score": hit["relevance_score"],
                    "why_selected": hit["why_selected"],
                    "matched_fields": hit["matched_fields"],
                    "missing_evidence": hit["missing_evidence"],
                    "missing_critical_evidence": hit["missing_critical_evidence"],
                }
                for hit in top
            ],
            "missing_evidence": missing_all,
            "missing_critical_evidence": missing_critical,
            "required_evidence_types": required,
            "diagnostic_steps": diagnostic_steps,
            "safe_actions": safe_actions,
            "approval_actions": approval_actions,
            "similar_cases": similar_cases,
            "why_selected": why,
        }
    )


@app.post("/knowledge/feedback")
async def create_feedback(body: KnowledgeFeedbackBody) -> dict:
    feedback_id = f"KFB-{uuid.uuid4().hex[:8].upper()}"
    _exec(
        """
        INSERT INTO knowledge_feedback(id,alert_knowledge_id,incident_id,match_correct,actual_root_cause,missing_evidence_json,accepted_actions_json,comment,user_id,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            feedback_id,
            body.alert_knowledge_id,
            body.incident_id,
            1 if body.match_correct else 0,
            body.actual_root_cause,
            _json(body.missing_evidence),
            _json(body.accepted_actions),
            body.comment,
            body.user_id,
            _now(),
        ),
    )
    return make_success({"id": feedback_id, "created_at": _now()})


@app.post("/knowledge/importers/prometheus-rules")
async def import_prometheus_rules(body: PrometheusRulesImportBody) -> dict:
    try:
        items = _parse_prometheus_rules(body.content, body.source_url, body.publish)
        bulk = AlertKnowledgeBulkImportBody(items=items, source_type="prometheus_rules", upsert=body.upsert)
        return await bulk_import_alert_items(bulk)
    except ValidationError as exc:
        return make_error("invalid generated AlertKnowledge", data={"errors": exc.errors()})


@app.get("/cases")
async def list_cases(category: Optional[str] = None) -> dict:
    data = _CASES if not category else [c for c in _CASES if c["category"] == category]
    return make_success({"items": data, "total": len(data)})


@app.get("/cases/{case_id}")
async def get_case(case_id: str) -> dict:
    item = next((c for c in _CASES if c["id"] == case_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Case not found")
    return make_success(item)
