from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal


VmwareAction = Literal[
    "count",
    "list",
    "summary",
    "detail",
    "metric",
    "capacity",
    "relationship",
    "topn",
    "diagnose",
    "export",
    "power_on",
    "power_off",
    "migrate",
    "restart",
    "delete",
    "snapshot",
]
VmwareResourceType = Literal["vm", "host", "datastore", "cluster", "datacenter", "network", "snapshot"]


@dataclass(frozen=True, slots=True)
class VmwareResourceSpec:
    type: VmwareResourceType
    label: str
    collection_key: str
    count_summary_key: str
    aliases: tuple[str, ...]
    fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VmwareFilter:
    field: str
    operator: str
    value: Any
    label: str


@dataclass(frozen=True, slots=True)
class VmwareIntent:
    domain: str
    action: VmwareAction
    resource_type: VmwareResourceType | None = None
    environment: str = "prod"
    filters: tuple[VmwareFilter, ...] = ()
    output_format: str = "text"
    target_object: str | None = None
    metric_name: str | None = None
    relationship_target: VmwareResourceType | None = None
    time_range_minutes: int = 0
    step_seconds: int = 300
    aggregation: str = "latest"
    limit: int = 5
    risk_level: str = "L0"
    raw_text: str = ""


RESOURCE_SPECS: dict[VmwareResourceType, VmwareResourceSpec] = {
    "vm": VmwareResourceSpec(
        type="vm",
        label="虚拟机",
        collection_key="virtual_machines",
        count_summary_key="vm_count",
        aliases=("虚拟机", "虚机", "vm", "vms", "virtual machine", "virtual machines"),
        fields=("vm_id", "name", "power_state", "host_id", "cluster_id"),
    ),
    "host": VmwareResourceSpec(
        type="host",
        label="ESXi 主机",
        collection_key="hosts",
        count_summary_key="host_count",
        aliases=("esxi", "主机", "物理主机", "host", "hosts", "vmware host"),
        fields=(
            "host_id",
            "name",
            "overall_status",
            "connection_state",
            "power_state",
            "vm_count",
            "cpu_mhz",
            "cpu_usage_mhz",
            "memory_mb",
            "memory_usage_mb",
        ),
    ),
    "datastore": VmwareResourceSpec(
        type="datastore",
        label="Datastore",
        collection_key="datastores",
        count_summary_key="datastore_count",
        aliases=("datastore", "datastores", "数据存储", "存储", "存储卷", "数据仓库"),
        fields=("id", "name", "type", "capacity_gb", "free_gb", "free_percent"),
    ),
    "cluster": VmwareResourceSpec(
        type="cluster",
        label="集群",
        collection_key="clusters",
        count_summary_key="cluster_count",
        aliases=("集群", "cluster", "clusters", "计算集群"),
        fields=("cluster_id", "name", "host_count", "vm_count", "overall_status"),
    ),
    "datacenter": VmwareResourceSpec(
        type="datacenter",
        label="Datacenter",
        collection_key="datacenters",
        count_summary_key="datacenter_count",
        aliases=("datacenter", "datacenters", "数据中心", "机房"),
        fields=("id", "name"),
    ),
    "network": VmwareResourceSpec(
        type="network",
        label="网络",
        collection_key="networks",
        count_summary_key="network_count",
        aliases=("network", "networks", "网络", "端口组", "portgroup"),
    ),
    "snapshot": VmwareResourceSpec(
        type="snapshot",
        label="快照",
        collection_key="snapshots",
        count_summary_key="snapshot_count",
        aliases=("snapshot", "snapshots", "快照"),
    ),
}

READ_ACTIONS = {"count", "list", "summary", "detail", "metric", "capacity", "relationship", "topn"}
WRITE_ACTIONS = {"power_on", "power_off", "migrate", "restart", "delete", "snapshot"}

METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "cpu_usage_percent": ("cpu使用率", "cpu 使用率", "cpu usage", "cpu.usage", "cpu_usage_percent"),
    "cpu_capacity_mhz": ("cpu容量", "cpu 总量", "cpu capacity", "cpu_capacity_mhz"),
    "memory_usage_percent": ("内存使用率", "内存 使用率", "memory usage", "mem usage", "memory_usage_percent"),
    "memory_capacity_mb": ("内存容量", "内存总量", "memory capacity", "memory_capacity_mb"),
    "datastore_free_percent": ("剩余容量", "可用容量", "free percent", "free_percent", "datastore_free_percent"),
    "datastore_capacity_gb": ("总容量", "容量", "capacity", "capacity_gb", "datastore_capacity_gb"),
    "datastore_iops": ("iops", "读写次数", "datastore_iops"),
    "datastore_latency_ms": ("延迟", "时延", "latency", "latency_ms", "datastore_latency_ms"),
    "datastore_throughput_mbps": ("吞吐", "吞吐量", "throughput", "mbps", "datastore_throughput_mbps"),
}

_ENV_PATTERNS = (
    (re.compile(r"生产(?:环境)?|\bprod\b", re.I), "prod"),
    (re.compile(r"测试(?:环境)?|\btest\b", re.I), "test"),
    (re.compile(r"开发(?:环境)?|\bdev\b", re.I), "dev"),
    (re.compile(r"预发(?:环境)?|\bstaging\b", re.I), "staging"),
)
_COUNT_PATTERN = re.compile(r"多少|数量|几个|几台|总数|\bcount\b", re.I)
_LIST_PATTERN = re.compile(r"哪些|列表|列出|清单|有哪些|明细|\blist\b|show", re.I)
_SUMMARY_PATTERN = re.compile(r"概览|摘要|overview|summary", re.I)
_RELATIONSHIP_PATTERN = re.compile(r"关联|挂载|连接|有哪些|哪些|\brelated\b|\battached\b", re.I)
_TOPN_PATTERN = re.compile(r"最高|最低|最大|最小|top\s*\d*|排行|排序", re.I)
_METRIC_HINT_PATTERN = re.compile(r"cpu|内存|memory|mem|使用率|性能|指标|iops|延迟|latency|吞吐|throughput", re.I)
_CAPACITY_PATTERN = re.compile(r"容量|剩余|可用|free|capacity|空间", re.I)
_EXPORT_PATTERN = re.compile(r"导出|export", re.I)
_DOC_PATTERN = re.compile(r"download|install|version|patch|kb|article|compatibility|文档|下载|版本|补丁|兼容", re.I)
_DIAG_PATTERN = re.compile(r"分析|诊断|排查|告警|根因|为什么|什么问题|可能.*问题|健康|overallstatus|yellow|red", re.I)
_TIME_RANGE_PATTERN = re.compile(r"(?:过去|最近|近)\s*(\d+)\s*(分钟|分|小时|h|hour|hours|m|min|minute|minutes)", re.I)
_WRITE_PATTERNS: tuple[tuple[VmwareAction, re.Pattern[str]], ...] = (
    ("power_on", re.compile(r"开机|打开|开启|启动|上电|power\s*on|turn\s*on", re.I)),
    ("power_off", re.compile(r"关机|关闭|断电|power\s*off|shutdown|turn\s*off", re.I)),
    ("migrate", re.compile(r"迁移|热迁移|vmotion|migrate", re.I)),
    ("restart", re.compile(r"重启|restart|reboot", re.I)),
    ("delete", re.compile(r"删除|销毁|delete|remove|destroy", re.I)),
    ("snapshot", re.compile(r"快照|snapshot", re.I)),
)
_CAPACITY_THRESHOLD_PATTERN = re.compile(
    r"(?:容量|剩余|free|可用).*?(?:小于|低于|少于|<|less than)\s*(\d+(?:\.\d+)?)\s*%?",
    re.I,
)
_NAME_CONTAINS_PATTERN = re.compile(r"(?:名称|名字|name).*(?:包含|含有|contains)\s*([A-Za-z0-9._-]+)", re.I)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def _environment(text: str) -> str:
    for pattern, env in _ENV_PATTERNS:
        if pattern.search(text):
            return env
    return "prod"


def _has_vmware_context(text: str) -> bool:
    lowered = _normalize(text)
    if any(token in lowered for token in ("vcenter", "vsphere", "vmware", "esxi")):
        return True
    if re.search(r"\besx[a-z0-9._-]*\b", lowered):
        return True
    if _METRIC_HINT_PATTERN.search(text) and re.search(r"\b[a-z0-9._-]*(?:esx|datastore)[a-z0-9._-]*\b", lowered):
        return True
    return any(alias in text for spec in RESOURCE_SPECS.values() for alias in spec.aliases if any("\u4e00" <= ch <= "\u9fff" for ch in alias))


def detect_resource_type(text: str) -> VmwareResourceType | None:
    lowered = _normalize(text)
    if re.search(r"\besx[a-z0-9._-]*\b", lowered):
        return "host"
    for resource_type, spec in RESOURCE_SPECS.items():
        if any(alias.lower() in lowered or alias in text for alias in spec.aliases):
            return resource_type
    if "cpu" in lowered or "memory" in lowered or "内存" in text:
        return "host"
    return None


def _detect_write_action(text: str) -> VmwareAction | None:
    for action, pattern in _WRITE_PATTERNS:
        if pattern.search(text):
            return action
    return None


def _detect_read_action(text: str) -> VmwareAction | None:
    if _EXPORT_PATTERN.search(text):
        return "export"
    if _TOPN_PATTERN.search(text) and (_METRIC_HINT_PATTERN.search(text) or _CAPACITY_PATTERN.search(text)):
        return "topn"
    if _RELATIONSHIP_PATTERN.search(text) and any(token in _normalize(text) for token in ("datastore", "vm", "host", "esx")):
        return "relationship"
    if _METRIC_HINT_PATTERN.search(text):
        return "metric"
    if _CAPACITY_PATTERN.search(text):
        return "capacity"
    if _COUNT_PATTERN.search(text):
        return "count"
    if _LIST_PATTERN.search(text):
        return "list"
    if _SUMMARY_PATTERN.search(text):
        return "summary"
    return None


def _metric_name(text: str, resource_type: VmwareResourceType | None) -> str | None:
    lowered = _normalize(text)
    for metric_name, aliases in METRIC_ALIASES.items():
        if any(alias.lower() in lowered or alias in text for alias in aliases):
            if metric_name.startswith("datastore_") and resource_type not in {None, "datastore"}:
                continue
            return metric_name
    if resource_type == "datastore" and _CAPACITY_PATTERN.search(text):
        return "datastore_free_percent" if any(token in text for token in ("剩余", "可用")) or "free" in lowered else "datastore_capacity_gb"
    if resource_type == "host" and "cpu" in lowered:
        return "cpu_usage_percent"
    if resource_type == "host" and ("内存" in text or "memory" in lowered or "mem" in lowered):
        return "memory_usage_percent"
    return None


def _time_range_minutes(text: str) -> int:
    match = _TIME_RANGE_PATTERN.search(text)
    if not match:
        return 0
    value = int(match.group(1))
    unit = match.group(2).lower()
    if unit in {"小时", "h", "hour", "hours"}:
        return max(1, min(value * 60, 10080))
    return max(1, min(value, 10080))


def _aggregation(text: str) -> str:
    lowered = _normalize(text)
    if "平均" in text or "avg" in lowered or "average" in lowered:
        return "avg"
    if "峰值" in text or "最大" in text or "最高" in text or "max" in lowered:
        return "max"
    if "最低" in text or "最小" in text or "min" in lowered:
        return "min"
    return "latest"


def _relationship_target(text: str, resource_type: VmwareResourceType | None) -> VmwareResourceType | None:
    lowered = _normalize(text)
    if "datastore" in lowered or "数据存储" in text or "存储" in text:
        return "datastore"
    if "虚拟机" in text or re.search(r"\bvm\b", lowered):
        return "vm"
    if "主机" in text or "host" in lowered or "esxi" in lowered:
        return "host"
    if resource_type == "host":
        return "datastore"
    if resource_type == "datastore":
        return "host"
    return None


def _target_object(text: str, resource_type: VmwareResourceType | None) -> str | None:
    lowered = _normalize(text)
    if resource_type == "host":
        match = re.search(r"\b[a-z0-9._-]*esx[a-z0-9._-]*\b", lowered, re.I)
        if match:
            return match.group(0)
    if resource_type == "datastore":
        match = re.search(r"\b[a-z0-9._-]*datastore[a-z0-9._-]*\b", text, re.I)
        if match:
            return match.group(0)
    match = re.search(r"(?:名称|名字|name)\s*(?:为|是|=|:|：)?\s*([A-Za-z0-9._-]+)", text, re.I)
    if match:
        return match.group(1)
    return None


def _limit(text: str) -> int:
    match = re.search(r"top\s*(\d+)|前\s*(\d+)", text, re.I)
    if not match:
        return 5
    value = match.group(1) or match.group(2)
    try:
        return max(1, min(int(value), 20))
    except ValueError:
        return 5


def _filters(text: str, resource_type: VmwareResourceType | None) -> tuple[VmwareFilter, ...]:
    result: list[VmwareFilter] = []
    lowered = _normalize(text)
    if resource_type == "vm":
        if "关机" in text or "poweredoff" in lowered or "powered off" in lowered:
            result.append(VmwareFilter("power_state", "eq", "poweredOff", "关机"))
        elif "开机" in text or "运行中" in text or "poweredon" in lowered or "powered on" in lowered:
            result.append(VmwareFilter("power_state", "eq", "poweredOn", "开机"))
    if resource_type == "host":
        if "异常" in text or "非健康" in text or "不健康" in text or any(s in lowered for s in ("yellow", "red")):
            result.append(VmwareFilter("overall_status", "not_in", ("green", "gray", None, ""), "非健康"))
    if resource_type == "datastore":
        capacity_match = _CAPACITY_THRESHOLD_PATTERN.search(text)
        if capacity_match:
            result.append(VmwareFilter("free_percent", "lt", float(capacity_match.group(1)), f"剩余容量低于 {capacity_match.group(1)}%"))
        elif "容量不足" in text or "空间不足" in text:
            result.append(VmwareFilter("free_percent", "lt", 20.0, "容量不足"))
    name_match = _NAME_CONTAINS_PATTERN.search(text)
    if name_match:
        result.append(VmwareFilter("name", "contains", name_match.group(1), f"名称包含 {name_match.group(1)}"))
    return tuple(result)


def parse_vmware_intent(text: str) -> VmwareIntent | None:
    raw = text or ""
    if not raw.strip() or _DOC_PATTERN.search(raw):
        return None
    resource_type = detect_resource_type(raw)
    has_context = _has_vmware_context(raw)
    if not has_context and resource_type is None:
        return None

    read_action = _detect_read_action(raw)
    write_action = _detect_write_action(raw)
    if write_action and read_action is None:
        return VmwareIntent(
            domain="vmware",
            action=write_action,
            resource_type=resource_type or ("vm" if write_action in {"power_on", "power_off", "snapshot", "migrate"} else None),
            environment=_environment(raw),
            filters=_filters(raw, resource_type),
            risk_level="L3",
            raw_text=raw,
        )

    if _DIAG_PATTERN.search(raw) and not (_COUNT_PATTERN.search(raw) or _LIST_PATTERN.search(raw) or _METRIC_HINT_PATTERN.search(raw)):
        return None

    action = read_action
    if action is None:
        if resource_type and _filters(raw, resource_type):
            action = "list"
        else:
            return None

    if action == "export" and resource_type not in (None, "vm"):
        action = "list"
    if action == "capacity" and resource_type is None:
        resource_type = "datastore"
    filters = _filters(raw, resource_type)
    if action == "capacity" and filters:
        action = "list"
    if resource_type is None and action in {"count", "list", "summary", "detail"}:
        resource_type = "vm"
    metric_name = _metric_name(raw, resource_type)
    if action == "capacity":
        metric_name = metric_name or ("datastore_free_percent" if resource_type == "datastore" else None)
    if action == "metric" and resource_type == "datastore" and metric_name is None:
        metric_name = "datastore_latency_ms" if any(token in raw for token in ("延迟", "时延")) else None

    return VmwareIntent(
        domain="vmware",
        action=action,
        resource_type=resource_type,
        environment=_environment(raw),
        filters=filters,
        target_object=_target_object(raw, resource_type),
        metric_name=metric_name,
        relationship_target=_relationship_target(raw, resource_type) if action == "relationship" else None,
        time_range_minutes=_time_range_minutes(raw),
        aggregation=_aggregation(raw),
        limit=_limit(raw),
        raw_text=raw,
    )


def _value_for_filter(row: dict[str, Any], field: str) -> Any:
    if field == "free_percent":
        capacity = row.get("capacity_gb")
        free = row.get("free_gb")
        try:
            capacity_f = float(capacity)
            free_f = float(free)
            if capacity_f <= 0:
                return None
            return round((free_f / capacity_f) * 100, 2)
        except (TypeError, ValueError):
            return None
    return row.get(field)


def _matches_filter(row: dict[str, Any], item_filter: VmwareFilter) -> bool:
    value = _value_for_filter(row, item_filter.field)
    if item_filter.operator == "eq":
        return str(value).lower() == str(item_filter.value).lower()
    if item_filter.operator == "not_in":
        return value not in item_filter.value
    if item_filter.operator == "lt":
        try:
            return float(value) < float(item_filter.value)
        except (TypeError, ValueError):
            return False
    if item_filter.operator == "contains":
        return str(item_filter.value).lower() in str(value or "").lower()
    return True


def collection_for_intent(inventory: dict[str, Any], intent: VmwareIntent) -> list[dict[str, Any]]:
    if not intent.resource_type:
        return []
    spec = RESOURCE_SPECS[intent.resource_type]
    rows = inventory.get(spec.collection_key, []) if isinstance(inventory, dict) else []
    if not isinstance(rows, list):
        return []
    normalized_rows = [row for row in rows if isinstance(row, dict)]
    for item_filter in intent.filters:
        normalized_rows = [row for row in normalized_rows if _matches_filter(row, item_filter)]
    return normalized_rows


def count_for_intent(inventory: dict[str, Any], intent: VmwareIntent) -> int:
    if intent.filters:
        return len(collection_for_intent(inventory, intent))
    if not intent.resource_type:
        return 0
    spec = RESOURCE_SPECS[intent.resource_type]
    summary = inventory.get("summary", {}) if isinstance(inventory, dict) else {}
    value = summary.get(spec.count_summary_key)
    if isinstance(value, int):
        return value
    return len(collection_for_intent(inventory, intent))


def filter_label(intent: VmwareIntent) -> str:
    if not intent.filters:
        return ""
    return "；".join(item.label for item in intent.filters)


def row_name(row: dict[str, Any]) -> str:
    return str(row.get("name") or row.get("vm_id") or row.get("host_id") or row.get("cluster_id") or row.get("id") or "")


def row_brief(row: dict[str, Any], resource_type: VmwareResourceType) -> str:
    name = row_name(row)
    if resource_type == "vm":
        return f"{name}（{row.get('power_state', 'unknown')}）"
    if resource_type == "host":
        return f"{name}（状态={row.get('overall_status', 'unknown')}，VM={row.get('vm_count', 'N/A')}）"
    if resource_type == "datastore":
        free_percent = _value_for_filter(row, "free_percent")
        return f"{name}（类型={row.get('type', 'N/A')}，剩余={row.get('free_gb', 'N/A')}GB/{free_percent if free_percent is not None else 'N/A'}%）"
    if resource_type == "cluster":
        return f"{name}（主机={row.get('host_count', 'N/A')}，VM={row.get('vm_count', 'N/A')}）"
    return name


def intent_to_dict(intent: VmwareIntent) -> dict[str, Any]:
    return {
        "domain": intent.domain,
        "action": intent.action,
        "resource_type": intent.resource_type,
        "environment": intent.environment,
        "filters": [asdict(item) for item in intent.filters],
        "output_format": intent.output_format,
        "target_object": intent.target_object,
        "metric_name": intent.metric_name,
        "relationship_target": intent.relationship_target,
        "time_range_minutes": intent.time_range_minutes,
        "step_seconds": intent.step_seconds,
        "aggregation": intent.aggregation,
        "limit": intent.limit,
        "risk_level": intent.risk_level,
    }
