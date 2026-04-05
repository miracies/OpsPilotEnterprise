"use client";

import { useState } from "react";
import {
  Shield, ToggleLeft, ToggleRight, AlertTriangle,
  CheckCircle2, XCircle, Eye, Code2, Clock,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockPolicies, mockPolicyHits } from "@/lib/mock-data";

const TYPE_LABEL: Record<string, string> = {
  approval_gate:  "审批门控",
  rate_limit:     "频率限制",
  scope_guard:    "范围保护",
  time_window:    "时间窗口",
  risk_threshold: "风险阈值",
  audit_only:     "仅审计",
};

const TYPE_COLOR: Record<string, string> = {
  approval_gate:  "bg-amber-50 text-amber-700",
  rate_limit:     "bg-blue-50 text-blue-700",
  scope_guard:    "bg-purple-50 text-purple-700",
  time_window:    "bg-sky-50 text-sky-700",
  risk_threshold: "bg-orange-50 text-orange-700",
  audit_only:     "bg-slate-100 text-slate-600",
};

const EFFECT_COLOR: Record<string, string> = {
  allow:            "bg-emerald-50 text-emerald-700",
  deny:             "bg-red-50 text-red-700",
  require_approval: "bg-amber-50 text-amber-700",
  alert_only:       "bg-blue-50 text-blue-700",
};

const EFFECT_LABEL: Record<string, string> = {
  allow:            "允许",
  deny:             "拒绝",
  require_approval: "要求审批",
  alert_only:       "仅告警",
};

const OUTCOME_STYLE: Record<string, { cls: string; label: string }> = {
  blocked:   { cls: "bg-red-50 text-red-700",     label: "已拦截" },
  allowed:   { cls: "bg-emerald-50 text-emerald-700", label: "已放行" },
  escalated: { cls: "bg-amber-50 text-amber-700",  label: "已升级" },
};

export default function PoliciesPage() {
  const [selected, setSelected] = useState<string | null>(mockPolicies[0]?.id ?? null);
  const [showRego, setShowRego] = useState(false);

  const detail = mockPolicies.find((p) => p.id === selected);
  const detailHits = detail ? mockPolicyHits.filter((h) => h.policy_id === detail.id) : [];

  const active = mockPolicies.filter((p) => p.status === "active").length;
  const totalHits = mockPolicies.reduce((acc, p) => acc + p.hit_count, 0);

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <PageHeader
        title="策略管理"
        description="AI 操作安全门控策略：审批规则、范围保护和时间窗口限制"
        actions={
          <div className="flex items-center gap-2 text-xs">
            <span className="text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-md px-2 py-1">
              {active} 个启用
            </span>
            <span className="text-slate-600 bg-slate-100 border border-slate-200 rounded-md px-2 py-1">
              累计命中 {totalHits} 次
            </span>
          </div>
        }
      />

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Policy list */}
        <div className="flex-1 rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          <div className="sticky top-0 bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">策略列表</span>
            <span className="text-xs text-slate-400">{mockPolicies.length} 条</span>
          </div>
          <div className="divide-y divide-slate-50">
            {mockPolicies.map((pol) => (
              <div
                key={pol.id}
                onClick={() => setSelected(pol.id)}
                className={cn(
                  "px-5 py-4 cursor-pointer transition-colors",
                  selected === pol.id ? "bg-blue-50" : "hover:bg-slate-50",
                  pol.status === "inactive" ? "opacity-60" : ""
                )}
              >
                <div className="flex items-start gap-3">
                  <div className={cn(
                    "h-10 w-10 rounded-xl flex items-center justify-center shrink-0 mt-0.5",
                    pol.status === "active" ? "bg-blue-50" : "bg-slate-100"
                  )}>
                    <Shield className={cn("h-4 w-4", pol.status === "active" ? "text-blue-500" : "text-slate-400")} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold", TYPE_COLOR[pol.type])}>
                        {TYPE_LABEL[pol.type] ?? pol.type}
                      </span>
                      <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold", EFFECT_COLOR[pol.effect])}>
                        {EFFECT_LABEL[pol.effect] ?? pol.effect}
                      </span>
                      {pol.status === "active" ? (
                        <span className="text-[10px] text-emerald-600 font-medium flex items-center gap-0.5">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" /> 启用
                        </span>
                      ) : (
                        <span className="text-[10px] text-slate-400 font-medium">停用</span>
                      )}
                    </div>
                    <p className="text-sm font-semibold text-slate-900">{pol.name}</p>
                    <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">{pol.description}</p>
                    <div className="flex items-center gap-3 mt-1.5 text-[11px] text-slate-400">
                      <span>命中 {pol.hit_count} 次</span>
                      {pol.last_hit_at && <span>最近：{formatDate(pol.last_hit_at)}</span>}
                      <span>v{pol.version}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Policy detail */}
        {detail && (
          <div className="w-80 shrink-0 rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
            <div className="px-4 py-3 border-b border-slate-100">
              <div className="flex items-center justify-between mb-1.5">
                <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold", EFFECT_COLOR[detail.effect])}>
                  {EFFECT_LABEL[detail.effect]}
                </span>
                <span className={cn(
                  "inline-flex items-center gap-1 text-[10px] font-semibold",
                  detail.status === "active" ? "text-emerald-600" : "text-slate-400"
                )}>
                  {detail.status === "active" ? (
                    <><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> 启用</>
                  ) : "停用"}
                </span>
              </div>
              <h3 className="text-sm font-semibold text-slate-900">{detail.name}</h3>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">{detail.id} · v{detail.version}</p>
            </div>

            <div className="px-4 py-4 space-y-4">
              <p className="text-xs text-slate-700 leading-relaxed">{detail.description}</p>

              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">作用范围</p>
                <div className="flex flex-wrap gap-1.5">
                  {detail.scope.map((s) => (
                    <Badge key={s} variant="neutral"><code className="text-[10px]">{s}</code></Badge>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">触发条件</p>
                <pre className="text-xs bg-[var(--bg-code)] border border-slate-200 rounded-lg px-3 py-2 font-mono text-slate-700 overflow-x-auto">
                  {JSON.stringify(detail.conditions, null, 2)}
                </pre>
              </div>

              {detail.rego_snippet && (
                <div>
                  <button
                    onClick={() => setShowRego(!showRego)}
                    className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider hover:text-slate-700 transition-colors"
                  >
                    <Code2 className="h-3 w-3" /> OPA Rego 策略
                    <span className="text-[10px] text-blue-600 ml-1">{showRego ? "收起" : "展开"}</span>
                  </button>
                  {showRego && (
                    <pre className="mt-1.5 text-xs bg-[var(--bg-code)] border border-slate-200 rounded-lg px-3 py-2 font-mono text-slate-700 overflow-x-auto whitespace-pre-wrap">
                      {detail.rego_snippet}
                    </pre>
                  )}
                </div>
              )}

              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">命中记录</p>
                {detailHits.length > 0 ? (
                  <div className="space-y-2">
                    {detailHits.map((hit) => {
                      const os = OUTCOME_STYLE[hit.outcome] ?? OUTCOME_STYLE.blocked;
                      return (
                        <div key={hit.id} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                          <div className="flex items-center justify-between mb-1">
                            <span className={cn("text-[10px] font-semibold rounded px-1.5 py-0.5", os.cls)}>{os.label}</span>
                            <span className="text-[10px] text-slate-400">{formatDate(hit.timestamp)}</span>
                          </div>
                          <p className="text-xs text-slate-700">
                            <span className="font-medium">{hit.actor}</span>
                            <span className="text-slate-400"> → </span>
                            <code className="text-blue-600 font-mono text-[10px]">{hit.tool_name}</code>
                          </p>
                          <p className="text-[11px] text-slate-400 mt-0.5">目标：{hit.resource}</p>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">暂无命中记录</p>
                )}
              </div>

              <div className="flex gap-2 pt-1 border-t border-slate-100">
                <Button
                  variant="secondary"
                  size="sm"
                  className={cn("flex-1", detail.status === "active" ? "text-slate-600" : "text-emerald-700 border-emerald-200 hover:bg-emerald-50")}
                >
                  {detail.status === "active" ? (
                    <><ToggleRight className="h-3.5 w-3.5 text-emerald-600" /> 停用策略</>
                  ) : (
                    <><ToggleLeft className="h-3.5 w-3.5" /> 启用策略</>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
