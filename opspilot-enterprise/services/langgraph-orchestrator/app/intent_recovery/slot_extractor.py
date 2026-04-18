from __future__ import annotations

import re
from typing import Any

from opspilot_schema.intent import EvidenceRef, SlotValue

_ENV_PATTERNS = [
    (re.compile(r"生产(?:环境)?", re.I), "prod"),
    (re.compile(r"\bprod\b", re.I), "prod"),
    (re.compile(r"测试(?:环境)?", re.I), "test"),
    (re.compile(r"开发(?:环境)?", re.I), "dev"),
    (re.compile(r"预发(?:环境)?", re.I), "staging"),
    (re.compile(r"\bstaging\b", re.I), "staging"),
]

_IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_REPLICAS_PATTERN = re.compile(r"(?:副本|replicas?)\s*(?:到|为|=)?\s*(\d+)", re.I)
_VM_PATTERN = re.compile(r"(?:虚拟机|\bvm\b)\s*[:：]?\s*([A-Za-z0-9._-]+)", re.I)
_POWER_VM_PATTERN = re.compile(r"(?:打开|开启|启动|开机|关闭|关机|power\s+on|power\s+off|turn\s+on|turn\s+off)\s*(?:虚拟机|\bvm\b)?\s*([A-Za-z0-9._-]+)", re.I)
_SERVICE_PATTERN = re.compile(r"([A-Za-z0-9._-]+)\s*(?:服务|service)", re.I)
_VERSION_PATTERN = re.compile(r"\b(\d+(?:\.\d+){1,3})\b")
_VMWARE_DOC_KEYWORDS = re.compile(
    r"vmware|esxi|vcenter|vsphere|download|install|version|patch|kb|article|compatibility|文档|下载|版本|补丁|兼容",
    re.I,
)


def normalize_utterance(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def extract_slots(utterance: str, history: list[dict[str, Any]] | None = None) -> list[SlotValue]:
    text = utterance or ""
    lower_text = normalize_utterance(text)
    slots: list[SlotValue] = []

    for pattern, env in _ENV_PATTERNS:
        if pattern.search(text):
            slots.append(SlotValue(name="environment", value=env, source="user", confidence=0.95))
            break

    ip_match = _IP_PATTERN.search(text)
    if ip_match:
        slots.append(SlotValue(name="target_object", value=ip_match.group(0), source="user", confidence=0.95))

    vm_match = _VM_PATTERN.search(text)
    if vm_match:
        slots.append(SlotValue(name="target_object", value=vm_match.group(1), source="user", confidence=0.9))
    else:
        power_vm_match = _POWER_VM_PATTERN.search(text)
        if power_vm_match:
            slots.append(SlotValue(name="target_object", value=power_vm_match.group(1), source="user", confidence=0.85))

    replicas_match = _REPLICAS_PATTERN.search(text)
    if replicas_match:
        slots.append(SlotValue(name="replicas", value=int(replicas_match.group(1)), source="user", confidence=0.9))

    service_match = _SERVICE_PATTERN.search(text)
    if service_match and "service_name" not in {slot.name for slot in slots}:
        slots.append(SlotValue(name="service_name", value=service_match.group(1), source="user", confidence=0.8))

    if _VMWARE_DOC_KEYWORDS.search(text):
        slots.append(SlotValue(name="query_text", value=text.strip(), source="user", confidence=0.95))
        slots.append(SlotValue(name="language", value="en_US", source="inferred", confidence=0.8))
        slots.append(SlotValue(name="resource_scope", value="global", source="inferred", confidence=0.9))
        if "esxi" in lower_text:
            slots.append(SlotValue(name="product", value="ESXi", source="inferred", confidence=0.9))
        elif "vcenter" in lower_text:
            slots.append(SlotValue(name="product", value="vCenter", source="inferred", confidence=0.85))
        elif "vsphere" in lower_text:
            slots.append(SlotValue(name="product", value="vSphere", source="inferred", confidence=0.85))
        version_match = _VERSION_PATTERN.search(text)
        if version_match:
            slots.append(SlotValue(name="version", value=version_match.group(1), source="user", confidence=0.95))

    if any(token in lower_text for token in ("批量", "多个", "集群", "cluster")):
        slots.append(SlotValue(name="resource_scope", value="cluster", source="inferred", confidence=0.7))
    elif any(token in lower_text for token in ("全局", "全部")):
        slots.append(SlotValue(name="resource_scope", value="global", source="inferred", confidence=0.65))
    else:
        slots.append(SlotValue(name="resource_scope", value="single", source="inferred", confidence=0.7))

    if history:
        for message in reversed(history[-6:]):
            content = str(message.get("content") or "")
            if not content:
                continue
            if "conn-vcenter-prod" in content:
                slots.append(SlotValue(name="connection_id", value="conn-vcenter-prod", source="memory", confidence=0.7))
                break

    dedup: dict[str, SlotValue] = {}
    for slot in slots:
        prev = dedup.get(slot.name)
        if prev is None or slot.confidence >= prev.confidence:
            dedup[slot.name] = slot
    return list(dedup.values())


def build_evidence_refs(utterance: str, slots: list[SlotValue]) -> list[EvidenceRef]:
    evidence: list[EvidenceRef] = []
    for slot in slots:
        evidence.append(
            EvidenceRef(
                type="session",
                ref_id=f"slot:{slot.name}",
                summary=f"从用户输入识别到 {slot.name}={slot.value}",
                score=slot.confidence,
            )
        )
    if utterance:
        evidence.append(
            EvidenceRef(
                type="session",
                ref_id="utterance",
                summary=f"原始输入: {utterance[:120]}",
                score=0.6,
            )
        )
    return evidence
