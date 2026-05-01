"use client";

import { useEffect, useMemo, useState } from "react";
import type { ElementType } from "react";
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Bot,
  User,
  Cpu,
  Search,
} from "lucide-react";
import type { AuditLog } from "@opspilot/shared-types";

import { PageHeader } from "@/components/ui/page-header";
import { cn, formatDate } from "@/lib/utils";
import { apiFetch } from "@/lib/api";

type AuditListEnvelope = {
  data?: {
    items?: AuditLog[];
    total?: number;
  };
};

const OUTCOME_STYLE: Record<string, { icon: ElementType; cls: string; label: string }> = {
  success: { icon: CheckCircle2, cls: "text-emerald-600 bg-emerald-50", label: "成功" },
  failure: { icon: XCircle, cls: "text-red-600 bg-red-50", label: "失败" },
  blocked: { icon: ShieldAlert, cls: "text-orange-600 bg-orange-50", label: "已拦截" },
};

const SEVERITY_STYLE: Record<string, string> = {
  info: "bg-blue-50 text-blue-700 ring-blue-600/20",
  warning: "bg-amber-50 text-amber-700 ring-amber-600/20",
  critical: "bg-red-50 text-red-700 ring-red-600/20",
};

const SEVERITY_LABEL: Record<string, string> = {
  info: "信息",
  warning: "警告",
  critical: "严重",
};

const ACTOR_ICON: Record<string, ElementType> = {
  agent: Bot,
  human: User,
  system: Cpu,
  service: Cpu,
};

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadLogs = async () => {
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (severityFilter !== "all") {
        params.set("severity", severityFilter);
      }
      const res = await apiFetch<AuditListEnvelope>(`/api/v1/audit/logs?${params.toString()}`);
      const items = res.data?.items ?? [];
      setLogs(items);
      setSelected((prev) => prev ?? items[0]?.id ?? null);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载审计日志失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
    const timer = setInterval(loadLogs, 3000);
    return () => clearInterval(timer);
  }, [severityFilter]);

  const filtered = useMemo(() => {
    return logs.filter((l) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        (l.actor ?? "").toLowerCase().includes(q) ||
        (l.action ?? "").toLowerCase().includes(q) ||
        (l.resource_name ?? "").toLowerCase().includes(q)
      );
    });
  }, [logs, search]);

  const detail = filtered.find((l) => l.id === selected) ?? filtered[0] ?? null;
  const warnings = logs.filter((l) => l.severity === "warning" || l.severity === "critical").length;

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <PageHeader
        title="审计中心"
        description="记录所有 AI 操作、人工决策、策略命中和执行事件"
        actions={
          warnings > 0 ? (
            <span className="text-xs text-amber-600 font-medium bg-amber-50 border border-amber-200 rounded-md px-2 py-1">
              {warnings} 条警告/严重事件
            </span>
          ) : undefined
        }
      />

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            placeholder="搜索操作者、动作、资源..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-9 pl-8 pr-3 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div className="flex items-center gap-1.5 text-sm">
          {["all", "info", "warning", "critical"].map((s) => (
            <button
              key={s}
              onClick={() => setSeverityFilter(s)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                severityFilter === s
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
              )}
            >
              {s === "all" ? "全部" : SEVERITY_LABEL[s] ?? s}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="text-sm text-slate-500 mb-2">正在加载审计日志...</div>}
      {error && <div className="text-sm text-red-600 mb-2">{error}</div>}

      <div className="flex gap-4 flex-1 min-h-0">
        <div className="flex-1 rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          <div className="p-4 space-y-1">
            {filtered.map((log) => {
              const outcome = OUTCOME_STYLE[log.outcome] ?? OUTCOME_STYLE.success;
              const OutcomeIcon = outcome.icon;
              const ActorIcon = ACTOR_ICON[log.actor_type] ?? User;

              return (
                <div
                  key={log.id}
                  onClick={() => setSelected(log.id)}
                  className={cn(
                    "relative flex gap-4 px-4 py-3 rounded-lg cursor-pointer transition-colors group",
                    detail?.id === log.id ? "bg-blue-50 ring-1 ring-blue-200" : "hover:bg-slate-50",
                    log.outcome === "blocked"
                      ? "border-l-2 border-l-orange-400 pl-3"
                      : log.severity === "warning"
                        ? "border-l-2 border-l-amber-400 pl-3"
                        : ""
                  )}
                >
                  <div className={cn("flex h-8 w-8 items-center justify-center rounded-full shrink-0 mt-0.5", outcome.cls)}>
                    <OutcomeIcon className="h-3.5 w-3.5" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold ring-1 ring-inset", SEVERITY_STYLE[log.severity] ?? SEVERITY_STYLE.info)}>
                        {SEVERITY_LABEL[log.severity] ?? log.severity}
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono">{log.event_type}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-sm">
                      <ActorIcon className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                      <span className="font-medium text-slate-800 truncate">{log.actor}</span>
                      <span className="text-slate-400">→</span>
                      <code className="text-xs text-blue-700 bg-blue-50 px-1 py-0.5 rounded font-mono truncate">{log.action}</code>
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs text-slate-500">
                        {log.resource_type || "N/A"} /{" "}
                        <span className="font-medium text-slate-700">{log.resource_name || "-"}</span>
                      </span>
                      <span className="text-[11px] text-slate-400">{formatDate(log.timestamp)}</span>
                    </div>
                    {log.reason && <p className="text-xs text-slate-500 mt-1 italic truncate">{log.reason}</p>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {detail && (
          <div className="w-72 shrink-0 rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
            <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">审计日志详情</p>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">{detail.id}</p>
            </div>

            <div className="px-4 py-4 space-y-4">
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: "事件类型", value: detail.event_type },
                  { label: "严重级别", value: SEVERITY_LABEL[detail.severity] ?? detail.severity },
                  { label: "操作者", value: detail.actor },
                  { label: "操作者类型", value: detail.actor_type },
                  { label: "结果", value: OUTCOME_STYLE[detail.outcome]?.label ?? detail.outcome },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-lg bg-slate-50 border border-slate-100 p-2">
                    <p className="text-[10px] text-slate-400 mb-0.5">{label}</p>
                    <p className="text-xs font-medium text-slate-700 truncate">{value}</p>
                  </div>
                ))}
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">执行动作</p>
                <code className="block text-xs bg-[var(--bg-code)] border border-slate-200 rounded-lg px-3 py-2 font-mono text-blue-700 break-all">
                  {detail.action}
                </code>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">目标资源</p>
                <div className="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2">
                  <p className="text-xs text-slate-500">{detail.resource_type || "N/A"}</p>
                  <p className="text-sm font-semibold text-slate-800">{detail.resource_name || "-"}</p>
                  <p className="text-[11px] text-slate-400 font-mono">{detail.resource_id || "-"}</p>
                </div>
              </div>

              {detail.reason && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">原因说明</p>
                  <p className="text-xs text-slate-700 leading-relaxed">{detail.reason}</p>
                </div>
              )}

              {Object.keys(detail.metadata ?? {}).length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">元数据</p>
                  <pre className="text-xs bg-[var(--bg-code)] border border-slate-200 rounded-lg px-3 py-2 font-mono text-slate-700 overflow-x-auto">
                    {JSON.stringify(detail.metadata, null, 2)}
                  </pre>
                </div>
              )}

              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">追踪信息</p>
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-[11px] text-slate-500">
                    <span className="text-slate-400">request_id：</span>
                    <code className="font-mono text-slate-600">{detail.request_id}</code>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-slate-500">
                    <span className="text-slate-400">trace_id：</span>
                    <code className="font-mono text-slate-600">{detail.trace_id}</code>
                  </div>
                  {detail.incident_ref && (
                    <div className="flex items-center gap-2 text-[11px] text-slate-500">
                      <span className="text-slate-400">incident：</span>
                      <span className="font-medium text-blue-600">{detail.incident_ref}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
