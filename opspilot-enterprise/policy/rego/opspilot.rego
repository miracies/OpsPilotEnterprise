package opspilot

import rego.v1

# Default deny
default allow := false

# Allow all read operations
allow if {
    input.action_type == "read"
}

# Allow write operations for non-dangerous risk levels
allow if {
    input.action_type == "write"
    input.risk_level in ["low", "medium"]
}

# Dangerous operations require approval
approval_required if {
    input.action_type == "dangerous"
}

approval_required if {
    input.action_type == "write"
    input.risk_level in ["high", "critical"]
}

approval_required if {
    input.environment == "prod"
    input.action_type == "write"
}

# Deny power-off in production without approval
deny_reason := "生产环境禁止直接 power off" if {
    input.environment == "prod"
    input.tool_name == "vmware.vm_power_off"
    not input.approved
}

# Same person cannot initiate and approve
deny_reason := "同一人不可同时发起和审批高风险动作" if {
    input.requester == input.approver
    input.risk_level == "high"
}
