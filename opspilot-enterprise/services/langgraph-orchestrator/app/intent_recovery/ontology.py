from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

IntentScope = Literal["single", "multiple", "cluster", "global"]


@dataclass(slots=True)
class IntentSpec:
    intent_code: str
    domain: str
    action: str
    description: str
    keywords: tuple[str, ...]
    required_slots: tuple[str, ...] = ()
    environment_keywords: tuple[str, ...] = ("生产", "prod", "测试", "test", "开发", "dev")
    resource_scope: IntentScope = "single"
    memory_hints: tuple[str, ...] = ()
    examples: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DomainOntology:
    domain: str
    resource_types: dict[str, tuple[str, ...]]
    actions: dict[str, tuple[str, ...]]
    fields: dict[str, tuple[str, ...]]
    operators: dict[str, tuple[str, ...]]


VMWARE_ONTOLOGY = DomainOntology(
    domain="vmware",
    resource_types={
        "vm": ("虚拟机", "虚机", "vm", "vms", "virtual machine"),
        "host": ("主机", "esxi", "host", "hosts", "vmware host"),
        "datastore": ("datastore", "数据存储", "存储", "数据仓库"),
        "cluster": ("集群", "cluster", "clusters", "计算集群"),
        "datacenter": ("数据中心", "datacenter"),
        "network": ("网络", "network", "端口组", "portgroup"),
        "snapshot": ("快照", "snapshot"),
    },
    actions={
        "count": ("多少", "数量", "几个", "几台", "总数", "count"),
        "list": ("哪些", "列表", "列出", "清单", "有哪些", "list"),
        "detail": ("详情", "明细", "detail"),
        "summary": ("概览", "摘要", "overview", "summary"),
        "diagnose": ("分析", "诊断", "排查", "健康", "告警"),
        "metric": ("指标", "性能", "使用率", "cpu", "内存", "iops", "延迟", "吞吐"),
        "capacity": ("容量", "剩余", "可用", "free", "capacity"),
        "relationship": ("关联", "挂载", "连接", "使用哪些", "有哪些"),
        "topn": ("最高", "最低", "top", "排行", "排序"),
        "power": ("开机", "关机", "上电", "断电", "power on", "power off"),
        "migrate": ("迁移", "热迁移", "vmotion", "migrate"),
        "restart": ("重启", "restart", "reboot"),
        "delete": ("删除", "delete", "destroy"),
        "snapshot": ("快照", "snapshot"),
    },
    fields={
        "power_state": ("电源状态", "运行状态", "power_state", "poweredOn", "poweredOff", "关机", "开机"),
        "overall_status": ("健康状态", "overallStatus", "overall_status", "yellow", "red", "green", "异常"),
        "capacity_gb": ("容量", "capacity", "capacity_gb"),
        "free_gb": ("剩余", "可用", "free", "free_gb"),
        "cluster_id": ("集群", "cluster", "cluster_id"),
        "host_name": ("主机名", "esxi", "host", "host_name"),
        "cpu_usage_percent": ("CPU 使用率", "cpu_usage_percent", "cpu usage"),
        "memory_usage_percent": ("内存使用率", "memory_usage_percent", "memory usage"),
        "datastore_latency_ms": ("datastore 延迟", "latency", "延迟"),
        "datastore_iops": ("datastore iops", "iops"),
        "datastore_throughput_mbps": ("datastore 吞吐", "throughput", "吞吐"),
    },
    operators={
        "eq": ("等于", "是", "="),
        "ne": ("不是", "不等于", "!="),
        "lt": ("小于", "低于", "少于", "<", "less than"),
        "gt": ("大于", "高于", "超过", ">", "greater than"),
        "contains": ("包含", "含有", "contains"),
        "abnormal": ("异常", "非健康", "不健康", "yellow", "red"),
    },
)


ONTOLOGY: list[IntentSpec] = [
    IntentSpec(
        intent_code="knowledge.explain",
        domain="knowledge",
        action="answer_question",
        description="通用运维知识问答",
        keywords=("为什么", "是否", "会不会", "原理", "影响", "风险", "最佳实践", "注意事项"),
        required_slots=(),
        resource_scope="global",
    ),
    IntentSpec(
        intent_code="generic_ops_qa",
        domain="knowledge",
        action="generic_ops_qa",
        description="通用运维问答与风险说明",
        keywords=(
            "是否会",
            "会不会",
            "影响",
            "中断",
            "丢包",
            "风险",
            "原理",
            "注意事项",
            "最佳实践",
            "热迁移",
            "vmotion",
            "deployment",
            "重启",
            "overallstatus",
            "yellow",
            "排查",
            "可能是什么问题",
        ),
        required_slots=(),
        resource_scope="global",
        examples=("虚拟机热迁移是否会丢包",),
    ),
    IntentSpec(
        intent_code="knowledge.vmware_kb_search",
        domain="knowledge",
        action="vmware_kb_search",
        description="VMware/Broadcom 文档与下载类知识检索",
        keywords=(
            "vmware",
            "esxi",
            "vcenter",
            "vsphere",
            "download",
            "install",
            "version",
            "patch",
            "kb",
            "article",
            "compatibility",
            "文档",
            "下载",
            "版本",
            "补丁",
            "兼容性",
        ),
        required_slots=(),
        resource_scope="global",
        examples=("How do I download ESXi version 9.0.3?",),
    ),
    IntentSpec(
        intent_code="resource.vcenter.inventory_summary",
        domain="vmware",
        action="vcenter_inventory_summary",
        description="查询 vCenter 资源概览与统计",
        keywords=(
            "vcenter",
            "vsphere",
            "生产",
            "prod",
            "虚拟机",
            "vm",
            "多少",
            "数量",
            "count",
            "主机数量",
            "esxi",
            "host",
            "datastore",
            "数据存储",
            "存储",
            "集群",
            "cluster",
            "列表",
            "哪些",
            "关机",
            "容量不足",
            "小于",
            "cpu",
            "内存",
            "使用率",
            "性能",
            "指标",
            "延迟",
            "iops",
            "吞吐",
            "关联",
            "最高",
            "最低",
            "异常摘要",
            "资源概览",
        ),
        required_slots=("environment",),
        resource_scope="global",
        examples=("vcenter生产环境有多少虚拟机",),
    ),
    IntentSpec(
        intent_code="resource.vcenter.vm_export",
        domain="vmware",
        action="vcenter_vm_export",
        description="导出 vCenter 生产环境虚拟机列表",
        keywords=("vcenter", "vsphere", "生产", "prod", "虚拟机", "vm", "列表", "list", "导出", "export"),
        required_slots=("environment",),
        resource_scope="global",
        examples=("导出vCenter生产环境虚拟机列表",),
    ),
    IntentSpec(
        intent_code="vmware.vm.power",
        domain="vmware",
        action="vm_power",
        description="vCenter 虚拟机电源操作",
        keywords=("虚拟机", "vm", "电源", "开机", "关机", "启动", "关闭"),
        required_slots=("target_object", "environment"),
        examples=("打开 Test-VM 电源",),
    ),
    IntentSpec(
        intent_code="vmware.write.blocked",
        domain="vmware",
        action="write_blocked",
        description="识别 VMware 高风险执行类操作并进入审批/确认门禁",
        keywords=("开机", "关机", "迁移", "热迁移", "vmotion", "重启", "删除", "快照", "power", "migrate", "restart", "delete", "snapshot"),
        required_slots=(),
        resource_scope="single",
    ),
    IntentSpec(
        intent_code="vmware.vm.status",
        domain="vmware",
        action="vm_status",
        description="查询虚拟机状态",
        keywords=("虚拟机", "vm", "状态", "运行状态", "电源状态"),
        required_slots=("target_object",),
    ),
    IntentSpec(
        intent_code="vmware.host.diagnose",
        domain="vmware",
        action="host_diagnose",
        description="分析 vCenter/ESXi 主机健康",
        keywords=("esxi", "主机", "host", "overallstatus", "yellow", "red", "健康", "分析"),
        required_slots=("target_object",),
    ),
    IntentSpec(
        intent_code="k8s.scale",
        domain="k8s",
        action="scale_deployment",
        description="K8s 工作负载扩缩容",
        keywords=("k8s", "kubernetes", "deployment", "副本", "扩容", "缩容", "scale"),
        required_slots=("target_object", "replicas", "environment"),
    ),
    IntentSpec(
        intent_code="host.service.restart",
        domain="host",
        action="service_restart",
        description="主机服务重启",
        keywords=("主机", "service", "服务", "重启", "restart"),
        required_slots=("target_object", "service_name", "environment"),
    ),
    IntentSpec(
        intent_code="jenkins.job.run",
        domain="jenkins",
        action="run_job",
        description="Jenkins 任务触发",
        keywords=("jenkins", "job", "流水线", "构建", "build", "运行"),
        required_slots=("target_object",),
    ),
]


def list_intents() -> list[IntentSpec]:
    return ONTOLOGY


def list_domain_ontologies() -> list[DomainOntology]:
    return [VMWARE_ONTOLOGY]
