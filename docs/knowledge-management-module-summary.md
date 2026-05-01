# OpsPilotEnterprise 知识管理模块总结

更新时间：2026-05-01  
部署环境：`192.168.51.169`  
模块范围：知识服务、API BFF、推理链路、证据聚合、案例复用、知识管理前端页面

## 1. 建设目标

本轮知识管理增强将 OpsPilotEnterprise 的知识能力从“文章检索 + mock 页面”升级为面向告警诊断的结构化知识体系。新的知识管理模块以 `AlertKnowledge` 为核心对象，支持告警匹配、证据约束、相似案例召回、人工反馈、外部规则导入，并参与 RCA 推理与复盘链路。

核心目标包括：

- 把知识从静态文章升级为结构化告警知识对象。
- 让知识参与告警诊断、证据补齐、根因置信度控制和修复建议生成。
- 提供知识导入、校验、废弃、统计、匹配测试等后端能力。
- 将知识管理前端从 mock 页面替换为真实 API 驱动页面。
- 保留原有文章接口、BFF 路由、诊断、证据和案例链路的兼容性。

## 2. 总体架构

知识管理能力按职责拆分为以下几层：

| 层级 | 模块 | 主要职责 |
| --- | --- | --- |
| 数据模型 | `packages/shared-schema`、`packages/shared-types` | 定义 `AlertKnowledge`、匹配结果、导入校验、反馈等共享结构 |
| 主服务 | `services/knowledge-service` | SQLite 持久化、知识 CRUD、导入、匹配、反馈、统计、相似案例 |
| 聚合代理 | `apps/api-bff` | 暴露 `/api/v1/knowledge/*` 和 `/api/v1/cases/*` 聚合路由 |
| 推理链路 | `services/langgraph-orchestrator` | Evidence、Knowledge、RootCause、Remediation Agent 消费知识匹配结果 |
| 证据聚合 | `services/evidence-aggregator` | 输出证据充分性、缺失证据、外部证据接入结果 |
| 前端 | `apps/web/src/app/knowledge` | 概览、列表、详情、导入、告警匹配测试页面 |
| 种子数据 | `fixtures/knowledge/vmware_alerts` | VMware 高频告警黄金知识 JSONL fixture |

## 3. 核心数据模型

新增和增强的核心对象为 `AlertKnowledge`。它用于描述一类告警的诊断知识，而不是普通文章。

主要字段包括：

- 基础信息：`id`、`alert_name`、`vendor`、`domain`、`category`、`severity`、`status`、`version`。
- 匹配信息：`aliases`、`match_keywords`、`negative_keywords`、`tags`。
- 诊断知识：`symptoms`、`possible_causes`、`diagnostic_steps`、`decision_tree`。
- 证据约束：`evidence_required`、`evidence_optional`。
- 处置建议：`remediation`、`automation.safe_actions`、`automation.approval_actions`。
- 治理信息：`source`、`owner`、`reviewer`、`review_notes`、`trust_score`、`hit_count`。
- 关联信息：`case_refs`、`knowledge_refs`。
- 时间信息：`created_at`、`updated_at`。

结构化 `DecisionRule` 已支持，同时兼容旧版 `decision_tree: string[]` 数据，导入或读取时会自动迁移为结构化规则。

## 4. 存储与种子数据

`knowledge-service` 使用 SQLite 作为本轮持久化方案，默认数据库路径为：

```text
services/knowledge-service/data/knowledge.db
```

主要数据表：

| 表名 | 用途 |
| --- | --- |
| `alert_knowledge` | 存储结构化告警知识 |
| `knowledge_import_jobs` | 存储导入任务、dry-run、失败明细和摘要 |
| `knowledge_feedback` | 存储人工反馈、命中纠偏、补充证据、采纳动作 |

VMware golden knowledge 已固化为 JSONL fixture：

```text
fixtures/knowledge/vmware_alerts/vmware_alert_knowledge.jsonl
```

当前覆盖 30 条 VMware 高频告警知识，并保证 6 个核心验收场景存在：

- VM CPU Usage
- Host Memory Usage
- Insufficient HA failover resources
- vMotion failed
- Datastore/Snapshot capacity
- Host disconnected

首次启动会幂等导入种子数据；后续导入按 `id` 或 `alert_name + vendor + category` 执行 upsert。

## 5. API 能力

### 5.1 Knowledge Service API

| API | 方法 | 说明 |
| --- | --- | --- |
| `/knowledge/alert-items` | `GET` | 查询告警知识，支持过滤和分页 |
| `/knowledge/alert-items` | `POST` | 创建或 upsert 单条告警知识 |
| `/knowledge/alert-items/{id}` | `GET` | 获取单条告警知识详情 |
| `/knowledge/alert-items/{id}:deprecate` | `POST` | 废弃知识 |
| `/knowledge/alert-items/{id}/deprecate` | `POST` | 兼容式废弃路由 |
| `/knowledge/alert-items:bulk-import` | `POST` | 批量导入 JSON/JSONL/规则转换结果 |
| `/knowledge/import/validate` | `POST` | 导入前 dry-run 校验 |
| `/knowledge/import-jobs` | `GET` | 查询导入任务列表 |
| `/knowledge/import-jobs/{job_id}` | `GET` | 查询导入任务详情 |
| `/knowledge/stats` | `GET` | 查询状态、分类、命中、反馈等统计 |
| `/knowledge/alert-match` | `POST` | 根据告警上下文匹配知识 |
| `/knowledge/feedback` | `POST` | 写入人工反馈 |
| `/knowledge/importers/prometheus-rules` | `POST` | Prometheus rule YAML 转 AlertKnowledge |
| `/cases/similar` | `POST` | 确定性相似案例召回 |

### 5.2 BFF API

BFF 保留 `/api/v1` 聚合入口，新增或补齐：

- `/api/v1/knowledge/stats`
- `/api/v1/knowledge/alert-items`
- `/api/v1/knowledge/alert-items/{id}`
- `/api/v1/knowledge/alert-items/{id}:deprecate`
- `/api/v1/knowledge/import/validate`
- `/api/v1/knowledge/import-jobs`
- `/api/v1/knowledge/import-jobs/{job_id}`
- `/api/v1/knowledge/alert-items:bulk-import`
- `/api/v1/knowledge/alert-match`
- `/api/v1/knowledge/feedback`
- `/api/v1/cases/similar`
- `/api/v1/cases/from-incident`

## 6. 告警匹配机制

`/knowledge/alert-match` 使用确定性、可解释的规则评分，不依赖向量库。

主要评分因子：

- `alert_name` 精确命中加分。
- `aliases` 命中加分。
- `match_keywords` 命中加分。
- `tags` 命中加分。
- `category` hint 命中加分。
- `vendor` 命中加分。
- `negative_keywords` 命中扣分。
- 文本 token 与告警摘要、描述、资源信息重叠加分。

接口返回内容包括：

- `matches`
- `why_selected`
- `matched_fields`
- `required_evidence_types`
- `missing_evidence`
- `missing_critical_evidence`
- `diagnostic_steps`
- `safe_actions`
- `approval_actions`
- `similar_cases`

该机制让匹配结果可解释、可测试，也便于人工反馈后继续优化关键词、别名和证据约束。

## 7. 推理与证据联动

知识管理模块已经接入 RCA 推理链路：

### EvidenceAgent

EvidenceAgent 在聚合证据时传入 `alert_context`，使 evidence aggregator 可以结合 AlertKnowledge 的 `evidence_required` 补充或替代原有规则式证据类型。

### Evidence Aggregator

证据聚合结果增强为：

- `required_evidence_types`
- `present_evidence_types`
- `missing_critical_evidence`
- `sufficiency_score`
- `freshness_score`
- `contradictions`

### RootCauseAgent

RootCauseAgent 使用知识证据门槛控制 RCA 输出：

- 存在关键缺证时，输出 `insufficient_evidence`。
- `sufficiency_score < 0.6` 时，不输出高置信根因。
- 同时给出下一轮补证建议。

### RemediationAgent

RemediationAgent 从 AlertKnowledge 的 `automation` 读取动作建议：

- 只读采集、查询、健康检查进入 `safe_actions`。
- 迁移、重启、合并快照、Storage vMotion 等高风险动作进入 `approval_actions`。
- 不会把需要审批的动作作为自动执行动作。

## 8. 外部证据与规则接入

本轮接入保持只读原则。

### Prometheus

新增 Prometheus rule YAML 转换器：

- 读取 `alert`
- 读取 `expr`
- 读取 `for`
- 读取 `labels.severity`
- 读取 `annotations.summary`
- 读取 `annotations.description`
- 读取 `annotations.runbook_url`

转换结果可作为 AlertKnowledge 草稿或发布项导入。

### Graylog

Evidence Aggregator 支持可选 `GRAYLOG_URL`。未配置时返回非致命 `EvidenceError`；配置后可拉取 event、anomaly、correlation，并映射为 `log` 或 `alert` evidence。

### OpenNMS

Evidence Aggregator 支持可选 `OPENNMS_URL`。可将 alarm 的 `uei`、`reductionKey`、`severity`、ack/clear 状态映射为 `alert` evidence，并把 `reductionKey` 作为 correlation key。

## 9. 前端页面

知识管理前端已从 mock 页面升级为真实 API 驱动页面。

| 页面 | 路径 | 说明 |
| --- | --- | --- |
| 知识概览 | `/knowledge` | 展示知识总量、状态统计、分类统计、导入任务、命中和反馈概览 |
| 告警知识列表 | `/knowledge/alert-items` | 支持过滤、分页、查看、废弃、匹配测试入口 |
| 告警知识详情 | `/knowledge/alert-items/[id]` | 展示症状、原因、证据、decision tree、处置、自动化动作、关联案例、反馈 |
| 知识导入 | `/knowledge/import` | 支持 JSON、JSONL、YAML 粘贴或上传、dry-run 校验、确认导入、job 结果 |
| 告警匹配测试 | `/knowledge/test-alert-match` | 输入告警上下文，展示 top-k、why、证据需求、缺证、动作建议和相似案例 |

## 10. 部署与验证

当前已部署到：

```text
http://192.168.51.169:3000
```

主要入口：

- `http://192.168.51.169:3000/knowledge`
- `http://192.168.51.169:3000/knowledge/alert-items`
- `http://192.168.51.169:3000/knowledge/import`
- `http://192.168.51.169:3000/knowledge/test-alert-match`
- `http://192.168.51.169:8000/api/v1/knowledge/stats`

远端验证结果：

- Web 页面返回 `200`。
- BFF `/health` 返回 `200`。
- Knowledge service `/health` 返回 `200`。
- `/api/v1/knowledge/stats` 正常返回。
- `/api/v1/knowledge/alert-items?vendor=VMware&page_size=5` 正常返回，总数为 30。
- `/api/v1/knowledge/alert-match` 能命中 VMware 告警知识，并返回 `matched_fields` 与 `missing_critical_evidence`。

## 11. 测试情况

已完成的重点验证：

- Python 语法检查通过。
- Focused backend tests 通过：
  - `tests/test_alert_knowledge.py`
  - `tests/test_knowledge.py`
  - `tests/test_alert_reasoning_integration.py`
  - `tests/test_evidence_aggregator.py`
  - `tests/test_orchestrator.py`
- 前端知识模块局部 lint 通过：
  - `pnpm exec eslint src/app/knowledge`
- 前端构建通过：
  - `pnpm build`

已知情况：

- 全量 pytest 存在若干既有非知识模块失败，集中在 approvals、auth、audit、change-impact、chat evidence、notifications、secret store 等领域。
- 全量 `pnpm lint` 存在既有非知识页面/模块 lint 问题；知识模块局部 lint 已通过。

## 12. 当前收益

本轮增强后，知识管理模块已经具备以下价值：

- 告警知识从文章描述变为可计算、可匹配、可治理的结构化对象。
- RCA 不再只依赖已有证据，而能根据知识反推缺失证据。
- 根因判断受到证据充分性约束，降低低证据高置信误判风险。
- 修复建议区分安全动作和审批动作，避免高风险动作被误自动化。
- 相似案例召回与人工反馈为后续复盘闭环提供数据基础。
- 前端提供可直接操作的导入、列表、详情和匹配验证入口。

## 13. 后续建议

建议下一阶段继续推进：

- 将人工反馈结果纳入匹配权重调整，例如提升正反馈知识的 `trust_score`，降低误命中项权重。
- 增加知识审核流，支持 draft、published、deprecated 的审批状态流转。
- 引入更细粒度的证据新鲜度配置，不同告警类型使用不同 freshness threshold。
- 增加知识版本 diff 和回滚能力。
- 后续在数据规模扩大后，引入向量召回或 pgvector，作为规则匹配的补充而不是替代。
- 将 Graylog、OpenNMS 真实环境配置纳入部署文档和运维检查项。
