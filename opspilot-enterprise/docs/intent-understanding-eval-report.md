# AI 对话意图理解实测报告

## 本轮范围

- 主入口：`orchestrator_v2`
- 实测层：`API + 页面`
- 当前阶段：`只读类 + 门禁类 + 澄清类`
- 写操作真实执行：`暂缓到后续低风险副作用验收`

## 执行方式

- API 实测脚本：[eval_intent_understanding.py](/E:/work/git/OpsPilot/opspilot-enterprise/scripts/eval_intent_understanding.py)
- 页面实测脚本：[eval_intent_understanding_page.js](/E:/work/git/OpsPilot/opspilot-enterprise/scripts/eval_intent_understanding_page.js)
- 用例数据集：[intent_understanding_cases.json](/E:/work/git/OpsPilot/opspilot-enterprise/tests/data/intent_understanding_cases.json)

## 当前基线结论

### 汇总统计

- API 评测：`30` 条样本
  - `18 passed`
  - `4 partial`
  - `8 failed`
  - `5 skipped`
- 页面评测：`7` 条页面样本
  - `3 passed`
  - `4 failed`

### 已验证可用

- `vmware.host.diagnose`
  - `分析主机 esx06.vstecs.lab 健康情况` 可稳定返回真实主机健康结果
  - `分析 esx06 健康情况` 可稳定解析到真实主机
- 多候选 Clarify
  - `分析 esx0 健康情况` 可返回真实候选 Host 列表
  - Clarify 点选后页面可继续回填真实诊断结果
- `knowledge.vmware_kb_search`
  - `How do I download ESXi version 9.0.3?` 可命中 KB 检索并返回官方来源

### 当前明显不足

- 通用运维问答
  - `虚拟机热迁移是否会丢包`
  - 当前主链路仍存在误路由或未稳定进入结构化问答路径
- 资源统计问法
  - `vcenter生产环境有多少虚拟机`
  - 当前 `orchestrator_v2` 下未稳定进入资源查询路径
- 中文资源统计/导出短句
  - `查一下生产环境主机数量`
  - `导出vCenter生产环境虚拟机列表，包括名称、ip地址、所在esxi主机名`
  - 仍可能误入 `knowledge.vmware_kb_search` 或错误缺槽
- 部分页面链路
  - 多候选 Clarify 的前端渲染与点选回填仍有 `ui_render_gap`
  - 页面脚本当前有 4 条样本失败，主要集中在 Clarify 展示和结果文本可见性

## 主要失败根因

### API 层

- `resource_query_rejected`
  - 典型问题：资源统计/导出类问题未进入资源查询分支
- `slot_missing_false_positive`
  - 典型问题：对象或连接本应可推断，但仍被当成缺槽
- 通用问答域门控不足
  - `generic_ops_qa` 与 `vmware.host.diagnose / knowledge.*` 之间仍有混淆

### 页面层

- `ui_render_gap`
  - 典型问题：后端已有结果，但页面未稳定呈现期望文本
  - Clarify 候选列表和回填结果在自动化验证下仍不够稳定

## 代表性结果

### 通过样本

- `J001` `分析主机 esx06.vstecs.lab 健康情况`
  - API：通过
  - 页面：通过
- `J003` `分析 esx0 健康情况`
  - API：通过
  - 说明：后端可进入多候选 Clarify，并允许继续回填
- `J006` `How do I download ESXi version 9.0.3?`
  - API：通过
  - 命中 `knowledge.vmware_kb_search`

### 失败样本

- `J005` `vcenter生产环境有多少虚拟机`
  - 现象：未稳定进入资源查询链路
- `J007` `虚拟机热迁移是否会丢包`
  - 现象：未稳定进入通用运维问答链路
- `S007` `导出vCenter生产环境虚拟机列表，包括名称、ip地址、所在esxi主机名`
  - 现象：被误判到 `knowledge.vmware_kb_search`

## 报告文件

脚本运行后会在 `tmp/intent-eval/` 目录生成：

- `api-report.json`
- `page-report.json`

这些文件用于记录本轮逐条样本的真实结果、检查项和根因标签。

## 验收建议

下一轮优先修复：

1. `generic_ops_qa` 路由稳定性
2. `resource_query` 在 `orchestrator_v2` 主链路中的识别与执行
3. Clarify 页面渲染与点选回填的稳定性
4. 写操作样本的 `approval / execute` 分流，再进入低风险真实执行验收
