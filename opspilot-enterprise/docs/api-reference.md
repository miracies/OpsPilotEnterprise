# OpsPilot Enterprise API Reference

## 通用约定

### 统一响应 Envelope

所有 API 返回统一格式：

```json
{
  "request_id": "req-abc123",
  "success": true,
  "message": "ok",
  "data": {},
  "error": null,
  "audit_ref": null,
  "trace_id": "trace-def456",
  "timestamp": "2026-04-05T09:00:00+00:00"
}
```

### 服务端口分配

| 服务 | 端口 | 描述 |
|------|------|------|
| API BFF | 8000 | 前端聚合层 |
| LangGraph Orchestrator | 8010 | Agent 编排服务 |
| Tool Gateway | 8020 | 统一工具控制面 |
| VMware Skill Gateway | 8030 | VMware 领域服务 |
| Change Impact Service | 8040 | 变更影响分析 |
| Evidence Aggregator | 8050 | 证据聚合 |
| Event Ingestion Service | 8060 | 事件接入 |

---

## API BFF (Port 8000)

BFF 层聚合前端所需的所有 API，前端只需与 BFF 通信。

### 健康检查
```
GET /health
```

### Chat

```
POST /api/v1/chat/sessions
Body: { "title": "string" }
Response: { "id", "title", "created_at", "updated_at", "tags", "message_count" }

POST /api/v1/chat/sessions/{session_id}/messages
Body: { "message": "string" }
Response: AI 回复（通过 Orchestrator）

GET /api/v1/chat/sessions/{session_id}
GET /api/v1/chat/sessions/{session_id}/evidence
GET /api/v1/chat/sessions/{session_id}/tool-traces
```

### Incidents

```
GET /api/v1/incidents
Response: { "incidents": [Incident] }

GET /api/v1/incidents/{incident_id}
Response: Incident

POST /api/v1/incidents/{incident_id}/analyze
Response: { "status": "queued", "message": "..." }
```

### Change Impact

```
POST /api/v1/change-impact/analyze
Body: {
  "change_type": "string",
  "target_type": "string",
  "target_id": "string",
  "requested_action": "string",
  "environment": "string"
}
Response: ChangeImpactResult
```

### Tools

```
GET /api/v1/tools
Response: [ToolMeta]

GET /api/v1/tools/health
Response: [ToolHealthStatus]
```

---

## Tool Gateway (Port 8020)

统一工具控制面，所有工具调用必须经过此网关。

### 工具管理

```
GET  /api/v1/tools/          → 列出已注册工具
GET  /api/v1/tools/{name}    → 按名查询工具
GET  /api/v1/tools/health    → 工具健康状态
POST /api/v1/tools/register  → 注册新工具
POST /api/v1/tools/unregister → 注销工具
```

### 工具调用

```
POST /api/v1/invoke/{tool_name}
Body: { "input": {}, "dry_run": false }
Response Headers: X-Request-Id, X-Trace-Id
```

路由规则：
- `vmware.*` → VMware Skill Gateway
- `change_impact.*` → Change Impact Service
- 其他 → mock 响应

---

## VMware Skill Gateway (Port 8030)

VMware 领域查询与受控执行接口。

### 查询

```
POST /api/v1/query/get_vcenter_inventory
POST /api/v1/query/get_vm_detail        Body: { "vm_id": "string" }
POST /api/v1/query/get_host_detail      Body: { "host_id": "string" }
POST /api/v1/query/get_cluster_detail   Body: { "cluster_id": "string" }
POST /api/v1/query/query_events         Body: { "object_id": "string", "hours": int }
POST /api/v1/query/query_metrics        Body: { "object_id": "string", "metric": "string" }
POST /api/v1/query/query_alerts
POST /api/v1/query/query_topology
```

### 执行

```
POST /api/v1/execute/create_snapshot    Body: { "vm_id": "string", "name": "string" }
POST /api/v1/execute/vm_migrate         Body: { "vm_id": "string", "target_host_id": "string", "dry_run": bool }
POST /api/v1/execute/vm_power_on        Body: { "vm_id": "string" }
POST /api/v1/execute/vm_power_off       Body: { "vm_id": "string" }
POST /api/v1/execute/vm_guest_restart   Body: { "vm_id": "string" }
```

---

## Change Impact Service (Port 8040)

```
POST /api/v1/change-impact/analyze
Body: ChangeImpactRequest
Response: ChangeImpactResult {
  analysis_id, target, action,
  risk_score, risk_level,
  impacted_objects, checks_required,
  rollback_plan, approval_suggestion,
  dependency_graph
}
```

---

## Evidence Aggregator (Port 8050)

```
POST /api/v1/evidence/aggregate
Body: { "incident_id": "string", "source_refs": ["string"] }
Response: EvidencePackage

GET /api/v1/evidence/{evidence_id}
Response: Evidence
```

---

## Event Ingestion Service (Port 8060)

```
POST /api/v1/events/ingest
Body: { "source", "source_type", "object_type", "object_id", "severity", "summary" }
Response: NormalizedEvent

GET /api/v1/incidents
GET /api/v1/incidents/{incident_id}
POST /api/v1/incidents/{incident_id}/analyze
```

---

## LangGraph Orchestrator (Port 8010)

```
POST /api/v1/orchestrate/diagnose
Body: { "description": "string", "object_id": "string" }
Response: 根因候选、证据、建议动作

POST /api/v1/orchestrate/change-impact
Body: ChangeImpactRequest
Response: ChangeImpactResult (转发至 Change Impact Service)

POST /api/v1/orchestrate/chat
Body: { "session_id": "string", "message": "string" }
Response: AI 助手回复
```

---

## 数据模型

### Evidence
| 字段 | 类型 | 说明 |
|------|------|------|
| evidence_id | string | 证据ID |
| source | string | 来源系统 |
| source_type | enum | event/metric/log/topology/kb/change/external_kb |
| object_type | string | 对象类型 |
| object_id | string | 对象ID |
| timestamp | string | ISO 时间戳 |
| summary | string | 摘要 |
| confidence | float | 置信度 (0-1) |

### Incident
| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 事件ID |
| title | string | 标题 |
| status | enum | new/analyzing/pending_action/resolved/archived |
| severity | enum | critical/high/medium/low/info |
| affected_objects | array | 受影响对象列表 |
| root_cause_candidates | array | 根因候选列表 |
| recommended_actions | array | 建议动作 |

### ToolMeta
| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 工具全名 (domain.tool_name) |
| action_type | enum | read/write/dangerous |
| risk_level | enum | low/medium/high/critical |
| approval_required | bool | 是否需要审批 |
| provider | string | 提供者 (Gateway 名) |
