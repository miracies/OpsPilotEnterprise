# OpsPilot Enterprise 架构说明

## 总体架构

```
[Web UI / Chat UI / Event Ingestion]
              │
              ▼
    [API BFF 聚合层]
              │
    ┌─────────┼─────────┐
    │         │         │
    ▼         ▼         ▼
[Orchestrator] [Event   [直接查询]
    │         Ingestion]
    ▼
[Tool Gateway 统一控制面]
    │
    ├─ [OPA 策略判定]  (预留)
    │
    ├─ [VMware Skill Gateway]
    ├─ [Change Impact Service]
    ├─ [Evidence Aggregator]
    └─ [RAG Service]  (预留)
```

## 核心设计原则

1. **Tool Gateway 前置控制** — 所有工具访问必须经过 Tool Gateway
2. **Agent 不直接访问底层系统** — Orchestrator 只负责编排
3. **前端不内嵌权限** — 权限判定由 OPA 负责
4. **证据先于结论** — 所有诊断必须附带证据来源
5. **Mock 优先** — 先 mock 跑通，再接真实系统

## 服务间通信

```
前端 → API BFF → Orchestrator → Tool Gateway → 领域 Gateway
                                    ↓
                               OPA (策略)
```

- 前端只与 API BFF 通信
- BFF 转发到 Orchestrator 或直接到 Event Ingestion
- Orchestrator 通过 Tool Gateway 调用所有工具
- Tool Gateway 做 schema 校验、权限检查、审计记录

## SubAgent 架构

Orchestrator 内部采用 SubAgent 模式：


| Agent                   | 职责         |
| ----------------------- | ---------- |
| IntentAgent             | 意图识别与请求结构化 |
| EvidenceCollectionAgent | 证据采集       |
| KBRetrievalAgent        | 知识库检索      |
| RCAAgent                | 根因分析       |
| NotificationAgent       | 通知值班人      |
| CaseArchiveAgent        | 案例归档       |


首期为结构桩，预留真实 LangGraph 接入位。

## 扩展模型

新领域能力通过 Gateway 模式接入：

1. 实现领域 Gateway（如 Kubernetes Skill Gateway）
2. 通过 Tool Registry 注册工具元数据
3. Tool Gateway 自动路由
4. Agent 按工具元数据发现新能力

