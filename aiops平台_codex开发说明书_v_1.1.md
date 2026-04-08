# AIOps 平台项目开发说明书（供 Codex 开发）

## 1. 项目名称

**项目名称：OpsPilot Enterprise**

### 1.1 命名说明

OpsPilot Enterprise 表示一个面向企业运维场景的智能运维平台：

* **Ops**：运维（Operations）
* **Pilot**：辅助驾驶/智能引导，体现“AI 辅助而非完全失控自治”
* **Enterprise**：强调企业级安全、治理、审计与离线部署能力

### 1.2 项目定位

OpsPilot Enterprise 是一个面向企业私有环境的 AIOps 平台，聚焦 VMware 场景下的**故障诊断、变更影响分析、证据汇聚、知识增强、审批闭环和受控执行**。

平台采用“**Agent 编排 + 统一控制面 + 策略中枢 + 领域 Skill Gateway + 流程编排 + 离线升级**”的总体架构。

---

## 2. 本文档用途

本文档用于指导 Codex 按照统一架构、明确模块边界和约束实现首期可交付版本（MVP / V1）。

Codex 的开发目标不是自由发挥，而是：

1. 按本文档定义的模块边界进行代码生成。
2. 按本文档给出的目录结构、接口规范、数据模型和调用链完成实现。
3. 不绕过 Tool Gateway。
4. 不将安全、审批、策略判断内嵌到前端或 Agent Prompt 中。
5. 不让 Agent 直接访问 VMware、知识库或外部流程系统。

---

## 3. 建设目标

### 3.0 可扩展能力目标

平台必须从首期开始具备 **Skill 可安装、可注册、可治理、可扩展** 的能力，不仅支持现有 VMware 场景，还要支持后续按领域逐步扩展新的运维能力，包括但不限于：

* Kubernetes / OpenShift 管理能力
* 物理网络设备管理能力
* 物理存储设备管理能力
* 公有云资源管理能力
* CMDB / ITSM / 监控平台 / 日志平台等外部系统集成能力

平台架构必须保证：

1. 新增 Skill 或新领域 Gateway 时，不需要重构主 Agent。
2. 新增能力必须仍然经过 Tool Gateway 和 OPA 控制。
3. 新增 Skill 必须支持标准化注册、版本管理、健康检查、权限控制、审计和下线。
4. 平台必须预留多领域扩展模型，而不是只为 VMware 单域设计。

### 3.1 首期目标

首期建设一个可上线的企业级 AIOps 平台，支持以下能力：

* 基于自然语言的运维问答与诊断
* VMware 监控/对象/事件/拓扑/性能信息查询
* 故障诊断分析与证据展示
* 变更影响分析
* 审批后执行部分 VMware 运维动作
* 与工单、通知、审批系统集成
* 审计留痕
* 全离线部署与离线升级
* 自动发现故障并触发分析流程
* 自动通知值班人员
* 自动分析故障并输出根因候选
* 自动查询外部 KB 与内部 RAG
* 输出面向值班人员的结论与处置建议
* 自动归档故障处理过程和处理结果
* 记忆用户偏好、历史需求与历史故障上下文

### 3.1A 智能运维闭环目标

平台不仅要支持“人发起 -> AI 辅助”，还要支持“**事件触发 -> 自动分析 -> 自动通知 -> 人机协同处置 -> 自动归档复盘**”的闭环。

首期闭环应至少覆盖：

1. 监控/告警/事件进入平台。
2. 平台自动判定是否疑似故障。
3. 自动触发多 SubAgent 协同分析。
4. 自动查询内部知识与外部 KB。
5. 自动形成分析结论、根因候选、影响范围、建议动作。
6. 自动通知值班人员，并将结论同步至待处理界面。
7. 值班人员反馈最终处理动作。
8. 平台自动归档为 Incident Case，并沉淀为后续检索和复用资产。
   首期建设一个可上线的企业级 AIOps 平台，支持以下能力：

* 基于自然语言的运维问答与诊断
* VMware 监控/对象/事件/拓扑/性能信息查询
* 故障诊断分析与证据展示
* 变更影响分析
* 审批后执行部分 VMware 运维动作
* 与工单、通知、审批系统集成
* 审计留痕
* 全离线部署与离线升级

### 3.2 二期方向

* 引入 Onyx 或类似组件增强企业搜索与知识连接能力
* 引入 VMware-Pilot 做 VMware 域内 workflow orchestration
* 保持 Tool Gateway 作为唯一统一控制入口

---

## 4. 范围定义

### 4.1 首期包含

* Web 界面
* Chat 对话界面
* 诊断工作台
* 变更影响分析工作台
* 审批与执行中心
* 审计与证据中心
* 知识管理基础能力
* Tool Gateway
* OPA 策略决策对接
* VMware Skill Gateway
* Change Impact Service
* Evidence Aggregator
* RAG Service
* n8n 对接
* Harbor / OCI / OPA bundle 升级机制
* Skill / Gateway 扩展框架（首期即需具备）
* 新领域能力接入规范（K8s / 网络 / 存储预留）
* Web 界面
* Chat 对话界面
* 诊断工作台
* 变更影响分析工作台
* 审批与执行中心
* 审计与证据中心
* 知识管理基础能力
* Tool Gateway
* OPA 策略决策对接
* VMware Skill Gateway
* Change Impact Service
* Evidence Aggregator
* RAG Service
* n8n 对接
* Harbor / OCI / OPA bundle 升级机制

### 4.2 首期不包含

* 全自治自动修复
* Agent 直接控制生产 VMware 环境
* 多领域全量 AIOps（如网络、数据库、云平台全部首期纳入）
* 复杂企业搜索平台作为首期基础依赖
* 全量多 Agent 自治协作系统

---

## 5. 用户角色

### 5.0 系统内置智能角色（SubAgent）

除人类用户角色外，平台需内置多种 SubAgent，由主 Agent / Orchestrator 统一编排：

* **Intent Agent**：负责理解用户意图、请求类型、约束条件、目标对象和上下文
* **Incident Detection Agent**：负责对接告警、事件、指标异常，识别疑似故障并触发分析
* **Evidence Collection Agent**：负责拉取监控、事件、日志、拓扑、变更记录等证据
* **KB Retrieval Agent**：负责查询外部 KB、厂商知识、内部 RAG 知识库
* **Root Cause Analysis Agent**：负责根因分析、故障归因、置信度排序
* **Change Correlation Agent**：负责分析近期变更与故障的相关性
* **Notification Agent**：负责通知值班人员、推送结论、跟踪确认状态
* **Case Archive Agent**：负责将故障过程、结论、动作、结果自动归档
* **Memory Agent**：负责记忆用户历史需求、偏好、关注对象、历史故障上下文
* **Recommendation Agent**：负责输出处置建议、恢复建议、下一步检查建议

这些 SubAgent 不直接越权访问底层系统，仍统一通过 Tool Gateway 调用各类能力。

### 5.1 平台管理员

负责平台配置、用户角色、策略发布、连接器配置、升级包管理。

### 5.2 运维工程师

负责日常故障诊断、对象查询、变更分析、执行申请。

### 5.3 审批人

负责审批高风险操作和生产环境变更。

### 5.4 审计/安全人员

负责查看操作审计、证据链、策略命中记录。

### 5.5 知识管理员

负责知识库导入、标签管理、版本管理、有效期管理。

---

## 6. 总体架构

```text
[Web UI / Chat UI / Event Ingestion / Monitoring Alerts]
                |
                v
      [LangGraph 主 Agent / 编排层]
                |
     --------------------------------------
     |        |         |        |         |
     v        v         v        v         v
[Intent] [Incident] [Evidence] [RCA]   [KB/RAG]
 Agent    Detection   Collection Agent  Retrieval
          Agent       Agent             Agent
     |___________________________________________|
                         |
                         v
               [Tool Gateway 统一控制面]
   |        |         |            |            |            |
   v        v         v            v            v            v
 [OPA] [VMware Skill] [Change      [Evidence    [RAG         [Notification/
        Gateway]      Impact]       Store]       Service]     n8n Adapter]

附加能力：
- Memory Service：记忆用户需求、历史故障、历史处置
- Case Archive Service：故障归档、复盘、案例沉淀
- Tool / Skill Registry：新能力动态注册与治理

离线升级体系：
Harbor + OCI Artifacts + OPA Bundles
```

### 6.1 新增核心能力层

为支持自动发现、自动分析、记忆与归档，平台需新增以下逻辑能力层：

* **Event Ingestion Layer**：对接监控、告警、事件、Webhook、消息总线
* **SubAgent Layer**：按职责拆分的分析代理层
* **Memory & Case Layer**：用于沉淀用户历史、故障历史、处理经验、案例归档
* **Notification Layer**：通知值班人员、跟踪响应状态、联动审批/工单

```text
[Web UI / Chat UI]
        |
        v
[LangGraph 主 Agent / 编排层]
        |
        v
[Tool Gateway 统一控制面]
   |        |         |           |            |
   v        v         v           v            v
 [OPA] [VMware Skill] [Change     [Evidence    [RAG
        Gateway]      Impact]      Aggregator]  Service]
                                          |
                                          v
                                       [Knowledge Base]

旁路集成：
Tool Gateway <-> n8n（审批 / 通知 / 工单 / 同步）

离线升级体系：
Harbor + OCI Artifacts + OPA Bundles
```

---

## 7. 核心设计原则

1. **所有工具访问必须经过 Tool Gateway。**
2. **OPA 负责策略判定，不把权限逻辑写死在业务代码中。**
3. **LangGraph 只负责编排和总结，不直接访问底层资源。**
4. **前端只展示和发起请求，不直接连后端工具服务。**
5. **执行类动作必须支持审批、审计、回执。**
6. **证据先于结论。所有诊断建议必须附带证据来源。**
7. **首期重可控、可审计、可扩展，不追求全自动自治。**
8. **平台必须可离线部署、可离线升级。**
9. **平台必须支持新 Skill 和新领域能力的持续接入，不允许形成 VMware 单域架构锁定。**
10. **所有新接入能力必须遵循统一的 Tool Schema、权限模型、审计模型和升级模型。**
11. **领域能力扩展优先采用 Gateway / Adapter 模式，不允许 Agent 直接适配不同系统。**

## 7.1 Skill 扩展原则

平台需具备企业级 Skill 扩展框架，支持将新的领域能力作为受控插件接入，包括：

* 新 Skill 安装
* Skill 注册
* Skill 版本管理
* Skill 配置管理
* Skill 启停与下线
* Skill 健康检查
* Skill 能力发现
* Skill 权限绑定
* Skill 审计纳管
* Skill 离线升级

推荐采用“**领域 Gateway + Tool Registry + Tool Gateway 统一纳管**”模式：

* 针对 VMware、Kubernetes、Physical Network、Physical Storage 分别构建对应 Gateway
* Gateway 向 Tool Gateway 注册自身工具集
* Tool Gateway 对外统一暴露标准化能力
* Agent 仅感知工具元数据，不感知底层异构系统差异

1. **所有工具访问必须经过 Tool Gateway。**
2. **OPA 负责策略判定，不把权限逻辑写死在业务代码中。**
3. **LangGraph 只负责编排和总结，不直接访问底层资源。**
4. **前端只展示和发起请求，不直接连后端工具服务。**
5. **执行类动作必须支持审批、审计、回执。**
6. **证据先于结论。所有诊断建议必须附带证据来源。**
7. **首期重可控、可审计、可扩展，不追求全自动自治。**
8. **平台必须可离线部署、可离线升级。**

---

## 8. 模块清单

### 8.0 新增核心智能模块

为满足自动故障发现、自动分析、意图理解、历史记忆和案例沉淀，首期需补充以下平台级模块：

1. Event Ingestion Service
2. Intent Analysis Service / Intent Agent
3. SubAgent Orchestration 机制
4. Root Cause Analysis Service / RCA Agent
5. Memory Service
6. Case Archive Service
7. Notification Service / Notification Agent
8. Incident Timeline / Incident Case 管理模块

这些模块可以作为独立服务，也可以部分内嵌在 LangGraph Orchestrator 中，但必须在代码结构和职责边界上清晰拆分。

### 8.1 前端 Web UI

建议技术栈：

* React
* TypeScript
* Next.js 或 Vite + React
* Tailwind CSS
* 组件库可选 shadcn/ui

#### 前端模块

1. 登录与权限入口
2. 首页驾驶舱
3. AI 对话页面
4. 诊断工作台
5. 变更影响分析页面
6. 执行申请页面
7. 审批中心
8. 审计中心
9. 证据中心
10. 知识管理页面
11. 策略管理页面
12. 系统配置页面
13. 升级管理页面
14. 故障事件中心
15. 值班通知中心
16. 案例归档中心
17. 用户记忆/偏好视图
18. SubAgent 运行轨迹视图
    建议技术栈：

* React
* TypeScript
* Next.js 或 Vite + React
* Tailwind CSS
* 组件库可选 shadcn/ui

#### 前端模块

1. 登录与权限入口
2. 首页驾驶舱
3. AI 对话页面
4. 诊断工作台
5. 变更影响分析页面
6. 执行申请页面
7. 审批中心
8. 审计中心
9. 证据中心
10. 知识管理页面
11. 策略管理页面
12. 系统配置页面
13. 升级管理页面

---

### 8.2 LangGraph Orchestrator

职责：

* 用户意图识别
* 故障诊断流程编排
* 变更影响分析流程编排
* 证据聚合后的总结
* 结果输出格式化
* 人工介入点控制
* 自动故障分析流程编排
* 多 SubAgent 协同调度
* 长流程状态管理
* 故障 case 生命周期管理的主流程控制

不负责：

* 直接访问 vCenter
* 直接调用 n8n
* 直接访问 OPA
* 存放高权限凭据

#### 8.2.1 SubAgent 编排要求

LangGraph Orchestrator 必须支持 SubAgent 模式，至少具备以下能力：

* 主 Agent 接收用户请求或事件触发
* 将任务分派给不同职责的 SubAgent
* 支持串行与并行子任务
* 支持子任务超时、失败降级、重试
* 支持聚合多个 SubAgent 输出形成最终结论
* 支持在处理链中引入 human-in-the-loop
* 支持把处理过程沉淀为 case memory

推荐首期 SubAgent 调度顺序：

1. Intent Agent
2. Incident Detection Agent（事件触发时）
3. Evidence Collection Agent
4. Change Correlation Agent
5. KB Retrieval Agent
6. Root Cause Analysis Agent
7. Recommendation Agent
8. Notification Agent
9. Case Archive Agent
10. Memory Agent
    职责：

* 用户意图识别
* 故障诊断流程编排
* 变更影响分析流程编排
* 证据聚合后的总结
* 结果输出格式化
* 人工介入点控制

不负责：

* 直接访问 vCenter
* 直接调用 n8n
* 直接访问 OPA
* 存放高权限凭据

---

### 8.3 Tool Gateway（核心）

职责：

* 统一 API 入口
* Tool 注册与发现
* 路由到后端领域服务
* 输入 schema 校验
* 输出 schema 校验
* 用户身份透传与 RBAC 映射
* 调用 OPA 获取 allow/deny/approval_required/risk_level
* 审计记录
* 幂等控制
* 请求追踪
* 重试/熔断/限流
* Skill 生命周期管理
* Skill 健康检查与能力发现
* Skill 安装包元数据纳管
* Tool 绑定资源连接的引用解析

关键要求：

* 所有 Tool 定义 metadata
* 所有 Tool 区分 read / write / dangerous
* 所有 write 操作支持 dry-run
* 所有结果返回统一 envelope
* 支持动态注册新 Skill / 新 Gateway
* 支持按领域、版本、状态过滤可用工具
* 支持在不重启主 Agent 的情况下增量接入新能力
* Tool 不直接保存资源连接明文，应通过 connection_ref 引用资源连接配置

#### 8.3.1 Tool Registry / Skill Registry 能力

Tool Gateway 内部或配套组件需提供 Registry 能力，至少包括：

* Tool/Skill 注册
* Tool/Skill 卸载
* Tool/Skill 启停
* Tool/Skill 版本查询
* Tool/Skill 健康状态
* Tool/Skill 所属领域分类
* Tool/Skill 风险级别定义
* Tool/Skill 权限策略绑定
* Tool/Skill 升级记录
* Tool/Skill 兼容性检查

Registry 需要支持以下领域分类：

* vmware
* kubernetes
* network
* storage
* knowledge
* workflow
* integration

#### 8.3.2 Tool 生命周期管理模型

每个 Tool / Skill 必须具备标准生命周期状态，建议如下：

* `draft`：已导入元数据，但未完成校验，不可用
* `registered`：已注册，可见但未启用
* `configuring`：正在绑定连接、凭据、策略、权限
* `ready`：已完成配置并通过健康检查，可启用
* `enabled`：已启用，可被 Agent / 用户调用
* `degraded`：部分异常，可受限使用
* `disabled`：人工禁用，不可调用
* `upgrading`：升级中
* `error`：存在配置或运行异常
* `retired`：已下线，仅保留历史审计引用

生命周期动作至少包括：

* register
* validate
* bind_connection
* bind_policy
* enable
* disable
* upgrade
* rollback
* retire
* uninstall

#### 8.3.3 Tool 注册流程

标准注册流程建议如下：

1. 上传或导入 Skill manifest / Tool metadata。
2. Registry 校验 schema、版本、依赖项、能力清单。
3. 绑定领域连接模板与 connection profile。
4. 绑定权限策略与风险等级。
5. 执行健康检查与连通性测试。
6. 通过后状态转为 ready。
7. 管理员手工启用后状态转为 enabled。

#### 8.3.4 Tool 与资源连接配置原则

Tool 不应在自身定义中直接硬编码资源地址、账号或密钥。资源连接配置应独立为平台级 Connection Profile，由 Tool / Gateway 通过引用方式使用。

原则如下：

* Tool metadata 中仅保存 `supported_connection_types` 和 `connection_ref`
* 资源地址、账号、token、证书、跳板机、命名空间、租户范围等保存在 Connection Center
* 敏感信息加密存储，并支持从 Vault/Secret Manager 引用
* 同一 Tool 可绑定多个 Connection Profile，以支持多 vCenter、多 K8s 集群、多网络域、多存储阵列
* 权限控制应同时作用于 Tool 和 Connection Profile

职责：

* 统一 API 入口
* Tool 注册与发现
* 路由到后端领域服务
* 输入 schema 校验
* 输出 schema 校验
* 用户身份透传与 RBAC 映射
* 调用 OPA 获取 allow/deny/approval_required/risk_level
* 审计记录
* 幂等控制
* 请求追踪
* 重试/熔断/限流

关键要求：

* 所有 Tool 定义 metadata
* 所有 Tool 区分 read / write / dangerous
* 所有 write 操作支持 dry-run
* 所有结果返回统一 envelope

---

### 8.4 OPA 策略中枢

职责：

* 基于用户、角色、环境、资产、动作、时间窗口做策略判定
* 返回 allow / deny / approval_required / obligations

策略示例：

* 生产环境禁止直接 power off
* 迁移类动作必须审批
* 证据不充分时禁止执行
* 同一人不可同时发起和审批高风险动作

---

### 8.5 VMware Skill Gateway

基于 zw008/VMware-AIops 与 VMware-Monitor 二开，封装成企业受控接口。

职责：

* 统一访问 VMware 域能力
* 对外暴露标准化查询和执行接口
* 隐藏底层凭据和底层工具实现细节
* 返回标准化对象模型

首期建议工具集：

#### 查询类

* get_vcenter_inventory
* get_vm_detail
* get_host_detail
* get_cluster_detail
* get_datastore_detail
* query_events
* query_alerts
* query_metrics
* query_topology
* query_vm_host_relation

#### 执行类

* create_snapshot
* delete_snapshot
* vm_power_on
* vm_power_off
* vm_guest_restart
* enter_maintenance_mode
* exit_maintenance_mode
* vm_migrate
* datastore_migrate

---

### 8.5A Kubernetes Skill Gateway（预留扩展）

平台必须预留 Kubernetes / OpenShift 领域扩展能力，后续可按同样模式新增 Kubernetes Skill Gateway。

职责：

* 查询 cluster / node / namespace / workload / pod / pvc / ingress 等对象
* 查询事件、状态、资源消耗、调度结果
* 执行受控操作，如 rollout、cordon / uncordon、drain、scale、restart
* 支持多集群接入与集群标签管理

建议工具集：

#### 查询类

* get_cluster_summary
* get_node_detail
* get_namespace_detail
* get_workload_detail
* get_pod_detail
* query_k8s_events
* query_k8s_metrics
* query_resource_topology
* query_workload_dependencies

#### 执行类

* scale_workload
* rollout_restart
* cordon_node
* uncordon_node
* drain_node
* delete_pod
* patch_resource

---

### 8.5B Physical Network Gateway（预留扩展）

平台必须预留物理网络设备纳管与运维能力，适用于交换机、防火墙、路由器、负载均衡等网络设备。

职责：

* 查询设备清单、接口、路由、VLAN、策略、会话、告警
* 执行受控的配置查看、配置变更、状态切换、健康检查
* 支持厂商适配层（如 Cisco、H3C、Huawei、Juniper 等）

建议工具集：

#### 查询类

* get_device_inventory
* get_interface_status
* get_vlan_config
* get_route_table
* query_network_alerts
* query_network_topology
* query_acl_policy
* query_session_status

#### 执行类

* shutdown_interface
* no_shutdown_interface
* apply_acl_change
* push_config_snippet
* backup_running_config
* restore_config_snapshot

---

### 8.5C Physical Storage Gateway（预留扩展）

平台必须预留物理存储设备纳管能力，适用于 SAN/NAS/分布式存储阵列等。

职责：

* 查询存储池、卷、LUN、控制器、端口、容量、性能、告警
* 支持受控的卷管理、映射管理、快照、性能诊断和健康检查
* 支持厂商适配层（如 Dell EMC、NetApp、Huawei、HPE 等）

建议工具集：

#### 查询类

* get_storage_system_summary
* get_pool_detail
* get_volume_detail
* get_lun_mapping
* query_storage_alerts
* query_storage_metrics
* query_storage_topology

#### 执行类

* create_volume_snapshot
* map_lun_to_host
* unmap_lun_from_host
* expand_volume
* trigger_health_check

---

### 8.5D 统一领域 Gateway 接入要求

无论是 VMware、Kubernetes、Network 还是 Storage，所有领域 Gateway 接入平台时必须满足：

* 实现统一 Tool Schema
* 实现健康检查接口
* 实现版本与能力清单接口
* 实现标准错误码
* 支持 dry-run（适用于执行类动作）
* 支持请求 trace_id 透传
* 支持审计字段补全
* 支持最小权限凭据模型
* 支持通过 Harbor/OCI 分发升级

基于 zw008/VMware-AIops 与 VMware-Monitor 二开，封装成企业受控接口。

职责：

* 统一访问 VMware 域能力
* 对外暴露标准化查询和执行接口
* 隐藏底层凭据和底层工具实现细节
* 返回标准化对象模型

首期建议工具集：

#### 查询类

* get_vcenter_inventory
* get_vm_detail
* get_host_detail
* get_cluster_detail
* get_datastore_detail
* query_events
* query_alerts
* query_metrics
* query_topology
* query_vm_host_relation

#### 执行类

* create_snapshot
* delete_snapshot
* vm_power_on
* vm_power_off
* vm_guest_restart
* enter_maintenance_mode
* exit_maintenance_mode
* vm_migrate
* datastore_migrate

---

### 8.6 Change Impact Service

职责：

* 对变更请求进行影响面分析
* 识别依赖对象
* 计算风险等级
* 输出前置检查项、影响对象、回退建议

输入：

* change_type
* target_type
* target_id
* requested_action
* environment
* change_window
* user_context

输出：

* impacted_objects
* dependency_graph
* risk_score
* risk_level
* checks_required
* rollback_plan
* approval_suggestion

---

### 8.7 Evidence Aggregator

职责：

* 接收多源证据
* 做标准化、去重、时间排序、关联分析
* 输出 evidence package 给 Agent 和 UI

证据来源：

* VMware Skill Gateway
* RAG Service
* Change Impact Service
* 工单/审批/执行结果
* 用户补充输入

---

### 8.8 RAG Service

职责：

* 知识导入
* 文档切片
* 向量索引 + 关键词检索
* 重排
* 引用返回
* 支持文档版本与有效期
* 支持内部知识与外部 KB 的统一检索抽象

知识源：

* 运维手册
* SOP / Runbook
* VMware KB 摘要
* 内部 FAQ
* 变更规范
* 巡检规范
* 历史故障案例
* 厂商故障 KB / 公共知识摘要（受控接入）

### 8.8.1 外部 KB 检索要求

平台要支持外部 KB 查询能力，但必须经过受控适配层，不允许 Agent 自由直接访问任意外部站点。

建议设计：

* External KB Adapter
* KB Retrieval Agent 统一调用
* 结果进入 Evidence Aggregator
* 返回结论时必须标识来源、时间、适用性和置信度

外部 KB 检索至少支持：

* 厂商 KB
* 官方文档
* 经过筛选的内部维护知识镜像
* 历史案例库
  职责：
* 知识导入
* 文档切片
* 向量索引 + 关键词检索
* 重排
* 引用返回
* 支持文档版本与有效期

知识源：

* 运维手册
* SOP / Runbook
* VMware KB 摘要
* 内部 FAQ
* 变更规范
* 巡检规范

---

### 8.9 n8n Integration

职责：

* 审批工作流
* 工单创建 / 更新 / 关闭
* 通知（邮件 / IM / webhook）
* 与外部系统同步
* 值班通知与升级通知
* 事故状态同步

---

### 8.10 Event Ingestion Service

职责：

* 接收监控告警、Webhook、事件流、消息队列消息
* 对不同来源的事件进行标准化
* 做去重、聚合、降噪、初步优先级判定
* 将疑似故障事件送入 Incident Detection Agent

输入来源可包括：

* 监控系统告警
* VMware 事件
* K8s 事件
* 网络告警
* 存储告警
* 用户主动报障
* webhook / message bus

标准事件模型至少包括：

* event_id
* source
* source_type
* object_type
* object_id
* severity
* first_seen_at
* last_seen_at
* summary
* raw_ref
* correlation_key

---

### 8.11 Root Cause Analysis Service

职责：

* 对汇总后的证据进行根因分析
* 输出根因候选和置信度
* 区分直接症状、疑似根因、潜在诱因、相关变更
* 支持基于规则、知识、历史案例和 LLM 的混合分析

输出建议包含：

* root_cause_candidates
* likely_trigger
* affected_scope
* recommended_actions
* need_more_evidence
* confidence_summary

---

### 8.12 Memory Service

职责：

* 记忆用户历史需求、关注对象、处理偏好、常见操作习惯
* 记忆历史故障、根因、处置动作、最终结果
* 为后续对话和自动分析提供上下文增强

Memory 不应保存无关噪声，应重点保存：

* 用户长期关注的系统或对象
* 用户常见的分析偏好
* 过去相同/类似故障的处理经验
* 某对象近期连续故障历史
* 组织内部已经验证过的处理方法

---

### 8.13 Case Archive Service

职责：

* 自动把一次完整故障过程归档为 Incident Case
* 记录事件、分析、证据、通知、处置、结果、复盘信息
* 支持按对象、故障类型、根因、值班人、时间范围检索
* 支持将典型案例反哺知识库和 RAG

Incident Case 最少应包含：

* case_id
* title
* source_event_refs
* impacted_objects
* timeline
* evidence_refs
* root_cause_summary
* recommended_actions
* actual_actions
* final_resolution
* owner
* archived_at

---

### 8.14 Notification Service / Agent

职责：

* 根据告警级别、故障类型、值班规则选择通知对象
* 通知值班人员分析结论、影响范围、建议动作
* 追踪是否已确认、是否升级、是否闭环
* 对接邮件、IM、Webhook、短信等渠道

通知内容至少包括：

* 故障摘要
* 影响范围
* 根因候选
* 建议动作
* 证据链接
* 工单/案例链接
  职责：
* 审批工作流
* 工单创建 / 更新 / 关闭
* 通知（邮件 / IM / webhook）
* 与外部系统同步

---

## 9. 首期界面设计要求

平台必须有完整可用的企业级界面，而不是单页聊天窗口。

### 9.0 新增核心界面要求

除了面向人工发起分析的界面外，平台还必须具备面向“自动发现故障 -> 自动通知 -> 自动分析 -> 自动归档”的事件化运营界面。

界面中应体现：

* 新故障事件入口
* 自动分析中的故障清单
* 值班通知状态
* SubAgent 分析轨迹
* 历史案例和相似故障推荐
* 用户偏好/记忆上下文展示（仅展示与当前任务相关部分）
* Tool / Skill 注册、启停、升级、下线状态
* 资源连接配置、测试、绑定状态

平台必须有完整可用的企业级界面，而不是单页聊天窗口。

### 9.0 新增核心界面要求

除了面向人工发起分析的界面外，平台还必须具备面向“自动发现故障 -> 自动通知 -> 自动分析 -> 自动归档”的事件化运营界面。

界面中应体现：

* 新故障事件入口
* 自动分析中的故障清单
* 值班通知状态
* SubAgent 分析轨迹
* 历史案例和相似故障推荐
* 用户偏好/记忆上下文展示（仅展示与当前任务相关部分）

平台必须有完整可用的企业级界面，而不是单页聊天窗口。

### 9.1 页面结构

#### 1）登录页

* 用户名/密码或企业 SSO 入口
* 环境标识
* 版本信息

#### 2）首页驾驶舱

* 今日告警统计
* 今日自动发现故障数
* 今日自动分析完成数
* 今日诊断次数
* 今日变更分析次数
* 待审批数
* 待确认故障数
* 最近高风险动作
* VMware 环境摘要
* 最近知识命中趋势
* 最近根因类型分布
* 最近相似故障命中情况
* 今日告警统计
* 今日诊断次数
* 今日变更分析次数
* 待审批数
* 最近高风险动作
* VMware 环境摘要
* 最近知识命中趋势

#### 3）AI 对话页

* 左侧会话列表
* 中间对话区域
* 右侧证据面板
* 可展开“调用工具轨迹”
* 可查看最终建议和引用依据

#### 4）诊断工作台

* 故障描述输入区
* 对象选择器（VM/Host/Cluster/Datastore）
* 诊断结果卡片
* 根因候选列表
* 证据时间线
* 建议动作列表
* 升级为执行申请按钮
* 历史相似故障推荐
* 用户历史偏好提示
* 外部 KB / 内部知识命中结果
* 故障描述输入区
* 对象选择器（VM/Host/Cluster/Datastore）
* 诊断结果卡片
* 根因候选列表
* 证据时间线
* 建议动作列表
* 升级为执行申请按钮

#### 5）变更影响分析页面

* 变更类型选择
* 目标对象选择
* 影响范围图
* 风险评分
* 前置检查项
* 回退建议
* 发起审批按钮

#### 6）执行申请页面

* 执行动作表单
* 风险展示
* 目标对象列表
* dry-run 结果
* 审批流展示
* 提交审批按钮

#### 7）审批中心

* 待审批列表
* 审批详情页
* 证据摘要
* 风险等级
* 审批意见
* 审批通过/拒绝

#### 7A）故障事件中心

* 自动发现故障列表
* 状态筛选（新建 / 分析中 / 待处理 / 已恢复 / 已归档）
* 告警合并视图
* 影响对象视图
* 根因候选视图
* 值班人状态
* 一键进入处置

#### 7B）值班通知中心

* 当前通知队列
* 通知渠道状态
* 值班人确认状态
* 升级通知记录
* 未确认超时提醒

#### 7C）案例归档中心

* 历史 incident case 列表
* 相似案例推荐
* 根因分类统计
* 处理耗时统计
* 复盘记录查看
* 待审批列表
* 审批详情页
* 证据摘要
* 风险等级
* 审批意见
* 审批通过/拒绝

#### 8）审计中心

* 操作列表
* 用户、时间、对象、动作、结果过滤
* 审计详情
* OPA 命中策略展示
* 原始证据引用

#### 9）证据中心

* 证据包列表
* 证据来源过滤
* 时间线视图
* 对象关系视图
* 证据详情页

#### 10）知识管理页面

* 文档上传
* 文档分类
* 标签管理
* 有效期管理
* 文档版本管理
* 索引状态查看

#### 11）策略管理页面

* 策略列表
* 策略版本
* 发布状态
* 模拟评估
* Bundle 发布记录

#### 12）系统配置页面

* OPA 配置
* n8n 配置
* RAG 索引配置
* 模型配置
* 审计保留周期
* 默认值班规则
* 外部 KB 适配配置

#### 12A）工具注册中心

* Tool / Skill 列表
* 按领域、状态、版本筛选
* 查看 tool metadata / manifest
* 查看可用能力清单
* 注册新 Skill
* 校验与健康检查
* 启用 / 停用 / 下线
* 版本升级与回滚
* Tool 与连接绑定关系查看
* Tool 审计与调用统计

#### 12B）资源连接中心

* 连接列表（vCenter / K8s / Network / Storage / KB / ITSM / 通知）
* 新建连接 Profile
* 配置 endpoint、范围、凭据引用、跳板配置
* 执行连通性测试
* 启用 / 停用连接
* 查看连接被哪些 Tool / Skill 使用
* 密钥轮换记录
* 连接审计记录
* VMware 连接配置
* OPA 配置
* n8n 配置
* RAG 索引配置
* 模型配置
* 审计保留周期

#### 13）升级管理页面

* 镜像版本列表
* 当前部署版本
* Bundle 版本
* 升级包导入
* 升级记录
* 回滚记录

---

## 10. 前端信息架构

```text
OpsPilot Enterprise
├── 首页驾驶舱
├── AI 对话
├── 故障事件中心
├── 诊断工作台
├── 变更分析
├── 执行申请
├── 审批中心
├── 值班通知中心
├── 审计中心
├── 证据中心
├── 案例归档中心
├── 知识管理
├── 策略管理
├── 工具注册中心
├── 资源连接中心
├── 用户记忆视图
├── SubAgent 运行视图
├── 系统配置
└── 升级管理
```

```text
OpsPilot Enterprise
├── 首页驾驶舱
├── AI 对话
├── 故障事件中心
├── 诊断工作台
├── 变更分析
├── 执行申请
├── 审批中心
├── 值班通知中心
├── 审计中心
├── 证据中心
├── 案例归档中心
├── 知识管理
├── 策略管理
├── 用户记忆视图
├── SubAgent 运行视图
├── 系统配置
└── 升级管理
```

```text
OpsPilot Enterprise
├── 首页驾驶舱
├── AI 对话
├── 诊断工作台
├── 变更分析
├── 执行申请
├── 审批中心
├── 审计中心
├── 证据中心
├── 知识管理
├── 策略管理
├── 系统配置
└── 升级管理
```

---

## 11. 后端服务拆分建议

```text
services/
  ui-web/
  api-bff/
  langgraph-orchestrator/
  event-ingestion-service/
  intent-service/
  tool-gateway/
  tool-registry/
  vmware-skill-gateway/
  kubernetes-skill-gateway/        # 二期或预留
  network-gateway/                 # 二期或预留
  storage-gateway/                 # 二期或预留
  change-impact-service/
  root-cause-analysis-service/
  evidence-aggregator/
  memory-service/
  case-archive-service/
  notification-service/
  rag-service/
  audit-service/
  auth-service/
  policy-adapter/
  n8n-adapter/
```

### 11.1 服务说明

* **ui-web**：前端界面
* **api-bff**：前后端聚合接口层
* **langgraph-orchestrator**：Agent 编排服务
* **event-ingestion-service**：事件接入与标准化
* **intent-service**：意图识别与需求结构化
* **tool-gateway**：统一控制面
* **tool-registry**：Tool / Skill 注册与生命周期管理
* **vmware-skill-gateway**：VMware 领域服务
* **kubernetes-skill-gateway**：K8s / OpenShift 领域服务
* **network-gateway**：物理网络领域服务
* **storage-gateway**：物理存储领域服务
* **change-impact-service**：变更影响分析服务
* **root-cause-analysis-service**：根因分析服务
* **evidence-aggregator**：证据聚合服务
* **memory-service**：用户/故障记忆服务
* **case-archive-service**：故障案例归档服务
* **notification-service**：通知与值班联动服务
* **rag-service**：知识检索服务
* **audit-service**：审计服务
* **auth-service**：认证授权服务
* **policy-adapter**：OPA 适配层
* **n8n-adapter**：n8n 流程适配层
* **connection-service**：资源连接配置、凭据引用、连通性测试与连接生命周期管理

```text
services/
  ui-web/
  api-bff/
  langgraph-orchestrator/
  tool-gateway/
  tool-registry/
  vmware-skill-gateway/
  kubernetes-skill-gateway/        # 二期或预留
  network-gateway/                 # 二期或预留
  storage-gateway/                 # 二期或预留
  change-impact-service/
  evidence-aggregator/
  rag-service/
  audit-service/
  auth-service/
  policy-adapter/
  n8n-adapter/
```

### 11.1 服务说明

* **ui-web**：前端界面
* **api-bff**：前后端聚合接口层
* **langgraph-orchestrator**：Agent 编排服务
* **tool-gateway**：统一控制面
* **tool-registry**：Tool / Skill 注册与生命周期管理
* **vmware-skill-gateway**：VMware 领域服务
* **kubernetes-skill-gateway**：K8s / OpenShift 领域服务
* **network-gateway**：物理网络领域服务
* **storage-gateway**：物理存储领域服务
* **change-impact-service**：变更影响分析服务
* **evidence-aggregator**：证据聚合服务
* **rag-service**：知识检索服务
* **audit-service**：审计服务
* **auth-service**：认证授权服务
* **policy-adapter**：OPA 适配层
* **n8n-adapter**：n8n 流程适配层

```text
services/
  ui-web/
  api-bff/
  langgraph-orchestrator/
  tool-gateway/
  vmware-skill-gateway/
  change-impact-service/
  evidence-aggregator/
  rag-service/
  audit-service/
  auth-service/
  policy-adapter/
  n8n-adapter/
```

### 11.1 服务说明

* **ui-web**：前端界面
* **api-bff**：前后端聚合接口层
* **langgraph-orchestrator**：Agent 编排服务
* **tool-gateway**：统一控制面
* **vmware-skill-gateway**：VMware 领域服务
* **change-impact-service**：变更影响分析服务
* **evidence-aggregator**：证据聚合服务
* **rag-service**：知识检索服务
* **audit-service**：审计服务
* **auth-service**：认证授权服务
* **policy-adapter**：OPA 适配层
* **n8n-adapter**：n8n 流程适配层

---

## 12. 建议代码仓结构

```text
opspilot-enterprise/
├── apps/
│   ├── web
│   ├── api-bff
│   └── admin-tools
├── services/
│   ├── langgraph-orchestrator
│   ├── tool-gateway
│   ├── tool-registry
│   ├── vmware-skill-gateway
│   ├── kubernetes-skill-gateway
│   ├── network-gateway
│   ├── storage-gateway
│   ├── change-impact-service
│   ├── evidence-aggregator
│   ├── rag-service
│   ├── audit-service
│   ├── policy-adapter
│   └── n8n-adapter
├── packages/
│   ├── shared-types
│   ├── shared-schema
│   ├── shared-ui
│   ├── shared-auth
│   └── shared-utils
├── skills/
│   ├── skill-sdk
│   ├── examples
│   │   ├── vmware-skill-example
│   │   ├── k8s-skill-example
│   │   ├── network-skill-example
│   │   └── storage-skill-example
│   └── manifests
├── deploy/
│   ├── k8s
│   ├── helm
│   ├── docker
│   └── offline-bundles
├── policy/
│   ├── rego
│   └── bundles
├── docs/
├── scripts/
└── tests/
```

```text
opspilot-enterprise/
├── apps/
│   ├── web
│   ├── api-bff
│   └── admin-tools
├── services/
│   ├── langgraph-orchestrator
│   ├── tool-gateway
│   ├── vmware-skill-gateway
│   ├── change-impact-service
│   ├── evidence-aggregator
│   ├── rag-service
│   ├── audit-service
│   ├── policy-adapter
│   └── n8n-adapter
├── packages/
│   ├── shared-types
│   ├── shared-schema
│   ├── shared-ui
│   ├── shared-auth
│   └── shared-utils
├── deploy/
│   ├── k8s
│   ├── helm
│   ├── docker
│   └── offline-bundles
├── policy/
│   ├── rego
│   └── bundles
├── docs/
├── scripts/
└── tests/
```

---

## 13. API 设计原则

1. 全部 API 使用版本化路径，例如 `/api/v1/...`
2. 所有写操作必须携带 request_id
3. 所有返回统一 envelope
4. 所有接口返回必须可追踪到审计记录
5. 所有执行类接口支持 dry_run=true

### 13.1 通用返回 envelope

```json
{
  "request_id": "req-123",
  "success": true,
  "message": "ok",
  "data": {},
  "error": null,
  "audit_ref": "audit-123",
  "trace_id": "trace-123",
  "timestamp": "2026-04-05T09:00:00Z"
}
```

---

## 14. 核心接口清单

### 14.0 Tool / Skill 管理

* GET /api/v1/tools
* GET /api/v1/tools/{name}
* POST /api/v1/tools/register
* POST /api/v1/tools/unregister
* GET /api/v1/tools/health
* GET /api/v1/skills
* POST /api/v1/skills/install
* POST /api/v1/skills/enable
* POST /api/v1/skills/disable
* POST /api/v1/skills/uninstall
* GET /api/v1/skills/{id}/versions
* GET /api/v1/skills/{id}/capabilities
* POST /api/v1/skills/{id}/validate
* POST /api/v1/skills/{id}/retire
* POST /api/v1/skills/{id}/rollback

### 14.0A Tool Connection / Resource Profile 管理

* GET /api/v1/connections
* POST /api/v1/connections
* GET /api/v1/connections/{id}
* PUT /api/v1/connections/{id}
* POST /api/v1/connections/{id}/test
* POST /api/v1/connections/{id}/enable
* POST /api/v1/connections/{id}/disable
* POST /api/v1/connections/{id}/rotate-secret
* GET /api/v1/skills/{id}/bindings
* POST /api/v1/skills/{id}/bindings
* DELETE /api/v1/skills/{id}/bindings/{binding_id}

### 14.0B 事件与故障

### 14.0 Tool / Skill 管理

* GET /api/v1/tools
* GET /api/v1/tools/{name}
* POST /api/v1/tools/register
* POST /api/v1/tools/unregister
* GET /api/v1/tools/health
* GET /api/v1/skills
* POST /api/v1/skills/install
* POST /api/v1/skills/enable
* POST /api/v1/skills/disable
* POST /api/v1/skills/uninstall
* GET /api/v1/skills/{id}/versions
* GET /api/v1/skills/{id}/capabilities

### 14.0A 事件与故障

* POST /api/v1/events/ingest
* GET /api/v1/incidents
* GET /api/v1/incidents/{id}
* POST /api/v1/incidents/{id}/analyze
* GET /api/v1/incidents/{id}/timeline
* GET /api/v1/incidents/{id}/subagent-traces
* POST /api/v1/incidents/{id}/notify
* POST /api/v1/incidents/{id}/archive

### 14.0B Memory / Case

* GET /api/v1/memory/users/{user_id}
* GET /api/v1/memory/objects/{object_id}
* GET /api/v1/cases
* GET /api/v1/cases/{id}
* GET /api/v1/cases/similar

### 14.1 Chat / Agent

* POST /api/v1/chat/sessions
* POST /api/v1/chat/sessions/{id}/messages
* GET /api/v1/chat/sessions/{id}
* GET /api/v1/chat/sessions/{id}/evidence
* GET /api/v1/chat/sessions/{id}/tool-traces
* GET /api/v1/chat/sessions/{id}/memory-context

### 14.0 Tool / Skill 管理

* GET /api/v1/tools
* GET /api/v1/tools/{name}
* POST /api/v1/tools/register
* POST /api/v1/tools/unregister
* GET /api/v1/tools/health
* GET /api/v1/skills
* POST /api/v1/skills/install
* POST /api/v1/skills/enable
* POST /api/v1/skills/disable
* POST /api/v1/skills/uninstall
* GET /api/v1/skills/{id}/versions
* GET /api/v1/skills/{id}/capabilities

### 14.1 Chat / Agent

* POST /api/v1/chat/sessions
* POST /api/v1/chat/sessions/{id}/messages
* GET /api/v1/chat/sessions/{id}
* GET /api/v1/chat/sessions/{id}/evidence
* GET /api/v1/chat/sessions/{id}/tool-traces

### 14.1 Chat / Agent

* POST /api/v1/chat/sessions
* POST /api/v1/chat/sessions/{id}/messages
* GET /api/v1/chat/sessions/{id}
* GET /api/v1/chat/sessions/{id}/evidence
* GET /api/v1/chat/sessions/{id}/tool-traces

### 14.2 Diagnosis

* POST /api/v1/diagnosis/run
* GET /api/v1/diagnosis/{id}
* GET /api/v1/diagnosis/{id}/evidence
* POST /api/v1/diagnosis/{id}/promote-to-execution

### 14.3 Change Impact

* POST /api/v1/change-impact/analyze
* GET /api/v1/change-impact/{id}
* GET /api/v1/change-impact/{id}/graph

### 14.4 Execution

* POST /api/v1/executions/dry-run
* POST /api/v1/executions/submit
* GET /api/v1/executions/{id}
* POST /api/v1/executions/{id}/cancel

### 14.5 Approval

* GET /api/v1/approvals
* GET /api/v1/approvals/{id}
* POST /api/v1/approvals/{id}/approve
* POST /api/v1/approvals/{id}/reject

### 14.6 Audit

* GET /api/v1/audits
* GET /api/v1/audits/{id}

### 14.7 Knowledge

* POST /api/v1/knowledge/documents
* GET /api/v1/knowledge/documents
* POST /api/v1/knowledge/reindex

### 14.8 Policy

* GET /api/v1/policies
* POST /api/v1/policies/simulate
* POST /api/v1/policies/publish

---

## 15. Tool Schema 规范

每个 Tool 必须定义以下元数据：

```json
{
  "name": "vmware.get_vm_detail",
  "display_name": "查询虚拟机详情",
  "category": "vmware",
  "domain": "infrastructure",
  "provider": "vmware-skill-gateway",
  "action_type": "read",
  "risk_level": "low",
  "approval_required": false,
  "supported_connection_types": ["vmware-vcenter"],
  "default_connection_strategy": "explicit_binding",
  "input_schema": {},
  "output_schema": {},
  "timeout_seconds": 30,
  "idempotent": true,
  "version": "1.0.0",
  "tags": ["vmware", "inventory"]
}
```

## 15.1 Skill Manifest 规范

每个 Skill / Gateway 安装包必须提供 manifest，例如：

```json
{
  "skill_name": "kubernetes-skill-gateway",
  "display_name": "Kubernetes Skill Gateway",
  "domain": "kubernetes",
  "version": "1.0.0",
  "description": "Provide controlled Kubernetes operational capabilities",
  "tools": [
    "k8s.get_cluster_summary",
    "k8s.get_pod_detail",
    "k8s.scale_workload"
  ],
  "health_endpoint": "/health",
  "capabilities_endpoint": "/capabilities",
  "required_config": ["cluster_credentials_ref"],
  "supported_connection_types": ["k8s-cluster"],
  "required_permissions": ["k8s.read", "k8s.write"],
  "deployment_type": "container",
  "distribution": "oci"
}
```

## 15.2 Connection Profile 规范

所有 Tool 连接资源时，必须通过平台级 Connection Profile。Connection Profile 示例：

```json
{
  "connection_id": "conn-vc-prod-01",
  "name": "VC-Prod-East",
  "connection_type": "vmware-vcenter",
  "environment": "prod",
  "endpoint": "https://vcenter.example.local",
  "credential_ref": "secret://vault/vcenter/prod-east",
  "scope": {
    "datacenter": ["DC1"],
    "cluster": ["Cluster-A", "Cluster-B"]
  },
  "network_path": {
    "via_bastion": true,
    "bastion_ref": "secret://vault/bastion/ops-01"
  },
  "status": "enabled"
}
```

Connection Type 建议枚举：

* `vmware-vcenter`
* `k8s-cluster`
* `network-device-domain`
* `storage-array`
* `knowledge-source`
* `webhook-endpoint`
* `itsm-endpoint`
* `notification-channel`

每个 Tool 必须定义以下元数据：

```json
{
  "name": "vmware.get_vm_detail",
  "display_name": "查询虚拟机详情",
  "category": "vmware",
  "domain": "infrastructure",
  "provider": "vmware-skill-gateway",
  "action_type": "read",
  "risk_level": "low",
  "approval_required": false,
  "input_schema": {},
  "output_schema": {},
  "timeout_seconds": 30,
  "idempotent": true,
  "version": "1.0.0",
  "tags": ["vmware", "inventory"]
}
```

## 15.1 Skill Manifest 规范

每个 Skill / Gateway 安装包必须提供 manifest，例如：

```json
{
  "skill_name": "kubernetes-skill-gateway",
  "display_name": "Kubernetes Skill Gateway",
  "domain": "kubernetes",
  "version": "1.0.0",
  "description": "Provide controlled Kubernetes operational capabilities",
  "tools": [
    "k8s.get_cluster_summary",
    "k8s.get_pod_detail",
    "k8s.scale_workload"
  ],
  "health_endpoint": "/health",
  "capabilities_endpoint": "/capabilities",
  "required_config": ["cluster_credentials_ref"],
  "required_permissions": ["k8s.read", "k8s.write"],
  "deployment_type": "container",
  "distribution": "oci"
}
```

每个 Tool 必须定义以下元数据：

```json
{
  "name": "vmware.get_vm_detail",
  "display_name": "查询虚拟机详情",
  "category": "vmware",
  "action_type": "read",
  "risk_level": "low",
  "approval_required": false,
  "input_schema": {},
  "output_schema": {},
  "timeout_seconds": 30,
  "idempotent": true,
  "tags": ["vmware", "inventory"]
}
```

---

## 16. 核心数据模型

### 16.0 Tool Registry Item

```json
{
  "tool_id": "tool-vmware-get-vm-detail",
  "name": "vmware.get_vm_detail",
  "domain": "vmware",
  "provider": "vmware-skill-gateway",
  "version": "1.0.0",
  "lifecycle_state": "enabled",
  "supported_connection_types": ["vmware-vcenter"],
  "bound_connections": ["conn-vc-prod-01"],
  "risk_level": "low",
  "health_status": "healthy"
}
```

### 16.0A Connection Profile

```json
{
  "connection_id": "conn-k8s-prod-01",
  "name": "K8s-Prod-Cluster-01",
  "connection_type": "k8s-cluster",
  "environment": "prod",
  "endpoint": "https://api.k8s.prod.local:6443",
  "credential_ref": "secret://vault/k8s/prod-01",
  "scope": {
    "namespaces": ["prod-a", "prod-b"]
  },
  "status": "enabled",
  "health_status": "healthy",
  "used_by_tools": ["k8s.get_pod_detail", "k8s.scale_workload"]
}
```

### 16.1 Evidence

### 16.1 Evidence

```json
{
  "evidence_id": "evd-001",
  "source": "vmware-monitor",
  "source_type": "event",
  "object_type": "VirtualMachine",
  "object_id": "vm-123",
  "timestamp": "2026-04-05T08:00:00Z",
  "summary": "VM migrated to another host",
  "raw_ref": "s3://.../raw.json",
  "confidence": 0.92,
  "correlation_key": "vm-123:incident-001"
}
```

### 16.2 Change Impact Result

```json
{
  "analysis_id": "cia-001",
  "target": {
    "type": "HostSystem",
    "id": "host-33"
  },
  "action": "enter_maintenance_mode",
  "risk_score": 78,
  "risk_level": "high",
  "impacted_objects": [],
  "checks_required": [],
  "rollback_plan": [],
  "approval_suggestion": "required"
}
```

### 16.3 Approval Request

```json
{
  "approval_id": "apr-001",
  "request_id": "req-001",
  "action": "vmware.vm_migrate",
  "environment": "prod",
  "risk_level": "high",
  "requester": "user-a",
  "status": "pending",
  "evidence_refs": ["evd-001", "evd-002"]
}
```

---

## 17. 关键流程

### 17.0 自动故障发现与通知流程

1. Event Ingestion Service 接收监控、告警、事件或用户报障。
2. Incident Detection Agent 进行降噪、聚合和初步故障识别。
3. LangGraph 主 Agent 创建 Incident。
4. Evidence Collection Agent 拉取监控、事件、拓扑、日志、变更证据。
5. KB Retrieval Agent 查询内部 RAG 与外部 KB。
6. Root Cause Analysis Agent 输出根因候选与置信度。
7. Recommendation Agent 输出建议动作。
8. Notification Agent 通知值班人员。
9. 值班人员在平台查看结果并执行后续动作。
10. Case Archive Agent 自动归档为案例，Memory Agent 更新相关记忆。

### 17.1 故障诊断流程

1. 用户在 AI 对话页或诊断工作台输入故障描述。
2. Intent Agent 识别用户意图、对象和约束。
3. LangGraph 识别为 diagnosis flow。
4. LangGraph 调用 Tool Gateway 请求查询 VMware 证据和知识证据。
5. Tool Gateway 调 OPA 判断只读工具是否允许。
6. VMware Skill Gateway / RAG Service 返回结果。
7. Evidence Aggregator 生成 evidence package。
8. Root Cause Analysis Agent 输出：根因候选、证据、建议动作。
9. Memory Agent 补充用户历史偏好和相似故障上下文。
10. 用户可进一步发起执行申请。

### 17.2 变更影响分析流程

1. 用户提交变更对象和动作。
2. Intent Agent 识别请求类型和约束条件。
3. LangGraph 调用 Change Impact Service。
4. Change Impact Service 查询依赖关系和现网状态。
5. Evidence Aggregator 汇总证据。
6. LangGraph 输出影响分析结果。
7. 用户决定是否发起审批。

### 17.3 审批后执行流程

1. 用户发起执行申请。
2. Tool Gateway 调 OPA 判断是否需要审批。
3. 若需要审批，则调用 n8n 发起审批流。
4. 审批完成后，n8n 回调平台。
5. Tool Gateway 调用 VMware Skill Gateway 执行。
6. 执行结果写入审计并回显 UI。
7. Case Archive Agent 将本次执行与故障 case 关联归档。

### 17.1 故障诊断流程

1. 用户在 AI 对话页或诊断工作台输入故障描述。
2. LangGraph 识别为 diagnosis flow。
3. LangGraph 调用 Tool Gateway 请求查询 VMware 证据和知识证据。
4. Tool Gateway 调 OPA 判断只读工具是否允许。
5. VMware Skill Gateway / RAG Service 返回结果。
6. Evidence Aggregator 生成 evidence package。
7. LangGraph 输出：根因候选、证据、建议动作。
8. 用户可进一步发起执行申请。

### 17.2 变更影响分析流程

1. 用户提交变更对象和动作。
2. LangGraph 调用 Change Impact Service。
3. Change Impact Service 查询依赖关系和现网状态。
4. Evidence Aggregator 汇总证据。
5. LangGraph 输出影响分析结果。
6. 用户决定是否发起审批。

### 17.3 审批后执行流程

1. 用户发起执行申请。
2. Tool Gateway 调 OPA 判断是否需要审批。
3. 若需要审批，则调用 n8n 发起审批流。
4. 审批完成后，n8n 回调平台。
5. Tool Gateway 调用 VMware Skill Gateway 执行。
6. 执行结果写入审计并回显 UI。

---

## 18. 安全要求

### 18.1 基本要求

* 所有接口鉴权
* 所有写操作审计
* 敏感配置加密存储
* 执行动作强制审批策略
* 生产环境额外策略限制
* 不允许前端持有系统级凭据
* SubAgent 间协作不得绕过 Tool Gateway 和策略控制

### 18.2 审计要求

审计记录必须包含：

* 谁发起
* 何时发起
* 对什么对象
* 发起什么动作
* 是否命中审批
* 命中哪条策略
* 执行结果
* 关联证据
* 关联请求链路
* 由哪个 SubAgent 产生何种分析结果
* 外部 KB / 内部 RAG 命中来源

### 18.3 记忆与归档安全要求

* Memory 仅存储与运维工作相关的长期有效上下文
* 不保存无关、噪声化或不必要的个人信息
* 故障 Case 与用户记忆需支持脱敏与访问控制
* 支持记忆纠正、归档补充和人工标注

### 18.1 基本要求

* 所有接口鉴权
* 所有写操作审计
* 敏感配置加密存储
* 执行动作强制审批策略
* 生产环境额外策略限制
* 不允许前端持有系统级凭据

### 18.2 审计要求

审计记录必须包含：

* 谁发起
* 何时发起
* 对什么对象
* 发起什么动作
* 是否命中审批
* 命中哪条策略
* 执行结果
* 关联证据
* 关联请求链路

---

## 19. 可观测性要求

每个服务应提供：

* /health
* /metrics
* 结构化日志
* trace_id 透传
* Prometheus 指标
* OpenTelemetry 链路追踪

---

## 20. 离线部署要求

必须支持离线环境部署：

* 所有镜像由 Harbor 分发
* 策略包通过 OPA bundles 分发
* 应用 Helm Chart / YAML 可离线安装
* 知识库导入不依赖公网
* 模型调用支持内网 OpenAI-compatible endpoint

---

## 21. 首期技术栈建议

### 前端

* React
* TypeScript
* Tailwind
* shadcn/ui
* Zustand / TanStack Query

### 后端

* Python（FastAPI）为主
* LangGraph for orchestrator
* Pydantic for schema
* PostgreSQL
* Redis
* Qdrant / pgvector（二选一）

### 平台与集成

* OPA
* n8n
* Harbor
* Kubernetes
* Prometheus + Grafana + Loki

---

## 22. 开发优先级

### P0

* Tool Gateway
* VMware Skill Gateway
* Event Ingestion Service
* Intent Service
* Root Cause Analysis Service
* Change Impact Service
* Evidence Aggregator
* Notification Service
* Memory Service（基础版）
* Case Archive Service（基础版）
* 基础 Web UI
* Chat / Diagnosis / Change Impact / Incident 页面

### P1

* 审批中心
* 审计中心
* 知识管理
* 策略管理
* 升级管理
* SubAgent 运行轨迹视图
* 值班通知中心
* 案例归档中心

### P2

* 首页驾驶舱优化
* 更强的对象关系图
* 更丰富的统计报表
* 历史案例推荐与相似故障自动召回优化

### P0

* Tool Gateway
* VMware Skill Gateway
* Change Impact Service
* Evidence Aggregator
* 基础 Web UI
* Chat / Diagnosis / Change Impact 页面

### P1

* 审批中心
* 审计中心
* 知识管理
* 策略管理
* 升级管理

### P2

* 首页驾驶舱优化
* 更强的对象关系图
* 更丰富的统计报表

---

## 23. 交付物要求（给 Codex）

Codex 需要输出以下内容：

1. 完整 monorepo 项目骨架
2. 前端 Web UI 可运行版本
3. 后端服务 skeleton 与核心 API
4. Tool Gateway 核心流程
5. VMware Skill Gateway mock + adapter 接口
6. OPA 接入示例
7. n8n 接入示例
8. 示例策略
9. 示例知识导入流程
10. Docker / Helm / K8s 部署文件
11. README
12. `.env.example`
13. 开发启动脚本
14. 基础单元测试
15. API 文档
16. Tool / Skill Registry 模块
17. Skill SDK 基础骨架
18. 至少一个 K8s Skill 示例
19. 至少一个 Network Skill 示例
20. 至少一个 Storage Skill 示例
21. Skill manifest 示例与安装流程示例
22. Tool 注册中心页面
23. 资源连接中心页面
24. Tool 生命周期状态机与示例数据
25. Connection Profile 管理与测试接口示例

Codex 需要输出以下内容：

1. 完整 monorepo 项目骨架
2. 前端 Web UI 可运行版本
3. 后端服务 skeleton 与核心 API
4. Tool Gateway 核心流程
5. VMware Skill Gateway mock + adapter 接口
6. OPA 接入示例
7. n8n 接入示例
8. 示例策略
9. 示例知识导入流程
10. Docker / Helm / K8s 部署文件
11. README
12. `.env.example`
13. 开发启动脚本
14. 基础单元测试
15. API 文档
16. Tool / Skill Registry 模块
17. Skill SDK 基础骨架
18. 至少一个 K8s Skill 示例
19. 至少一个 Network Skill 示例
20. 至少一个 Storage Skill 示例
21. Skill manifest 示例与安装流程示例

Codex 需要输出以下内容：

1. 完整 monorepo 项目骨架
2. 前端 Web UI 可运行版本
3. 后端服务 skeleton 与核心 API
4. Tool Gateway 核心流程
5. VMware Skill Gateway mock + adapter 接口
6. OPA 接入示例
7. n8n 接入示例
8. 示例策略
9. 示例知识导入流程
10. Docker / Helm / K8s 部署文件
11. README
12. `.env.example`
13. 开发启动脚本
14. 基础单元测试
15. API 文档

---

## 24. Codex 开发约束

1. 不允许绕过 Tool Gateway 直接访问 VMware Skill。

2. 不允许在前端硬编码权限判断。

3. 不允许把审批逻辑写死在 LangGraph Prompt 中。

4. 所有接口必须有 schema。

5. 所有关键服务必须有 Dockerfile。

6. 所有关键模块必须有 README。

7. 所有环境变量必须集中示例化。

8. 所有 mock 实现必须与正式接口一致。

9. 必须先实现 mock 跑通，再接真实 VMware 适配。

10. 必须考虑新 Skill 动态接入能力，不允许把领域能力写死在 orchestrator 中。

11. K8s / Network / Storage 扩展必须通过统一 Gateway/Registry 模型接入。

12. 所有 Skill 安装包必须具备 manifest。

13. 资源连接配置必须独立于 Tool metadata 管理，不允许将 endpoint、用户名、密码硬编码在 Tool 定义中。

14. 前端必须提供 Tool 注册中心和资源连接中心，不得仅依靠配置文件手工维护。

15. 不允许绕过 Tool Gateway 直接访问 VMware Skill。

16. 不允许在前端硬编码权限判断。

17. 不允许把审批逻辑写死在 LangGraph Prompt 中。

18. 所有接口必须有 schema。

19. 所有关键服务必须有 Dockerfile。

20. 所有关键模块必须有 README。

21. 所有环境变量必须集中示例化。

22. 所有 mock 实现必须与正式接口一致。

23. 必须先实现 mock 跑通，再接真实 VMware 适配。

24. 必须考虑新 Skill 动态接入能力，不允许把领域能力写死在 orchestrator 中。

25. K8s / Network / Storage 扩展必须通过统一 Gateway/Registry 模型接入。

26. 所有 Skill 安装包必须具备 manifest。

27. 不允许绕过 Tool Gateway 直接访问 VMware Skill。

28. 不允许在前端硬编码权限判断。

29. 不允许把审批逻辑写死在 LangGraph Prompt 中。

30. 所有接口必须有 schema。

31. 所有关键服务必须有 Dockerfile。

32. 所有关键模块必须有 README。

33. 所有环境变量必须集中示例化。

34. 所有 mock 实现必须与正式接口一致。

35. 必须先实现 mock 跑通，再接真实 VMware 适配。

---

## 25. 第一阶段开发任务拆解

### Sprint 1：项目骨架

* 初始化 monorepo
* 创建前端 web
* 创建 api-bff
* 创建 tool-gateway
* 创建 langgraph-orchestrator
* 创建 shared schema
* 创建 docker compose 开发环境

### Sprint 2：基础流程跑通

* 实现 chat -> orchestrator -> tool-gateway -> mock tool
* 实现 evidence package 输出
* 实现 diagnosis 页面
* 实现 tool trace 展示
* 实现 intent-service 初版

### Sprint 3：自动故障发现链路

* 实现 event-ingestion-service
* 实现 incident 列表与详情页
* 实现 incident detection 基础流程
* 实现 notification-service mock

### Sprint 4：VMware 查询链路

* 接入 vmware-skill-gateway mock
* 实现 inventory / events / metrics 查询
* 实现证据面板
* 实现 RCA service 初版

### Sprint 5：变更分析与审批执行链路

* 实现 change-impact-service
* 实现变更分析页面
* 实现 dependency graph mock
* 接入 OPA
* 接入 n8n
* 实现 dry-run / submit / approve / execute

### Sprint 6：记忆、案例、知识

* 实现 memory-service 基础版
* 实现 case-archive-service 基础版
* 实现 audit center
* 实现 knowledge management
* 实现文档导入与检索
* 实现相似案例推荐初版

### Sprint 1：项目骨架

* 初始化 monorepo
* 创建前端 web
* 创建 api-bff
* 创建 tool-gateway
* 创建 langgraph-orchestrator
* 创建 shared schema
* 创建 docker compose 开发环境

### Sprint 2：基础流程跑通

* 实现 chat -> orchestrator -> tool-gateway -> mock tool
* 实现 evidence package 输出
* 实现 diagnosis 页面
* 实现 tool trace 展示

### Sprint 3：VMware 查询链路

* 接入 vmware-skill-gateway mock
* 实现 inventory / events / metrics 查询
* 实现证据面板

### Sprint 4：变更分析链路

* 实现 change-impact-service
* 实现变更分析页面
* 实现 dependency graph mock

### Sprint 5：审批执行链路

* 接入 OPA
* 接入 n8n
* 实现 dry-run / submit / approve / execute

### Sprint 6：审计与知识

* 实现 audit center
* 实现 knowledge management
* 实现文档导入与检索

---

## 26. 验收标准

### 26.1 功能验收

* 用户可登录并进入平台
* 可通过聊天触发诊断
* 可查看证据和工具轨迹
* 平台可接收事件并自动生成 incident
* 平台可自动通知值班人员
* 平台可自动查询内部知识与外部 KB
* 平台可输出根因候选和建议动作
* 可发起变更影响分析
* 可提交执行申请并进入审批
* 审批完成后可执行示例动作
* 可查看审计记录
* 可上传知识文档并完成检索
* 可查看历史案例和相似故障
* 平台可记忆用户相关偏好和历史上下文

### 26.2 技术验收

* 所有服务可容器化运行
* API 文档完整
* 核心接口有自动化测试
* OPA 策略可热更新
* UI 页面完整可导航
* 所有关键链路具备 trace_id
* SubAgent 轨迹可观测
* Incident -> Analyze -> Notify -> Archive 链路可跑通

### 26.1 功能验收

* 用户可登录并进入平台
* 可通过聊天触发诊断
* 可查看证据和工具轨迹
* 可发起变更影响分析
* 可提交执行申请并进入审批
* 审批完成后可执行示例动作
* 可查看审计记录
* 可上传知识文档并完成检索

### 26.2 技术验收

* 所有服务可容器化运行
* API 文档完整
* 核心接口有自动化测试
* OPA 策略可热更新
* UI 页面完整可导航
* 所有关键链路具备 trace_id

---

## 27. 给 Codex 的最终实现要求

请基于本说明书直接生成一个可运行的企业级原型项目，要求：

* 先实现完整 UI 和 mock 后端
* 再预留真实 VMware/OPA/n8n/RAG 接口适配位
* 保持模块边界清晰
* 代码结构适合后续团队继续开发
* 文档完整
* 不要偷省模块，把多个核心服务混成一个文件
* 必须体现 SubAgent 架构，而不是单一 Agent 直接串联所有逻辑
* 必须预留用户记忆、故障记忆、案例归档能力
* 必须支持事件触发型自动分析流程

如遇到未定义细节，按以下原则决策：

1. 优先可维护性
2. 优先模块边界清晰
3. 优先企业级治理能力
4. 优先 mock 可跑通
5. 不破坏 Tool Gateway 前置控制架构
6. 不把所有智能能力塞进单个 orchestrator 文件

请基于本说明书直接生成一个可运行的企业级原型项目，要求：

* 先实现完整 UI 和 mock 后端
* 再预留真实 VMware/OPA/n8n/RAG 接口适配位
* 保持模块边界清晰
* 代码结构适合后续团队继续开发
* 文档完整
* 不要偷省模块，把多个核心服务混成一个文件

如遇到未定义细节，按以下原则决策：

1. 优先可维护性
2. 优先模块边界清晰
3. 优先企业级治理能力
4. 优先 mock 可跑通
5. 不破坏 Tool Gateway 前置控制架构

---

## 28. 二期预留点

### 28.1 Onyx 集成预留

预留 enterprise-search adapter：

* search_documents
* search_people
* search_incidents
* search_change_records

### 28.2 VMware-Pilot 集成预留

预留 vmware workflow adapter：

* run_workflow
* get_workflow_status
* cancel_workflow

二期仍必须走 Tool Gateway，不允许直连。

---

## 29. 推荐英文仓库名

* `opspilot-enterprise`
* `opspilot-aiops-platform`

推荐最终仓库名：
**opspilot-enterprise**

---

## 30. 一句话项目说明

OpsPilot Enterprise 是一个面向企业私有环境的 AIOps 平台，通过 LangGraph 编排、Tool Gateway 统一控制、OPA 策略治理、VMware Skill Gateway 领域能力封装、Evidence Aggregator 证据汇聚和 RAG 知识增强，提供可审计、可审批、可离线部署的智能运维能力。
