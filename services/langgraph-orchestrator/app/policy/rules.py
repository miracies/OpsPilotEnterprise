from __future__ import annotations

import json
from datetime import datetime, timezone

from opspilot_schema.policy_rule import (
    RiskEvaluationInput,
    RiskPolicyDecision,
    RiskPolicyMatcher,
    RiskPolicyRule,
)


def _rule(code: str, priority: int, *, matcher: dict, decision: dict, remark: str) -> RiskPolicyRule:
    return RiskPolicyRule(
        rule_code=code,
        enabled=True,
        priority=priority,
        matcher=RiskPolicyMatcher(**matcher),
        decision=RiskPolicyDecision(**decision),
        remark=remark,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def default_rules() -> list[RiskPolicyRule]:
    return [
        _rule(
            "L4_DESTRUCTIVE_SHELL",
            10,
            matcher={"command_regex": [r"rm\s+-rf", r"drop\s+database", r"delete\s+pvc", r"mkfs\."]},
            decision={"risk_level": "L4", "deny": True, "require_change_ticket": True},
            remark="破坏性 shell 模式，默认拒绝，需要工单。",
        ),
        _rule(
            "L4_K8S_DESTRUCTIVE",
            11,
            matcher={"domain": ["k8s"], "action": ["drain_node", "delete_namespace", "delete_pvc", "delete_deployment"]},
            decision={"risk_level": "L4", "deny": True, "require_change_ticket": True},
            remark="K8s 破坏性动作默认拒绝。",
        ),
        _rule(
            "L4_VMWARE_DESTRUCTIVE",
            12,
            matcher={"domain": ["vmware"], "action": ["destroy_vm", "delete_vm", "delete_datastore"]},
            decision={"risk_level": "L4", "deny": True, "require_change_ticket": True},
            remark="VMware 破坏性动作默认拒绝。",
        ),
        _rule(
            "L3_PROD_BATCH_WRITE",
            20,
            matcher={"environment": ["prod"], "resource_scope": ["multiple", "cluster", "global"]},
            decision={"risk_level": "L3", "require_approval": True, "require_rollback_plan": True, "allow_scopes": ["once"]},
            remark="生产批量或集群级变更必须审批并附回滚方案。",
        ),
        _rule(
            "L2_PROD_VMWARE_RESTART",
            30,
            matcher={"domain": ["vmware"], "action": ["vm_power", "restart_vm", "vm_guest_restart", "scale_cluster"], "environment": ["prod"], "resource_scope": ["single"]},
            decision={"risk_level": "L2", "require_approval": True, "require_rollback_plan": True, "allow_scopes": ["once", "session"]},
            remark="生产单对象 VMware 变更需要审批。",
        ),
        _rule(
            "L2_PROD_K8S_ROLLOUT",
            31,
            matcher={"domain": ["k8s"], "action": ["scale_deployment", "rollout_restart", "scale_statefulset"], "environment": ["prod"]},
            decision={"risk_level": "L2", "require_approval": True, "require_rollback_plan": True, "allow_scopes": ["once", "session"]},
            remark="生产 K8s 扩缩容和重启需要审批。",
        ),
        _rule(
            "L2_PROD_HOST_SERVICE",
            32,
            matcher={"domain": ["host"], "action": ["service_restart", "service_reload"], "environment": ["prod"]},
            decision={"risk_level": "L2", "require_approval": True, "allow_scopes": ["once", "session"]},
            remark="生产主机服务重启需要审批。",
        ),
        _rule(
            "L1_NONPROD_WRITE",
            50,
            matcher={"environment": ["dev", "test", "staging"]},
            decision={"risk_level": "L1", "require_approval": False, "allow_scopes": ["once", "session"]},
            remark="非生产写操作默认低风险，但仍记录审计。",
        ),
        _rule(
            "L0_KNOWLEDGE",
            80,
            matcher={"domain": ["knowledge"]},
            decision={"risk_level": "L0", "allow_scopes": ["once"]},
            remark="知识问答为只读操作。",
        ),
        _rule(
            "L0_VMWARE_READ",
            81,
            matcher={"domain": ["vmware"], "action": ["vm_status", "host_diagnose", "get_vcenter_inventory", "get_host_detail", "query_events", "query_metrics", "query_alerts", "query_topology"]},
            decision={"risk_level": "L0", "allow_scopes": ["once"]},
            remark="VMware 只读查询可直接执行。",
        ),
        _rule(
            "L0_K8S_READ",
            82,
            matcher={"domain": ["k8s"], "action": ["get_pod_status", "get_logs", "get_workload_status", "get_node_status", "get_events"]},
            decision={"risk_level": "L0", "allow_scopes": ["once"]},
            remark="K8s 只读查询可直接执行。",
        ),
        _rule(
            "L0_HOST_CHECK",
            83,
            matcher={"domain": ["host"], "action": ["check_disk", "tail_log", "service_status", "ping", "host_diagnose"]},
            decision={"risk_level": "L0", "allow_scopes": ["once"]},
            remark="主机只读检查可直接执行。",
        ),
    ]


def load_rules_from_db() -> list[RiskPolicyRule]:
    from app.storage.db import query_all

    try:
        rows = query_all("SELECT * FROM op_policy_rules WHERE enabled=1 ORDER BY priority_no ASC")
    except Exception:
        return default_rules()
    if not rows:
        return default_rules()
    result: list[RiskPolicyRule] = []
    for row in rows:
        try:
            matcher = RiskPolicyMatcher(**json.loads(row["matcher_json"] or "{}"))
            decision = RiskPolicyDecision(**json.loads(row["decision_json"] or "{}"))
            result.append(
                RiskPolicyRule(
                    rule_code=row["rule_code"],
                    enabled=bool(row["enabled"]),
                    priority=int(row["priority_no"] or 100),
                    matcher=matcher,
                    decision=decision,
                    remark=row.get("remark"),
                    updated_at=row.get("updated_at"),
                )
            )
        except Exception:
            continue
    return result


def save_rules(rules: list[RiskPolicyRule]) -> None:
    from app.storage.db import execute

    execute("DELETE FROM op_policy_rules")
    now = datetime.now(timezone.utc).isoformat()
    for rule in rules:
        execute(
            """
            INSERT INTO op_policy_rules(rule_code, enabled, priority_no, matcher_json, decision_json, remark, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule.rule_code,
                1 if rule.enabled else 0,
                rule.priority,
                json.dumps(rule.matcher.model_dump(), ensure_ascii=False),
                json.dumps(rule.decision.model_dump(), ensure_ascii=False),
                rule.remark,
                now,
            ),
        )
