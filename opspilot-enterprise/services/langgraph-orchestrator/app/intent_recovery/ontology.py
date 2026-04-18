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
        intent_code="vmware.vm.power",
        domain="vmware",
        action="vm_power",
        description="vCenter 虚拟机电源操作",
        keywords=("虚拟机", "vm", "电源", "开机", "关机", "启动", "关闭"),
        required_slots=("target_object", "environment"),
        examples=("打开 Test-VM 电源",),
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
