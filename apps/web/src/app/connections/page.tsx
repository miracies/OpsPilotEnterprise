"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  Loader2,
  Plug,
  Plus,
  Power,
  PowerOff,
  RefreshCcw,
  Search,
  Server,
  Trash2,
  XCircle,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MetricCard } from "@/components/ui/metric-card";
import { apiFetch } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import type {
  ConnectionAuditRecord,
  ConnectionProfile,
  ConnectivityTestResult,
  KeyRotationRecord,
  LogSourceConfig,
} from "@opspilot/shared-types";

type TabId = "connections" | "logs" | "audits" | "rotations" | "retention";

const TYPE_LABELS: Record<string, string> = {
  vcenter: "vCenter",
  kubeconfig: "Kubernetes",
  network_device: "网络设备",
  storage_array: "存储阵列",
  milvus: "Milvus",
  elasticsearch: "Elasticsearch",
  opa: "OPA",
  n8n: "n8n",
  rag_index: "RAG 索引",
  llm: "大模型",
  itsm: "ITSM",
  notification: "通知渠道",
};

const STATUS_LABELS: Record<string, string> = {
  active: "正常",
  inactive: "未启用",
  error: "异常",
  testing: "测试中",
};

export default function ConnectionCenterPage() {
  const [tab, setTab] = useState<TabId>("connections");
  const [connections, setConnections] = useState<ConnectionProfile[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [audits, setAudits] = useState<ConnectionAuditRecord[]>([]);
  const [rotations, setRotations] = useState<KeyRotationRecord[]>([]);
  const [retention, setRetention] = useState<Record<string, number>>({});
  const [logSources, setLogSources] = useState<LogSourceConfig[]>([]);
  const [selected, setSelected] = useState<ConnectionProfile | null>(null);
  const [testResult, setTestResult] = useState<ConnectivityTestResult | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [status, setStatus] = useState("");
  const [logForm, setLogForm] = useState({
    name: "VMware OpenSearch",
    backend_type: "opensearch",
    endpoint: "",
    auth_type: "none",
    username: "",
    password: "",
    token: "",
    index_pattern: "opspilot-vmware-*",
    web_url: "",
    tls_verify: true,
    enabled: true,
  });

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [connRes, statRes, auditRes, rotationRes, retentionRes, logRes] = await Promise.all([
        apiFetch<{ data: ConnectionProfile[] }>("/api/v1/connections"),
        apiFetch<{ data: Record<string, number> }>("/api/v1/connections/stats"),
        apiFetch<{ data: ConnectionAuditRecord[] }>("/api/v1/connections/audits"),
        apiFetch<{ data: KeyRotationRecord[] }>("/api/v1/connections/rotations"),
        apiFetch<{ data: Record<string, number> }>("/api/v1/connections/retention"),
        apiFetch<{ data: { items: LogSourceConfig[] } }>("/api/v1/logs/sources").catch(() => ({ data: { items: [] } })),
      ]);
      setConnections(connRes.data ?? []);
      setStats(statRes.data ?? {});
      setAudits(auditRes.data ?? []);
      setRotations(rotationRes.data ?? []);
      setRetention(retentionRes.data ?? {});
      setLogSources(logRes.data?.items ?? []);
      setSelected((current) => current ?? (connRes.data ?? [])[0] ?? null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return connections;
    return connections.filter((item) =>
      [item.name, item.display_name, item.endpoint, item.type].some((value) => String(value ?? "").toLowerCase().includes(term))
    );
  }, [connections, query]);

  async function handleToggle(conn: ConnectionProfile) {
    await apiFetch(`/api/v1/connections/${conn.id}/toggle`, {
      method: "PATCH",
      body: JSON.stringify({ enabled: !conn.enabled }),
    });
    await fetchAll();
  }

  async function handleDelete(conn: ConnectionProfile) {
    await apiFetch(`/api/v1/connections/${conn.id}`, { method: "DELETE" });
    setSelected(null);
    await fetchAll();
  }

  async function handleTest(conn: ConnectionProfile) {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiFetch<{ data: ConnectivityTestResult }>(`/api/v1/connections/${conn.id}/test`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setTestResult(res.data ?? null);
      await fetchAll();
    } finally {
      setTesting(false);
    }
  }

  async function reloadLogSources() {
    const res = await apiFetch<{ data: { items: LogSourceConfig[] } }>("/api/v1/logs/sources");
    setLogSources(res.data?.items ?? []);
  }

  async function saveLogSource() {
    setStatus("Saving log source...");
    const res = await apiFetch<{ success: boolean; error?: string }>("/api/v1/logs/sources", {
      method: "POST",
      body: JSON.stringify({
        ...logForm,
        password: logForm.password || null,
        token: logForm.token || null,
        username: logForm.username || null,
        web_url: logForm.web_url || null,
      }),
    });
    setStatus(res.success ? "Log source saved" : res.error || "Save failed");
    await reloadLogSources();
  }

  async function testLogSource(source: LogSourceConfig) {
    setStatus(`Testing ${source.name}...`);
    const res = await apiFetch<{ success: boolean; error?: string }>("/api/v1/logs/sources/test", {
      method: "POST",
      body: JSON.stringify({ source_id: source.id }),
    });
    setStatus(res.success ? `${source.name} connection ok` : res.error || `${source.name} connection failed`);
  }

  async function deleteLogSource(sourceId: string) {
    await apiFetch(`/api/v1/logs/sources/${sourceId}`, { method: "DELETE" });
    await reloadLogSources();
  }

  async function saveRetention() {
    await apiFetch("/api/v1/connections/retention", { method: "PUT", body: JSON.stringify(retention) });
    setStatus("Retention policy saved");
  }

  const tabs: Array<{ id: TabId; label: string; count?: number }> = [
    { id: "connections", label: "连接列表", count: connections.length },
    { id: "logs", label: "日志平台", count: logSources.length },
    { id: "audits", label: "连接审计", count: audits.length },
    { id: "rotations", label: "密钥轮换", count: rotations.length },
    { id: "retention", label: "保留策略" },
  ];

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="资源连接中心"
        description="统一管理外部资源连接、日志平台连接、连通性测试和审计记录。"
        actions={
          <Button variant="secondary" size="sm" onClick={() => void fetchAll()}>
            <RefreshCcw className="h-3.5 w-3.5" /> 刷新
          </Button>
        }
      />

      <div className="grid grid-cols-4 gap-3">
        <MetricCard title="连接总数" value={stats.total ?? connections.length} icon={Plug} accent="blue" />
        <MetricCard title="正常" value={stats.active ?? 0} icon={CheckCircle2} accent="green" />
        <MetricCard title="异常" value={stats.error ?? 0} icon={AlertTriangle} accent="red" />
        <MetricCard title="日志源" value={logSources.length} icon={Database} accent="amber" />
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {tabs.map((item) => (
          <button
            key={item.id}
            onClick={() => setTab(item.id)}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
              tab === item.id ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-700"
            )}
          >
            {item.label}
            {item.count !== undefined && <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">{item.count}</span>}
          </button>
        ))}
      </div>

      {status && <div className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600">{status}</div>}

      {tab === "connections" && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <Card>
            <CardHeader>
              <CardTitle>连接列表</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                <input className="form-input pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索连接名称、类型或端点" />
              </div>
              <div className="space-y-2">
                {filtered.map((conn) => (
                  <button
                    key={conn.id}
                    onClick={() => setSelected(conn)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg border p-3 text-left transition",
                      selected?.id === conn.id ? "border-blue-300 bg-blue-50/40" : "border-slate-200 bg-white hover:border-blue-200"
                    )}
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100">
                      {conn.type === "vcenter" ? <Server className="h-5 w-5 text-blue-600" /> : <Plug className="h-5 w-5 text-slate-500" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-semibold text-slate-900">{conn.display_name}</p>
                        <Badge variant="neutral">{TYPE_LABELS[conn.type] ?? conn.type}</Badge>
                      </div>
                      <p className="truncate font-mono text-xs text-slate-500">{conn.endpoint}</p>
                    </div>
                    <StatusBadge status={conn.status} />
                  </button>
                ))}
                {filtered.length === 0 && <div className="rounded-lg border border-dashed border-slate-200 p-8 text-center text-sm text-slate-500">无匹配连接</div>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>连接详情</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {!selected ? (
                <div className="text-sm text-slate-500">选择一个连接查看详情。</div>
              ) : (
                <>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{selected.display_name}</p>
                    <p className="font-mono text-xs text-slate-500">{selected.name}</p>
                  </div>
                  <InfoRow label="类型" value={TYPE_LABELS[selected.type] ?? selected.type} />
                  <InfoRow label="端点" value={selected.endpoint} />
                  <InfoRow label="凭据" value={selected.credential_ref || "-"} />
                  <InfoRow label="更新" value={formatDate(selected.updated_at)} />
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" onClick={() => void handleTest(selected)} disabled={testing}>
                      {testing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Activity className="h-3.5 w-3.5" />} 测试
                    </Button>
                    <Button variant="secondary" size="sm" onClick={() => void handleToggle(selected)}>
                      {selected.enabled ? <PowerOff className="h-3.5 w-3.5" /> : <Power className="h-3.5 w-3.5" />} {selected.enabled ? "停用" : "启用"}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void handleDelete(selected)}>
                      <Trash2 className="h-3.5 w-3.5" /> 删除
                    </Button>
                  </div>
                  {testResult && (
                    <div className={cn("rounded-lg p-3 text-sm", testResult.success ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800")}>
                      <div className="flex items-center gap-2 font-semibold">
                        {testResult.success ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                        {testResult.success ? "连接正常" : "连接异常"} · {testResult.latency_ms}ms
                      </div>
                      <div className="mt-2 space-y-1">
                        {testResult.checks.map((check) => (
                          <div key={check.name} className="text-xs">{check.name}: {check.message}</div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "logs" && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
          <Card>
            <CardHeader>
              <CardTitle>日志平台连接</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {logSources.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                  尚未配置日志平台。配置 OpenSearch 后，RCA 可以检索 vCenter / ESXi 原始日志并生成证据链接。
                </div>
              ) : (
                logSources.map((source) => (
                  <div key={source.id} className="rounded-lg border border-slate-200 bg-white p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold text-slate-900">{source.name}</p>
                          <Badge variant={source.enabled ? "success" : "neutral"}>{source.backend_type}</Badge>
                          {source.has_secret && <Badge variant="info">secret</Badge>}
                        </div>
                        <p className="mt-1 truncate font-mono text-xs text-slate-500">{source.endpoint}</p>
                        <p className="mt-1 text-xs text-slate-500">Index: {source.index_pattern}</p>
                        {source.web_url && <p className="mt-1 truncate text-xs text-blue-600">UI: {source.web_url}</p>}
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <Button variant="secondary" size="xs" onClick={() => void testLogSource(source)}>测试</Button>
                        <Button variant="ghost" size="xs" onClick={() => void deleteLogSource(source.id)}>删除</Button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>新增 OpenSearch</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Field label="名称"><input className="form-input" value={logForm.name} onChange={(event) => setLogForm((prev) => ({ ...prev, name: event.target.value }))} /></Field>
              <Field label="Endpoint"><input className="form-input" value={logForm.endpoint} onChange={(event) => setLogForm((prev) => ({ ...prev, endpoint: event.target.value }))} placeholder="https://opensearch.example.com:9200" /></Field>
              <Field label="Dashboards URL"><input className="form-input" value={logForm.web_url} onChange={(event) => setLogForm((prev) => ({ ...prev, web_url: event.target.value }))} /></Field>
              <Field label="Index Pattern"><input className="form-input" value={logForm.index_pattern} onChange={(event) => setLogForm((prev) => ({ ...prev, index_pattern: event.target.value }))} /></Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="认证方式">
                  <select className="form-input" value={logForm.auth_type} onChange={(event) => setLogForm((prev) => ({ ...prev, auth_type: event.target.value }))}>
                    <option value="none">none</option>
                    <option value="basic">basic</option>
                    <option value="token">token</option>
                  </select>
                </Field>
                <Field label="用户名"><input className="form-input" value={logForm.username} onChange={(event) => setLogForm((prev) => ({ ...prev, username: event.target.value }))} /></Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="密码"><input className="form-input" type="password" value={logForm.password} onChange={(event) => setLogForm((prev) => ({ ...prev, password: event.target.value }))} /></Field>
                <Field label="Token"><input className="form-input" type="password" value={logForm.token} onChange={(event) => setLogForm((prev) => ({ ...prev, token: event.target.value }))} /></Field>
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-600">
                <input type="checkbox" checked={logForm.tls_verify} onChange={(event) => setLogForm((prev) => ({ ...prev, tls_verify: event.target.checked }))} />
                校验 TLS 证书
              </label>
              <Button variant="primary" size="sm" onClick={() => void saveLogSource()} disabled={!logForm.name || !logForm.endpoint}>
                <Plus className="h-3.5 w-3.5" /> 保存日志平台
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "audits" && (
        <SimpleTable
          title="连接审计"
          empty="暂无审计记录"
          rows={audits.map((item) => [item.connection_id, item.action, item.actor, item.detail, formatDate(item.timestamp)])}
        />
      )}

      {tab === "rotations" && (
        <SimpleTable
          title="密钥轮换"
          empty="暂无轮换记录"
          rows={rotations.map((item) => [item.connection_id, item.rotated_by, item.status, item.note ?? "-", formatDate(item.rotated_at)])}
        />
      )}

      {tab === "retention" && (
        <Card>
          <CardHeader>
            <CardTitle>保留策略</CardTitle>
          </CardHeader>
          <CardContent className="max-w-lg space-y-4">
            <RetentionField label="审计记录保留天数" value={retention.audit_retention_days ?? 365} onChange={(value) => setRetention((prev) => ({ ...prev, audit_retention_days: value }))} />
            <RetentionField label="连通性测试历史保留天数" value={retention.connection_test_history_days ?? 90} onChange={(value) => setRetention((prev) => ({ ...prev, connection_test_history_days: value }))} />
            <RetentionField label="密钥轮换记录保留天数" value={retention.key_rotation_history_days ?? 730} onChange={(value) => setRetention((prev) => ({ ...prev, key_rotation_history_days: value }))} />
            <Button variant="primary" size="sm" onClick={() => void saveRetention()}>保存</Button>
          </CardContent>
        </Card>
      )}

      <style>{`
        .form-input { display:block; width:100%; height:34px; padding:0 10px; border:1px solid #e2e8f0; border-radius:8px; font-size:13px; color:#1e293b; background:#fff; outline:none; }
        .form-input:focus { border-color:#3b82f6; box-shadow:0 0 0 3px rgba(59,130,246,.15); }
      `}</style>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone = status === "active" ? "success" : status === "error" ? "danger" : "neutral";
  return <Badge variant={tone}>{STATUS_LABELS[status] ?? status}</Badge>;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2">
      <p className="mb-0.5 text-[10px] text-slate-400">{label}</p>
      <p className="break-all text-xs font-medium text-slate-700">{value}</p>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-700">{label}</span>
      {children}
    </label>
  );
}

function RetentionField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-700">{label}</span>
      <input className="form-input w-40" type="number" min={1} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function SimpleTable({ title, rows, empty }: { title: string; rows: string[][]; empty: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-slate-500">{empty}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-slate-100">
                {rows.map((row, index) => (
                  <tr key={index}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} className="px-3 py-2 text-xs text-slate-600">{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
