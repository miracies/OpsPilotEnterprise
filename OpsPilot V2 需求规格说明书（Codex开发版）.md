

# 📘 OpsPilot V2 需求规格说明书（Codex开发版）

版本：V2.0
日期：2026-04
适用对象：前后端开发 / Agent开发 / 平台架构 / 运维自动化团队

---

# 一、项目目标（必须统一认知）

## 🎯 1.1 目标定义

OpsPilot V2 的目标：

```text
从自动化运维平台 → 升级为 AIOps 智能运维平台
```

---

## 🎯 1.2 核心能力闭环

```text
事件 → 分析 → 根因 → 决策 → 执行 → 验证 → 归档 → 学习
```

---

## 🎯 1.3 本版本重点能力

* 多 Agent 协同诊断
* VMware 自动化运维（Skill化）
* Evidence + Topology 数据驱动分析
* 自动修复（Auto Remediation）
* Tool Gateway 统一控制

---

# 二、总体功能架构（开发视图）

---

## 2.1 分层架构（必须按此拆模块）

```text
1. 前端层（Web）
2. BFF层（API聚合）
3. AI编排层（Orchestrator）
4. Agent层（多Agent）
5. Tool Gateway（控制平面）
6. Skill层（执行层）
7. 数据智能层（Evidence / Graph / RAG）
```

---

## 2.2 模块拆分（后端服务）

| 模块       | 服务名                  | 是否已有 | V2动作       |
| -------- | -------------------- | ---- | ---------- |
| 编排       | orchestrator         | ✔    | 增强多Agent   |
| 工具控制     | tool-gateway         | ✔    | 强化Schema校验 |
| VMware执行 | vmware-skill-gateway | ✔    | 扩展Skill    |
| 事件中心     | event-ingestion      | ✔    | 接入Evidence |
| 证据       | evidence-aggregator  | ⚠    | 去mock      |
| 拓扑       | topology-service     | ❌    | 新建         |
| 知识       | knowledge-service    | ✔    | 增强RAG      |
| 策略       | governance + OPA     | ✔    | 深化         |
| 连接中心     | connection-service   | ⚠    | 去mock      |
| 认证       | auth-service         | ⚠    | 接Keycloak  |

---

# 三、Agent设计（核心模块）

---

## 3.1 Agent分类（必须实现）

| Agent            | 职责     |
| ---------------- | ------ |
| RootCauseAgent   | 故障根因分析 |
| EvidenceAgent    | 证据收集   |
| TopologyAgent    | 拓扑推理   |
| RemediationAgent | 自动修复   |
| KnowledgeAgent   | 知识检索   |

---

## 3.2 Agent调用流程

```text
事件触发
 → RootCauseAgent
   → EvidenceAgent（拉数据）
   → TopologyAgent（分析依赖）
   → KnowledgeAgent（查KB）
 → RemediationAgent（生成执行方案）
```

---

## 3.3 Agent Prompt（必须实现）

```text
你是VMware运维专家。

任务：
1. 找根因
2. 找证据
3. 给修复方案

流程：
- 分析现象
- 列出3个可能原因
- 调用工具获取证据
- 排除错误原因
- 输出唯一根因

约束：
- 不允许猜测
- 必须引用证据

输出：
{
  "root_cause": "",
  "evidence": [],
  "confidence": 0.0,
  "solution": []
}
```

---

# 四、Skill 标准接口（强制规范）

---

## 4.1 Skill定义规范

```yaml
Skill:
  name: string
  description: string
  input_schema: JSON Schema
  output_schema: JSON Schema
  auth_required: true
```

---

## 4.2 VMware Skill 列表（必须实现）

---

### 1）虚拟机操作

* vmware.vm.power
* vmware.vm.create
* vmware.vm.delete

---

### 2）迁移与调度（核心）

* vmware.vm.migrate
* vmware.cluster.balance

---

### 3）监控查询

* vmware.vm.metrics
* vmware.host.metrics

---

### 4）存储

* vmware.vsan.health
* vmware.datastore.usage

---

---

## 4.3 示例 Schema（必须实现）

```json
{
  "name": "vmware.vm.migrate",
  "input_schema": {
    "type": "object",
    "properties": {
      "vm_id": { "type": "string" },
      "target_host": { "type": "string" }
    },
    "required": ["vm_id", "target_host"]
  }
}
```

---

## 4.4 Tool Gateway 校验机制（必须实现）

```text
LLM输出 → JSON Schema校验 → 不通过拒绝执行
```

---

# 五、VMware 运维操作（转Skill清单）

---

## 5.1 生命周期管理

* 创建 VM
* 删除 VM
* 开关机
* 快照管理

---

## 5.2 调度与迁移（重点）

* vMotion
* DRS 调度
* 跨主机迁移

---

## 5.3 故障处理

* 主机宕机处理
* VM异常重启
* 存储不可用处理

---

## 5.4 监控巡检

* CPU / 内存 / latency
* vSAN健康
* 网络流量

---

## 5.5 变更管理

* 主机维护模式
* 补丁升级

---

# 六、数据基础（AIOps核心）

---

## 6.1 必须采集的数据

---

### 1）Metrics

* CPU / Memory
* vSAN latency
* 网络流量

---

### 2）Events

* VM迁移
* HA事件
* 故障事件

---

### 3）Logs

* hostd.log
* vmkernel.log

---

### 4）Topology（必须新增）

```text
VM → Host → Cluster
VM → Datastore
VM → Network
```

---

### 5）Knowledge

* 故障案例
* Runbook

---

---

## 6.2 Evidence 模型

```text
Evidence = Metrics + Events + Logs + Topology
```

---

# 七、自动修复（核心能力）

---

## 7.1 自动修复策略

| 场景      | 自动动作    |
| ------- | ------- |
| Host过载  | 自动迁移VM  |
| VM CPU高 | 调整资源    |
| vSAN拥塞  | balance |

---

---

## 7.2 执行流程

```text
分析 → 策略判断 → 自动执行 or 审批 → 执行 → 验证
```

---

---

# 八、前端功能需求

---

## 8.1 页面模块

* 首页驾驶舱
* AI对话
* 故障事件中心
* 诊断工作台
* 执行中心
* 审批中心
* 证据中心
* 拓扑视图（新增）

---

---

## 8.2 关键能力

* 实时分析进度
* 证据可视化
* 一键执行修复

---

# 九、非功能要求

---

## 9.1 安全

* RBAC
* OPA策略
* 审计日志

---

## 9.2 性能

* 事件分析 ≤ 60秒
* Tool调用 ≤ 5秒

---

## 9.3 可扩展性

* 支持新增Skill
* 支持新增Agent

---

# 十、开发优先级（必须按此执行）

---

## P0（立即）

* Topology Graph
* Evidence Aggregator（去mock）
* RootCause Agent

---

## P1

* 自动修复
* Skill扩展
* Tool Gateway校验

---

## P2

* RAG增强
* 多Agent协同

---

# ✅ 最终说明（给Codex/研发）

这份文档的本质：

```text
不是功能说明，而是“可执行架构蓝图”
```

Codex开发时必须遵循：

* 所有能力必须通过 Skill 暴露
* 所有调用必须走 Tool Gateway
* 所有分析必须基于 Evidence
* 所有决策必须可审计

---
