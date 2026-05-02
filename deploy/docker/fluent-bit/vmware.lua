local vcenter_components = {
  ["vpxd"] = true,
  ["vpxd-alert"] = true,
  ["sps"] = true,
  ["eam"] = true,
  ["vapi"] = true,
  ["vpostgres"] = true,
  ["vmdird"] = true
}

local known_components = {
  "vpxd%-alert", "vmkernel", "vmksummary", "hostd", "vpxa", "vobd",
  "fdm", "vpxd", "sps", "eam", "vapi", "vpostgres", "vmdird"
}

local function first_non_empty(...)
  for i = 1, select("#", ...) do
    local value = select(i, ...)
    if value ~= nil and tostring(value) ~= "" and tostring(value) ~= "-" then
      return tostring(value)
    end
  end
  return nil
end

local function infer_component(record, raw)
  local ident = first_non_empty(record["ident"], record["appname"], record["program"])
  if ident then
    ident = ident:match("([^/%s]+)$") or ident
    ident = ident:gsub("%.log$", "")
    return ident
  end
  for _, pattern in ipairs(known_components) do
    local found = raw:match("(" .. pattern .. ")")
    if found then
      return found:gsub("%%%-", "-")
    end
  end
  return "vmware"
end

local function infer_severity(record, raw)
  local existing = first_non_empty(record["severity"], record["level"])
  if existing then
    return string.lower(existing)
  end
  local lower = string.lower(raw or "")
  if lower:find("error") or lower:find("failed") or lower:find("panic") then
    return "error"
  end
  if lower:find("warn") or lower:find("apd") or lower:find("pdl") or lower:find("timeout") then
    return "warning"
  end
  return "info"
end

function normalize_vmware(tag, timestamp, record)
  local raw = first_non_empty(record["raw_message"], record["syslog_message"], record["message"], record["log"]) or ""
  local hostname = first_non_empty(
    record["hostname"],
    record["hostname5424"],
    record["hostname3164"],
    record["host"],
    record["source_host"],
    record["source"]
  ) or "unknown"
  local component = infer_component(record, raw)
  local product = vcenter_components[component] and "vcenter" or "esxi"

  record["@timestamp"] = os.date("!%Y-%m-%dT%H:%M:%SZ", timestamp)
  record["collector_received_time"] = os.date("!%Y-%m-%dT%H:%M:%SZ")
  record["raw_message"] = raw
  record["message"] = raw
  record["source_type"] = "vmware"
  record["product"] = product
  record["component"] = component
  record["severity"] = infer_severity(record, raw)
  record["hostname"] = hostname
  record["source_host"] = hostname
  record["source"] = hostname
  record["index_prefix"] = product == "vcenter" and "opspilot-vmware-vcenter-logs" or "opspilot-vmware-esxi-logs"

  local vm_moid = raw:match("(vm%-%d+)")
  if vm_moid then
    record["object_moid"] = vm_moid
    record["vm_moid"] = vm_moid
  end

  local datastore = raw:match("[Dd]atastore[%s=:]+([%w%._%-]+)")
  if datastore then
    record["datastore"] = datastore
    record["datastore_name"] = datastore
  end

  local task_id = raw:match("(task%-%d+)")
  if task_id then
    record["task_id"] = task_id
  end

  local event_type = raw:match("([%w]+Event)")
  if event_type then
    record["event_type"] = event_type
  end

  return 1, timestamp, record
end
