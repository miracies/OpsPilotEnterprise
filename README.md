# OpsPilot Enterprise

OpsPilot Enterprise 是面向私有化环境的企业级 AIOps 智能运维平台，覆盖故障诊断、证据汇聚、变更影响分析、知识增强、案例复盘、审批治理、受控执行和运维记忆管理。

当前版本已经完成一条可演示的诊断闭环：事件/对话触发诊断，Orchestrator 编排多 Agent 收集证据、匹配知识、判断根因、生成处置建议，并将知识、案例、证据和审批动作纳入复盘链路。

## 当前能力

- **AI 对话与诊断工作台**：支持自然语言诊断请求、结构化 RCA 输出、证据展示、工具轨迹和诊断详情。
- **资源与拓扑**：支持 vCenter、Kubernetes 资源总览、清单、拓扑视图和资源页面。
- **证据聚合**：统一汇聚指标、日志、事件、拓扑、变更、告警等证据，并输出证据充分性、缺失证据和矛盾点。
- **知识管理增强**：从文章列表升级为结构化 `AlertKnowledge` 告警知识对象，支持导入、校验、告警匹配、证据反推、相似案例和人工反馈。
- **案例复盘**：支持案例归档、相似案例召回、从 incident 生成案例草稿。
- **变更影响分析**：支持风险评分、影响范围、依赖关系和回退建议。
- **审批与治理**：支持审批中心、通知、审计、策略管理和高风险动作审批边界。
- **受控执行与工具网关**：工具访问统一经过 Tool Gateway，执行类动作保留审批、审计和回执链路。
- **运维记忆**：Memory Service 提供记忆、策略和图谱相关能力。

## 架构概览

```text
Web UI (Next.js :3000)
    |
    v
API BFF (FastAPI :8000)
    |
    |-- LangGraph Orchestrator (:8010)
    |      |-- Tool Gateway (:8020)
    |      |-- Evidence Aggregator (:8050)
    |      |-- Knowledge Service (:8072)
    |      |-- Memory Service (:8073)
    |
    |-- Event Ingestion Service (:8060)
    |-- Change Impact Service (:8040)
    |-- Approval Center Service (:8070)
    |-- Governance Service (:8071)
    |-- Topology Service (:8090)
    |
    |-- VMware Skill Gateway (:8030)
    |-- Kubernetes Skill Gateway (:8080)
```

外部与基础设施组件：

- PostgreSQL：业务数据和 Memory Service 数据。
- Neo4j：拓扑与记忆图谱。
- Prometheus：指标与监控数据。
- OPA：策略判定。
- 可选接入：vCenter、Kubernetes、Graylog、OpenNMS、Prometheus Rule YAML。

## 技术栈

### 前端

- Next.js 16 + React 19 + TypeScript
- Tailwind CSS 4
- TanStack Query
- Recharts
- Lucide Icons

### 后端

- Python 3.12 + FastAPI
- Pydantic v2 共享 schema
- httpx 服务间通信
- SQLite 用于知识服务轻量持久化
- PostgreSQL / Neo4j 用于记忆和图谱能力

### 大模型

- 默认使用智谱 AI `glm-5-turbo` 的 OpenAI 兼容 API。
- 可通过 `LLM_API_BASE`、`LLM_API_KEY`、`LLM_MODEL` 切换任意 OpenAI 兼容模型。
- LLM 不可用时，诊断链路可降级为本地 mock 输出，便于离线演示和开发。

## 快速开始

### 前置条件

- Node.js >= 18
- pnpm >= 8
- Python >= 3.11
- Docker + Docker Compose

### 1. 配置环境变量

```bash
cp .env.example .env
```

关键配置项：

| 变量 | 默认值/示例 | 说明 |
| --- | --- | --- |
| `LLM_ENABLED` | `true` | 是否启用 LLM |
| `LLM_API_BASE` | `https://open.bigmodel.cn/api/paas/v4` | OpenAI 兼容 API 地址 |
| `LLM_API_KEY` | `your-api-key-here` | LLM API Key |
| `LLM_MODEL` | `glm-5-turbo` | 模型名称 |
| `JWT_SECRET` | `change-this-to-a-random-secret` | JWT 签名密钥 |
| `OPSPILOT_SECRET_KEY` | `change-me-for-production` | 本地密钥库主密码 |
| `RESOURCE_BFF_URL` | `http://127.0.0.1:8000` | Orchestrator 读取资源信息时调用的 BFF 地址 |
| `VMWARE_GATEWAY_URL` | `http://127.0.0.1:8030` | VMware Gateway 地址 |
| `KUBERNETES_GATEWAY_URL` | `http://127.0.0.1:8080` | Kubernetes Gateway 地址 |
| `MEMORY_SERVICE_URL` | `http://127.0.0.1:8073` | Memory Service 地址 |
| `GRAYLOG_URL` | 空 | 可选 Graylog 证据接入地址 |
| `OPENNMS_URL` | 空 | 可选 OpenNMS 告警证据接入地址 |

### 2. 安装依赖

```bash
# 前端
pnpm install

# 后端共享 schema
pip install -e packages/shared-schema

# 后端服务
pip install -e apps/api-bff --no-deps
pip install -e services/tool-gateway --no-deps
pip install -e services/vmware-skill-gateway --no-deps
pip install -e services/kubernetes-skill-gateway --no-deps
pip install -e services/change-impact-service --no-deps
pip install -e services/evidence-aggregator --no-deps
pip install -e services/event-ingestion-service --no-deps
pip install -e services/langgraph-orchestrator --no-deps
pip install -e services/approval-center-service --no-deps
pip install -e services/governance-service --no-deps
pip install -e services/knowledge-service --no-deps
```

如需在 Windows 本地直接运行 OPA CLI，可按需下载到 `tools/opa.exe`：

```powershell
.\scripts\install-opa.ps1
```

Docker Compose 部署会使用 `openpolicyagent/opa` 镜像，不依赖本地 `tools/opa.exe`。

### 3. 启动后端服务

Windows PowerShell：

```powershell
.\scripts\dev-backend.ps1
```

Linux/macOS：

```bash
bash scripts/dev-backend.sh
```

也可以手动启动单个服务：

```bash
uvicorn app.main:app --port 8000 --reload  # API BFF
uvicorn app.main:app --port 8010 --reload  # Orchestrator
uvicorn app.main:app --port 8020 --reload  # Tool Gateway
uvicorn app.main:app --port 8030 --reload  # VMware Gateway
uvicorn app.main:app --port 8040 --reload  # Change Impact
uvicorn app.main:app --port 8050 --reload  # Evidence Aggregator
uvicorn app.main:app --port 8060 --reload  # Event Ingestion
uvicorn app.main:app --port 8070 --reload  # Approval Center
uvicorn app.main:app --port 8071 --reload  # Governance
uvicorn app.main:app --port 8072 --reload  # Knowledge Service
uvicorn app.main:app --port 8073 --reload  # Memory Service
uvicorn app.main:app --port 8080 --reload  # Kubernetes Gateway
uvicorn app.main:app --port 8090 --reload  # Topology Service
```

### 4. 启动前端

```bash
pnpm --filter @opspilot/web dev
```

访问：

- 本地 Web：[http://localhost:3000](http://localhost:3000)
- 本地 BFF：[http://localhost:8000](http://localhost:8000)

### 5. Docker Compose 一键启动

```bash
cd deploy/docker
docker compose up --build
```

### 6. 远端部署

项目提供远端部署脚本：

```powershell
.\scripts\deploy-remote.ps1 -RemoteHost 192.168.51.169 -DisableK8sMonitoring
```

当前已验证部署环境：

- Web：[http://192.168.51.169:3000](http://192.168.51.169:3000)
- BFF：[http://192.168.51.169:8000](http://192.168.51.169:8000)
- 知识概览：[http://192.168.51.169:3000/knowledge](http://192.168.51.169:3000/knowledge)
- 告警知识列表：[http://192.168.51.169:3000/knowledge/alert-items](http://192.168.51.169:3000/knowledge/alert-items)
- 知识导入：[http://192.168.51.169:3000/knowledge/import](http://192.168.51.169:3000/knowledge/import)
- 告警匹配测试：[http://192.168.51.169:3000/knowledge/test-alert-match](http://192.168.51.169:3000/knowledge/test-alert-match)

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `admin123` | 管理员 |
| `zhangsan` | `ops123` | 运维人员 |
| `lisi` | `ops123` | 运维人员 |

## 项目结构

```text
OpsPilot/
|-- apps/
|   |-- web/                       # Next.js 前端
|   `-- api-bff/                   # /api/v1 聚合层
|-- services/
|   |-- langgraph-orchestrator/    # Agent 编排与 RCA
|   |-- tool-gateway/              # 统一工具控制面
|   |-- vmware-skill-gateway/      # VMware 领域服务
|   |-- kubernetes-skill-gateway/  # Kubernetes 领域服务
|   |-- change-impact-service/     # 变更影响分析
|   |-- evidence-aggregator/       # 证据聚合
|   |-- event-ingestion-service/   # 事件与案例接入
|   |-- approval-center-service/   # 审批中心与通知
|   |-- governance-service/        # 审计、策略、升级
|   |-- knowledge-service/         # 知识管理、告警知识、案例相似召回
|   |-- memory-service/            # 运维记忆
|   `-- topology-service/          # 拓扑服务
|-- packages/
|   |-- shared-schema/             # Python Pydantic schema
|   `-- shared-types/              # TypeScript 类型定义
|-- fixtures/
|   `-- knowledge/vmware_alerts/   # VMware 告警知识 JSONL 种子数据
|-- deploy/docker/                 # Docker Compose
|-- docs/                          # 文档
|-- policy/rego/                   # OPA 策略示例
|-- scripts/                       # 开发与部署脚本
`-- tests/                         # 单元、集成和回归测试
```

## 知识管理增强

知识管理模块已经从“文章列表”升级为“结构化告警知识 + 证据约束 + 案例复盘 + 外部证据接入”的能力。

### AlertKnowledge 模型

`AlertKnowledge` 是当前知识管理的核心对象，主要字段包括：

- 基础信息：`id`、`alert_name`、`vendor`、`domain`、`category`、`severity`、`status`、`version`。
- 匹配信息：`aliases`、`match_keywords`、`negative_keywords`、`tags`。
- 诊断知识：`symptoms`、`possible_causes`、`diagnostic_steps`、`decision_tree`。
- 证据约束：`evidence_required`、`evidence_optional`。
- 处置建议：`remediation`、`automation.safe_actions`、`automation.approval_actions`。
- 治理信息：`source`、`owner`、`reviewer`、`review_notes`、`trust_score`、`hit_count`。
- 关联信息：`case_refs`、`knowledge_refs`。

结构化 `DecisionRule` 已支持，并兼容旧版 `decision_tree: string[]` 数据。

### 存储与种子数据

Knowledge Service 使用 SQLite 持久化，默认数据库路径：

```text
services/knowledge-service/data/knowledge.db
```

主要数据表：

- `alert_knowledge`
- `knowledge_import_jobs`
- `knowledge_feedback`

VMware golden knowledge 已固化在：

```text
fixtures/knowledge/vmware_alerts/vmware_alert_knowledge.jsonl
```

当前覆盖 30 条 VMware 高频告警知识，核心验收场景包括：

- VM CPU Usage
- Host Memory Usage
- Insufficient HA failover resources
- vMotion failed
- Datastore/Snapshot capacity
- Host disconnected

### 告警匹配

`/knowledge/alert-match` 使用确定性、可解释的规则评分：

- exact alert name 命中加分
- alias 命中加分
- match keywords 命中加分
- tags 命中加分
- category hint 命中加分
- negative keywords 扣分

匹配结果返回：

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

### 推理联动

- EvidenceAgent 调用 evidence aggregator 时传入 `alert_context`。
- Evidence Aggregator 输出 `required_evidence_types`、`present_evidence_types`、`missing_critical_evidence`、`sufficiency_score`、`freshness_score`、`contradictions`。
- RootCauseAgent 在关键证据缺失或 `sufficiency_score < 0.6` 时输出 `insufficient_evidence`，避免低证据高置信根因。
- RemediationAgent 只展示 `safe_actions` 与 `approval_actions`，迁移、重启、快照合并、Storage vMotion 等动作保持审批动作。

### 外部接入

- Prometheus rule YAML 可通过导入接口转换为 AlertKnowledge 草稿或发布项。
- Graylog 通过可选 `GRAYLOG_URL` 接入日志、事件、异常和关联证据。
- OpenNMS 通过可选 `OPENNMS_URL` 接入 alarm、`uei`、`reductionKey`、严重级别和 ack/clear 状态。

详细总结见：[docs/knowledge-management-module-summary.md](docs/knowledge-management-module-summary.md)。

## 前端页面

| 页面 | 路径 | 说明 |
| --- | --- | --- |
| 驾驶舱 | `/` | 全局运维态势 |
| 登录 | `/login` | 演示账号登录 |
| AI 对话 | `/chat` | 自然语言运维协作 |
| 故障事件 | `/incidents` | 事件列表与诊断入口 |
| 诊断工作台 | `/diagnosis` | RCA、证据、工具轨迹 |
| 证据中心 | `/evidence` | 证据查看与关联 |
| 变更分析 | `/change-impact` | 变更风险与影响范围 |
| 资源 vCenter | `/resources/vcenter` | vCenter 资源总览 |
| 资源 Kubernetes | `/resources/k8s` | K8s 资源总览 |
| 拓扑 | `/topology` | 资源拓扑视图 |
| 工具 | `/tools` | 工具清单与健康 |
| 执行记录 | `/executions` | 执行与回执 |
| 审批中心 | `/approvals` | 高风险动作审批 |
| 通知中心 | `/notifications` | 通知与值班 |
| 审计中心 | `/audit` | 审计时间线 |
| Agent 运行 | `/agents`、`/runs/[id]` | Agent DAG 与运行详情 |
| 案例归档 | `/cases` | 历史案例与复盘 |
| 知识概览 | `/knowledge` | 知识统计、分类、导入任务 |
| 告警知识列表 | `/knowledge/alert-items` | 过滤、分页、查看、废弃、匹配测试入口 |
| 告警知识详情 | `/knowledge/alert-items/[id]` | 证据、规则、处置、自动化动作和关联案例 |
| 知识导入 | `/knowledge/import` | JSON、JSONL、Prometheus YAML dry-run 与确认导入 |
| 告警匹配测试 | `/knowledge/test-alert-match` | 验证 top-k、why、证据需求和动作建议 |
| 策略管理 | `/policies`、`/memory-policies` | OPA 和记忆策略 |
| 记忆管理 | `/memory` | 运维记忆 |
| 密钥管理 | `/secrets` | Secret Store |
| 连接管理 | `/connections` | 外部系统连接 |
| 升级管理 | `/upgrade` | 版本包与部署历史 |
| 设置 | `/settings` | 系统设置 |

## 核心 API

所有 API 遵循统一 envelope：

```json
{
  "request_id": "req-xxx",
  "success": true,
  "message": "ok",
  "data": {},
  "error": null,
  "audit_ref": null,
  "trace_id": "trace-xxx",
  "timestamp": "2026-04-05T09:00:00Z"
}
```

### 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | 登录，返回 JWT HttpOnly Cookie |
| `GET` | `/api/v1/auth/me` | 获取当前用户 |
| `POST` | `/api/v1/auth/logout` | 注销 |

### 诊断与事件

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/v1/chat/sessions` | 创建会话 |
| `GET` | `/api/v1/chat/sessions` | 会话列表 |
| `POST` | `/api/v1/chat/sessions/{id}/messages` | 发送消息并触发诊断意图识别 |
| `GET` | `/api/v1/chat/sessions/{id}/messages` | 会话消息 |
| `GET` | `/api/v1/chat/sessions/{id}/evidence` | 会话关联证据 |
| `GET` | `/api/v1/chat/sessions/{id}/tool-traces` | 工具轨迹 |
| `GET` | `/api/v1/chat/diagnoses/{id}` | 诊断详情 |
| `GET` | `/api/v1/incidents` | 事件列表 |
| `GET` | `/api/v1/incidents/{id}` | 事件详情 |
| `POST` | `/api/v1/incidents/{id}/analyze` | 触发 RCA 分析 |

### 资源、工具与拓扑

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/tools` | 工具列表 |
| `GET` | `/api/v1/tools/health` | 工具健康 |
| `GET` | `/api/v1/resources/vcenter/overview` | vCenter 资源总览 |
| `GET` | `/api/v1/resources/vcenter/inventory` | vCenter 资源清单 |
| `GET` | `/api/v1/resources/k8s/overview` | Kubernetes 资源总览 |
| `GET` | `/api/v1/resources/k8s/workloads` | Kubernetes 工作负载 |
| `GET` | `/api/v1/topology/*` | 拓扑相关接口 |

### 知识管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/knowledge/stats` | 知识统计 |
| `GET` | `/api/v1/knowledge/articles` | 兼容旧文章列表 |
| `GET` | `/api/v1/knowledge/articles/{id}` | 兼容旧文章详情 |
| `GET` | `/api/v1/knowledge/alert-items` | 告警知识列表，支持过滤和分页 |
| `POST` | `/api/v1/knowledge/alert-items` | 创建或 upsert 告警知识 |
| `GET` | `/api/v1/knowledge/alert-items/{id}` | 告警知识详情 |
| `POST` | `/api/v1/knowledge/alert-items/{id}:deprecate` | 废弃告警知识 |
| `POST` | `/api/v1/knowledge/import/validate` | 导入 dry-run 校验 |
| `POST` | `/api/v1/knowledge/alert-items:bulk-import` | 批量导入 |
| `GET` | `/api/v1/knowledge/import-jobs` | 导入任务列表 |
| `GET` | `/api/v1/knowledge/import-jobs/{job_id}` | 导入任务详情 |
| `POST` | `/api/v1/knowledge/alert-match` | 告警知识匹配 |
| `POST` | `/api/v1/knowledge/feedback` | 人工反馈 |
| `POST` | `/api/v1/knowledge/importers/prometheus-rules` | Prometheus rule YAML 转知识 |

### 案例、治理与执行

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/cases` | 案例列表 |
| `GET` | `/api/v1/cases/{id}` | 案例详情 |
| `POST` | `/api/v1/cases/similar` | 相似案例召回 |
| `POST` | `/api/v1/cases/from-incident` | 从 incident 生成案例草稿 |
| `GET` | `/api/v1/approvals` | 审批列表 |
| `GET` | `/api/v1/approvals/{id}` | 审批详情 |
| `POST` | `/api/v1/approvals/{id}/decide` | 审批决策 |
| `GET` | `/api/v1/notifications` | 通知列表 |
| `POST` | `/api/v1/notifications/{id}/acknowledge` | 确认通知 |
| `GET` | `/api/v1/audit/logs` | 审计日志 |
| `GET` | `/api/v1/audit/logs/{id}` | 审计日志详情 |
| `GET` | `/api/v1/policies` | 策略列表 |
| `PATCH` | `/api/v1/policies/{id}/toggle` | 启停策略 |
| `GET` | `/api/v1/agent-runs` | Agent 运行记录 |
| `GET` | `/api/v1/agent-runs/{id}` | Agent 运行详情 |
| `GET` | `/api/v1/upgrades` | 升级包列表 |
| `POST` | `/api/v1/upgrades/{id}/deploy` | 触发部署 |

## 服务健康检查

| 服务 | 端口 | 健康检查 |
| --- | --- | --- |
| Web | 3000 | `GET /` |
| API BFF | 8000 | `GET /health` |
| Orchestrator | 8010 | `GET /health` |
| Tool Gateway | 8020 | `GET /api/v1/health` |
| VMware Gateway | 8030 | `GET /health` |
| Change Impact | 8040 | `GET /health` |
| Evidence Aggregator | 8050 | `GET /health` |
| Event Ingestion | 8060 | `GET /health` |
| Approval Center | 8070 | `GET /health` |
| Governance | 8071 | `GET /health` |
| Knowledge Service | 8072 | `GET /health` |
| Memory Service | 8073 | `GET /health` |
| Kubernetes Gateway | 8080 | `GET /health` |
| Topology Service | 8090 | `GET /health` |

## 测试与验证

常用命令：

```bash
# 后端测试
python -m pytest

# 知识管理和推理链路 focused tests
python -m pytest tests/test_alert_knowledge.py tests/test_knowledge.py tests/test_alert_reasoning_integration.py tests/test_evidence_aggregator.py tests/test_orchestrator.py -q

# 前端 lint
pnpm --filter @opspilot/web lint

# 前端构建
pnpm --filter @opspilot/web build
```

当前知识管理增强已验证：

- `AlertKnowledge` schema、legacy decision tree 兼容和动作风险分类。
- 单条 upsert、bulk import、dry-run、import jobs、deprecate、feedback。
- `alert-match` 的 exact、alias、keyword、tag、category、negative keyword 评分。
- CPU、HA、vMotion、storage、network 等相似案例召回排序。
- RCA 输出包含 matched knowledge、evidence required、missing critical evidence、evidence sufficiency、safe actions、approval actions 和 similar cases。
- 远端 `192.168.51.169` 部署后 Web、BFF、Knowledge Service、知识列表和 alert-match API 均验证通过。

注意：全量测试和全量 lint 可能仍包含非知识模块的既有失败项，开发时建议先跑对应模块的 focused tests，再按发布范围处理全量回归。

## 设计原则

1. 所有工具访问经过 Tool Gateway。
2. 前端只访问 API BFF，不直接连接底层服务。
3. Orchestrator 负责编排和总结，不直接绕过工具、证据和策略边界。
4. 证据先于结论，根因必须受到证据充分性约束。
5. 高风险动作必须进入审批链路，不自动执行。
6. 知识要能被匹配、解释、反馈和复盘，而不只是被检索。
7. 外部接入默认只读，自动化执行必须显式治理。
8. 优先保持私有化、可离线、可审计、可回滚。

## 许可证

Proprietary - OpsPilot Enterprise
