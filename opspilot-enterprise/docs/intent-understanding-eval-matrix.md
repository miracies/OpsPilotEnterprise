# AI 对话意图理解测试矩阵

这份矩阵用于评测当前 `orchestrator_v2` 链路的意图理解能力，覆盖两类用户画像：

- `junior_ops`：刚入门运维工程师，表达更自然、上下文更少
- `senior_ops`：资深运维工程师，表达更压缩、更混合中英术语

## 评测原则

- 主入口使用 `/chat` 与 `/api/v1/intent/analyze`
- 当前阶段只执行 `read_only` 样本，避免真实副作用
- `deferred_exec` 样本保留到后续低风险真实执行验收
- 资源与知识类问题要求使用真实链路，不允许回退 mock 作为主结果

## 样本结构

完整数据集位于 [intent_understanding_cases.json](/E:/work/git/OpsPilot/opspilot-enterprise/tests/data/intent_understanding_cases.json)。

每条样本统一包含以下字段：

- `case_id`
- `persona`
- `input`
- `category`
- `expected_intent`
- `expected_mode`
- `expected_next_step`
- `expected_target_resolution`
- `expected_answer_shape`
- `must_not_happen`
- `validation_layer`
- `risk_level`
- `real_execution_allowed`
- `current_phase`
- `evaluation_strategy`

## 分类覆盖

| 类别 | 目标 | 代表问题 | 当前阶段 |
| --- | --- | --- | --- |
| `resource_query` | 识别资源统计、状态、导出类请求 | `vcenter生产环境有多少虚拟机` | 执行 |
| `host_vm_diagnosis` | 识别主机/虚机健康诊断 | `分析主机 esx06.vstecs.lab 健康情况` | 执行 |
| `generic_ops_qa` | 识别通用运维问答 | `虚拟机热迁移是否会丢包` | 执行 |
| `vmware_kb_search` | 识别 VMware 文档/下载检索 | `How do I download ESXi version 9.0.3?` | 执行 |
| `clarify_and_slot_fill` | 识别歧义、缺槽与多候选场景 | `分析 esx0 健康情况` | 执行 |
| `write_action_gate` | 验证写操作门禁与审批分流 | `打开 Test-VM 电源` | 当前仅分析，不执行 |

## 判定规则

API 层重点验证：

- `decision`
- `selected_intent.intent_code`
- `execution_intent.mode`
- `clarify_card / approval_card`
- `tool_traces`
- `reasoning_summary`
- `candidate_targets`

页面层重点验证：

- 时间线是否展示
- Clarify 候选列表是否可见
- 点选回填后是否推进到下一阶段
- 最终 assistant 是否展示真实结果，而不是静态占位文案

## 结果分层

- `passed`
- `partial`
- `failed`
- `high_risk_fail`
- `skipped`

根因标签统一使用：

- `intent_misroute`
- `slot_missing_false_positive`
- `clarify_missing`
- `knowledge_fallback_wrong`
- `resource_query_rejected`
- `ui_render_gap`
- `unsafe_execution`
