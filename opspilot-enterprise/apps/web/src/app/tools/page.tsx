"use client";

import { useState, useEffect, useCallback, Fragment } from "react";
import {
  Wrench, Server, Activity, Shield, Clock, CheckCircle2, XCircle,
  AlertTriangle, ChevronRight, ChevronDown, Power, PowerOff, Search,
  ArrowUpDown, Eye, Zap, Ban, RotateCcw, Loader2, Plus, Trash2, Upload,
  Box, Network, Database, BookOpen, Workflow, Link2, FileJson, List,
  HeartPulse, BarChart3, GitBranch, Unplug, History, X, Plug, Package,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MetricCard } from "@/components/ui/metric-card";
import { cn, formatDate } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import type {
  ToolMeta, GatewayInfo, ToolInvocation, ToolManifest,
  ToolCapability, ConnectionBinding, ToolAuditStats, ToolHealthCheckResult,
} from "@opspilot/shared-types";

// ── Constants ──────────────────────────────────────────────

const LIFECYCLE_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  enabled:     { bg: "bg-emerald-50", text: "text-emerald-700", dot: "bg-emerald-500" },
  ready:       { bg: "bg-blue-50",    text: "text-blue-700",    dot: "bg-blue-500" },
  disabled:    { bg: "bg-slate-100",  text: "text-slate-500",   dot: "bg-slate-400" },
  draft:       { bg: "bg-amber-50",   text: "text-amber-700",   dot: "bg-amber-500" },
  degraded:    { bg: "bg-orange-50",  text: "text-orange-700",  dot: "bg-orange-500" },
  error:       { bg: "bg-red-50",     text: "text-red-700",     dot: "bg-red-500" },
  retired:     { bg: "bg-slate-50",   text: "text-slate-400",   dot: "bg-slate-300" },
  configuring: { bg: "bg-purple-50",  text: "text-purple-700",  dot: "bg-purple-500" },
  registered:  { bg: "bg-sky-50",     text: "text-sky-700",     dot: "bg-sky-500" },
  upgrading:   { bg: "bg-indigo-50",  text: "text-indigo-700",  dot: "bg-indigo-500" },
};

const LIFECYCLE_LABELS: Record<string, string> = {
  enabled: "已启用", ready: "就绪", disabled: "已禁用", draft: "草稿",
  degraded: "降级", error: "异常", retired: "已下线", configuring: "配置中",
  registered: "已注册", upgrading: "升级中",
};

const RISK_COLORS: Record<string, string> = {
  low: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  medium: "bg-amber-50 text-amber-700 ring-amber-200",
  high: "bg-orange-50 text-orange-700 ring-orange-200",
  critical: "bg-red-50 text-red-700 ring-red-200",
};

const ACTION_TYPE_ICON: Record<string, { icon: typeof Eye; color: string; label: string }> = {
  read:      { icon: Eye,  color: "text-blue-500",   label: "只读" },
  write:     { icon: Zap,  color: "text-amber-500",  label: "写入" },
  dangerous: { icon: Ban,  color: "text-red-500",    label: "危险" },
};

const DOMAIN_ICONS: Record<string, typeof Box> = {
  vmware: Server, kubernetes: Box, network: Network, storage: Database,
  knowledge: BookOpen, workflow: Workflow, integration: Link2, platform: Wrench,
};

function LifecycleBadge({ status }: { status: string }) {
  const c = LIFECYCLE_COLORS[status] ?? LIFECYCLE_COLORS.draft;
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-medium", c.bg, c.text)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", c.dot)} />
      {LIFECYCLE_LABELS[status] ?? status}
    </span>
  );
}

type TabId = "overview" | "registry" | "gateways" | "invocations";
type DetailSection = "info" | "manifest" | "capabilities" | "connections" | "stats" | "health";

// ── Main Component ─────────────────────────────────────────

export default function ToolGatewayPage() {
  const [tab, setTab] = useState<TabId>("overview");
  const [tools, setTools] = useState<ToolMeta[]>([]);
  const [gateways, setGateways] = useState<GatewayInfo[]>([]);
  const [invocations, setInvocations] = useState<ToolInvocation[]>([]);
  const [stats, setStats] = useState<Record<string, any>>({});
  const [selectedTool, setSelectedTool] = useState<ToolMeta | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterDomain, setFilterDomain] = useState("");
  const [filterActionType, setFilterActionType] = useState("");
  const [filterLifecycle, setFilterLifecycle] = useState("");
  const [filterVersion, setFilterVersion] = useState("");
  const [loading, setLoading] = useState(true);

  // Detail panel sub-state
  const [detailSection, setDetailSection] = useState<DetailSection>("info");
  const [manifest, setManifest] = useState<ToolManifest | null>(null);
  const [capabilities, setCapabilities] = useState<ToolCapability[]>([]);
  const [connections, setConnections] = useState<ConnectionBinding[]>([]);
  const [auditStats, setAuditStats] = useState<ToolAuditStats | null>(null);
  const [healthResult, setHealthResult] = useState<ToolHealthCheckResult | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [healthChecking, setHealthChecking] = useState(false);

  // Register dialog
  const [showRegister, setShowRegister] = useState(false);
  const [regForm, setRegForm] = useState({ name: "", display_name: "", description: "", domain: "vmware", provider: "", action_type: "read", risk_level: "low", version: "1.0.0", tags: "" });
  const [registering, setRegistering] = useState(false);

  const fetchAll = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch<{ data: ToolMeta[] }>("/api/v1/tools").then(r => setTools(r.data ?? [])),
      apiFetch<{ data: GatewayInfo[] }>("/api/v1/tools/gateways").then(r => setGateways(r.data ?? [])),
      apiFetch<{ data: ToolInvocation[] }>("/api/v1/tools/invocations").then(r => setInvocations(r.data ?? [])),
      apiFetch<{ data: Record<string, any> }>("/api/v1/tools/stats").then(r => setStats(r.data ?? {})),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  async function handleToggle(toolName: string, action: "enable" | "disable") {
    await apiFetch(`/api/v1/tools/${toolName}/toggle`, { method: "PATCH", body: JSON.stringify({ action }) });
    const res = await apiFetch<{ data: ToolMeta[] }>("/api/v1/tools");
    setTools(res.data ?? []);
    if (selectedTool?.name === toolName) setSelectedTool(res.data?.find(t => t.name === toolName) ?? null);
  }

  async function handleLifecycle(toolName: string, action: string, targetVersion?: string) {
    await apiFetch(`/api/v1/tools/${toolName}/lifecycle`, { method: "PATCH", body: JSON.stringify({ action, target_version: targetVersion }) });
    const res = await apiFetch<{ data: ToolMeta[] }>("/api/v1/tools");
    setTools(res.data ?? []);
    if (selectedTool?.name === toolName) setSelectedTool(res.data?.find(t => t.name === toolName) ?? null);
  }

  async function loadDetailSection(tool: ToolMeta, section: DetailSection) {
    setDetailSection(section);
    if (section === "info") return;
    setLoadingDetail(true);
    try {
      if (section === "manifest") {
        const r = await apiFetch<{ data: ToolManifest }>(`/api/v1/tools/${tool.name}/manifest`);
        setManifest(r.data ?? null);
      } else if (section === "capabilities") {
        const r = await apiFetch<{ data: ToolCapability[] }>(`/api/v1/tools/${tool.name}/capabilities`);
        setCapabilities(r.data ?? []);
      } else if (section === "connections") {
        const r = await apiFetch<{ data: ConnectionBinding[] }>(`/api/v1/tools/${tool.name}/connections`);
        setConnections(r.data ?? []);
      } else if (section === "stats") {
        const r = await apiFetch<{ data: ToolAuditStats }>(`/api/v1/tools/${tool.name}/audit-stats`);
        setAuditStats(r.data ?? null);
      }
    } finally { setLoadingDetail(false); }
  }

  async function runHealthCheck(toolName: string) {
    setHealthChecking(true);
    try {
      const r = await apiFetch<{ data: ToolHealthCheckResult }>(`/api/v1/tools/${toolName}/health-check`, { method: "POST" });
      setHealthResult(r.data ?? null);
      setDetailSection("health");
    } finally { setHealthChecking(false); }
  }

  async function handleRegister() {
    setRegistering(true);
    try {
      await apiFetch("/api/v1/tools/register", {
        method: "POST",
        body: JSON.stringify({ ...regForm, tags: regForm.tags.split(",").map(t => t.trim()).filter(Boolean) }),
      });
      setShowRegister(false);
      setRegForm({ name: "", display_name: "", description: "", domain: "vmware", provider: "", action_type: "read", risk_level: "low", version: "1.0.0", tags: "" });
      fetchAll();
    } finally { setRegistering(false); }
  }

  function selectTool(tool: ToolMeta) {
    setSelectedTool(tool);
    setDetailSection("info");
    setManifest(null);
    setCapabilities([]);
    setConnections([]);
    setAuditStats(null);
    setHealthResult(null);
  }

  const filteredTools = tools.filter(t => {
    if (searchQuery && !t.name.toLowerCase().includes(searchQuery.toLowerCase()) && !t.display_name.includes(searchQuery)) return false;
    if (filterDomain && t.domain !== filterDomain) return false;
    if (filterActionType && t.action_type !== filterActionType) return false;
    if (filterLifecycle && t.lifecycle_status !== filterLifecycle) return false;
    if (filterVersion && t.version !== filterVersion) return false;
    return true;
  });

  const domains = [...new Set(tools.map(t => t.domain))];
  const versions = [...new Set(tools.map(t => t.version))].sort();
  const TABS: { id: TabId; label: string; count?: number }[] = [
    { id: "overview", label: "总览" },
    { id: "registry", label: "工具注册中心", count: tools.length },
    { id: "gateways", label: "网关状态", count: gateways.length },
    { id: "invocations", label: "调用历史", count: invocations.length },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Tool Gateway 控制台"
        description="统一工具注册、生命周期管理、网关监控与调用审计"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={fetchAll}>
              <RotateCcw className="h-3.5 w-3.5" /> 刷新
            </Button>
            <Button variant="primary" size="sm" onClick={() => { setShowRegister(true); setTab("registry"); }}>
              <Plus className="h-3.5 w-3.5" /> 注册 Skill
            </Button>
          </div>
        }
      />

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
              tab === t.id
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Overview Tab ─────────────────── */}
      {tab === "overview" && <OverviewTab stats={stats} gateways={gateways} invocations={invocations} setTab={setTab} />}

      {/* ── Registry Tab ─────────────────── */}
      {tab === "registry" && (
        <div className="flex gap-4 h-[calc(100vh-14rem)]">
          {/* Left: Tool List */}
          <div className="flex-1 min-w-0 flex flex-col">
            {/* Filters */}
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                <input
                  type="text" placeholder="搜索工具名称..."
                  value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                  className="h-8 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-[13px] focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                />
              </div>
              <FilterSelect value={filterDomain} onChange={setFilterDomain} options={domains} placeholder="全部领域" />
              <FilterSelect value={filterActionType} onChange={setFilterActionType} options={["read", "write", "dangerous"]} labels={{ read: "只读", write: "写入", dangerous: "危险" }} placeholder="全部类型" />
              <FilterSelect value={filterLifecycle} onChange={setFilterLifecycle} options={["enabled", "disabled", "draft", "degraded", "retired", "ready"]} labels={LIFECYCLE_LABELS} placeholder="全部状态" />
              <FilterSelect value={filterVersion} onChange={setFilterVersion} options={versions} placeholder="全部版本" />
            </div>

            <p className="text-[11px] text-slate-400 mb-2">{filteredTools.length} / {tools.length} 工具</p>

            {/* Table */}
            <div className="flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-slate-50 z-10">
                  <tr className="border-b border-slate-200 text-left">
                    <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">工具名称</th>
                    <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">领域</th>
                    <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">类型</th>
                    <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">风险</th>
                    <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">状态</th>
                    <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">版本</th>
                    <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">审批</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {filteredTools.map(tool => {
                    const at = ACTION_TYPE_ICON[tool.action_type] ?? ACTION_TYPE_ICON.read;
                    const AtIcon = at.icon;
                    const DomainIcon = DOMAIN_ICONS[tool.domain] ?? Wrench;
                    return (
                      <tr
                        key={tool.name}
                        onClick={() => selectTool(tool)}
                        className={cn(
                          "cursor-pointer hover:bg-blue-50/50 transition-colors",
                          selectedTool?.name === tool.name && "bg-blue-50"
                        )}
                      >
                        <td className="px-3 py-2.5">
                          <p className="font-medium text-slate-900 text-[13px]">{tool.display_name}</p>
                          <p className="font-mono text-[11px] text-slate-400">{tool.name}</p>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="inline-flex items-center gap-1 text-xs text-slate-600">
                            <DomainIcon className="h-3 w-3 text-slate-400" />
                            {tool.domain}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={cn("inline-flex items-center gap-1 text-xs font-medium", at.color)}>
                            <AtIcon className="h-3 w-3" />
                            {at.label}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={cn("inline-flex rounded-md px-1.5 py-0.5 text-[10px] font-medium ring-1 ring-inset", RISK_COLORS[tool.risk_level])}>
                            {tool.risk_level}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <LifecycleBadge status={tool.lifecycle_status ?? "enabled"} />
                        </td>
                        <td className="px-3 py-2.5 text-xs text-slate-500 font-mono">{tool.version}</td>
                        <td className="px-3 py-2.5">
                          {tool.approval_required ? (
                            <Shield className="h-3.5 w-3.5 text-amber-500" />
                          ) : (
                            <span className="text-[11px] text-slate-300">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {filteredTools.length === 0 && (
                    <tr><td colSpan={7} className="py-12 text-center text-sm text-slate-400">无匹配工具</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right: Detail Panel */}
          <div className="w-[340px] shrink-0 overflow-y-auto space-y-3">
            {selectedTool ? (
              <>
                {/* Section Tabs */}
                <div className="flex gap-0.5 rounded-lg bg-slate-100 p-0.5">
                  {(
                    [
                      { id: "info", icon: List, label: "基本" },
                      { id: "manifest", icon: FileJson, label: "Manifest" },
                      { id: "capabilities", icon: Package, label: "能力" },
                      { id: "connections", icon: Plug, label: "连接" },
                      { id: "stats", icon: BarChart3, label: "统计" },
                      { id: "health", icon: HeartPulse, label: "校验" },
                    ] as { id: DetailSection; icon: typeof List; label: string }[]
                  ).map(s => (
                    <button
                      key={s.id}
                      onClick={() => loadDetailSection(selectedTool, s.id)}
                      className={cn(
                        "flex-1 flex items-center justify-center gap-1 rounded-md py-1.5 text-[10px] font-medium transition-colors",
                        detailSection === s.id ? "bg-white text-blue-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
                      )}
                    >
                      <s.icon className="h-3 w-3" />
                      {s.label}
                    </button>
                  ))}
                </div>

                {/* Info Section */}
                {detailSection === "info" && (
                  <Card>
                    <CardContent className="pt-4 space-y-3">
                      <div className="flex items-start justify-between">
                        <div>
                          <h3 className="text-sm font-semibold text-slate-900">{selectedTool.display_name}</h3>
                          <p className="font-mono text-[11px] text-slate-400 mt-0.5">{selectedTool.name}</p>
                        </div>
                        <LifecycleBadge status={selectedTool.lifecycle_status ?? "enabled"} />
                      </div>
                      {selectedTool.description && (
                        <p className="text-xs text-slate-600 leading-relaxed">{selectedTool.description}</p>
                      )}
                      <div className="grid grid-cols-2 gap-2">
                        <InfoCell label="领域" value={selectedTool.domain} />
                        <InfoCell label="提供者" value={selectedTool.provider} />
                        <InfoCell label="操作类型" value={ACTION_TYPE_ICON[selectedTool.action_type]?.label ?? selectedTool.action_type} />
                        <InfoCell label="风险等级">
                          <span className={cn("inline-flex rounded-md px-1.5 py-0.5 text-[10px] font-medium ring-1 ring-inset", RISK_COLORS[selectedTool.risk_level])}>
                            {selectedTool.risk_level}
                          </span>
                        </InfoCell>
                        <InfoCell label="超时" value={`${selectedTool.timeout_seconds}s`} />
                        <InfoCell label="幂等" value={selectedTool.idempotent ? "是" : "否"} />
                        <InfoCell label="版本" value={selectedTool.version} />
                        <InfoCell label="需审批" value={selectedTool.approval_required ? "是" : "否"} />
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {selectedTool.tags.map(tag => (
                          <Badge key={tag} variant="neutral" className="text-[10px]">{tag}</Badge>
                        ))}
                      </div>
                      {selectedTool.registered_at && (
                        <div className="text-[11px] text-slate-400 space-y-0.5 pt-1 border-t border-slate-100">
                          <p>注册: {formatDate(selectedTool.registered_at)}</p>
                          {selectedTool.updated_at && <p>更新: {formatDate(selectedTool.updated_at)}</p>}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Manifest Section */}
                {detailSection === "manifest" && (
                  <Card>
                    <CardContent className="pt-4 space-y-3">
                      {loadingDetail ? <LoadingBlock /> : manifest ? (
                        <>
                          <SectionTitle icon={FileJson}>Skill Manifest</SectionTitle>
                          <div className="grid grid-cols-2 gap-2">
                            <InfoCell label="版本" value={manifest.version} />
                            <InfoCell label="作者" value={manifest.author} />
                            <InfoCell label="许可证" value={manifest.license} />
                            <InfoCell label="最低平台版本" value={manifest.min_platform_version} />
                          </div>
                          {manifest.dependencies.length > 0 && (
                            <div>
                              <p className="text-[10px] text-slate-400 font-medium mb-1">依赖项</p>
                              <div className="flex flex-wrap gap-1">
                                {manifest.dependencies.map(d => (
                                  <Badge key={d} variant="neutral" className="text-[10px] font-mono">{d}</Badge>
                                ))}
                              </div>
                            </div>
                          )}
                          {manifest.supported_connection_types.length > 0 && (
                            <div>
                              <p className="text-[10px] text-slate-400 font-medium mb-1">支持的连接类型</p>
                              <div className="flex flex-wrap gap-1">
                                {manifest.supported_connection_types.map(c => (
                                  <Badge key={c} variant="info" className="text-[10px]">{c}</Badge>
                                ))}
                              </div>
                            </div>
                          )}
                          <div>
                            <p className="text-[10px] text-slate-400 font-medium mb-1">Input Schema</p>
                            <pre className="text-[10px] font-mono text-slate-600 bg-slate-50 rounded-lg p-2 overflow-x-auto max-h-28 whitespace-pre-wrap">{JSON.stringify(manifest.input_schema, null, 2)}</pre>
                          </div>
                          <div>
                            <p className="text-[10px] text-slate-400 font-medium mb-1">Output Schema</p>
                            <pre className="text-[10px] font-mono text-slate-600 bg-slate-50 rounded-lg p-2 overflow-x-auto max-h-28 whitespace-pre-wrap">{JSON.stringify(manifest.output_schema, null, 2)}</pre>
                          </div>
                          {manifest.changelog && (
                            <div>
                              <p className="text-[10px] text-slate-400 font-medium mb-1">变更日志</p>
                              <pre className="text-[11px] text-slate-600 bg-slate-50 rounded-lg p-2 whitespace-pre-wrap">{manifest.changelog}</pre>
                            </div>
                          )}
                        </>
                      ) : <EmptyBlock message="暂无 Manifest 数据" />}
                    </CardContent>
                  </Card>
                )}

                {/* Capabilities Section */}
                {detailSection === "capabilities" && (
                  <Card>
                    <CardContent className="pt-4 space-y-3">
                      <SectionTitle icon={Package}>可用能力清单</SectionTitle>
                      {loadingDetail ? <LoadingBlock /> : capabilities.length > 0 ? (
                        <div className="space-y-2">
                          {capabilities.map((cap, idx) => {
                            const at = ACTION_TYPE_ICON[cap.action_type] ?? ACTION_TYPE_ICON.read;
                            const AtIcon = at.icon;
                            return (
                              <div key={idx} className="rounded-lg border border-slate-100 bg-slate-50/50 p-2.5">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-xs font-semibold text-slate-800">{cap.name}</span>
                                  <span className={cn("inline-flex items-center gap-1 text-[10px] font-medium", at.color)}>
                                    <AtIcon className="h-2.5 w-2.5" />
                                    {at.label}
                                  </span>
                                </div>
                                <p className="text-[11px] text-slate-500 mb-1.5">{cap.description}</p>
                                {cap.parameters.length > 0 && (
                                  <div className="flex flex-wrap gap-1">
                                    {cap.parameters.map(p => (
                                      <span key={p} className="inline-flex items-center rounded bg-white px-1.5 py-0.5 text-[9px] font-mono text-slate-500 ring-1 ring-slate-200">{p}</span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      ) : <EmptyBlock message="暂无能力数据" />}
                    </CardContent>
                  </Card>
                )}

                {/* Connections Section */}
                {detailSection === "connections" && (
                  <Card>
                    <CardContent className="pt-4 space-y-3">
                      <SectionTitle icon={Plug}>连接绑定</SectionTitle>
                      {loadingDetail ? <LoadingBlock /> : connections.length > 0 ? (
                        <div className="space-y-2">
                          {connections.map(conn => (
                            <div key={conn.connection_id} className="rounded-lg border border-slate-100 bg-slate-50/50 p-2.5 space-y-1.5">
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-slate-800">{conn.connection_name}</span>
                                <LifecycleBadge status={conn.status === "active" ? "enabled" : conn.status === "error" ? "error" : "disabled"} />
                              </div>
                              <div className="grid grid-cols-2 gap-1.5">
                                <InfoCell label="类型" value={conn.connection_type} />
                                <InfoCell label="ID" value={conn.connection_id} />
                              </div>
                              <div className="rounded bg-white px-2 py-1.5 font-mono text-[10px] text-slate-600 ring-1 ring-slate-100 truncate">{conn.target_url}</div>
                              <div className="text-[10px] text-slate-400 flex gap-3">
                                <span>绑定: {formatDate(conn.bound_at)}</span>
                                <span>最近使用: {formatDate(conn.last_used)}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <EmptyBlock message="无绑定连接" icon={Unplug} />
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Stats Section */}
                {detailSection === "stats" && (
                  <Card>
                    <CardContent className="pt-4 space-y-3">
                      <SectionTitle icon={BarChart3}>调用统计</SectionTitle>
                      {loadingDetail ? <LoadingBlock /> : auditStats ? (
                        <>
                          <div className="grid grid-cols-3 gap-2">
                            <StatCell label="总调用" value={auditStats.total_invocations} />
                            <StatCell label="成功" value={auditStats.success_count} color="text-emerald-600" />
                            <StatCell label="失败" value={auditStats.error_count} color="text-red-600" />
                            <StatCell label="拒绝" value={auditStats.denied_count} color="text-amber-600" />
                            <StatCell label="今日" value={auditStats.invocations_today} />
                            <StatCell label="近7天" value={auditStats.invocations_7d} />
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <InfoCell label="平均耗时" value={`${auditStats.avg_duration_ms}ms`} />
                            <InfoCell label="P95 耗时" value={`${auditStats.p95_duration_ms}ms`} />
                          </div>
                          {auditStats.last_invoked && (
                            <InfoCell label="最近调用" value={formatDate(auditStats.last_invoked)} />
                          )}
                          {auditStats.top_callers.length > 0 && (
                            <div>
                              <p className="text-[10px] text-slate-400 font-medium mb-1.5">Top 调用者</p>
                              <div className="space-y-1">
                                {auditStats.top_callers.map(tc => (
                                  <div key={tc.caller} className="flex items-center justify-between">
                                    <span className="text-[11px] text-slate-600">{tc.caller}</span>
                                    <span className="text-[11px] font-medium text-slate-700">{tc.count}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {auditStats.daily_trend.length > 0 && (
                            <div>
                              <p className="text-[10px] text-slate-400 font-medium mb-1.5">7日趋势</p>
                              <div className="flex items-end gap-1 h-16">
                                {auditStats.daily_trend.map((d, i) => {
                                  const max = Math.max(...auditStats.daily_trend.map(x => x.count), 1);
                                  const h = Math.max(4, (d.count / max) * 56);
                                  const successH = Math.max(2, (d.success / max) * 56);
                                  return (
                                    <div key={i} className="flex-1 flex flex-col items-center gap-0.5" title={`${d.date}: ${d.count} 次 (${d.success} 成功)`}>
                                      <div className="w-full rounded-t bg-slate-200 relative" style={{ height: h }}>
                                        <div className="absolute bottom-0 left-0 right-0 rounded-t bg-blue-500" style={{ height: successH }} />
                                      </div>
                                      <span className="text-[8px] text-slate-400">{d.date.slice(-2)}</span>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </>
                      ) : <EmptyBlock message="暂无统计数据" />}
                    </CardContent>
                  </Card>
                )}

                {/* Health Check Section */}
                {detailSection === "health" && (
                  <Card>
                    <CardContent className="pt-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <SectionTitle icon={HeartPulse}>校验与健康检查</SectionTitle>
                        <Button variant="secondary" size="xs" onClick={() => runHealthCheck(selectedTool.name)} disabled={healthChecking}>
                          {healthChecking ? <Loader2 className="h-3 w-3 animate-spin" /> : <RotateCcw className="h-3 w-3" />}
                          检查
                        </Button>
                      </div>
                      {healthResult ? (
                        <>
                          <div className={cn("rounded-lg p-3 flex items-center gap-2",
                            healthResult.healthy ? "bg-emerald-50" : "bg-red-50"
                          )}>
                            {healthResult.healthy ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <XCircle className="h-5 w-5 text-red-600" />}
                            <div>
                              <p className={cn("text-sm font-semibold", healthResult.healthy ? "text-emerald-800" : "text-red-800")}>
                                {healthResult.healthy ? "健康" : "异常"}
                              </p>
                              <p className="text-[11px] text-slate-500">延迟 {healthResult.latency_ms}ms · {formatDate(healthResult.checked_at)}</p>
                            </div>
                          </div>
                          <div className="space-y-1.5">
                            {healthResult.checks.map((chk, idx) => (
                              <div key={idx} className="flex items-center gap-2 rounded-lg border border-slate-100 bg-white px-2.5 py-2">
                                {chk.passed ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" /> : <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />}
                                <div className="flex-1 min-w-0">
                                  <p className="text-[11px] font-medium text-slate-700">{chk.name}</p>
                                  <p className="text-[10px] text-slate-400">{chk.message}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </>
                      ) : (
                        <div className="text-center py-8">
                          <HeartPulse className="h-8 w-8 text-slate-200 mx-auto mb-2" />
                          <p className="text-xs text-slate-400">点击"检查"执行校验与健康检查</p>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Lifecycle Actions */}
                <Card>
                  <CardHeader>
                    <CardTitle>生命周期操作</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1.5">
                    {selectedTool.lifecycle_status === "enabled" && (
                      <Button variant="secondary" size="sm" className="w-full justify-start" onClick={() => handleToggle(selectedTool.name, "disable")}>
                        <PowerOff className="h-3.5 w-3.5 text-red-500" /> 停用工具
                      </Button>
                    )}
                    {(selectedTool.lifecycle_status === "disabled" || selectedTool.lifecycle_status === "ready") && (
                      <Button variant="secondary" size="sm" className="w-full justify-start" onClick={() => handleToggle(selectedTool.name, "enable")}>
                        <Power className="h-3.5 w-3.5 text-emerald-500" /> 启用工具
                      </Button>
                    )}
                    {selectedTool.lifecycle_status === "draft" && (
                      <Button variant="secondary" size="sm" className="w-full justify-start" onClick={() => handleLifecycle(selectedTool.name, "validate")}>
                        <CheckCircle2 className="h-3.5 w-3.5 text-blue-500" /> 校验并就绪
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" className="w-full justify-start text-slate-600" onClick={() => runHealthCheck(selectedTool.name)}>
                      <HeartPulse className="h-3.5 w-3.5" /> 健康检查
                    </Button>
                    <Button variant="ghost" size="sm" className="w-full justify-start text-slate-600" onClick={() => loadDetailSection(selectedTool, "stats")}>
                      <BarChart3 className="h-3.5 w-3.5" /> 调用统计
                    </Button>
                    {selectedTool.lifecycle_status !== "retired" && (
                      <>
                        <Button variant="ghost" size="sm" className="w-full justify-start text-slate-600" onClick={() => handleLifecycle(selectedTool.name, "upgrade", `${Number(selectedTool.version.split(".")[0]) + 1}.0.0`)}>
                          <GitBranch className="h-3.5 w-3.5" /> 版本升级
                        </Button>
                        <Button variant="ghost" size="sm" className="w-full justify-start text-slate-600" onClick={() => handleLifecycle(selectedTool.name, "rollback")}>
                          <History className="h-3.5 w-3.5" /> 版本回滚
                        </Button>
                        <Button variant="ghost" size="sm" className="w-full justify-start text-red-500 hover:text-red-700" onClick={() => handleLifecycle(selectedTool.name, "retire")}>
                          <Trash2 className="h-3.5 w-3.5" /> 下线工具
                        </Button>
                      </>
                    )}
                  </CardContent>
                </Card>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <Wrench className="h-10 w-10 text-slate-200 mb-3" />
                <p className="text-sm text-slate-400">选择一个工具查看详情</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Gateways Tab ─────────────────── */}
      {tab === "gateways" && <GatewaysTab gateways={gateways} tools={tools} />}

      {/* ── Invocations Tab ──────────────── */}
      {tab === "invocations" && <InvocationsTab invocations={invocations} />}

      {/* ── Register Dialog ──────────────── */}
      {showRegister && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowRegister(false)}>
          <div className="w-[520px] bg-white rounded-xl shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
              <h2 className="text-sm font-semibold text-slate-900">注册新 Skill</h2>
              <button onClick={() => setShowRegister(false)} className="text-slate-400 hover:text-slate-600"><X className="h-4 w-4" /></button>
            </div>
            <div className="px-5 py-4 space-y-3 max-h-[60vh] overflow-y-auto">
              <FormField label="工具名称" hint="格式: domain.action_name">
                <input className="form-input" value={regForm.name} onChange={e => setRegForm(p => ({ ...p, name: e.target.value }))} placeholder="vmware.list_snapshots" />
              </FormField>
              <FormField label="显示名称">
                <input className="form-input" value={regForm.display_name} onChange={e => setRegForm(p => ({ ...p, display_name: e.target.value }))} placeholder="查询快照列表" />
              </FormField>
              <FormField label="描述">
                <textarea className="form-input min-h-[60px]" value={regForm.description} onChange={e => setRegForm(p => ({ ...p, description: e.target.value }))} placeholder="该工具的详细描述..." />
              </FormField>
              <div className="grid grid-cols-2 gap-3">
                <FormField label="领域">
                  <select className="form-input" value={regForm.domain} onChange={e => setRegForm(p => ({ ...p, domain: e.target.value }))}>
                    <option value="vmware">vmware</option>
                    <option value="kubernetes">kubernetes</option>
                    <option value="network">network</option>
                    <option value="storage">storage</option>
                    <option value="knowledge">knowledge</option>
                    <option value="workflow">workflow</option>
                    <option value="integration">integration</option>
                    <option value="platform">platform</option>
                  </select>
                </FormField>
                <FormField label="提供者">
                  <input className="form-input" value={regForm.provider} onChange={e => setRegForm(p => ({ ...p, provider: e.target.value }))} placeholder="vmware-skill-gateway" />
                </FormField>
                <FormField label="操作类型">
                  <select className="form-input" value={regForm.action_type} onChange={e => setRegForm(p => ({ ...p, action_type: e.target.value }))}>
                    <option value="read">只读</option>
                    <option value="write">写入</option>
                    <option value="dangerous">危险</option>
                  </select>
                </FormField>
                <FormField label="风险等级">
                  <select className="form-input" value={regForm.risk_level} onChange={e => setRegForm(p => ({ ...p, risk_level: e.target.value }))}>
                    <option value="low">低</option>
                    <option value="medium">中</option>
                    <option value="high">高</option>
                    <option value="critical">严重</option>
                  </select>
                </FormField>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <FormField label="版本">
                  <input className="form-input" value={regForm.version} onChange={e => setRegForm(p => ({ ...p, version: e.target.value }))} />
                </FormField>
                <FormField label="标签" hint="逗号分隔">
                  <input className="form-input" value={regForm.tags} onChange={e => setRegForm(p => ({ ...p, tags: e.target.value }))} placeholder="vmware, snapshot" />
                </FormField>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-slate-100">
              <Button variant="secondary" size="sm" onClick={() => setShowRegister(false)}>取消</Button>
              <Button variant="primary" size="sm" onClick={handleRegister} disabled={registering || !regForm.name || !regForm.display_name}>
                {registering ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                注册
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Global form input styles */}
      <style>{`
        .form-input {
          display: block;
          width: 100%;
          height: 32px;
          padding: 0 10px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          font-size: 13px;
          color: #1e293b;
          background: #fff;
          outline: none;
          transition: border-color 150ms, box-shadow 150ms;
        }
        .form-input:focus {
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
        }
        textarea.form-input {
          height: auto;
          padding: 8px 10px;
          resize: vertical;
        }
        select.form-input {
          appearance: auto;
        }
      `}</style>
    </div>
  );
}


// ── Sub-components ──────────────────────────────────────────

function FilterSelect({ value, onChange, options, labels, placeholder }: {
  value: string; onChange: (v: string) => void; options: string[]; labels?: Record<string, string>; placeholder: string;
}) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="h-8 rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20">
      <option value="">{placeholder}</option>
      {options.map(o => <option key={o} value={o}>{labels?.[o] ?? o}</option>)}
    </select>
  );
}

function InfoCell({ label, value, children }: { label: string; value?: string; children?: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2">
      <p className="text-[10px] text-slate-400 mb-0.5">{label}</p>
      {children ?? <p className="text-xs font-medium text-slate-700">{value}</p>}
    </div>
  );
}

function StatCell({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2 text-center">
      <p className={cn("text-lg font-bold", color ?? "text-slate-900")}>{value}</p>
      <p className="text-[10px] text-slate-400">{label}</p>
    </div>
  );
}

function SectionTitle({ icon: Icon, children }: { icon: typeof List; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
      <Icon className="h-3.5 w-3.5 text-slate-400" />
      {children}
    </div>
  );
}

function LoadingBlock() {
  return <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-blue-500" /></div>;
}

function EmptyBlock({ message, icon: Icon }: { message: string; icon?: typeof Wrench }) {
  const I = Icon ?? Wrench;
  return (
    <div className="text-center py-6">
      <I className="h-7 w-7 text-slate-200 mx-auto mb-2" />
      <p className="text-xs text-slate-400">{message}</p>
    </div>
  );
}

function FormField({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-700 mb-1">
        {label}
        {hint && <span className="text-slate-400 font-normal ml-1">({hint})</span>}
      </label>
      {children}
    </div>
  );
}


// ── Overview Tab ────────────────────────────────────────────

function OverviewTab({ stats, gateways, invocations, setTab }: {
  stats: Record<string, any>; gateways: GatewayInfo[]; invocations: ToolInvocation[]; setTab: (t: TabId) => void;
}) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-5 gap-3">
        <MetricCard title="注册工具总数" value={stats.total_tools ?? 0} icon={Wrench} accent="blue" />
        <MetricCard title="已启用" value={stats.enabled ?? 0} icon={CheckCircle2} accent="green" />
        <MetricCard title="高风险工具" value={stats.high_risk_tools ?? 0} icon={AlertTriangle} accent="orange" />
        <MetricCard title="网关健康" value={`${stats.gateways_healthy ?? 0}/${stats.gateways_total ?? 0}`} icon={Server} accent="blue" />
        <MetricCard title="调用成功率" value={`${stats.invocation_success_rate ?? 0}%`} icon={Activity} accent="green" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>网关状态</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {gateways.map(gw => {
              const DomainIcon = DOMAIN_ICONS[gw.domain] ?? Wrench;
              return (
                <div key={gw.id} className="flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50/50 p-3 hover:border-blue-200 transition-colors">
                  <div className={cn("flex h-9 w-9 items-center justify-center rounded-lg",
                    gw.status === "healthy" ? "bg-emerald-100" : gw.status === "degraded" ? "bg-amber-100" : "bg-red-100"
                  )}>
                    <DomainIcon className={cn("h-4 w-4",
                      gw.status === "healthy" ? "text-emerald-600" : gw.status === "degraded" ? "text-amber-600" : "text-red-600"
                    )} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900">{gw.display_name}</p>
                    <p className="text-[11px] text-slate-500">{gw.url} · {gw.tool_count} 工具</p>
                  </div>
                  <div className="text-right shrink-0">
                    <LifecycleBadge status={gw.status === "healthy" ? "enabled" : gw.status === "degraded" ? "degraded" : "error"} />
                    {gw.latency_ms > 0 && <p className="text-[10px] text-slate-400 mt-0.5">{gw.latency_ms}ms</p>}
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>领域分布</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {Object.entries(stats.domains ?? {}).map(([domain, count]) => {
              const DomainIcon = DOMAIN_ICONS[domain] ?? Wrench;
              const total = stats.total_tools || 1;
              const pct = Math.round((count as number) / total * 100);
              return (
                <div key={domain} className="flex items-center gap-3">
                  <DomainIcon className="h-4 w-4 text-slate-400 shrink-0" />
                  <span className="text-sm text-slate-700 w-24">{domain}</span>
                  <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full rounded-full bg-blue-500 transition-all" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs text-slate-500 w-16 text-right">{count as number} ({pct}%)</span>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>最近调用</CardTitle>
          <button onClick={() => setTab("invocations")} className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-0.5">
            查看全部 <ChevronRight className="h-3 w-3" />
          </button>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left">
                  <th className="pb-2 font-medium text-slate-500 text-xs">工具</th>
                  <th className="pb-2 font-medium text-slate-500 text-xs">调用者</th>
                  <th className="pb-2 font-medium text-slate-500 text-xs">结果</th>
                  <th className="pb-2 font-medium text-slate-500 text-xs">策略</th>
                  <th className="pb-2 font-medium text-slate-500 text-xs">耗时</th>
                  <th className="pb-2 font-medium text-slate-500 text-xs">时间</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {invocations.slice(0, 5).map(inv => (
                  <tr key={inv.id} className="hover:bg-slate-50/50">
                    <td className="py-2 font-mono text-xs text-blue-600">{inv.tool_name}</td>
                    <td className="py-2">
                      <span className="text-xs text-slate-700">{inv.caller}</span>
                      <Badge variant="neutral" className="ml-1 text-[9px]">{inv.caller_type}</Badge>
                    </td>
                    <td className="py-2">
                      <span className={cn("inline-flex items-center gap-1 text-[11px] font-medium",
                        inv.status === "success" ? "text-emerald-600" : inv.status === "denied" ? "text-red-600" : "text-amber-600"
                      )}>
                        {inv.status === "success" ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                        {inv.status}
                      </span>
                    </td>
                    <td className="py-2">
                      <Badge variant={inv.policy_result === "allow" ? "info" : inv.policy_result === "deny" ? "danger" : "warning"} className="text-[9px]">
                        {inv.policy_result}
                      </Badge>
                    </td>
                    <td className="py-2 text-xs text-slate-500">{inv.duration_ms}ms</td>
                    <td className="py-2 text-[11px] text-slate-400">{formatDate(inv.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


// ── Gateways Tab ────────────────────────────────────────────

function GatewaysTab({ gateways, tools }: { gateways: GatewayInfo[]; tools: ToolMeta[] }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      {gateways.map(gw => {
        const DomainIcon = DOMAIN_ICONS[gw.domain] ?? Wrench;
        const gwTools = tools.filter(t => t.provider === gw.name);
        return (
          <Card key={gw.id}>
            <CardContent className="pt-4 space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl",
                    gw.status === "healthy" ? "bg-emerald-100" : gw.status === "degraded" ? "bg-amber-100" : "bg-red-100"
                  )}>
                    <DomainIcon className={cn("h-5 w-5",
                      gw.status === "healthy" ? "text-emerald-600" : gw.status === "degraded" ? "text-amber-600" : "text-red-600"
                    )} />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">{gw.display_name}</h3>
                    <p className="text-[11px] text-slate-400 font-mono">{gw.url}</p>
                  </div>
                </div>
                <LifecycleBadge status={gw.status === "healthy" ? "enabled" : gw.status === "degraded" ? "degraded" : "error"} />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-lg bg-slate-50 p-2 text-center">
                  <p className="text-lg font-bold text-slate-900">{gw.tool_count}</p>
                  <p className="text-[10px] text-slate-400">工具数</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-2 text-center">
                  <p className="text-lg font-bold text-slate-900">{gw.latency_ms > 0 ? `${gw.latency_ms}` : "—"}</p>
                  <p className="text-[10px] text-slate-400">延迟(ms)</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-2 text-center">
                  <p className="text-lg font-bold text-slate-900">{gw.version}</p>
                  <p className="text-[10px] text-slate-400">版本</p>
                </div>
              </div>

              {gwTools.length > 0 && (
                <div>
                  <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider">注册工具</p>
                  <div className="flex flex-wrap gap-1">
                    {gwTools.map(t => (
                      <span key={t.name} className="inline-flex items-center gap-1 rounded bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-600 font-mono">
                        {t.action_type === "read" ? <Eye className="h-2.5 w-2.5 text-blue-400" /> : <Zap className="h-2.5 w-2.5 text-amber-400" />}
                        {t.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <p className="text-[11px] text-slate-400 flex items-center gap-1">
                <Clock className="h-3 w-3" />
                上次心跳: {formatDate(gw.last_heartbeat)}
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}


// ── Invocations Tab ─────────────────────────────────────────

function InvocationsTab({ invocations }: { invocations: ToolInvocation[] }) {
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left">
                <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">工具</th>
                <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">调用者</th>
                <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">输入摘要</th>
                <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">输出摘要</th>
                <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">结果</th>
                <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">策略</th>
                <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">耗时</th>
                <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">时间</th>
                <th className="px-3 py-2.5 font-medium text-slate-500 text-xs">Trace</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {invocations.map(inv => (
                <tr key={inv.id} className="hover:bg-slate-50/50">
                  <td className="px-3 py-2.5 font-mono text-xs text-blue-600">{inv.tool_name}</td>
                  <td className="px-3 py-2.5">
                    <span className="text-xs text-slate-700">{inv.caller}</span>
                    <Badge variant="neutral" className="ml-1 text-[9px]">{inv.caller_type}</Badge>
                  </td>
                  <td className="px-3 py-2.5 max-w-[180px]">
                    <p className="text-[11px] text-slate-500 truncate font-mono">{inv.input_summary}</p>
                  </td>
                  <td className="px-3 py-2.5 max-w-[180px]">
                    <p className="text-[11px] text-slate-500 truncate">{inv.output_summary}</p>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={cn("inline-flex items-center gap-1 text-[11px] font-medium",
                      inv.status === "success" ? "text-emerald-600" : inv.status === "denied" ? "text-red-600" : "text-amber-600"
                    )}>
                      {inv.status === "success" ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                      {inv.status}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <Badge variant={inv.policy_result === "allow" ? "info" : inv.policy_result === "deny" ? "danger" : "warning"} className="text-[9px]">
                      {inv.policy_result}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5 text-xs text-slate-500">{inv.duration_ms}ms</td>
                  <td className="px-3 py-2.5 text-[11px] text-slate-400">{formatDate(inv.timestamp)}</td>
                  <td className="px-3 py-2.5">
                    <span className="text-[10px] font-mono text-slate-400">{inv.trace_id.slice(0, 12)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
