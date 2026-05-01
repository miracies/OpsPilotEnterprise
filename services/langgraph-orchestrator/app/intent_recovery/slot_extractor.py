from __future__ import annotations

import re
from typing import Any

from opspilot_schema.intent import EvidenceRef, ResolutionRef, SlotValue

_ENV_PATTERNS = [
    (re.compile(r"生产(?:环境)?", re.I), "prod"),
    (re.compile(r"\bprod\b", re.I), "prod"),
    (re.compile(r"测试(?:环境)?", re.I), "test"),
    (re.compile(r"开发(?:环境)?", re.I), "dev"),
    (re.compile(r"预发(?:环境)?", re.I), "staging"),
    (re.compile(r"\bstaging\b", re.I), "staging"),
]

_IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_REPLICAS_PATTERN = re.compile(
    r"(?:副本|replicas?)\s*(?:到|为|=)?\s*(\d+)|(?:扩到|扩容到|缩到|scale\s+\S+\s+to|to)\s*(\d+)\b",
    re.I,
)
_VM_PATTERN = re.compile(r"(?:虚拟机|\bvm\b)\s*[:：]?\s*([A-Za-z0-9._-]+)", re.I)
_POWER_VM_PATTERN = re.compile(r"(?:打开|开启|启动|开机|关闭|关机|power\s+on|power\s+off|turn\s+on|turn\s+off)\s*(?:虚拟机|\bvm\b)?\s*([A-Za-z0-9._-]+)", re.I)
_SERVICE_PATTERN = re.compile(r"([A-Za-z0-9._-]+)\s*(?:服务|service)", re.I)
_RESTART_TARGET_PATTERN = re.compile(r"(?:restart|重启)\s+([A-Za-z0-9._-]+)", re.I)
_SCALE_TARGET_PATTERN = re.compile(r"(?:scale)\s+([A-Za-z0-9._-]+)\s+(?:to)?\s*\d+|\b([A-Za-z0-9._-]+)\s*(?:扩到|扩容到|缩到)\s*\d+", re.I)
_VERSION_PATTERN = re.compile(r"\b(\d+(?:\.\d+){1,3})\b")
_HOST_PATTERN = re.compile(
    r"(?:主机|host|esxi)\s*[:：]?\s*([A-Za-z0-9][A-Za-z0-9._-]*(?:\.[A-Za-z0-9._-]+)*)",
    re.I,
)
_FQDN_PATTERN = re.compile(r"\b([A-Za-z0-9][A-Za-z0-9-]*(?:\.[A-Za-z0-9-]+){1,})\b")
_HOSTNAME_TOKEN_PATTERN = re.compile(r"\b(esx[a-z0-9._-]*)\b", re.I)
_VMWARE_DOC_KEYWORDS = re.compile(
    r"vmware|esxi|vcenter|vsphere|download|install|version|patch|kb|article|compatibility|文档|下载|版本|补丁|兼容",
    re.I,
)
_HOST_HINTS = re.compile(r"主机|host|esxi", re.I)
_DIAGNOSIS_HINTS = re.compile(r"健康|健康情况|状态|overallstatus|yellow|red|分析|检查|诊断|health|status|diagnose", re.I)
_INVALID_HOST_MENTIONS = {
    "esxi",
    "version",
    "versions",
    "download",
    "patch",
    "article",
    "kb",
    "compatibility",
    "status",
    "health",
    "overallstatus",
    "connectionstate",
    "powerstate",
    "count",
    "summary",
    "inventory",
    "deployment",
    "service",
}
_GENERIC_TARGET_STOPWORDS = {
    "deployment",
    "deployments",
    "service",
    "services",
    "pod",
    "pods",
    "host",
    "主机",
}


def _short_name(value: str) -> str:
    text = (value or "").strip().lower()
    return text.split(".", 1)[0] if "." in text else text


def _dedup_aliases(values: list[str]) -> list[str]:
    seen: set[str] = set()
    aliases: list[str] = []
    for value in values:
        text = (value or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        aliases.append(text)
    return aliases


def _candidate_aliases(item: dict[str, Any]) -> list[str]:
    name = str(item.get("name") or "").strip()
    aliases = [str(alias).strip() for alias in (item.get("aliases") or []) if str(alias).strip()]
    short = _short_name(name)
    if short and short != name.lower():
        aliases.append(short)
    return _dedup_aliases([name, *aliases])


def _infer_target_type(intent_hint: str | None, text: str) -> str | None:
    hint = (intent_hint or "").lower()
    if "host_diagnose" in hint:
        return "host"
    if "scale_deployment" in hint:
        return "deployment"
    if "service_restart" in hint:
        return "service"
    if bool(_HOST_HINTS.search(text)) and bool(_DIAGNOSIS_HINTS.search(text)):
        return "host"
    if "vm_" in hint or "虚拟机" in text.lower() or re.search(r"\bvm\b", text, re.I):
        return "vm"
    return None


def _is_version_like(value: str) -> bool:
    candidate = (value or "").strip()
    return bool(candidate and _VERSION_PATTERN.fullmatch(candidate))


def _is_invalid_host_mention(value: str) -> bool:
    candidate = (value or "").strip().lower().strip(".,:;!?()[]{}")
    return not candidate or candidate in _INVALID_HOST_MENTIONS or _is_version_like(candidate)


def _is_invalid_generic_target(value: str) -> bool:
    candidate = (value or "").strip().lower().strip(".,:;!?()[]{}")
    return not candidate or candidate in _GENERIC_TARGET_STOPWORDS


def _extract_target_mention(utterance: str, intent_hint: str | None = None) -> tuple[str | None, str | None]:
    text = utterance or ""
    inferred_type = _infer_target_type(intent_hint, text)

    ip_match = _IP_PATTERN.search(text)
    if ip_match:
        return ip_match.group(0), inferred_type or "host"

    if inferred_type == "host":
        host_match = _HOST_PATTERN.search(text)
        if host_match and not _is_invalid_host_mention(host_match.group(1)):
            return host_match.group(1), "host"
        fqdn_match = _FQDN_PATTERN.search(text)
        if fqdn_match and not _is_invalid_host_mention(fqdn_match.group(1)):
            return fqdn_match.group(1), "host"
        token_match = _HOSTNAME_TOKEN_PATTERN.search(text)
        if token_match and not _is_invalid_host_mention(token_match.group(1)):
            return token_match.group(1), "host"

    if inferred_type == "service":
        restart_match = _RESTART_TARGET_PATTERN.search(text)
        if restart_match and not _is_invalid_generic_target(restart_match.group(1)):
            return restart_match.group(1), "service"

    if inferred_type == "deployment":
        scale_match = _SCALE_TARGET_PATTERN.search(text)
        if scale_match:
            candidate = scale_match.group(1) or scale_match.group(2)
            if candidate and not _is_invalid_generic_target(candidate):
                return candidate, "deployment"

    vm_match = _VM_PATTERN.search(text)
    if vm_match:
        return vm_match.group(1), "vm"

    power_vm_match = _POWER_VM_PATTERN.search(text)
    if power_vm_match:
        return power_vm_match.group(1), "vm"

    if inferred_type == "host":
        token_match = _HOSTNAME_TOKEN_PATTERN.search(text)
        if token_match and not _is_invalid_host_mention(token_match.group(1)):
            return token_match.group(1), "host"
    return None, inferred_type


def _resource_type_matches(resource_type: str, expected_type: str | None) -> bool:
    if not expected_type:
        return True
    normalized = (resource_type or "").strip().lower()
    if expected_type == "host":
        return normalized in {"host", "esxi", "vmware_host"}
    if expected_type == "vm":
        return normalized in {"vm", "virtual_machine"}
    if expected_type == "deployment":
        return normalized in {"deployment", "workload", "k8s_deployment"}
    if expected_type == "service":
        return normalized in {"service", "host_service", "application_service"}
    return True


def resolve_target_candidates(
    mention: str | None,
    resource_catalog: list[dict[str, Any]] | None = None,
    *,
    expected_type: str | None = None,
) -> list[ResolutionRef]:
    if not mention or not resource_catalog:
        return []

    mention_norm = mention.strip().lower()
    mention_short = _short_name(mention)
    candidates: list[ResolutionRef] = []
    for item in resource_catalog:
        resource_type = str(item.get("type") or "resource")
        if not _resource_type_matches(resource_type, expected_type):
            continue
        name = str(item.get("name") or item.get("id") or "").strip()
        aliases = _candidate_aliases(item)
        if not name:
            continue

        matched_by = ""
        score = 0.0
        lowered_aliases = [alias.lower() for alias in aliases]
        short_aliases = {_short_name(alias) for alias in aliases}
        if mention_norm == name.lower():
            matched_by = "exact_name"
            score = 1.0
        elif mention_norm in lowered_aliases:
            matched_by = "exact_alias"
            score = 0.98
        elif mention_short and mention_short in short_aliases:
            matched_by = "short_name"
            score = 0.94
        elif mention_norm in name.lower():
            matched_by = "partial_name"
            score = 0.82
        elif any(mention_norm in alias for alias in lowered_aliases):
            matched_by = "partial_alias"
            score = 0.78
        if score <= 0:
            continue
        candidates.append(
            ResolutionRef(
                ref_id=str(item.get("id") or name),
                name=name,
                type=resource_type,
                matched_by=matched_by,
                connection_id=str(item.get("connection_id") or "") or None,
                environment=str(item.get("environment") or "") or None,
                aliases=aliases,
                score=score,
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:5]


def normalize_utterance(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def extract_slots(
    utterance: str,
    history: list[dict[str, Any]] | None = None,
    *,
    intent_hint: str | None = None,
    resource_catalog: list[dict[str, Any]] | None = None,
) -> list[SlotValue]:
    text = utterance or ""
    lower_text = normalize_utterance(text)
    slots: list[SlotValue] = []

    for pattern, env in _ENV_PATTERNS:
        if pattern.search(text):
            slots.append(SlotValue(name="environment", value=env, source="user", confidence=0.95))
            break

    target_mention, inferred_type = _extract_target_mention(text, intent_hint=intent_hint)
    if target_mention:
        slots.append(SlotValue(name="target_object", value=target_mention, source="user", confidence=0.92))
        slots.append(SlotValue(name="target_object_raw", value=target_mention, source="user", confidence=0.92))
    if inferred_type:
        slots.append(SlotValue(name="target_type", value=inferred_type, source="inferred", confidence=0.85))

    resolution_candidates = resolve_target_candidates(
        target_mention,
        resource_catalog,
        expected_type=inferred_type,
    )
    if resolution_candidates:
        top = resolution_candidates[0]
        slots.append(SlotValue(name="target_object_resolved", value=top.name, source="tool_discovery", confidence=top.score))
        slots.append(SlotValue(name="target_resolution_confidence", value=top.score, source="tool_discovery", confidence=top.score))
        slots.append(SlotValue(name="target_resolution_ref_id", value=top.ref_id, source="tool_discovery", confidence=top.score))
        slots.append(SlotValue(name="target_type", value=top.type, source="tool_discovery", confidence=top.score))
        mention_short = _short_name(target_mention or "")
        is_shortname_ambiguous = len(resolution_candidates) > 1 and mention_short and mention_short == _short_name(top.name)
        if top.score >= 0.9 and not is_shortname_ambiguous and (
            len(resolution_candidates) == 1 or top.score - resolution_candidates[1].score >= 0.08
        ):
            slots.append(SlotValue(name="target_object", value=top.name, source="tool_discovery", confidence=top.score))

    replicas_match = _REPLICAS_PATTERN.search(text)
    if replicas_match:
        replicas_value = replicas_match.group(1) or replicas_match.group(2)
        if replicas_value:
            slots.append(SlotValue(name="replicas", value=int(replicas_value), source="user", confidence=0.9))

    service_match = _SERVICE_PATTERN.search(text)
    if service_match and "service_name" not in {slot.name for slot in slots}:
        slots.append(SlotValue(name="service_name", value=service_match.group(1), source="user", confidence=0.8))
    elif inferred_type == "service":
        restart_match = _RESTART_TARGET_PATTERN.search(text)
        if restart_match and not _is_invalid_generic_target(restart_match.group(1)):
            slots.append(SlotValue(name="service_name", value=restart_match.group(1), source="user", confidence=0.85))

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
