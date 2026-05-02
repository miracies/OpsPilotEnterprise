from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


LogBackendType = Literal["opensearch", "loki", "graylog", "elastic"]
LogAuthType = Literal["none", "basic", "token"]


class LogExternalLink(BaseModel):
    provider: str
    title: str
    url: str
    query: str | None = None
    kind: str = "search"


class LogSourceConfig(BaseModel):
    id: str
    name: str
    backend_type: LogBackendType = "opensearch"
    endpoint: str
    auth_type: LogAuthType = "none"
    username: str | None = None
    password: str | None = None
    token: str | None = None
    index_pattern: str = "opspilot-vmware-*"
    tenant: str | None = None
    tls_verify: bool = True
    default_time_window: int = 60
    max_result_limit: int = 200
    enabled: bool = True
    web_url: str | None = None


class LogSourcePublic(BaseModel):
    id: str
    name: str
    backend_type: LogBackendType
    endpoint: str
    auth_type: LogAuthType
    username: str | None = None
    index_pattern: str
    tenant: str | None = None
    tls_verify: bool
    default_time_window: int
    max_result_limit: int
    enabled: bool
    web_url: str | None = None
    has_secret: bool = False


class LogSourceUpsert(BaseModel):
    id: str | None = None
    name: str
    backend_type: LogBackendType = "opensearch"
    endpoint: str
    auth_type: LogAuthType = "none"
    username: str | None = None
    password: str | None = None
    token: str | None = None
    index_pattern: str = "opspilot-vmware-*"
    tenant: str | None = None
    tls_verify: bool = True
    default_time_window: int = 60
    max_result_limit: int = 200
    enabled: bool = True
    web_url: str | None = None


class LogTimeRange(BaseModel):
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None


class LogSearchRequest(BaseModel):
    backend: LogBackendType | None = None
    source_id: str | None = None
    time_range: LogTimeRange | None = None
    filters: dict[str, Any] = {}
    query: str | None = None
    limit: int = 100


class LogItem(BaseModel):
    log_id: str
    timestamp: str
    source: str
    product: str | None = None
    component: str | None = None
    severity: str | None = None
    message: str
    raw_message: str
    fields: dict[str, Any] = {}
    backend: LogBackendType
    index: str | None = None
    document_id: str | None = None
    external_links: list[LogExternalLink] = []


class LogSearchResponse(BaseModel):
    total: int
    items: list[LogItem] = []
    backend: LogBackendType | None = None
    source_id: str | None = None
    queries_executed: list[str] = []


class VMwareLogTimeWindow(BaseModel):
    before_minutes: int = 30
    after_minutes: int = 10


class VMwareLogContextQuery(BaseModel):
    incident_id: str | None = None
    vcenter: str | None = None
    host: str | None = None
    vm_name: str | None = None
    vm_moid: str | None = None
    datastore: str | None = None
    time_window: VMwareLogTimeWindow = Field(default_factory=VMwareLogTimeWindow)
    scenario: str = "vm_overall_status_red"
    timestamp: str | None = None
    limit: int = 100


class LogContextGroup(BaseModel):
    name: str
    count: int
    items: list[LogItem] = []


class LogContextResponse(BaseModel):
    incident_id: str | None = None
    queries_executed: list[str] = []
    groups: list[LogContextGroup] = []


class LogEvidenceRequest(BaseModel):
    incident_id: str
    log_ids: list[str]
    evidence_type: str = "raw_log"
    comment: str | None = None

