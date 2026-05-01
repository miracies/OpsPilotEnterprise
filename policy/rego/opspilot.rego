package opspilot

import rego.v1

# Decision outputs
default allow := false
default approval_required := false
default deny_reason := ""

is_read if input.action_type == "read"
is_write if input.action_type in ["write", "dangerous"]
is_high_risk if input.risk_level in ["high", "critical"]
is_high_risk if to_number(input.risk_score) >= 70

# Approval gates
approval_required if {
	is_write
	is_high_risk
}

approval_required if {
	is_write
	lower(input.environment) == "prod"
}

# Explicit deny reasons as a set (avoid conflicting complete rules)
deny_reasons contains "Prod direct power-off is blocked" if {
	lower(input.environment) == "prod"
	input.tool_name == "vmware.vm_power_off"
	not input.approved
}

deny_reasons contains "Same person cannot request and approve high-risk action" if {
	is_high_risk
	input.requester != ""
	input.approver != ""
	input.requester == input.approver
}

deny_reason := concat("; ", sort([r | r := deny_reasons[_]])) if {
	count(deny_reasons) > 0
}

# Allow reads unless explicitly denied
allow if {
	is_read
	deny_reason == ""
}

# Allow writes only when no approval is required and no deny reason
allow if {
	is_write
	not approval_required
	deny_reason == ""
}

# Allow writes requiring approval only after approved flag is true
allow if {
	is_write
	approval_required
	input.approved == true
	deny_reason == ""
}
