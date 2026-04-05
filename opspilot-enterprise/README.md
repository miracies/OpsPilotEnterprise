# OpsPilot Enterprise

企业级 AIOps 智能运维平台 — 面向私有环境的故障诊断、变更影响分析、证据汇聚、知识增强、审批闭环和受控执行。

## 架构概览

```
Web UI (Next.js)
    │
    ▼
API BFF (FastAPI :8000)
    │
    ├──► LangGraph Orchestrator (:8010)
    │        │
    │        ▼
    │    Tool Gateway (:8020)
    │        ├──► VMware Skill Gateway (:8030)
    │        ├──► Change Impact Service (:8040)
    │        └──► Evidence Aggregator (:8050)
    │
    └──► Event Ingestion Service (:8060)
```

## 技术栈

### 前端

- Next.js 16 + React 19 + TypeScript
- Tailwind CSS 4 + shadcn/ui 风格组件
- TanStack Query + Recharts + Lucide Icons

### 后端

- Python 3.12 + FastAPI
- Pydantic v2 统一 schema
- httpx 服务间通信

### 平台（首期预留）

- OPA 策略中枢
- n8n 审批/工单/通知
- Harbor + OCI 离线分发

## 快速开始

### 前置条件

- Node.js >= 18 + pnpm >= 8
- Python >= 3.11
- (可选) Docker + Docker Compose

### 1. 安装依赖

```bash
# 前端
cd apps/web && pnpm install

# 后端共享 schema
pip install -e packages/shared-schema

# 各后端服务
pip install -e services/tool-gateway --no-deps
pip install -e services/vmware-skill-gateway --no-deps
pip install -e services/change-impact-service --no-deps
pip install -e services/evidence-aggregator --no-deps
pip install -e services/event-ingestion-service --no-deps
pip install -e services/langgraph-orchestrator --no-deps
pip install -e apps/api-bff --no-deps
```

### 2. 启动后端服务

**PowerShell (Windows):**

```powershell
.\scripts\dev-backend.ps1
```

**Bash (Linux/macOS):**

```bash
bash scripts/dev-backend.sh
```

或手动逐个启动：

```bash
uvicorn app.main:app --port 8020 --reload  # Tool Gateway
uvicorn app.main:app --port 8030 --reload  # VMware Gateway
uvicorn app.main:app --port 8040 --reload  # Change Impact
uvicorn app.main:app --port 8050 --reload  # Evidence Aggregator
uvicorn app.main:app --port 8060 --reload  # Event Ingestion
uvicorn app.main:app --port 8010 --reload  # Orchestrator
uvicorn app.main:app --port 8000 --reload  # API BFF
```

### 3. 启动前端

```bash
cd apps/web && pnpm dev
```

访问 [http://localhost:3000](http://localhost:3000)

### 4. Docker Compose (一键启动全部)

```bash
cd deploy/docker
docker compose up --build
```

## 项目结构

```
opspilot-enterprise/
├── apps/
│   ├── web/                          # Next.js 前端
│   └── api-bff/                      # BFF 聚合层
├── services/
│   ├── langgraph-orchestrator/       # Agent 编排服务
│   ├── tool-gateway/                 # 统一工具控制面
│   ├── vmware-skill-gateway/         # VMware 领域服务 (mock)
│   ├── change-impact-service/        # 变更影响分析
│   ├── evidence-aggregator/          # 证据聚合
│   └── event-ingestion-service/      # 事件接入
├── packages/
│   ├── shared-types/                 # TypeScript 类型定义
│   ├── shared-schema/                # Python Pydantic schema
│   └── shared-ui/                    # (预留) 公共 UI 组件
├── deploy/docker/                    # Docker Compose
├── policy/rego/                      # OPA 策略示例
├── scripts/                          # 开发脚本
├── tests/                            # 集成测试
└── docs/                             # 架构文档
```

## 核心 API

所有 API 遵循统一 envelope 格式：

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

### P0 接口


| 方法   | 路径                                    | 说明     |
| ---- | ------------------------------------- | ------ |
| POST | `/api/v1/chat/sessions`               | 创建对话   |
| POST | `/api/v1/chat/sessions/{id}/messages` | 发送消息   |
| GET  | `/api/v1/incidents`                   | 故障事件列表 |
| GET  | `/api/v1/incidents/{id}`              | 事件详情   |
| POST | `/api/v1/incidents/{id}/analyze`      | 触发分析   |
| POST | `/api/v1/change-impact/analyze`       | 变更影响分析 |
| GET  | `/api/v1/tools`                       | 工具列表   |
| GET  | `/api/v1/tools/health`                | 工具健康   |


### 各服务健康检查


| 服务              | 端口   | 端点                   |
| --------------- | ---- | -------------------- |
| API BFF         | 8000 | `GET /health`        |
| Orchestrator    | 8010 | `GET /health`        |
| Tool Gateway    | 8020 | `GET /api/v1/health` |
| VMware Gateway  | 8030 | `GET /health`        |
| Change Impact   | 8040 | `GET /health`        |
| Evidence Agg.   | 8050 | `GET /health`        |
| Event Ingestion | 8060 | `GET /health`        |


## 设计原则

1. **所有工具访问必须经过 Tool Gateway**
2. **OPA 负责策略判定，不把权限逻辑写死在代码中**
3. **LangGraph 只负责编排和总结，不直接访问底层资源**
4. **前端只展示和发起请求，不直接连后端工具服务**
5. **执行类动作必须支持审批、审计、回执**
6. **证据先于结论 — 所有诊断建议必须附带证据来源**
7. **先 mock 跑通，再接真实 VMware/OPA/n8n/RAG**
8. **平台必须支持新 Skill/Gateway 动态接入**

## 首期 P0 页面

- **驾驶舱** — 全局运维态势总览
- **AI 对话** — 自然语言运维协作，支持工具轨迹与证据展示
- **故障事件中心** — 事件列表、筛选、预览与快速进入处置
- **诊断工作台** — 三栏布局：上下文 + 分析 + 辅助信息
- **变更分析** — 影响范围、风险评分、依赖图、回退方案

## 许可证

Proprietary — OpsPilot Enterprise