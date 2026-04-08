"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Server, Box, Network, Database, BookOpen, Link2, Shield, Cpu,
  Plug, Search, Plus, RotateCcw, CheckCircle2, XCircle, Loader2,
  Power, PowerOff, Activity, Clock, X, ChevronRight, AlertTriangle,
  FileText, KeyRound, History, Eye, Zap, Settings2, Bell, Workflow,
  Pencil, Trash2,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MetricCard } from "@/components/ui/metric-card";
import { cn, formatDate } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import type {
  ConnectionProfile, ConnectivityTestResult, KeyRotationRecord, ConnectionAuditRecord,
} from "@opspilot/shared-types";

// ── Constants ──────────────────────────────────────────────

const TYPE_ICONS: Record<string, typeof Server> = {
  vcenter: Server, kubeconfig: Box, network_device: Network, storage_array: Database,
  milvus: Database, elasticsearch: Database, opa: Shield, n8n: Workflow,
  rag_index: BookOpen, llm: Cpu, itsm: Link2, notification: Bell,
};

const TYPE_LABELS: Record<string, string> = {
  vcenter: "vCenter", kubeconfig: "Kubernetes", network_device: "网络设备",
  storage_array: "存储阵列", milvus: "Milvus", elasticsearch: "Elasticsearch",
  opa: "OPA", n8n: "n8n", rag_index: "RAG 索引", llm: "大模型",
  itsm: "ITSM", notification: "通知渠道",
};

const STATUS_CONFIG: Record<string, { bg: string; text: string; dot: string; label: string }> = {
  active:   { bg: "bg-emerald-50", text: "text-emerald-700", dot: "bg-emerald-500", label: "正常" },
  inactive: { bg: "bg-slate-100",  text: "text-slate-500",   dot: "bg-slate-400",   label: "未启用" },
  error:    { bg: "bg-red-50",     text: "text-red-700",     dot: "bg-red-500",     label: "异常" },
  testing:  { bg: "bg-blue-50",    text: "text-blue-700",    dot: "bg-blue-500",    label: "测试中" },
};

function StatusBadge({ status }: { status: string }) {
  const c = STATUS_CONFIG[status] ?? STATUS_CONFIG.inactive;
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-medium", c.bg, c.text)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", c.dot)} />
      {c.label}
    </span>
  );
}

type TabId = "connections" | "audits" | "rotations" | "retention";
type DetailTab = "info" | "test" | "tools" | "rotations" | "audits";

// ── Main Component ─────────────────────────────────────────

export default function ConnectionCenterPage() {
  const [tab, setTab] = useState<TabId>("connections");
  const [connections, setConnections] = useState<ConnectionProfile[]>([]);
  const [stats, setStats] = useState<Record<string, any>>({});
  const [audits, setAudits] = useState<ConnectionAuditRecord[]>([]);
  const [rotations, setRotations] = useState<KeyRotationRecord[]>([]);
  const [retention, setRetention] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  const [selected, setSelected] = useState<ConnectionProfile | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("info");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  const [testResult, setTestResult] = useState<ConnectivityTestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [connRotations, setConnRotations] = useState<KeyRotationRecord[]>([]);
  const [connAudits, setConnAudits] = useState<ConnectionAuditRecord[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", display_name: "", type: "vcenter", endpoint: "", scope: "", credential_ref: "", proxy_config: "", description: "", tags: "" });
  const [creating, setCreating] = useState(false);

  const [showEdit, setShowEdit] = useState(false);
  const [editForm, setEditForm] = useState({ display_name: "", endpoint: "", scope: "", credential_ref: "", proxy_config: "", description: "", tags: "" });
  const [saving, setSaving] = useState(false);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [testCreds, setTestCreds] = useState({ username: "", password: "" });

  const fetchAll = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch<{ data: ConnectionProfile[] }>("/api/v1/connections").then(r => setConnections(r.data ?? [])),
      apiFetch<{ data: Record<string, any> }>("/api/v1/connections/stats").then(r => setStats(r.data ?? {})),
      apiFetch<{ data: ConnectionAuditRecord[] }>("/api/v1/connections/audits").then(r => setAudits(r.data ?? [])),
      apiFetch<{ data: KeyRotationRecord[] }>("/api/v1/connections/rotations").then(r => setRotations(r.data ?? [])),
      apiFetch<{ data: Record<string, number> }>("/api/v1/connections/retention").then(r => setRetention(r.data ?? {})),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  async function handleToggle(connId: string, enabled: boolean) {
    await apiFetch(`/api/v1/connections/${connId}/toggle`, { method: "PATCH", body: JSON.stringify({ enabled }) });
    const res = await apiFetch<{ data: ConnectionProfile[] }>("/api/v1/connections");
    setConnections(res.data ?? []);
    if (selected?.id === connId) setSelected(res.data?.find(c => c.id === connId) ?? null);
  }

  async function handleTest(connId: string) {
    setTesting(true);
    setDetailTab("test");
    try {
      const body: Record<string, string> = {};
      if (testCreds.username) body.username = testCreds.username;
      if (testCreds.password) body.password = testCreds.password;
      const r = await apiFetch<{ data: ConnectivityTestResult }>(`/api/v1/connections/${connId}/test`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setTestResult(r.data ?? null);
      const res = await apiFetch<{ data: ConnectionProfile[] }>("/api/v1/connections");
      setConnections(res.data ?? []);
      if (selected?.id === connId) setSelected(res.data?.find(c => c.id === connId) ?? null);
    } finally { setTesting(false); }
  }

  async function loadDetailTab(conn: ConnectionProfile, dtab: DetailTab) {
    setDetailTab(dtab);
    if (dtab === "info" || dtab === "test" || dtab === "tools") return;
    setLoadingDetail(true);
    try {
      if (dtab === "rotations") {
        const r = await apiFetch<{ data: KeyRotationRecord[] }>(`/api/v1/connections/rotations?connection_id=${conn.id}`);
        setConnRotations(r.data ?? []);
      } else if (dtab === "audits") {
        const r = await apiFetch<{ data: ConnectionAuditRecord[] }>(`/api/v1/connections/audits?connection_id=${conn.id}`);
        setConnAudits(r.data ?? []);
      }
    } finally { setLoadingDetail(false); }
  }

  function selectConn(conn: ConnectionProfile) {
    setSelected(conn);
    setDetailTab("info");
    setTestResult(null);
    setConnRotations([]);
    setConnAudits([]);
    setTestCreds({ username: "", password: "" });
  }

  async function handleCreate() {
    setCreating(true);
    try {
      await apiFetch("/api/v1/connections", {
        method: "POST",
        body: JSON.stringify({ ...createForm, tags: createForm.tags.split(",").map(t => t.trim()).filter(Boolean) }),
      });
      setShowCreate(false);
      setCreateForm({ name: "", display_name: "", type: "vcenter", endpoint: "", scope: "", credential_ref: "", proxy_config: "", description: "", tags: "" });
      fetchAll();
    } finally { setCreating(false); }
  }

  async function handleRetentionSave() {
    await apiFetch("/api/v1/connections/retention", { method: "PUT", body: JSON.stringify(retention) });
  }

  function openEdit(conn: ConnectionProfile) {
    setEditForm({
      display_name: conn.display_name,
      endpoint: conn.endpoint,
      scope: conn.scope ?? "",
      credential_ref: conn.credential_ref,
      proxy_config: conn.proxy_config ?? "",
      description: conn.description ?? "",
      tags: conn.tags.join(", "),
    });
    setShowEdit(true);
  }

  async function handleEdit() {
    if (!selected) return;
    setSaving(true);
    try {
      await apiFetch(`/api/v1/connections/${selected.id}`, {
        method: "PUT",
        body: JSON.stringify({ ...editForm, tags: editForm.tags.split(",").map(t => t.trim()).filter(Boolean) }),
      });
      setShowEdit(false);
      const res = await apiFetch<{ data: ConnectionProfile[] }>("/api/v1/connections");
      setConnections(res.data ?? []);
      setSelected(res.data?.find(c => c.id === selected.id) ?? null);
    } finally { setSaving(false); }
  }

  async function handleDelete() {
    if (!selected) return;
    setDeleting(true);
    try {
      await apiFetch(`/api/v1/connections/${selected.id}`, { method: "DELETE" });
      setShowDeleteConfirm(false);
      setSelected(null);
      fetchAll();
    } finally { setDeleting(false); }
  }

  const filtered = connections.filter(c => {
    if (searchQuery && !c.name.includes(searchQuery) && !c.display_name.includes(searchQuery) && !c.endpoint.includes(searchQuery)) return false;
    if (filterType && c.type !== filterType) return false;
    if (filterStatus && c.status !== filterStatus) return false;
    return true;
  });

  const types = [...new Set(connections.map(c => c.type))];

  const TABS: { id: TabId; label: string; count?: number }[] = [
    { id: "connections", label: "连接列表", count: connections.length },
    { id: "audits", label: "连接审计", count: audits.length },
    { id: "rotations", label: "密钥轮换", count: rotations.length },
    { id: "retention", label: "保留策略" },
  ];

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;

  return (
    <div className="space-y-5">
      <PageHeader
        title="资源连接中心"
        description="统一管理平台所有外部资源连接、凭据、连通性和审计"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={fetchAll}><RotateCcw className="h-3.5 w-3.5" /> 刷新</Button>
            <Button variant="primary" size="sm" onClick={() => setShowCreate(true)}><Plus className="h-3.5 w-3.5" /> 新建连接</Button>
          </div>
        }
      />

      {/* Metric Cards */}
      <div className="grid grid-cols-4 gap-3">
        <MetricCard title="连接总数" value={stats.total ?? 0} icon={Plug} accent="blue" />
        <MetricCard title="正常" value={stats.active ?? 0} icon={CheckCircle2} accent="green" />
        <MetricCard title="异常" value={stats.error ?? 0} icon={AlertTriangle} accent="red" />
        <MetricCard title="未启用" value={stats.inactive ?? 0} icon={PowerOff} accent="amber" />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
            tab === t.id ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
          )}>
            {t.label}
            {t.count !== undefined && <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">{t.count}</span>}
          </button>
        ))}
      </div>

      {/* ── Connections Tab ─────────────── */}
      {tab === "connections" && (
        <div className="flex gap-4 h-[calc(100vh-18rem)]">
          {/* List */}
          <div className="flex-1 min-w-0 flex flex-col">
            <div className="flex items-center gap-2 mb-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                <input type="text" placeholder="搜索连接名称或端点..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                  className="h-8 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-[13px] focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
              </div>
              <select value={filterType} onChange={e => setFilterType(e.target.value)}
                className="h-8 rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20">
                <option value="">全部类型</option>
                {types.map(t => <option key={t} value={t}>{TYPE_LABELS[t] ?? t}</option>)}
              </select>
              <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
                className="h-8 rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20">
                <option value="">全部状态</option>
                <option value="active">正常</option>
                <option value="error">异常</option>
                <option value="inactive">未启用</option>
              </select>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2">
              {filtered.map(conn => {
                const TypeIcon = TYPE_ICONS[conn.type] ?? Plug;
                return (
                  <div
                    key={conn.id}
                    onClick={() => selectConn(conn)}
                    className={cn(
                      "flex items-center gap-3 rounded-xl border bg-white p-3 cursor-pointer transition-all",
                      selected?.id === conn.id ? "border-blue-300 ring-2 ring-blue-500/20 shadow-sm" : "border-slate-200 hover:border-blue-200 hover:shadow-sm"
                    )}
                  >
                    <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl shrink-0",
                      conn.status === "active" ? "bg-emerald-100" : conn.status === "error" ? "bg-red-100" : "bg-slate-100"
                    )}>
                      <TypeIcon className={cn("h-5 w-5",
                        conn.status === "active" ? "text-emerald-600" : conn.status === "error" ? "text-red-600" : "text-slate-400"
                      )} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-slate-900 truncate">{conn.display_name}</p>
                        <Badge variant="neutral" className="text-[9px] shrink-0">{TYPE_LABELS[conn.type] ?? conn.type}</Badge>
                      </div>
                      <p className="text-[11px] text-slate-400 font-mono truncate">{conn.endpoint}</p>
                    </div>
                    <div className="text-right shrink-0 space-y-0.5">
                      <StatusBadge status={conn.status} />
                      {conn.last_test_latency_ms != null && (
                        <p className="text-[10px] text-slate-400">{conn.last_test_latency_ms}ms</p>
                      )}
                    </div>
                  </div>
                );
              })}
              {filtered.length === 0 && (
                <div className="text-center py-12 text-sm text-slate-400">无匹配连接</div>
              )}
            </div>
          </div>

          {/* Detail */}
          <div className="w-[360px] shrink-0 overflow-y-auto space-y-3">
            {selected ? (
              <>
                {/* Detail Tabs */}
                <div className="flex gap-0.5 rounded-lg bg-slate-100 p-0.5">
                  {([
                    { id: "info" as DetailTab, icon: FileText, label: "基本" },
                    { id: "test" as DetailTab, icon: Activity, label: "测试" },
                    { id: "tools" as DetailTab, icon: Zap, label: "关联工具" },
                    { id: "rotations" as DetailTab, icon: KeyRound, label: "密钥轮换" },
                    { id: "audits" as DetailTab, icon: History, label: "审计" },
                  ]).map(s => (
                    <button key={s.id} onClick={() => loadDetailTab(selected, s.id)} className={cn(
                      "flex-1 flex items-center justify-center gap-1 rounded-md py-1.5 text-[10px] font-medium transition-colors",
                      detailTab === s.id ? "bg-white text-blue-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
                    )}>
                      <s.icon className="h-3 w-3" />{s.label}
                    </button>
                  ))}
                </div>

                {/* Info */}
                {detailTab === "info" && (
                  <Card>
                    <CardContent className="pt-4 space-y-3">
                      <div className="flex items-start justify-between">
                        <div>
                          <h3 className="text-sm font-semibold text-slate-900">{selected.display_name}</h3>
                          <p className="font-mono text-[11px] text-slate-400 mt-0.5">{selected.name}</p>
                        </div>
                        <StatusBadge status={selected.status} />
                      </div>
                      {selected.description && <p className="text-xs text-slate-600 leading-relaxed">{selected.description}</p>}
                      <div className="grid grid-cols-2 gap-2">
                        <InfoCell label="类型" value={TYPE_LABELS[selected.type] ?? selected.type} />
                        <InfoCell label="版本" value={selected.version ?? "—"} />
                      </div>
                      <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5 space-y-1.5">
                        <p className="text-[10px] text-slate-400 font-medium">Endpoint</p>
                        <p className="text-xs font-mono text-slate-700 break-all">{selected.endpoint}</p>
                      </div>
                      {selected.scope && (
                        <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5 space-y-1">
                          <p className="text-[10px] text-slate-400 font-medium">范围 (Scope)</p>
                          <p className="text-xs text-slate-700">{selected.scope}</p>
                        </div>
                      )}
                      <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5 space-y-1">
                        <p className="text-[10px] text-slate-400 font-medium">凭据引用</p>
                        <p className="text-xs font-mono text-blue-600 break-all">{selected.credential_ref || "—"}</p>
                      </div>
                      {selected.proxy_config && (
                        <div className="rounded-lg border border-amber-100 bg-amber-50/50 p-2.5 space-y-1">
                          <p className="text-[10px] text-amber-600 font-medium">跳板机配置</p>
                          <p className="text-xs font-mono text-slate-700">{selected.proxy_config}</p>
                        </div>
                      )}
                      <div className="flex flex-wrap gap-1">
                        {selected.tags.map(tag => <Badge key={tag} variant="neutral" className="text-[10px]">{tag}</Badge>)}
                      </div>
                      <div className="text-[11px] text-slate-400 space-y-0.5 pt-1 border-t border-slate-100">
                        <p>创建: {formatDate(selected.created_at)}</p>
                        <p>更新: {formatDate(selected.updated_at)}</p>
                        {selected.last_tested && <p>最近测试: {formatDate(selected.last_tested)} ({selected.last_test_result === "pass" ? "通过" : "失败"})</p>}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Test */}
                {detailTab === "test" && (
                  <Card>
                    <CardContent className="pt-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-semibold text-slate-700 flex items-center gap-1.5"><Activity className="h-3.5 w-3.5 text-slate-400" />连通性测试</p>
                        <Button variant="secondary" size="xs" onClick={() => handleTest(selected.id)} disabled={testing}>
                          {testing ? <Loader2 className="h-3 w-3 animate-spin" /> : <RotateCcw className="h-3 w-3" />} 测试
                        </Button>
                      </div>

                      {/* vCenter: real credential inputs */}
                      {selected.type === "vcenter" && (
                        <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-3 space-y-2">
                          <p className="text-[11px] font-medium text-blue-700 flex items-center gap-1"><Shield className="h-3 w-3" />vCenter 实时连通性测试</p>
                          <p className="text-[10px] text-blue-600/70">将对 {selected.endpoint} 进行真实的 DNS、TCP、TLS、REST API 检测。</p>

                          {selected.credential_ref?.startsWith("secret://") && (
                            <div className="rounded-md border border-emerald-200 bg-emerald-50/60 px-2.5 py-2 flex items-center gap-2">
                              <KeyRound className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                              <div className="flex-1 min-w-0">
                                <p className="text-[10px] text-emerald-700 font-medium">凭据自动获取</p>
                                <p className="text-[9px] text-emerald-600/70">不填凭据时将自动从密钥库 <code className="font-mono bg-emerald-100 px-0.5 rounded">{selected.credential_ref}</code> 获取</p>
                              </div>
                            </div>
                          )}

                          <p className="text-[10px] text-slate-500">手动输入凭据（优先级高于自动获取）：</p>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="text-[10px] text-slate-500 mb-0.5 block">用户名</label>
                              <input
                                className="form-input text-[12px] h-7"
                                placeholder="administrator@vsphere.local"
                                value={testCreds.username}
                                onChange={e => setTestCreds(p => ({ ...p, username: e.target.value }))}
                              />
                            </div>
                            <div>
                              <label className="text-[10px] text-slate-500 mb-0.5 block">密码</label>
                              <input
                                className="form-input text-[12px] h-7"
                                type="password"
                                placeholder="••••••••"
                                value={testCreds.password}
                                onChange={e => setTestCreds(p => ({ ...p, password: e.target.value }))}
                              />
                            </div>
                          </div>
                        </div>
                      )}

                      {testResult ? (
                        <>
                          <div className={cn("rounded-lg p-3 flex items-center gap-2", testResult.success ? "bg-emerald-50" : "bg-red-50")}>
                            {testResult.success ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <XCircle className="h-5 w-5 text-red-600" />}
                            <div>
                              <p className={cn("text-sm font-semibold", testResult.success ? "text-emerald-800" : "text-red-800")}>
                                {testResult.success ? "连通正常" : "连通异常"}
                              </p>
                              <p className="text-[11px] text-slate-500">延迟 {testResult.latency_ms}ms · {formatDate(testResult.tested_at)}</p>
                            </div>
                          </div>
                          <div className="space-y-1.5">
                            {testResult.checks.map((chk, idx) => (
                              <div key={idx} className="flex items-center gap-2 rounded-lg border border-slate-100 bg-white px-2.5 py-2">
                                {chk.passed ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" /> : <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />}
                                <div className="flex-1 min-w-0">
                                  <p className="text-[11px] font-medium text-slate-700">{chk.name}</p>
                                  <p className="text-[10px] text-slate-400">{chk.message}</p>
                                </div>
                                <span className="text-[10px] text-slate-400 shrink-0">{chk.duration_ms}ms</span>
                              </div>
                            ))}
                          </div>
                        </>
                      ) : (
                        <div className="text-center py-8">
                          <Activity className="h-8 w-8 text-slate-200 mx-auto mb-2" />
                          <p className="text-xs text-slate-400">点击"测试"执行连通性检查</p>
                          {selected.last_tested && (
                            <p className="text-[10px] text-slate-400 mt-1">
                              上次测试: {formatDate(selected.last_tested)} · {selected.last_test_result === "pass" ? "通过" : "失败"} · {selected.last_test_latency_ms}ms
                            </p>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Bound Tools */}
                {detailTab === "tools" && (
                  <Card>
                    <CardContent className="pt-4 space-y-3">
                      <p className="text-xs font-semibold text-slate-700 flex items-center gap-1.5"><Zap className="h-3.5 w-3.5 text-slate-400" />关联 Tool / Skill</p>
                      {selected.bound_tools.length > 0 ? (
                        <div className="space-y-1.5">
                          {selected.bound_tools.map(tn => (
                            <div key={tn} className="flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50/50 px-2.5 py-2">
                              <Eye className="h-3 w-3 text-blue-400 shrink-0" />
                              <span className="text-xs font-mono text-slate-700">{tn}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-6"><Plug className="h-7 w-7 text-slate-200 mx-auto mb-2" /><p className="text-xs text-slate-400">暂无关联工具</p></div>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Rotations */}
                {detailTab === "rotations" && (
                  <Card>
                    <CardContent className="pt-4 space-y-3">
                      <p className="text-xs font-semibold text-slate-700 flex items-center gap-1.5"><KeyRound className="h-3.5 w-3.5 text-slate-400" />密钥轮换记录</p>
                      {loadingDetail ? <LoadingBlock /> : connRotations.length > 0 ? (
                        <div className="space-y-2">
                          {connRotations.map(r => (
                            <div key={r.id} className="rounded-lg border border-slate-100 bg-slate-50/50 p-2.5 space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="text-[11px] font-medium text-slate-700">{r.rotated_by}</span>
                                <span className={cn("text-[10px] font-medium", r.status === "success" ? "text-emerald-600" : "text-red-600")}>{r.status}</span>
                              </div>
                              <div className="text-[10px] text-slate-500 font-mono space-y-0.5">
                                <p className="truncate">旧: {r.old_credential_ref}</p>
                                <p className="truncate">新: {r.new_credential_ref}</p>
                              </div>
                              {r.note && <p className="text-[10px] text-slate-400">{r.note}</p>}
                              <p className="text-[10px] text-slate-400">{formatDate(r.rotated_at)}</p>
                            </div>
                          ))}
                        </div>
                      ) : <div className="text-center py-6"><KeyRound className="h-7 w-7 text-slate-200 mx-auto mb-2" /><p className="text-xs text-slate-400">暂无轮换记录</p></div>}
                    </CardContent>
                  </Card>
                )}

                {/* Audits */}
                {detailTab === "audits" && (
                  <Card>
                    <CardContent className="pt-4 space-y-3">
                      <p className="text-xs font-semibold text-slate-700 flex items-center gap-1.5"><History className="h-3.5 w-3.5 text-slate-400" />连接审计</p>
                      {loadingDetail ? <LoadingBlock /> : connAudits.length > 0 ? (
                        <div className="space-y-1.5">
                          {connAudits.map(a => (
                            <div key={a.id} className="rounded-lg border border-slate-100 bg-white px-2.5 py-2 space-y-0.5">
                              <div className="flex items-center justify-between">
                                <Badge variant={a.action.includes("test") ? "info" : a.action === "created" ? "success" : "neutral"} className="text-[9px]">{a.action}</Badge>
                                <span className="text-[10px] text-slate-400">{formatDate(a.timestamp)}</span>
                              </div>
                              <p className="text-[11px] text-slate-600">{a.detail}</p>
                              <p className="text-[10px] text-slate-400">{a.actor}{a.ip ? ` · ${a.ip}` : ""}</p>
                            </div>
                          ))}
                        </div>
                      ) : <div className="text-center py-6"><History className="h-7 w-7 text-slate-200 mx-auto mb-2" /><p className="text-xs text-slate-400">暂无审计记录</p></div>}
                    </CardContent>
                  </Card>
                )}

                {/* Actions */}
                <Card>
                  <CardHeader><CardTitle>操作</CardTitle></CardHeader>
                  <CardContent className="space-y-1.5">
                    <Button variant="secondary" size="sm" className="w-full justify-start" onClick={() => openEdit(selected)}>
                      <Pencil className="h-3.5 w-3.5 text-blue-500" /> 编辑连接
                    </Button>
                    {selected.enabled ? (
                      <Button variant="secondary" size="sm" className="w-full justify-start" onClick={() => handleToggle(selected.id, false)}>
                        <PowerOff className="h-3.5 w-3.5 text-red-500" /> 停用连接
                      </Button>
                    ) : (
                      <Button variant="secondary" size="sm" className="w-full justify-start" onClick={() => handleToggle(selected.id, true)}>
                        <Power className="h-3.5 w-3.5 text-emerald-500" /> 启用连接
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" className="w-full justify-start text-slate-600" onClick={() => handleTest(selected.id)}>
                      <Activity className="h-3.5 w-3.5" /> 连通性测试
                    </Button>
                    <Button variant="ghost" size="sm" className="w-full justify-start text-slate-600" onClick={() => loadDetailTab(selected, "rotations")}>
                      <KeyRound className="h-3.5 w-3.5" /> 密钥轮换记录
                    </Button>
                    <Button variant="ghost" size="sm" className="w-full justify-start text-slate-600" onClick={() => loadDetailTab(selected, "audits")}>
                      <History className="h-3.5 w-3.5" /> 审计记录
                    </Button>
                    <div className="border-t border-slate-100 pt-1.5 mt-1.5">
                      <Button variant="ghost" size="sm" className="w-full justify-start text-red-500 hover:text-red-600 hover:bg-red-50" onClick={() => setShowDeleteConfirm(true)}>
                        <Trash2 className="h-3.5 w-3.5" /> 删除连接
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <Plug className="h-10 w-10 text-slate-200 mb-3" />
                <p className="text-sm text-slate-400">选择一个连接查看详情</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Audits Tab ──────────────────── */}
      {tab === "audits" && (
        <Card>
          <CardContent className="pt-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-slate-200 text-left">
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">连接</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">操作</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">详情</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">操作人</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">IP</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">时间</th>
                </tr></thead>
                <tbody className="divide-y divide-slate-50">
                  {audits.map(a => {
                    const connName = connections.find(c => c.id === a.connection_id)?.display_name ?? a.connection_id;
                    return (
                      <tr key={a.id} className="hover:bg-slate-50/50">
                        <td className="px-3 py-2.5 text-xs font-medium text-slate-700">{connName}</td>
                        <td className="px-3 py-2.5"><Badge variant={a.action.includes("test") ? "info" : a.action === "created" ? "success" : a.action.includes("rotation") ? "warning" : "neutral"} className="text-[9px]">{a.action}</Badge></td>
                        <td className="px-3 py-2.5 text-[11px] text-slate-500 max-w-[300px] truncate">{a.detail}</td>
                        <td className="px-3 py-2.5 text-xs text-slate-600">{a.actor}</td>
                        <td className="px-3 py-2.5 text-[11px] text-slate-400 font-mono">{a.ip ?? "—"}</td>
                        <td className="px-3 py-2.5 text-[11px] text-slate-400">{formatDate(a.timestamp)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Rotations Tab ───────────────── */}
      {tab === "rotations" && (
        <Card>
          <CardContent className="pt-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-slate-200 text-left">
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">连接</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">操作人</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">旧凭据</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">新凭据</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">状态</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">备注</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500">时间</th>
                </tr></thead>
                <tbody className="divide-y divide-slate-50">
                  {rotations.map(r => {
                    const connName = connections.find(c => c.id === r.connection_id)?.display_name ?? r.connection_id;
                    return (
                      <tr key={r.id} className="hover:bg-slate-50/50">
                        <td className="px-3 py-2.5 text-xs font-medium text-slate-700">{connName}</td>
                        <td className="px-3 py-2.5 text-xs text-slate-600">{r.rotated_by}</td>
                        <td className="px-3 py-2.5 text-[10px] font-mono text-slate-400 max-w-[160px] truncate">{r.old_credential_ref}</td>
                        <td className="px-3 py-2.5 text-[10px] font-mono text-slate-600 max-w-[160px] truncate">{r.new_credential_ref}</td>
                        <td className="px-3 py-2.5">
                          <span className={cn("text-[11px] font-medium", r.status === "success" ? "text-emerald-600" : "text-red-600")}>
                            {r.status === "success" ? <CheckCircle2 className="h-3 w-3 inline mr-0.5" /> : <XCircle className="h-3 w-3 inline mr-0.5" />}
                            {r.status}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-[11px] text-slate-500">{r.note ?? "—"}</td>
                        <td className="px-3 py-2.5 text-[11px] text-slate-400">{formatDate(r.rotated_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Retention Tab ───────────────── */}
      {tab === "retention" && (
        <Card>
          <CardHeader><CardTitle>审计保留周期配置</CardTitle></CardHeader>
          <CardContent className="space-y-4 max-w-lg">
            <RetentionField label="审计记录保留天数" value={retention.audit_retention_days ?? 365} onChange={v => setRetention(p => ({ ...p, audit_retention_days: v }))} />
            <RetentionField label="连通性测试历史保留天数" value={retention.connection_test_history_days ?? 90} onChange={v => setRetention(p => ({ ...p, connection_test_history_days: v }))} />
            <RetentionField label="密钥轮换记录保留天数" value={retention.key_rotation_history_days ?? 730} onChange={v => setRetention(p => ({ ...p, key_rotation_history_days: v }))} />
            <Button variant="primary" size="sm" onClick={handleRetentionSave}>保存</Button>
          </CardContent>
        </Card>
      )}

      {/* ── Create Dialog ───────────────── */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowCreate(false)}>
          <div className="w-[560px] bg-white rounded-xl shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
              <h2 className="text-sm font-semibold text-slate-900">新建连接 Profile</h2>
              <button onClick={() => setShowCreate(false)} className="text-slate-400 hover:text-slate-600"><X className="h-4 w-4" /></button>
            </div>
            <div className="px-5 py-4 space-y-3 max-h-[60vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-3">
                <FormField label="连接名称"><input className="form-input" value={createForm.name} onChange={e => setCreateForm(p => ({ ...p, name: e.target.value }))} placeholder="vcenter-staging" /></FormField>
                <FormField label="显示名称"><input className="form-input" value={createForm.display_name} onChange={e => setCreateForm(p => ({ ...p, display_name: e.target.value }))} placeholder="vCenter 测试环境" /></FormField>
              </div>
              <FormField label="连接类型">
                <select className="form-input" value={createForm.type} onChange={e => setCreateForm(p => ({ ...p, type: e.target.value }))}>
                  {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </FormField>
              <FormField label="Endpoint"><input className="form-input" value={createForm.endpoint} onChange={e => setCreateForm(p => ({ ...p, endpoint: e.target.value }))} placeholder="https://vcenter.corp.local:443/sdk" /></FormField>
              <FormField label="范围 (Scope)"><input className="form-input" value={createForm.scope} onChange={e => setCreateForm(p => ({ ...p, scope: e.target.value }))} placeholder="Datacenter: DC-01" /></FormField>
              <FormField label="凭据引用"><input className="form-input" value={createForm.credential_ref} onChange={e => setCreateForm(p => ({ ...p, credential_ref: e.target.value }))} placeholder="vault://secret/vcenter/staging" /></FormField>
              <FormField label="跳板机配置"><input className="form-input" value={createForm.proxy_config} onChange={e => setCreateForm(p => ({ ...p, proxy_config: e.target.value }))} placeholder="jumphost: bastion.corp.local:22（可选）" /></FormField>
              <FormField label="描述"><textarea className="form-input min-h-[50px]" value={createForm.description} onChange={e => setCreateForm(p => ({ ...p, description: e.target.value }))} /></FormField>
              <FormField label="标签" hint="逗号分隔"><input className="form-input" value={createForm.tags} onChange={e => setCreateForm(p => ({ ...p, tags: e.target.value }))} placeholder="vmware, staging" /></FormField>
            </div>
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-slate-100">
              <Button variant="secondary" size="sm" onClick={() => setShowCreate(false)}>取消</Button>
              <Button variant="primary" size="sm" onClick={handleCreate} disabled={creating || !createForm.name || !createForm.endpoint}>
                {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />} 创建
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Edit Dialog ─────────────────── */}
      {showEdit && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowEdit(false)}>
          <div className="w-[560px] bg-white rounded-xl shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
              <h2 className="text-sm font-semibold text-slate-900">编辑连接 — {selected.display_name}</h2>
              <button onClick={() => setShowEdit(false)} className="text-slate-400 hover:text-slate-600"><X className="h-4 w-4" /></button>
            </div>
            <div className="px-5 py-4 space-y-3 max-h-[60vh] overflow-y-auto">
              <FormField label="显示名称"><input className="form-input" value={editForm.display_name} onChange={e => setEditForm(p => ({ ...p, display_name: e.target.value }))} /></FormField>
              <FormField label="Endpoint"><input className="form-input" value={editForm.endpoint} onChange={e => setEditForm(p => ({ ...p, endpoint: e.target.value }))} /></FormField>
              <FormField label="范围 (Scope)"><input className="form-input" value={editForm.scope} onChange={e => setEditForm(p => ({ ...p, scope: e.target.value }))} /></FormField>
              <FormField label="凭据引用"><input className="form-input" value={editForm.credential_ref} onChange={e => setEditForm(p => ({ ...p, credential_ref: e.target.value }))} /></FormField>
              <FormField label="跳板机配置"><input className="form-input" value={editForm.proxy_config} onChange={e => setEditForm(p => ({ ...p, proxy_config: e.target.value }))} /></FormField>
              <FormField label="描述"><textarea className="form-input min-h-[50px]" value={editForm.description} onChange={e => setEditForm(p => ({ ...p, description: e.target.value }))} /></FormField>
              <FormField label="标签" hint="逗号分隔"><input className="form-input" value={editForm.tags} onChange={e => setEditForm(p => ({ ...p, tags: e.target.value }))} /></FormField>
            </div>
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-slate-100">
              <Button variant="secondary" size="sm" onClick={() => setShowEdit(false)}>取消</Button>
              <Button variant="primary" size="sm" onClick={handleEdit} disabled={saving || !editForm.display_name || !editForm.endpoint}>
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Pencil className="h-3.5 w-3.5" />} 保存
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete Confirm Dialog ─────── */}
      {showDeleteConfirm && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowDeleteConfirm(false)}>
          <div className="w-[420px] bg-white rounded-xl shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="px-5 py-5 text-center">
              <div className="mx-auto w-10 h-10 rounded-full bg-red-50 flex items-center justify-center mb-3">
                <Trash2 className="h-5 w-5 text-red-500" />
              </div>
              <h3 className="text-sm font-semibold text-slate-900 mb-1">确认删除连接</h3>
              <p className="text-xs text-slate-500 mb-1">即将删除连接 <span className="font-medium text-slate-700">{selected.display_name}</span></p>
              {selected.bound_tools.length > 0 && (
                <p className="text-xs text-amber-600 mb-1">
                  <AlertTriangle className="h-3 w-3 inline mr-0.5" />
                  该连接被 {selected.bound_tools.length} 个工具引用，删除后相关工具将丢失连接绑定
                </p>
              )}
              <p className="text-[11px] text-slate-400">此操作不可恢复</p>
            </div>
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-slate-100">
              <Button variant="secondary" size="sm" onClick={() => setShowDeleteConfirm(false)}>取消</Button>
              <Button variant="danger" size="sm" onClick={handleDelete} disabled={deleting}>
                {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />} 确认删除
              </Button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .form-input { display:block; width:100%; height:32px; padding:0 10px; border:1px solid #e2e8f0; border-radius:8px; font-size:13px; color:#1e293b; background:#fff; outline:none; transition:border-color 150ms,box-shadow 150ms; }
        .form-input:focus { border-color:#3b82f6; box-shadow:0 0 0 3px rgba(59,130,246,.15); }
        textarea.form-input { height:auto; padding:8px 10px; resize:vertical; }
        select.form-input { appearance:auto; }
      `}</style>
    </div>
  );
}


// ── Sub-components ──────────────────────────────────────────

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2">
      <p className="text-[10px] text-slate-400 mb-0.5">{label}</p>
      <p className="text-xs font-medium text-slate-700">{value}</p>
    </div>
  );
}

function LoadingBlock() {
  return <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-blue-500" /></div>;
}

function FormField({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-700 mb-1">
        {label}{hint && <span className="text-slate-400 font-normal ml-1">({hint})</span>}
      </label>
      {children}
    </div>
  );
}

function RetentionField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-700 mb-1">{label}</label>
      <div className="flex items-center gap-2">
        <input type="number" className="form-input w-32" value={value} onChange={e => onChange(Number(e.target.value))} min={1} />
        <span className="text-xs text-slate-500">天</span>
      </div>
    </div>
  );
}
