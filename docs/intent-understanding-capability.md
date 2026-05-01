# OpsPilot V2 意图感知能力说明（全面版）

## 1. 文档目的

本文档系统整理 OpsPilot 当前意图感知（Intent Understanding / Intent Recovery）能力的设计与实现现状，覆盖：

- 能力边界与目标
- 架构与流程
- 接口与数据模型
- Clarify/Approve/执行联动
- 审计与恢复
- 评测与验收口径
- 运维配置与常见问题
- 后续演进路线（P0/P1/P2）

适用对象：后端开发、前端开发、测试、运维、产品与架构评审。

---

## 2. 能力目标与范围

### 2.1 目标

将用户自然语言请求稳定转化为可执行、可审计、可回滚的运维意图，避免“咨询语义误执行”。

### 2.2 范围

当前能力重点覆盖：

- vCenter/VMware、K8s、主机、Jenkins、知识问答
- 对话入口（chat）中的意图恢复、澄清补槽、审批门禁、执行推进
- 意图分析链路的审计可追踪与 checkpoint 可恢复

### 2.3 非目标

- 不替换现有 legacy chat/diagnosis 硬编码链路
- 不引入新的 Node 意图引擎服务
- 不在本阶段做高风险策略自动放开

---

## 3. 总体架构

### 3.1 服务分层

- Web（Next.js）：对话页面、卡片交互、时间线展示
- API-BFF（FastAPI）：统一对外 API 入口与代理聚合
- Langgraph-Orchestrator（FastAPI）：意图分析、交互编排、审计/恢复核心
- Tool Gateway：工具注册、输入输出校验、策略门禁、路由执行
- Knowledge Service：知识检索与证据来源
- Event Ingestion：审计日志与事件数据联动

### 3.2 关键路径

1. 用户发消息 -> `POST /api/v1/chat/sessions/{id}/messages`
2. BFF 按模式转发到 Orchestrator v2
3. Orchestrator 执行意图分析与门禁决策
4. 结果回传（含卡片、轨迹、证据、摘要）
5. 前端按 `kind` + 字段渲染交互卡片与状态时间线

---

## 4. 意图分析六层流程（P0 Lite）

实现入口：`POST /api/v1/intent/analyze`

固定顺序：

1. Context Completion（上下文补全）
2. Semantic Normalization（语义标准化）
3. Intent Recovery（候选召回与打分）
4. Intent Disambiguation（歧义消解）
5. Execution Intent Separation（执行意图分离）
6. Environment Awareness（环境与范围感知）

### 4.1 Context Completion

输入：`utterance + history + memory + ui_context + resource_catalog`
输出：`context_hints`、补全后的查询文本

作用：

- 利用会话历史、UI 环境、连接偏好补齐关键信息
- 记录 memory 命中引用，供审计与页面展示

### 4.2 Semantic Normalization

输出：`normalized_utterance`

作用：

- 将同义表达映射到标准动作/对象词（如“开机/上电 -> power on”）
- 降低多表达导致的匹配不稳定

### 4.3 Intent Recovery

输出：`candidates[]`、`selected_intent`、`decision`

当前评分公式：
`final = 0.35*rules + 0.20*slot_completeness + 0.15*entity_match + 0.15*memory_boost + 0.15*llm_rerank`

决策阈值：

- recovered：`top1 >= 0.78` 且 `top1-top2 >= 0.15` 且无关键缺槽
- clarify_required：`top1 >= 0.55` 或存在关键缺槽
- rejected：其余

### 4.4 Intent Disambiguation

作用：

- top1/top2 接近或缺槽时不直接执行
- 转为 Clarify 交互，由用户补槽/确认

### 4.5 Execution Intent Separation

输出：`execution_intent.mode = read | plan | execute`

强约束：

- 咨询/分析类语义（如“先看看/怎么做/分析一下”）禁止直接 execute
- 只读/规划请求必须停留在 read/plan

### 4.6 Environment Awareness

输出：`risk_context`（environment/resource_scope/object_count）

作用：

- 为策略引擎与审批门禁提供上下文
- 支撑生产环境更严格约束

---

## 5. 交互联动：Clarify -> Approve -> Execute

### 5.1 Clarify

- 缺槽或歧义时创建 Clarify 卡片
- 用户回答后自动 rerun analyze/recover
- rerun 结果可继续 Clarify 或进入审批/执行门禁

### 5.2 Approve

- 风险达到 L2+ 默认走审批
- Approve 不负责补槽，只负责授权决策
- 拒绝后流程终止，不进入执行

### 5.3 自动推进执行

- 审批通过后自动进入执行步骤
- 每步写 `PRE_EXEC / POST_EXEC` 审计与 checkpoint
- 返回 `execution_progress` 供前端展示

---

## 6. API 一览（`/api/v1`）

### 6.1 意图与记忆检索

- `POST /api/v1/intent/analyze`
- `POST /api/v1/intent/recover`（兼容保留）
- `POST /api/v1/memory/upsert`
- `POST /api/v1/rag/retrieve`

### 6.2 交互

- `POST /api/v1/interactions/clarify`
- `POST /api/v1/interactions/clarify/{id}/answer`
- `POST /api/v1/interactions/approve`
- `POST /api/v1/interactions/approve/{id}/decision`

### 6.3 审计与恢复

- `GET /api/v1/runs/{run_id}/audit`
- `POST /api/v1/runs/{run_id}/resume`

---

## 7. 关键数据结构

### 7.1 Intent Analyze 响应核心字段

- `decision`
- `selected_intent`
- `candidates[]`
- `execution_intent`
- `risk_context`
- `context_hints`
- `normalized_utterance`
- `memory_refs[]`
- `evidence_refs[]`
- `clarify_card?`
- `approval_card?`

### 7.2 前端消息扩展字段

- `intent_recovery`
- `execution_intent`
- `risk_context`
- `memory_refs`
- `rerun_result`
- `execution_progress`

### 7.3 审计事件扩展

- `CONTEXT_COMPLETED`
- `NORMALIZED`
- `DISAMBIGUATED`
- `EXECUTION_INTENT_SET`
- `MEMORY_HIT`
- `RAG_RETRIEVED`

---

## 8. 存储策略与迁移

### 8.1 当前策略

- 主链路仍可用 SQLite（保证兼容）
- 同步引入 PostgreSQL + pgvector 骨架
- 关键实体写入支持 shadow 事件（用于双写验证）

### 8.2 迁移建议

- 阶段一：SQLite 主读写 + Postgres 影子验证
- 阶段二：切 Intent/Interaction/Audit/Checkpoint 到 Postgres 主读写
- 阶段三：SQLite 仅保留回溯窗口后下线

---

## 9. 前端展示规范

### 9.1 卡片

- IntentRecoveryCard：候选意图、缺槽、执行意图、风险上下文、记忆/证据引用
- ClarifyCard：补槽与歧义确认
- ApprovalCard：风险与授权范围
- ResumeCard：恢复点信息
- AuditTimeline：全过程审计事件

### 9.2 时间线

- in_progress 时展示最新状态
- 历史状态折叠
- 交互后自动推进通过 `workflow_update` 与 `execution_progress` 可见

---

## 10. 验收指标与测试建议

### 10.1 精度与门禁

- Top-1 接受率 >= 90%
- Clarify 召回率 >= 95%（歧义场景）
- 咨询语句误执行率 = 0%

### 10.2 联动流程

- Clarify 回答后自动 rerun 成功
- Approve 通过后自动执行推进成功
- Approve 拒绝后不进入执行

### 10.3 可追溯与恢复

- run 可完整追踪：recover -> clarify -> approve -> exec -> resume
- 重试/恢复不出现同一 idempotency key 重复副作用

### 10.4 已落地基础测试

Orchestrator 当前包含：

- `test_intent_scorer.py`
- `test_risk_policy.py`
- `test_resume_idempotent.py`
- `test_intent_analyze.py`
- `test_memory_rag.py`

---

## 11. 运维配置

### 11.1 关键环境变量

- `ORCHESTRATOR_POSTGRES_DSN`
- `NEXT_PUBLIC_CHAT_MODE=legacy|orchestrator_v2`
- `DEFAULT_CHAT_MODE=legacy|orchestrator_v2`
- `KNOWLEDGE_SERVICE_URL`

### 11.2 Docker

`deploy/docker/docker-compose.yml` 已支持 `postgres (pgvector 镜像)`，可用于 memory/rag 与双写演进。

---

## 12. 常见问题（FAQ）

### Q1: 为什么咨询语句不直接执行？

A: 执行意图分离是强安全门禁，避免“问法像执行”导致生产副作用误触发。

### Q2: 为什么仍保留 recover 接口？

A: 为兼容旧链路和外部调用方，`analyze` 是增强入口，`recover` 作为兼容层保留。

### Q3: RAG 未命中怎么办？

A: 明确返回“证据不足”，不给高置信结论，不使用 mock 填充。

### Q4: PostgreSQL 不可用会怎样？

A: 主链路可回退 SQLite/内存存储，不阻断基础对话与意图流程；建议尽快恢复 Postgres 以保证长期记忆与检索质量。

---

## 13. 后续路线（P1/P2）

### P1

- 组织级 Memory 与真实向量检索增强
- RAG 重排与证据质量评分
- 指标看板（命中率、clarify率、误执行率）

### P2

- 反馈学习闭环（人工纠正 -> 别名/模板增量）
- Shadow Eval 回放与灰度阈值治理
- 更细粒度多租户合规与生命周期管理

---

## 14. 参考实现位置

- Orchestrator: `services/langgraph-orchestrator/app/`
- BFF: `apps/api-bff/app/routers/`
- Web Chat: `apps/web/src/app/chat/page.tsx`
- Shared Schema: `packages/shared-schema/src/opspilot_schema/`
- Shared Types: `packages/shared-types/src/`

> 建议将本文件作为意图能力基线文档，后续每次规则/阈值/API 变更同步更新。