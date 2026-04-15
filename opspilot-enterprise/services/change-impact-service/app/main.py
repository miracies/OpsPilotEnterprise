from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml
from fastapi import FastAPI
from opspilot_schema.change_impact import (
    ChangeImpactRequest,
    ChangeImpactResult,
    DependencyNode,
    ImpactedObject,
)
from opspilot_schema.envelope import make_error, make_success

app = FastAPI(title="OpsPilot Change Impact Service")

TOOL_GATEWAY_URL = os.environ.get("TOOL_GATEWAY_URL", "http://127.0.0.1:8020").rstrip("/")
GOVERNANCE_SERVICE_URL = os.environ.get("GOVERNANCE_SERVICE_URL", "http://127.0.0.1:8071").rstrip("/")

VCENTER_ENDPOINT = os.environ.get("VCENTER_ENDPOINT", "https://10.0.80.21:443/sdk")
VCENTER_USERNAME = os.environ.get("VCENTER_USERNAME", "administrator@vsphere.local")
VCENTER_PASSWORD = os.environ.get("VCENTER_PASSWORD", "VMware1!")
K8S_KUBECONFIG_PATH = os.environ.get("K8S_KUBECONFIG_PATH", r"C:\Users\mirac\.kube\config")


def _vcenter_connection_input() -> dict[str, Any]:
    return {
        "endpoint": VCENTER_ENDPOINT,
        "username": VCENTER_USERNAME,
        "password": VCENTER_PASSWORD,
        "insecure": True,
    }


def _k8s_connection_input() -> dict[str, Any]:
    path = Path(K8S_KUBECONFIG_PATH)
    if not path.exists():
        raise RuntimeError(f"kubeconfig not found: {K8S_KUBECONFIG_PATH}")
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"invalid kubeconfig: {K8S_KUBECONFIG_PATH}")
    return {"kubeconfig": parsed}


async def _invoke_tool(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{TOOL_GATEWAY_URL}/api/v1/invoke/{tool_name}"
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(url, json={"input": payload, "dry_run": False})
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error") or f"invoke failed: {tool_name}")
    return body.get("data", {})


async def _evaluate_policy(context: dict[str, Any]) -> dict[str, Any]:
    url = f"{GOVERNANCE_SERVICE_URL}/policies/evaluate"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, json=context)
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error") or "policy evaluate failed")
    data = body.get("data", {})
    return {
        "allowed": bool(data.get("allowed", True)),
        "require_approval": bool(data.get("require_approval", False)),
        "reason": str(data.get("reason") or ""),
    }


def _risk_level(score: int) -> Literal["critical", "high", "medium", "low"]:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _approval_suggestion_from_policy(
    *,
    allowed: bool,
    require_approval: bool,
    risk_level: Literal["critical", "high", "medium", "low"],
) -> Literal["required", "recommended", "not_required"]:
    if not allowed:
        return "required"
    if require_approval:
        return "required"
    if risk_level in {"critical", "high"}:
        return "recommended"
    return "not_required"


def _tool_name_from_action(action: str) -> tuple[str, str]:
    txt = action.lower()
    if "host restart" in txt or "host reboot" in txt or "重启主机" in txt or "主机重启" in txt:
        return "vmware.host_restart", "dangerous"
    if "migrate" in txt or "迁移" in txt:
        return "vmware.vm_migrate", "write"
    if "power off" in txt or "关机" in txt:
        return "vmware.vm_power_off", "write"
    if "power on" in txt or "开机" in txt:
        return "vmware.vm_power_on", "write"
    if "snapshot" in txt or "快照" in txt:
        return "vmware.create_snapshot", "write"
    if "restart deployment" in txt or "重启部署" in txt:
        return "k8s.restart_deployment", "write"
    if "scale" in txt or "扩缩容" in txt:
        return "k8s.scale_deployment", "write"
    return "change_impact.analyze", "read"


def _severity_from_ratio(ratio: float) -> str:
    if ratio >= 0.75:
        return "high"
    if ratio >= 0.4:
        return "medium"
    return "low"


def _match_item(items: list[dict[str, Any]], target_id: str, keys: list[str]) -> dict[str, Any] | None:
    t = target_id.strip().lower()
    for item in items:
        for k in keys:
            v = str(item.get(k, "")).strip().lower()
            if t and v and (t == v or t in v):
                return item
    return None


def _build_tree(topology_nodes: list[dict[str, Any]], root_id: str, max_depth: int = 3, max_children: int = 20) -> list[DependencyNode]:
    by_parent: dict[str | None, list[dict[str, Any]]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for n in topology_nodes:
        nid = str(n.get("id", ""))
        pid = n.get("parent_id")
        by_id[nid] = n
        by_parent.setdefault(pid, []).append(n)

    def _expand(nid: str, depth: int) -> DependencyNode:
        node = by_id.get(nid, {"id": nid, "name": nid, "type": "unknown"})
        children: list[DependencyNode] = []
        if depth < max_depth:
            for c in by_parent.get(nid, [])[:max_children]:
                children.append(_expand(str(c.get("id")), depth + 1))
        return DependencyNode(
            id=str(node.get("id", nid)),
            name=str(node.get("name", nid)),
            type=str(node.get("type", "unknown")),
            children=children,
        )

    if root_id in by_id:
        return [_expand(root_id, 0)]

    roots = [n for n in topology_nodes if n.get("parent_id") is None][:5]
    return [
        _expand(str(r.get("id")), 0)
        for r in roots
    ]


async def _analyze_vmware(body: ChangeImpactRequest) -> tuple[list[ImpactedObject], list[DependencyNode], list[str], list[str], int]:
    inventory = await _invoke_tool(
        "vmware.get_vcenter_inventory",
        {"connection": _vcenter_connection_input()},
    )
    topology_data = await _invoke_tool(
        "vmware.query_topology",
        {"connection": _vcenter_connection_input()},
    )
    topology_nodes = topology_data.get("nodes", []) if isinstance(topology_data.get("nodes"), list) else []

    hosts = inventory.get("hosts", []) if isinstance(inventory.get("hosts"), list) else []
    vms = inventory.get("virtual_machines", []) if isinstance(inventory.get("virtual_machines"), list) else []
    clusters = inventory.get("clusters", []) if isinstance(inventory.get("clusters"), list) else []

    target = body.target_id.strip()
    target_type = body.target_type.lower()

    impacted: list[ImpactedObject] = []
    checks: list[str] = []
    rollback: list[str] = []
    graph: list[DependencyNode] = []
    base_score = 28

    if target_type in {"vm", "virtualmachine"}:
        vm = _match_item(vms, target, ["vm_id", "name"])
        if not vm:
            raise RuntimeError(f"未在 vCenter 中找到目标虚拟机: {target}")
        vm_id = str(vm.get("vm_id", target))
        vm_name = str(vm.get("name", target))
        impacted.append(
            ImpactedObject(
                object_type="VirtualMachine",
                object_id=vm_id,
                object_name=vm_name,
                impact_type="compute_state",
                severity="high",
            )
        )
        graph = _build_tree(topology_nodes, vm_id)
        checks = [
            "核对目标虚拟机当前业务窗口与依赖关系",
            "检查同宿主机关键 VM 资源占用",
            "确认备份/快照策略可回退",
        ]
        rollback = ["执行回退至原主机或回滚上次快照", "恢复变更前资源配额与调度策略"]
        base_score = 55
    elif target_type in {"host", "hostsystem"}:
        host = _match_item(hosts, target, ["host_id", "name"])
        if not host:
            raise RuntimeError(f"未在 vCenter 中找到目标主机: {target}")
        host_id = str(host.get("host_id", target))
        host_name = str(host.get("name", target))
        host_overall = str(host.get("overall_status", "unknown")).lower()
        impacted.append(
            ImpactedObject(
                object_type="HostSystem",
                object_id=host_id,
                object_name=host_name,
                impact_type="compute_capacity",
                severity="high" if host_overall not in {"green", "gray"} else "medium",
            )
        )
        vm_children = [n for n in topology_nodes if str(n.get("parent_id", "")) == host_id][:20]
        for vmn in vm_children:
            impacted.append(
                ImpactedObject(
                    object_type="VirtualMachine",
                    object_id=str(vmn.get("id", "")),
                    object_name=str(vmn.get("name", "")),
                    impact_type="placement",
                    severity="medium",
                )
            )
        graph = _build_tree(topology_nodes, host_id)
        checks = [
            "确认主机硬件健康与管理网络连通性",
            "评估主机承载 VM 的 SLA 与迁移窗口",
            "校验集群剩余容量是否满足故障转移",
        ]
        rollback = ["撤销本次主机变更并恢复原调度策略", "必要时将关键 VM 迁回原宿主机"]
        base_score = 62
    else:
        cluster = _match_item(clusters, target, ["cluster_id", "name"])
        if not cluster:
            raise RuntimeError(f"未在 vCenter 中找到目标集群: {target}")
        cluster_id = str(cluster.get("cluster_id", target))
        cluster_name = str(cluster.get("name", target))
        impacted.append(
            ImpactedObject(
                object_type="ClusterComputeResource",
                object_id=cluster_id,
                object_name=cluster_name,
                impact_type="cluster_policy",
                severity="high",
            )
        )
        host_children = [n for n in topology_nodes if str(n.get("parent_id", "")) == cluster_id][:20]
        for hn in host_children:
            impacted.append(
                ImpactedObject(
                    object_type="HostSystem",
                    object_id=str(hn.get("id", "")),
                    object_name=str(hn.get("name", "")),
                    impact_type="placement",
                    severity="medium",
                )
            )
        graph = _build_tree(topology_nodes, cluster_id)
        checks = [
            "确认 DRS/HA 策略与维护窗口一致",
            "校验集群内主机容量与故障域分布",
            "评估关键业务 VM 的迁移影响",
        ]
        rollback = ["恢复变更前集群策略配置", "按优先级回迁关键工作负载"]
        base_score = 58

    summary = inventory.get("summary", {}) if isinstance(inventory.get("summary"), dict) else {}
    unhealthy_ratio = 0.0
    host_count = int(summary.get("host_count") or 0)
    if host_count > 0:
        unhealthy_hosts = sum(1 for h in hosts if str(h.get("overall_status", "")).lower() not in {"green", "gray"})
        unhealthy_ratio = unhealthy_hosts / host_count
    risk_score = min(95, base_score + int(len(impacted) * 1.5) + int(unhealthy_ratio * 20))
    return impacted[:40], graph[:20], checks, rollback, risk_score


async def _analyze_k8s(body: ChangeImpactRequest) -> tuple[list[ImpactedObject], list[DependencyNode], list[str], list[str], int]:
    status = await _invoke_tool(
        "k8s.get_workload_status",
        {"connection": _k8s_connection_input()},
    )
    deployments = status.get("deployments", []) if isinstance(status.get("deployments"), list) else []
    pods = status.get("pods", []) if isinstance(status.get("pods"), list) else []
    nodes = status.get("nodes", []) if isinstance(status.get("nodes"), list) else []
    summary = status.get("summary", {}) if isinstance(status.get("summary"), dict) else {}

    target_id = body.target_id.strip()
    target_norm = target_id.lower()
    m = re.match(r"^(?P<ns>[^/]+)/(?P<name>.+)$", target_id)
    ns = m.group("ns") if m else None
    name = m.group("name") if m else target_id

    dep = None
    for d in deployments:
        dep_name = str(d.get("name", ""))
        dep_ns = str(d.get("namespace", ""))
        if ns:
            if dep_name == name and dep_ns == ns:
                dep = d
                break
        elif target_norm in f"{dep_ns}/{dep_name}".lower() or target_norm == dep_name.lower():
            dep = d
            break
    if not dep:
        raise RuntimeError(f"未在 Kubernetes 中找到目标工作负载: {target_id}")

    dep_name = str(dep.get("name", name))
    dep_ns = str(dep.get("namespace", ns or "default"))
    dep_ref = f"{dep_ns}/{dep_name}"
    impacted: list[ImpactedObject] = [
        ImpactedObject(
            object_type="Deployment",
            object_id=dep_ref,
            object_name=dep_ref,
            impact_type="availability",
            severity="high" if int(dep.get("replicas_available") or 0) < int(dep.get("replicas_desired") or 0) else "medium",
        )
    ]

    pod_children = []
    for p in pods:
        p_ns = str(p.get("namespace", ""))
        p_name = str(p.get("pod_name", ""))
        if p_ns == dep_ns and p_name.startswith(dep_name):
            pod_children.append(p)
            impacted.append(
                ImpactedObject(
                    object_type="Pod",
                    object_id=f"{p_ns}/{p_name}",
                    object_name=p_name,
                    impact_type="runtime",
                    severity="high" if int(p.get("restart_count") or 0) > 3 else "low",
                )
            )

    graph = [
        DependencyNode(
            id=dep_ref,
            name=dep_name,
            type="deployment",
            children=[
                DependencyNode(
                    id=f"{dep_ns}/{str(p.get('pod_name', ''))}",
                    name=str(p.get("pod_name", "")),
                    type="pod",
                    children=[],
                )
                for p in pod_children[:30]
            ],
        )
    ]

    checks = [
        "确认部署副本与 HPA 策略一致",
        "检查近期 Pod 重启与探针失败原因",
        "核对节点资源余量与调度限制",
    ]
    rollback = ["回滚 Deployment 到上一个稳定版本", "恢复变更前副本数并观察 10 分钟"]

    node_count = int(summary.get("node_count") or 0)
    not_ready_count = sum(1 for n in nodes if not bool(n.get("ready", True)))
    risk_score = min(95, 46 + len(pod_children) + int((not_ready_count / node_count) * 25) if node_count else 55)
    return impacted[:40], graph, checks, rollback, risk_score


@app.get("/health")
async def health() -> dict:
    return make_success(
        {
            "status": "healthy",
            "tool_gateway_url": TOOL_GATEWAY_URL,
            "governance_service_url": GOVERNANCE_SERVICE_URL,
            "vcenter_endpoint": VCENTER_ENDPOINT,
            "kubeconfig_path": K8S_KUBECONFIG_PATH,
        }
    )


@app.post("/api/v1/change-impact/analyze")
async def analyze_change_impact(body: ChangeImpactRequest) -> dict:
    try:
        ttype = body.target_type.lower()
        action_lower = body.requested_action.lower()
        is_k8s = ttype in {"deployment", "pod", "namespace", "k8s", "kubernetes"} or "k8s" in action_lower
        if is_k8s:
            impacted, graph, checks, rollback, risk_score = await _analyze_k8s(body)
        else:
            impacted, graph, checks, rollback, risk_score = await _analyze_vmware(body)

        tool_name, action_type = _tool_name_from_action(body.requested_action)
        risk_level = _risk_level(risk_score)
        policy = await _evaluate_policy(
            {
                "tool_name": tool_name,
                "action_type": action_type,
                "risk_level": risk_level,
                "risk_score": risk_score,
                "environment": body.environment,
                "approved": False,
                "requester": "change-impact-service",
            }
        )
        approval_suggestion = _approval_suggestion_from_policy(
            allowed=policy["allowed"],
            require_approval=policy["require_approval"],
            risk_level=risk_level,
        )
        if not policy["allowed"]:
            checks = [f"策略门禁：{policy['reason']}"] + checks

        result = ChangeImpactResult(
            analysis_id=f"cia-{uuid.uuid4().hex[:12]}",
            target={
                "target_type": body.target_type,
                "target_id": body.target_id,
                "environment": body.environment,
            },
            action=body.requested_action,
            risk_score=risk_score,
            risk_level=risk_level,
            impacted_objects=impacted,
            checks_required=checks,
            rollback_plan=rollback,
            approval_suggestion=approval_suggestion,
            dependency_graph=graph,
        )
        return make_success(result.model_dump())
    except Exception as exc:  # noqa: BLE001
        return make_error(str(exc))
