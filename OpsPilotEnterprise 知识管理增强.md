下面是一份可以直接丢给 **Codex / Copilot Coding Agent** 的开发说明。目标是把 OpsPilotEnterprise 的“知识管理”从传统文档 RAG，升级为面向 VMware 告警诊断的 **结构化知识 + 证据编排 + 案例复用** 能力。

---

# OpsPilotEnterprise 知识管理增强：Codex 开发需求与架构需求

## 1. 开发目标

在现有 OpsPilotEnterprise 项目基础上，增强“知识管理”模块，使其不只是上传文档、检索文档，而是能够支撑 VMware 告警的准确诊断。

目标能力包括：

```text
1. 支持导入结构化 VMware 告警知识
2. 支持告警文本 / 事件上下文匹配 AlertKnowledge
3. 支持按告警类型生成证据需求清单
4. 支持与 Evidence Aggregator 联动，判断证据是否充分
5. 支持相似历史案例召回
6. 支持输出根因分析建议、缺失证据、处理步骤和自动化动作建议
7. 支持人工反馈，持续优化知识命中效果
```

不要把重点放在“硬件传感器类告警”。第一阶段优先覆盖可观测性更强的 VMware 常见告警：

```text
CPU / Memory 资源类告警
HA / 集群类告警
vMotion / DRS 类告警
Datastore / Snapshot / vSAN 存储类告警
Host disconnected / 网络类告警
VMware Tools / VM Monitoring / Consolidation Needed 类告警
```

---

# 2. 当前架构改造原则

## 2.1 保持现有模块边界

不要重写整个平台。建议在现有模块上增强：

```text
services/
├── knowledge-service          # 增强为结构化知识服务
├── evidence-aggregator        # 接收知识侧 evidence_required
├── langgraph-orchestrator     # 增加知识驱动诊断节点
├── tool-gateway               # 映射 safe_actions / approval_actions
└── bff / frontend             # 增加知识管理页面和验证页面
```

## 2.2 核心架构变化

从：

```text
用户问题 / 告警
   ↓
文档检索
   ↓
LLM 总结
```

升级为：

```text
告警 / 事件 / 用户问题
   ↓
AlertKnowledge 匹配
   ↓
Evidence Contract 生成
   ↓
Evidence Aggregator 采集与评分
   ↓
Case Memory 相似案例召回
   ↓
RootCause Agent 证据约束推理
   ↓
Remediation / Automation 建议
   ↓
人工反馈 / 案例归档
```

---

# 3. 新增核心对象：AlertKnowledge

## 3.1 新增数据模型

新增文件建议：

```text
packages/shared-schema/opspilot/schema/alert_knowledge.py
```

或按当前项目结构放入已有 shared-schema 包中。

### Pydantic 模型要求

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class AlertCategory(str, Enum):
    resource = "resource"
    ha_cluster = "ha_cluster"
    vmotion_drs = "vmotion_drs"
    storage = "storage"
    network = "network"
    vm_level = "vm_level"
    other = "other"


class AlertSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class KnowledgeStatus(str, Enum):
    draft = "draft"
    published = "published"
    deprecated = "deprecated"


class KnowledgeSource(BaseModel):
    type: Literal["manual", "rule", "kb", "case", "external"]
    title: str
    url: Optional[str] = None
    trust_score: float = Field(default=0.8, ge=0.0, le=1.0)


class AutomationMapping(BaseModel):
    safe_actions: list[str] = Field(default_factory=list)
    approval_actions: list[str] = Field(default_factory=list)
    suppression_window: Optional[str] = None


class DecisionRule(BaseModel):
    condition: str
    conclusion: str
    confidence_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    required_evidence: list[str] = Field(default_factory=list)


class AlertKnowledge(BaseModel):
    id: str
    alert_name: str
    aliases: list[str] = Field(default_factory=list)
    category: AlertCategory
    severity: AlertSeverity

    symptoms: list[str]
    possible_causes: list[str]
    diagnostic_steps: list[str]
    decision_tree: list[DecisionRule]
    remediation: list[str]

    evidence_required: list[str]
    evidence_optional: list[str] = Field(default_factory=list)

    automation: AutomationMapping

    tags: list[str] = Field(default_factory=list)
    source: KnowledgeSource
    status: KnowledgeStatus = KnowledgeStatus.draft
    version: str = "1.0.0"
    updated_at: datetime

    case_refs: list[str] = Field(default_factory=list)
    knowledge_refs: list[str] = Field(default_factory=list)

    match_keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)

    owner: Optional[str] = None
    reviewer: Optional[str] = None
    review_notes: Optional[str] = None
```

---

# 4. 新增知识数据示例

新增目录：

```text
fixtures/knowledge/vmware_alerts/
```

新增文件：

```text
fixtures/knowledge/vmware_alerts/vmware_alert_knowledge.jsonl
```

第一阶段至少内置 6 条 golden knowledge。

## 4.1 VM CPU Usage

```json
{
  "id": "vmware.vm.cpu_usage.high.v1",
  "alert_name": "Virtual machine CPU usage",
  "aliases": ["VM CPU usage high", "VM CPU High", "虚拟机 CPU 使用率高"],
  "category": "resource",
  "severity": "critical",
  "symptoms": [
    "VM CPU usage is higher than threshold",
    "CPU Ready may increase",
    "Application response becomes slow"
  ],
  "possible_causes": [
    "Guest OS application consumes high CPU",
    "Host CPU contention",
    "vCPU over-provisioning",
    "CPU limit or reservation misconfiguration",
    "VM was recently migrated to a busy host"
  ],
  "diagnostic_steps": [
    "Collect VM CPU usage, CPU Ready and Co-Stop metrics",
    "Collect host CPU usage and top VM CPU consumers",
    "Check VM CPU limit, reservation and shares",
    "Check recent vMotion and DRS events",
    "Check VMware Tools status and guest OS process evidence if available"
  ],
  "decision_tree": [
    {
      "condition": "vm.cpu.usage > 90 and vm.cpu.ready < 5",
      "conclusion": "Likely guest workload spike",
      "confidence_delta": 0.25,
      "required_evidence": ["vm.cpu.usage", "vm.cpu.ready"]
    },
    {
      "condition": "vm.cpu.usage > 90 and vm.cpu.ready >= 5",
      "conclusion": "Likely host CPU contention or vCPU over-provisioning",
      "confidence_delta": 0.35,
      "required_evidence": ["vm.cpu.usage", "vm.cpu.ready", "host.cpu.usage"]
    }
  ],
  "remediation": [
    "Identify and validate high CPU process inside guest OS",
    "Migrate VM to a less busy host after approval",
    "Review vCPU sizing, CPU limit and reservation",
    "Review DRS automation level and cluster capacity"
  ],
  "evidence_required": [
    "vm.cpu.usage",
    "vm.cpu.ready",
    "host.cpu.usage",
    "vm.cpu.config",
    "recent.vmotion.events"
  ],
  "evidence_optional": [
    "guest.process.cpu",
    "cluster.drs.config"
  ],
  "automation": {
    "safe_actions": [
      "vmware.collect_vm_cpu_metrics",
      "vmware.collect_host_cpu_metrics",
      "vmware.query_recent_events"
    ],
    "approval_actions": [
      "vmware.vm.migrate"
    ]
  },
  "tags": ["vmware", "cpu", "vm", "resource"],
  "source": {
    "type": "manual",
    "title": "OpsPilot VMware CPU High Runbook",
    "trust_score": 0.9
  },
  "status": "published",
  "version": "1.0.0",
  "updated_at": "2026-04-30T00:00:00Z",
  "match_keywords": ["cpu usage", "cpu high", "cpu ready", "虚拟机cpu"]
}
```

## 4.2 Host Memory Usage

```json
{
  "id": "vmware.host.memory_usage.high.v1",
  "alert_name": "Host Memory Usage",
  "aliases": ["Host memory usage high", "ESXi memory high", "主机内存使用率高"],
  "category": "resource",
  "severity": "warning",
  "symptoms": [
    "Host memory usage is higher than threshold",
    "Active memory may not be high",
    "Ballooning or swapping may occur"
  ],
  "possible_causes": [
    "Configured memory is high but active memory is low",
    "Memory overcommitment",
    "Ballooning or swapping",
    "Large VM reservation",
    "Cluster imbalance"
  ],
  "diagnostic_steps": [
    "Collect host consumed memory, active memory, balloon and swap metrics",
    "Collect VM configured memory and active memory",
    "Check VM reservations",
    "Check recent DRS and vMotion events"
  ],
  "decision_tree": [
    {
      "condition": "host.memory.usage > 90 and host.memory.active < 60",
      "conclusion": "Likely high allocated memory rather than real pressure",
      "confidence_delta": 0.25,
      "required_evidence": ["host.memory.usage", "host.memory.active"]
    },
    {
      "condition": "host.memory.balloon > 0 or host.memory.swap > 0",
      "conclusion": "Likely real memory pressure",
      "confidence_delta": 0.35,
      "required_evidence": ["host.memory.balloon", "host.memory.swap"]
    }
  ],
  "remediation": [
    "Do not expand capacity before verifying active memory and ballooning",
    "Review VM memory right-sizing",
    "Migrate selected VMs if host memory pressure is confirmed",
    "Review alert threshold if it repeatedly fires without real pressure"
  ],
  "evidence_required": [
    "host.memory.usage",
    "host.memory.active",
    "host.memory.balloon",
    "host.memory.swap",
    "vm.memory.config"
  ],
  "evidence_optional": [
    "vm.memory.reservation",
    "recent.drs.events"
  ],
  "automation": {
    "safe_actions": [
      "vmware.collect_host_memory_metrics",
      "vmware.collect_vm_memory_summary"
    ],
    "approval_actions": [
      "vmware.vm.migrate"
    ]
  },
  "tags": ["vmware", "memory", "host", "resource"],
  "source": {
    "type": "manual",
    "title": "OpsPilot VMware Host Memory Runbook",
    "trust_score": 0.9
  },
  "status": "published",
  "version": "1.0.0",
  "updated_at": "2026-04-30T00:00:00Z",
  "match_keywords": ["memory usage", "host memory", "balloon", "swap", "主机内存"]
}
```

## 4.3 HA Failover Resources

```json
{
  "id": "vmware.cluster.ha_failover_resources.insufficient.v1",
  "alert_name": "Insufficient HA failover resources",
  "aliases": ["HA failover resources insufficient", "HA资源不足", "Admission Control warning"],
  "category": "ha_cluster",
  "severity": "warning",
  "symptoms": [
    "HA admission control cannot satisfy failover policy",
    "Cluster does not have enough failover resources"
  ],
  "possible_causes": [
    "Not enough hosts in cluster",
    "High VM reservations",
    "Failover level is configured too high",
    "Host is in maintenance or disconnected state"
  ],
  "diagnostic_steps": [
    "Collect HA admission control configuration",
    "Collect cluster host count and host state",
    "Collect VM CPU and memory reservations",
    "Check recent maintenance events"
  ],
  "decision_tree": [
    {
      "condition": "cluster.host.available_count < cluster.ha.required_count",
      "conclusion": "Insufficient physical hosts for configured HA policy",
      "confidence_delta": 0.35,
      "required_evidence": ["cluster.host.available_count", "cluster.ha.config"]
    },
    {
      "condition": "vm.reservation.total is high",
      "conclusion": "VM reservations reduce HA failover capacity",
      "confidence_delta": 0.3,
      "required_evidence": ["vm.reservations", "cluster.ha.config"]
    }
  ],
  "remediation": [
    "Add host capacity or recover unavailable hosts",
    "Review HA failover policy",
    "Review unnecessary VM reservations",
    "Align HA policy with business SLA"
  ],
  "evidence_required": [
    "cluster.ha.config",
    "cluster.host.state",
    "vm.reservations",
    "maintenance.events"
  ],
  "automation": {
    "safe_actions": [
      "vmware.collect_cluster_ha_config",
      "vmware.collect_host_state",
      "vmware.collect_vm_reservations"
    ],
    "approval_actions": []
  },
  "tags": ["vmware", "ha", "cluster", "admission-control"],
  "source": {
    "type": "manual",
    "title": "OpsPilot VMware HA Runbook",
    "trust_score": 0.9
  },
  "status": "published",
  "version": "1.0.0",
  "updated_at": "2026-04-30T00:00:00Z",
  "match_keywords": ["ha failover", "admission control", "failover resources", "HA资源"]
}
```

## 4.4 vMotion Failure

```json
{
  "id": "vmware.vmotion.failure.v1",
  "alert_name": "vMotion compatibility / timeout failure",
  "aliases": ["vMotion failed", "Migration failed", "vMotion timeout", "vMotion兼容性失败"],
  "category": "vmotion_drs",
  "severity": "critical",
  "symptoms": [
    "vMotion task failed",
    "Compatibility check failed",
    "Migration timeout occurred"
  ],
  "possible_causes": [
    "vMotion VMkernel configuration issue",
    "VLAN, subnet or routing issue",
    "MTU mismatch",
    "CPU or EVC incompatibility",
    "Network bandwidth or latency issue",
    "DRS rule conflict"
  ],
  "diagnostic_steps": [
    "Collect source and destination VMkernel configuration",
    "Validate vMotion network connectivity",
    "Check MTU path with vmkping if available",
    "Check EVC and CPU compatibility",
    "Check DRS rules and recent migration events"
  ],
  "decision_tree": [
    {
      "condition": "error contains vmkernel or network",
      "conclusion": "Likely vMotion VMkernel or network configuration issue",
      "confidence_delta": 0.35,
      "required_evidence": ["vmk.config", "vmotion.events"]
    },
    {
      "condition": "error contains cpu or compatibility",
      "conclusion": "Likely CPU/EVC compatibility issue",
      "confidence_delta": 0.35,
      "required_evidence": ["cluster.evc", "host.cpu.compatibility"]
    },
    {
      "condition": "error contains timeout",
      "conclusion": "Likely MTU, packet loss, bandwidth or storage latency issue",
      "confidence_delta": 0.25,
      "required_evidence": ["network.mtu.path", "packet_loss_test", "datastore.latency"]
    }
  ],
  "remediation": [
    "Fix vMotion VMkernel network configuration",
    "Align VLAN, subnet and MTU settings",
    "Enable or adjust EVC when appropriate",
    "Retry vMotion after approval"
  ],
  "evidence_required": [
    "vmotion.events",
    "vmk.config",
    "network.mtu.path",
    "cluster.evc",
    "host.cpu.compatibility"
  ],
  "evidence_optional": [
    "packet_loss_test",
    "datastore.latency",
    "drs.rules"
  ],
  "automation": {
    "safe_actions": [
      "vmware.collect_vmkernel_config",
      "vmware.query_vmotion_events",
      "vmware.collect_evc_config"
    ],
    "approval_actions": [
      "vmware.vm.retry_vmotion"
    ]
  },
  "tags": ["vmware", "vmotion", "drs", "network"],
  "source": {
    "type": "manual",
    "title": "OpsPilot VMware vMotion Failure Runbook",
    "trust_score": 0.9
  },
  "status": "published",
  "version": "1.0.0",
  "updated_at": "2026-04-30T00:00:00Z",
  "match_keywords": ["vmotion failed", "migration failed", "compatibility", "timeout", "迁移失败"]
}
```

## 4.5 Datastore / Snapshot

```json
{
  "id": "vmware.datastore.usage.snapshot.v1",
  "alert_name": "Datastore usage on disk / Consolidation Needed",
  "aliases": ["Datastore usage high", "Consolidation Needed", "Snapshot consolidation failed", "数据存储空间不足"],
  "category": "storage",
  "severity": "warning",
  "symptoms": [
    "Datastore usage exceeds threshold",
    "VM shows Consolidation Needed",
    "Snapshot consolidation failed"
  ],
  "possible_causes": [
    "Snapshot chain growth",
    "Insufficient datastore free space",
    "Backup job left stale snapshots",
    "Large VM disk growth",
    "vSAN capacity pressure"
  ],
  "diagnostic_steps": [
    "Collect datastore usage and free space",
    "Collect VM snapshot tree and delta disk size",
    "Check recent backup and snapshot tasks",
    "Check vSAN capacity health if datastore is vSAN",
    "Check whether consolidation requires additional free space"
  ],
  "decision_tree": [
    {
      "condition": "datastore.usage >= 75 and snapshot_tree.empty",
      "conclusion": "Likely datastore capacity growth without snapshot root cause",
      "confidence_delta": 0.2,
      "required_evidence": ["datastore.usage", "vm.snapshot.tree"]
    },
    {
      "condition": "consolidation_needed == true and datastore.free_space insufficient",
      "conclusion": "Consolidation blocked by insufficient free space",
      "confidence_delta": 0.35,
      "required_evidence": ["vm.consolidation.status", "datastore.free_space"]
    },
    {
      "condition": "snapshot delta size is large and backup job failed recently",
      "conclusion": "Likely backup-created snapshot residue",
      "confidence_delta": 0.35,
      "required_evidence": ["vm.snapshot.tree", "backup.jobs"]
    }
  ],
  "remediation": [
    "Do not delete VMDK files manually",
    "Confirm backup job status before consolidation",
    "Reserve enough free space before snapshot consolidation",
    "Migrate cold VMs or expand datastore if capacity is insufficient",
    "Run snapshot consolidation after approval"
  ],
  "evidence_required": [
    "datastore.usage",
    "datastore.free_space",
    "vm.snapshot.tree",
    "vm.consolidation.status",
    "recent.backup.jobs"
  ],
  "evidence_optional": [
    "vsan.capacity.health",
    "datastore.latency"
  ],
  "automation": {
    "safe_actions": [
      "vmware.collect_datastore_usage",
      "vmware.collect_snapshot_tree",
      "vmware.collect_recent_tasks"
    ],
    "approval_actions": [
      "vmware.vm.snapshot_consolidate",
      "vmware.vm.storage_vmotion"
    ]
  },
  "tags": ["vmware", "datastore", "snapshot", "storage"],
  "source": {
    "type": "manual",
    "title": "OpsPilot VMware Datastore and Snapshot Runbook",
    "trust_score": 0.9
  },
  "status": "published",
  "version": "1.0.0",
  "updated_at": "2026-04-30T00:00:00Z",
  "match_keywords": ["datastore usage", "consolidation needed", "snapshot", "delta", "数据存储"]
}
```

## 4.6 Host Disconnected

```json
{
  "id": "vmware.host.connection.not_responding.v1",
  "alert_name": "Host connection and power state",
  "aliases": ["Host disconnected", "Host not responding", "ESXi主机断连", "DVS out of sync"],
  "category": "network",
  "severity": "critical",
  "symptoms": [
    "ESXi host is disconnected or not responding in vCenter",
    "vCenter cannot communicate with ESXi host",
    "DVS may be out of sync"
  ],
  "possible_causes": [
    "Management network interruption",
    "vCenter to ESXi heartbeat loss",
    "hostd or vpxa issue",
    "DNS or routing problem",
    "DVS or physical switch configuration issue",
    "vCenter-side issue if multiple hosts disconnect simultaneously"
  ],
  "diagnostic_steps": [
    "Check whether single host or multiple hosts are affected",
    "Check vCenter to ESXi management connectivity",
    "Collect hostd, vpxa and vobd events if available",
    "Check vmk0, pNIC and switch port configuration",
    "Check recent network changes"
  ],
  "decision_tree": [
    {
      "condition": "multiple hosts disconnected at same time",
      "conclusion": "Likely vCenter-side, DNS or shared management network issue",
      "confidence_delta": 0.3,
      "required_evidence": ["host.connection.events", "vcenter.health", "network.change.events"]
    },
    {
      "condition": "host reachable by OOB but not by vCenter",
      "conclusion": "Likely management network or host management agent issue",
      "confidence_delta": 0.3,
      "required_evidence": ["host.oob.status", "management.network.reachability"]
    },
    {
      "condition": "dvs out of sync detected",
      "conclusion": "Likely DVS configuration synchronization issue",
      "confidence_delta": 0.25,
      "required_evidence": ["dvs.sync.status", "vmk0.binding"]
    }
  ],
  "remediation": [
    "Recover management network connectivity first",
    "Avoid rebooting ESXi before confirming VM runtime state",
    "Restart management agents only after risk assessment",
    "Fix DVS or physical switch configuration after approval"
  ],
  "evidence_required": [
    "host.connection.events",
    "management.network.reachability",
    "hostd.logs",
    "vpxa.logs",
    "vmk0.binding",
    "recent.network.changes"
  ],
  "evidence_optional": [
    "host.oob.status",
    "dvs.sync.status"
  ],
  "automation": {
    "safe_actions": [
      "vmware.collect_host_connection_events",
      "vmware.collect_management_nic_state",
      "vmware.query_recent_network_changes"
    ],
    "approval_actions": [
      "vmware.host.restart_management_agents",
      "vmware.host.enter_maintenance_mode"
    ]
  },
  "tags": ["vmware", "host", "network", "disconnected"],
  "source": {
    "type": "manual",
    "title": "OpsPilot VMware Host Disconnected Runbook",
    "trust_score": 0.9
  },
  "status": "published",
  "version": "1.0.0",
  "updated_at": "2026-04-30T00:00:00Z",
  "match_keywords": ["host disconnected", "not responding", "connection and power state", "DVS out of sync", "主机断连"]
}
```

---

# 5. Knowledge Service 后端需求

## 5.1 新增 API

在 `knowledge-service` 中新增以下接口。

### 5.1.1 新增或更新 AlertKnowledge

```http
POST /api/v1/knowledge/alert-items
```

请求：

```json
{
  "item": {},
  "upsert": true
}
```

响应：

```json
{
  "success": true,
  "id": "vmware.vm.cpu_usage.high.v1",
  "status": "published",
  "version": "1.0.0"
}
```

要求：

```text
1. 校验 AlertKnowledge schema
2. 如果 upsert=true，同 id 则覆盖
3. 如果 upsert=false，同 id 返回 409
4. 写入本地 JSON 存储或 SQLite/PostgreSQL，视当前项目持久化方式决定
5. 写入后刷新全文索引 / 内存索引
```

---

### 5.1.2 批量导入 AlertKnowledge

```http
POST /api/v1/knowledge/alert-items:bulk-import
```

请求：

```json
{
  "items": [],
  "upsert": true,
  "source_name": "vmware-golden-alerts"
}
```

响应：

```json
{
  "success": true,
  "job_id": "import-20260430-001",
  "total": 6,
  "created": 6,
  "updated": 0,
  "failed": 0,
  "errors": []
}
```

要求：

```text
1. 支持一次导入多条 AlertKnowledge
2. 每条独立校验
3. 部分失败不影响成功项
4. 记录 import job
5. import job 可以查询
```

---

### 5.1.3 查询导入任务

```http
GET /api/v1/knowledge/import-jobs
GET /api/v1/knowledge/import-jobs/{job_id}
```

响应：

```json
{
  "job_id": "import-20260430-001",
  "source_name": "vmware-golden-alerts",
  "status": "completed",
  "total": 6,
  "created": 6,
  "updated": 0,
  "failed": 0,
  "started_at": "2026-04-30T00:00:00Z",
  "finished_at": "2026-04-30T00:00:03Z",
  "errors": []
}
```

---

### 5.1.4 告警匹配知识

```http
POST /api/v1/knowledge/alert-match
```

请求：

```json
{
  "alert_name": "Host connection and power state",
  "summary": "esxi-03 not responding in vCenter",
  "object_type": "host",
  "object_name": "esxi-03",
  "labels": {
    "cluster": "prod-b",
    "vcenter": "vcsa-prod-01"
  },
  "top_k": 3
}
```

响应：

```json
{
  "matches": [
    {
      "id": "vmware.host.connection.not_responding.v1",
      "alert_name": "Host connection and power state",
      "category": "network",
      "score": 0.92,
      "why_selected": [
        "Exact alert_name matched",
        "Keyword matched: not responding",
        "Object type matched: host"
      ],
      "evidence_required": [
        "host.connection.events",
        "management.network.reachability",
        "hostd.logs",
        "vpxa.logs",
        "vmk0.binding",
        "recent.network.changes"
      ],
      "safe_actions": [
        "vmware.collect_host_connection_events",
        "vmware.collect_management_nic_state"
      ],
      "approval_actions": [
        "vmware.host.restart_management_agents",
        "vmware.host.enter_maintenance_mode"
      ]
    }
  ]
}
```

匹配算法第一阶段可以采用：

```text
score = alert_name_exact_match * 0.4
      + aliases_match * 0.2
      + keyword_match * 0.2
      + category_hint_match * 0.1
      + tag_match * 0.1
```

后续再接向量检索。第一阶段不要强依赖向量库。

Prometheus 的 alerting rule 本身包含 alert name、expr、for、labels、annotations，可用于生成知识种子；Alertmanager 负责告警分组、去重、路由、静默和抑制，因此后续也可以把 Alertmanager 的 group labels 与 silence/inhibition 语义用于 OpsPilot 的告警归并与知识匹配。([prometheus.io][1])

---

### 5.1.5 知识反馈

```http
POST /api/v1/knowledge/feedback
```

请求：

```json
{
  "knowledge_id": "vmware.host.connection.not_responding.v1",
  "incident_id": "inc-001",
  "feedback": "useful",
  "correct_root_cause": true,
  "comment": "匹配正确，缺少交换机端口变更证据",
  "suggested_evidence": [
    "switch.port.config"
  ]
}
```

响应：

```json
{
  "success": true,
  "knowledge_id": "vmware.host.connection.not_responding.v1",
  "feedback_recorded": true
}
```

要求：

```text
1. useful / not_useful / partially_useful
2. 支持追加 suggested_evidence
3. 支持统计 hit_count、positive_feedback_count、negative_feedback_count
4. 后续用于 trust_score 调整
```

---

# 6. Evidence Aggregator 集成需求

## 6.1 新增输入字段

当前诊断流程中，Evidence Aggregator 应支持从 AlertKnowledge 获取证据需求。

新增输入：

```json
{
  "incident_id": "inc-001",
  "alert_context": {},
  "knowledge_matches": [
    {
      "knowledge_id": "vmware.host.connection.not_responding.v1",
      "evidence_required": [
        "host.connection.events",
        "management.network.reachability",
        "hostd.logs",
        "vpxa.logs"
      ]
    }
  ]
}
```

## 6.2 输出要求

Evidence Aggregator 输出需要明确：

```json
{
  "incident_id": "inc-001",
  "required_evidence_types": [
    "host.connection.events",
    "management.network.reachability",
    "hostd.logs",
    "vpxa.logs"
  ],
  "present_evidence_types": [
    "host.connection.events",
    "management.network.reachability"
  ],
  "missing_critical_evidence": [
    "hostd.logs",
    "vpxa.logs"
  ],
  "sufficiency_score": 0.55,
  "freshness_score": 0.9,
  "contradictions": [],
  "evidence_items": []
}
```

## 6.3 诊断约束

RootCause Agent 必须遵守：

```text
1. sufficiency_score < 0.6 时，不允许输出高置信度根因
2. 存在 missing_critical_evidence 时，必须在结论中声明缺失证据
3. 存在 contradictions 时，必须列出冲突证据，不得直接给唯一根因
4. 证据充分时，才输出“高置信度根因”
```

---

# 7. Orchestrator / Agent 编排需求

## 7.1 新增诊断链路

在现有 LangGraph Orchestrator 中增加知识驱动诊断流程。

建议节点：

```text
AlertNormalizeNode
AlertKnowledgeMatchNode
EvidencePlanNode
EvidenceCollectNode
CaseRetrieveNode
RootCauseReasonNode
RemediationPlanNode
FeedbackArchiveNode
```

## 7.2 编排流程

```text
输入 alert / incident
   ↓
AlertNormalizeNode
   - 规范化 alert_name、object_type、labels
   - 识别 VMware domain

   ↓
AlertKnowledgeMatchNode
   - 调用 /knowledge/alert-match
   - 获取 top-k AlertKnowledge

   ↓
EvidencePlanNode
   - 合并 top-1/top-3 evidence_required
   - 去重
   - 标记 critical evidence

   ↓
EvidenceCollectNode
   - 调用 Evidence Aggregator
   - 如 evidence 不足，输出缺失证据

   ↓
CaseRetrieveNode
   - 调用 /cases/similar
   - 召回历史案例

   ↓
RootCauseReasonNode
   - 使用 AlertKnowledge.decision_tree
   - 使用 EvidencePackage
   - 使用 similar cases
   - 输出 root cause candidates

   ↓
RemediationPlanNode
   - 输出 remediation
   - 输出 safe_actions 和 approval_actions
   - approval_actions 只生成申请，不直接执行

   ↓
FeedbackArchiveNode
   - 支持人工反馈
   - 支持归档 case
```

---

# 8. Case Memory 需求

## 8.1 新增相似案例接口

```http
POST /api/v1/cases/similar
```

请求：

```json
{
  "alert_name": "Datastore usage on disk",
  "category": "storage",
  "object_type": "datastore",
  "symptoms": [
    "datastore usage reached 78%",
    "vm app-db-01 has snapshot"
  ],
  "evidence_summary": {
    "datastore.usage": 78,
    "snapshot.count": 3
  },
  "top_k": 5
}
```

响应：

```json
{
  "matches": [
    {
      "case_id": "case-storage-001",
      "title": "Backup job left stale snapshot and datastore reached 82%",
      "similarity_score": 0.87,
      "root_cause_summary": "Backup-created snapshot was not consolidated",
      "resolution_summary": "Consolidated snapshots after reserving free space",
      "matched_fields": [
        "category",
        "alert_name",
        "snapshot symptoms"
      ]
    }
  ]
}
```

## 8.2 第一阶段相似度算法

不强依赖向量库，先用可解释评分：

```text
similarity_score =
  category_match * 0.2
+ alert_name_match * 0.25
+ symptoms_overlap * 0.25
+ evidence_type_overlap * 0.2
+ environment_match * 0.1
```

## 8.3 案例入库要求

每个关闭的 incident 可以转为 case：

```json
{
  "case_id": "case-20260430-001",
  "incident_id": "inc-001",
  "title": "Host disconnected caused by management VLAN change",
  "category": "network",
  "alert_names": [
    "Host connection and power state"
  ],
  "root_cause_summary": "Management VLAN was removed from trunk port",
  "resolution_summary": "Restored trunk VLAN configuration",
  "evidence_summary": {
    "host.connection.events": "host not responding",
    "network.change.events": "switch port VLAN changed"
  },
  "lessons_learned": [
    "Network change should be linked to VMware host impact analysis"
  ],
  "knowledge_refs": [
    "vmware.host.connection.not_responding.v1"
  ],
  "created_at": "2026-04-30T00:00:00Z"
}
```

---

# 9. Tool Gateway 集成需求

## 9.1 自动化动作分级

AlertKnowledge 中的 automation 必须分成两类：

```text
safe_actions:
  只读采集动作，可以自动执行

approval_actions:
  会改变环境状态的动作，必须走审批
```

示例：

```json
{
  "safe_actions": [
    "vmware.collect_datastore_usage",
    "vmware.collect_snapshot_tree"
  ],
  "approval_actions": [
    "vmware.vm.snapshot_consolidate",
    "vmware.vm.storage_vmotion"
  ]
}
```

## 9.2 Tool Gateway 校验

Tool Gateway 必须校验：

```text
1. action 是否存在于工具注册表
2. action_type 是否符合 safe / approval 分级
3. approval_required=true 的动作不得直接执行
4. 所有动作都要写 audit
5. 执行结果要回写 evidence 或 case
```

StackStorm 可以作为后续事件驱动自动化执行层：它的 sensor 用于接收外部事件并注入 trigger，rule 用于把 trigger 匹配到 action 或 workflow，因此适合承接 OpsPilot 的“告警触发 → 动作执行”场景。([docs.stackstorm.com][2])

Rundeck 更适合作为人工可审计的 Runbook Automation 平台；它提供 Web API，因此可以由 OpsPilot 在审批通过后调用 Rundeck Job 执行半自动运维动作。([docs.rundeck.com][3])

---

# 10. 前端页面需求

## 10.1 知识管理首页

路径建议：

```text
/knowledge
```

页面模块：

```text
1. 知识总览卡片
   - Published 数量
   - Draft 数量
   - Deprecated 数量
   - VMware 告警知识数量
   - 近 7 天命中次数
   - 近 7 天负反馈次数

2. 分类统计
   - resource
   - ha_cluster
   - vmotion_drs
   - storage
   - network
   - vm_level

3. 最近导入任务
   - job_id
   - source_name
   - total / created / updated / failed
   - status
```

---

## 10.2 AlertKnowledge 列表页

路径：

```text
/knowledge/alert-items
```

字段：

```text
ID
Alert Name
Category
Severity
Status
Version
Updated At
Trust Score
Hit Count
Feedback Score
Actions: View / Edit / Deprecate / Test Match
```

筛选条件：

```text
category
severity
status
tag
source.type
keyword
```

---

## 10.3 AlertKnowledge 详情页

路径：

```text
/knowledge/alert-items/:id
```

展示：

```text
1. 基本信息
2. aliases / tags / source
3. symptoms
4. possible_causes
5. evidence_required
6. diagnostic_steps
7. decision_tree
8. remediation
9. automation.safe_actions
10. automation.approval_actions
11. related cases
12. feedback records
```

---

## 10.4 知识导入页面

路径：

```text
/knowledge/import
```

功能：

```text
1. 上传 JSONL / YAML
2. 粘贴 JSON
3. 选择 source_name
4. dry-run 校验
5. 展示校验错误
6. 确认导入
7. 查看 import job 状态
```

---

## 10.5 告警知识验证页面

路径：

```text
/knowledge/test-alert-match
```

输入：

```text
alert_name
summary
object_type
object_name
labels JSON
```

输出：

```text
1. 匹配到的 AlertKnowledge top-k
2. why_selected
3. evidence_required
4. missing_evidence 模拟结果
5. recommended safe_actions
6. recommended approval_actions
7. similar cases
```

这个页面是给运维专家和开发测试用的，优先级很高。

---

# 11. Codex 开发任务拆分

## Epic 1：AlertKnowledge Schema 与存储

### Task 1.1 新增 Pydantic Schema

```text
新增 AlertKnowledge、DecisionRule、AutomationMapping、KnowledgeSource 模型。
```

验收标准：

```text
1. pytest 通过
2. 非法 category 校验失败
3. 非法 severity 校验失败
4. 缺少 evidence_required 校验失败
5. 缺少 decision_tree 校验失败
```

---

### Task 1.2 新增本地存储实现

第一阶段可用 JSON 文件或 SQLite。

建议接口：

```python
class AlertKnowledgeRepository:
    def upsert(self, item: AlertKnowledge) -> AlertKnowledge: ...
    def get(self, item_id: str) -> AlertKnowledge | None: ...
    def list(self, filters: dict) -> list[AlertKnowledge]: ...
    def delete_or_deprecate(self, item_id: str) -> AlertKnowledge: ...
```

验收标准：

```text
1. 可以 upsert
2. 可以 list/filter
3. 可以按 id get
4. 可以将 status 改为 deprecated
```

---

## Epic 2：导入接口

### Task 2.1 单条导入 API

实现：

```text
POST /api/v1/knowledge/alert-items
```

验收标准：

```text
1. 合法 item 返回 success=true
2. 非法 item 返回 422
3. upsert=false 且 id 已存在返回 409
4. upsert=true 可覆盖
```

---

### Task 2.2 批量导入 API

实现：

```text
POST /api/v1/knowledge/alert-items:bulk-import
```

验收标准：

```text
1. 支持导入 6 条 VMware golden knowledge
2. 失败项不影响成功项
3. 返回 created / updated / failed
4. 创建 import job
```

---

### Task 2.3 Import Jobs API

实现：

```text
GET /api/v1/knowledge/import-jobs
GET /api/v1/knowledge/import-jobs/{job_id}
```

验收标准：

```text
1. 可以查看最近导入任务
2. 可以查看指定 job 详情
3. 失败错误可读
```

---

## Epic 3：告警匹配

### Task 3.1 实现 AlertKnowledgeMatcher

接口：

```python
class AlertKnowledgeMatcher:
    def match(self, alert_context: dict, top_k: int = 3) -> list[AlertKnowledgeMatch]: ...
```

评分要求：

```text
alert_name 精确匹配
alias 匹配
keyword 匹配
tag 匹配
category hint 匹配
negative keyword 扣分
```

验收标准：

```text
1. 输入 "Host connection and power state" 命中 network 类知识
2. 输入 "Datastore usage reached 78%" 命中 storage 类知识
3. 输入 "vMotion timeout" 命中 vmotion_drs 类知识
4. why_selected 非空
5. score 在 0 到 1 之间
```

---

### Task 3.2 实现 alert-match API

实现：

```text
POST /api/v1/knowledge/alert-match
```

验收标准：

```text
1. 返回 top-k
2. 返回 evidence_required
3. 返回 safe_actions / approval_actions
4. 返回 why_selected
```

---

## Epic 4：Evidence 联动

### Task 4.1 Orchestrator 调用 alert-match

在诊断入口中增加：

```text
alert_context -> /knowledge/alert-match -> knowledge_matches
```

验收标准：

```text
1. diagnose 请求中包含 VMware 告警时，会调用 alert-match
2. 诊断结果中包含 matched_knowledge
3. 诊断结果中包含 evidence_required
```

---

### Task 4.2 Evidence Aggregator 接收 evidence_required

要求：

```text
1. Evidence Aggregator 使用知识侧 evidence_required 作为 required_evidence_types
2. 输出 present_evidence_types
3. 输出 missing_critical_evidence
4. 输出 sufficiency_score
```

验收标准：

```text
1. 缺少 vpxa_logs 时，Host disconnected 场景显示 missing_critical_evidence
2. 证据不足时，RootCause 不输出高置信度结论
```

---

## Epic 5：Case Memory

### Task 5.1 实现 cases/similar API

实现：

```text
POST /api/v1/cases/similar
```

验收标准：

```text
1. 输入 datastore + snapshot 症状，命中 snapshot 相关案例
2. 输入 host disconnected + management network 症状，命中网络相关案例
3. 返回 similarity_score
4. 返回 matched_fields
```

---

### Task 5.2 Incident 转 Case

实现：

```text
POST /api/v1/cases/from-incident
```

请求：

```json
{
  "incident_id": "inc-001",
  "root_cause_summary": "Management VLAN removed from trunk",
  "resolution_summary": "Restored switch trunk VLAN",
  "lessons_learned": [
    "Network changes should trigger VMware impact analysis"
  ],
  "knowledge_refs": [
    "vmware.host.connection.not_responding.v1"
  ]
}
```

验收标准：

```text
1. 必须包含 root_cause_summary
2. 必须包含 resolution_summary
3. 自动关联 alert_name / category / evidence_summary
4. 生成后可被 /cases/similar 召回
```

---

## Epic 6：前端页面

### Task 6.1 AlertKnowledge 列表页

验收标准：

```text
1. 可以分页展示知识
2. 可以按 category / severity / status 搜索
3. 可以查看详情
4. 可以 deprecated
```

---

### Task 6.2 AlertKnowledge 详情页

验收标准：

```text
1. 展示 symptoms / causes / evidence / decision_tree / remediation
2. 展示 safe_actions / approval_actions
3. 展示 related cases
4. 展示 feedback
```

---

### Task 6.3 Import 页面

验收标准：

```text
1. 支持上传 JSONL
2. 支持 dry-run
3. 支持导入
4. 支持查看 import job 结果
```

---

### Task 6.4 Test Alert Match 页面

验收标准：

```text
1. 输入告警文本后展示 top-k 匹配知识
2. 展示 why_selected
3. 展示 evidence_required
4. 展示推荐动作
5. 展示相似案例
```

---

# 12. 测试场景设计

## 场景 1：VM CPU 使用率高

输入：

```json
{
  "alert_name": "Virtual machine CPU usage",
  "summary": "vm app-01 CPU > 90% for 5m and CPU ready is high",
  "object_type": "vm",
  "object_name": "app-01",
  "labels": {
    "cluster": "prod-a",
    "host": "esxi-03"
  }
}
```

期望：

```text
1. 命中 vmware.vm.cpu_usage.high.v1
2. category = resource
3. evidence_required 包含 vm.cpu.usage、vm.cpu.ready、host.cpu.usage
4. safe_actions 包含 collect_vm_cpu_metrics
5. 如果缺少 vm.cpu.ready，则输出 missing_critical_evidence
```

---

## 场景 2：Host Memory Usage 但 active memory 低

输入：

```json
{
  "alert_name": "Host Memory Usage",
  "summary": "host esxi-07 memory usage > 90% but active memory is low",
  "object_type": "host",
  "object_name": "esxi-07",
  "labels": {
    "cluster": "prod-a"
  }
}
```

期望：

```text
1. 命中 host memory 知识
2. 输出“高分配不等于真实内存压力”的判断路径
3. evidence_required 包含 active memory、balloon、swap
4. 不直接建议扩容
```

---

## 场景 3：HA 资源不足

输入：

```json
{
  "alert_name": "Insufficient HA failover resources",
  "summary": "HA admission control cannot satisfy configured failover level",
  "object_type": "cluster",
  "object_name": "prod-a",
  "labels": {
    "vcenter": "vcsa-prod-01"
  }
}
```

期望：

```text
1. 命中 ha_cluster 知识
2. evidence_required 包含 cluster.ha.config、cluster.host.state、vm.reservations
3. remediation 指向增加主机、调整 reservation、复核 HA policy
```

---

## 场景 4：vMotion 失败

输入：

```json
{
  "alert_name": "vMotion failed",
  "summary": "Migration failed due to destination host vMotion VMkernel misconfigured",
  "object_type": "task",
  "object_name": "task-8871",
  "labels": {
    "src": "esxi-02",
    "dst": "esxi-08"
  }
}
```

期望：

```text
1. 命中 vmotion_drs 知识
2. evidence_required 包含 vmk.config、network.mtu.path、cluster.evc
3. safe_actions 包含 collect_vmkernel_config
4. retry_vmotion 只能作为 approval_action
```

---

## 场景 5：Datastore usage + Snapshot

输入：

```json
{
  "alert_name": "Datastore usage on disk",
  "summary": "datastore nfs-prod-01 reached 78%, vm app-db-01 has large snapshot delta",
  "object_type": "datastore",
  "object_name": "nfs-prod-01",
  "labels": {
    "cluster": "prod-a"
  }
}
```

期望：

```text
1. 命中 storage 知识
2. evidence_required 包含 datastore.usage、snapshot.tree、recent.backup.jobs
3. remediation 包含先确认备份任务、预留空间、再合并快照
4. snapshot_consolidate 只能作为 approval_action
```

---

## 场景 6：Host disconnected

输入：

```json
{
  "alert_name": "Host connection and power state",
  "summary": "host esxi-03 not responding in vCenter",
  "object_type": "host",
  "object_name": "esxi-03",
  "labels": {
    "cluster": "prod-b"
  }
}
```

期望：

```text
1. 命中 network 知识
2. evidence_required 包含 host.connection.events、management.network.reachability、hostd.logs、vpxa.logs
3. 不建议直接重启 ESXi
4. 如果多个 host 同时断连，优先判断 vCenter / DNS / 管理网络问题
```

---

# 13. 自动化与安全要求

## 13.1 只读动作自动执行

允许自动执行：

```text
collect_vm_metrics
collect_host_metrics
query_recent_events
collect_datastore_usage
collect_snapshot_tree
collect_cluster_ha_config
collect_vmkernel_config
```

## 13.2 变更动作必须审批

以下动作不能自动执行：

```text
vmware.vm.migrate
vmware.vm.snapshot_consolidate
vmware.vm.storage_vmotion
vmware.host.restart_management_agents
vmware.host.enter_maintenance_mode
vmware.vm.retry_vmotion
```

## 13.3 审计要求

每次诊断必须记录：

```text
incident_id
alert_context
matched_knowledge
evidence_required
present_evidence
missing_evidence
similar_cases
root_cause_candidates
recommended_actions
user_feedback
```

---

# 14. 开源项目集成建议

第一阶段不要马上深度集成外部平台，先保留适配接口。

## 14.1 Prometheus / Alertmanager

用途：

```text
1. 从 alerting rules 自动生成 AlertKnowledge 初稿
2. 从 Alertmanager webhook 接收 firing alert
3. 使用 group labels 做告警归并
4. 使用 silence / inhibition 语义减少噪声
```

Prometheus alerting rules 天然包含告警名称、表达式、持续时间、标签和注解；Alertmanager 负责分组、去重、路由、静默和抑制，适合作为 OpsPilot 告警输入和知识种子来源。([prometheus.io][1])

## 14.2 StackStorm

用途：

```text
1. 事件驱动自动化执行
2. safe_actions 的外部执行器
3. 将 OpsPilot 诊断结果转换为 trigger
4. rule 匹配后触发 action / workflow
```

StackStorm 的 sensors 会向系统注入 triggers，rules 将 triggers 匹配到 actions 或 workflows，适合承接 OpsPilot 的自动化动作层。([docs.stackstorm.com][2])

## 14.3 Rundeck

用途：

```text
1. 审批后的 Runbook 执行
2. 人工可控的半自动化
3. 运维 Job 编排
4. 执行结果回写 OpsPilot
```

Rundeck 是 Runbook Automation 平台，并提供 Web API，适合接入审批后的运维动作执行。([docs.rundeck.com][3])

---

# 15. 验收指标

## 15.1 功能验收

```text
1. 能导入 6 条 VMware golden AlertKnowledge
2. 能通过 alert-match 命中正确知识
3. 能输出 evidence_required
4. 能识别 missing_critical_evidence
5. 能召回 similar cases
6. 能输出 safe_actions / approval_actions
7. 前端能完成导入、列表、详情、测试匹配
```

## 15.2 效果验收

用 20 条模拟告警测试：

```text
1. Top-1 知识命中率 >= 80%
2. Top-3 知识命中率 >= 95%
3. evidence_required 覆盖率 >= 90%
4. 高风险动作误自动执行次数 = 0
5. sufficiency_score < 0.6 时高置信度结论输出次数 = 0
```

---

# 16. 给 Codex 的最终开发 Prompt

可以直接复制下面这段给 Codex：

```text
请在当前 OpsPilotEnterprise 项目中增强知识管理模块，将其从普通文档检索升级为面向 VMware 告警诊断的结构化 AlertKnowledge 系统。

开发目标：
1. 新增 AlertKnowledge Pydantic schema，字段包括 id、alert_name、aliases、category、severity、symptoms、possible_causes、diagnostic_steps、decision_tree、remediation、evidence_required、evidence_optional、automation、tags、source、status、version、updated_at、case_refs、knowledge_refs、match_keywords、negative_keywords。
2. 在 knowledge-service 中新增 AlertKnowledgeRepository，支持 upsert/get/list/deprecate。
3. 新增 API：
   - POST /api/v1/knowledge/alert-items
   - POST /api/v1/knowledge/alert-items:bulk-import
   - GET /api/v1/knowledge/import-jobs
   - GET /api/v1/knowledge/import-jobs/{job_id}
   - POST /api/v1/knowledge/alert-match
   - POST /api/v1/knowledge/feedback
4. 实现 AlertKnowledgeMatcher，第一阶段使用可解释规则评分：alert_name 精确匹配、aliases、match_keywords、tags、category hint、negative_keywords。
5. 新增 fixtures/knowledge/vmware_alerts/vmware_alert_knowledge.jsonl，至少包含 6 类 VMware 告警知识：VM CPU、Host Memory、HA failover resources、vMotion failure、Datastore/Snapshot、Host disconnected。
6. 修改 Orchestrator 的 diagnose 流程，在 Evidence 采集前调用 /knowledge/alert-match，获取 matched_knowledge 和 evidence_required。
7. 修改 Evidence Aggregator 输入，使其支持从 matched_knowledge 接收 evidence_required，并输出 required_evidence_types、present_evidence_types、missing_critical_evidence、sufficiency_score、freshness_score、contradictions。
8. RootCause Agent 必须遵守 evidence sufficiency 约束：sufficiency_score < 0.6 或存在 missing_critical_evidence 时，不得输出高置信度根因。
9. 新增 /api/v1/cases/similar，支持基于 category、alert_name、symptoms、evidence_type_overlap 的相似案例召回。
10. 前端新增页面：
    - /knowledge/alert-items
    - /knowledge/alert-items/:id
    - /knowledge/import
    - /knowledge/test-alert-match
11. 所有 approval_actions 不允许直接执行，只能生成审批申请；safe_actions 可以自动调用。
12. 增加 pytest 测试，覆盖 schema 校验、bulk import、alert-match、missing evidence、similar cases、orchestrator diagnose 集成流程。

验收标准：
1. 导入 6 条 VMware golden knowledge 成功。
2. 输入 Host connection and power state 能命中 vmware.host.connection.not_responding.v1。
3. 输入 Datastore usage on disk 能命中 storage 类知识。
4. 输入 vMotion failed 能命中 vmotion_drs 类知识。
5. diagnose 输出中必须包含 matched_knowledge、evidence_required、missing_critical_evidence、recommended_actions。
6. 对 vmware.vm.migrate、snapshot_consolidate、restart_management_agents 等动作必须标记为 approval_actions，不得自动执行。
7. pytest 全部通过。
```

---

这份需求的核心是：**先把知识结构化，再让知识驱动证据采集和根因推理**。不要一开始就把重点放在复杂向量库和大规模 RAG，第一阶段先用可解释规则、golden knowledge、证据契约和测试场景，把 VMware 告警诊断闭环跑通。

[1]: https://prometheus.io/docs/prometheus/2.53/configuration/alerting_rules/?utm_source=chatgpt.com "Alerting rules | Prometheus"
[2]: https://docs.stackstorm.com/sensors.html?utm_source=chatgpt.com "Sensors and Triggers — StackStorm 3.9.0 documentation"
[3]: https://docs.rundeck.com/docs/?utm_source=chatgpt.com "Rundeck | Runbook Automation Documentation"
