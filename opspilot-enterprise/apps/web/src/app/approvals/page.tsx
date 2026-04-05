"use client";

import { useState } from "react";
import {
  ShieldCheck, Clock, AlertTriangle, CheckCircle2,
  XCircle, ChevronRight, ExternalLink, User, FileText,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge, SeverityBadge, RiskBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockApprovals } from "@/lib/mock-data";
import Link from "next/link";

const STATUS_TABS = [
  { key: "all",      label: "全部" },
  { key: "pending",  label: "待审批" },
  { key: "approved", label: "已通过" },
  { key: "rejected", label: "已驳回" },
  { key: "expired",  label: "已过期" },
];

const STATUS_STYLE: Record<string, string> = {
  pending:  "bg-amber-50 text-amber-700 ring-amber-600/20",
  approved: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  rejected: "bg-red-50 text-red-700 ring-red-600/20",
  expired:  "bg-slate-100 text-slate-500 ring-slate-300",
  recalled: "bg-slate-100 text-slate-500 ring-slate-300",
};

const STATUS_LABEL: Record<string, string> = {
  pending:  "待审批",
  approved: "已通过",
  rejected: "已驳回",
  expired:  "已过期",
  recalled: "已撤回",
};

export default function ApprovalsPage() {
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<string | null>(mockApprovals[0]?.id ?? null);

  const filtered = filter === "all" ? mockApprovals : mockApprovals.filter((a) => a.status === filter);
  const detail = mockApprovals.find((a) => a.id === selected);

  const counts: Record<string, number> = {
    all:      mockApprovals.length,
    pending:  mockApprovals.filter((a) => a.status === "pending").length,
    approved: mockApprovals.filter((a) => a.status === "approved").length,
    rejected: mockApprovals.filter((a) => a.status === "rejected").length,
    expired:  mockApprovals.filter((a) => a.status === "expired").length,
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <PageHeader
        title="审批中心"
        description="待审批执行请求与高风险操作管控"
        actions={
          <div className="flex items-center gap-2">
            <span className="text-xs text-amber-600 font-medium bg-amber-50 border border-amber-200 rounded-md px-2 py-1">
              {counts.pending} 项待审批
            </span>
          </div>
        }
      />

      {/* Status Tabs */}
      <div className="flex items-center gap-1 mb-4 border-b border-slate-200">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium transition-all border-b-2 -mb-px",
              filter === tab.key
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
            )}
          >
            {tab.label}
            <span className={cn(
              "ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold",
              filter === tab.key ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-500"
            )}>
              {counts[tab.key] ?? 0}
            </span>
          </button>
        ))}
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        {/* List */}
        <div className="flex-1 rounded-xl border border-slate-200 bg-white overflow-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">申请标题</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-slate-500 w-20">操作类型</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-slate-500 w-20">风险等级</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-slate-500 w-20">状态</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-slate-500 w-20">申请人</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-slate-500 w-32">申请时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filtered.map((apr) => (
                <tr
                  key={apr.id}
                  onClick={() => setSelected(apr.id)}
                  className={cn(
                    "cursor-pointer transition-colors hover:bg-slate-50",
                    selected === apr.id ? "bg-blue-50" : "",
                    apr.status === "pending" ? "border-l-2 border-l-amber-400" : ""
                  )}
                >
                  <td className="px-5 py-3">
                    <p className="font-medium text-slate-900 truncate max-w-[260px]">{apr.title}</p>
                    <p className="text-[11px] text-slate-400 font-mono mt-0.5">{apr.id}</p>
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant="neutral">{apr.action_type}</Badge>
                  </td>
                  <td className="px-3 py-3"><RiskBadge level={apr.risk_level} /></td>
                  <td className="px-3 py-3">
                    <span className={cn("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset", STATUS_STYLE[apr.status] ?? STATUS_STYLE.expired)}>
                      {STATUS_LABEL[apr.status] ?? apr.status}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-xs text-slate-600">{apr.requester}</td>
                  <td className="px-3 py-3 text-xs text-slate-500 flex items-center gap-1">
                    <Clock className="h-3 w-3 text-slate-300" />
                    {formatDate(apr.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Detail */}
        {detail && (
          <div className="w-80 shrink-0 rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
            <div className={cn(
              "px-4 py-3 border-b border-slate-100 border-l-4",
              detail.risk_level === "critical" ? "border-l-red-500" :
              detail.risk_level === "high" ? "border-l-orange-400" :
              detail.risk_level === "medium" ? "border-l-amber-400" : "border-l-emerald-400"
            )}>
              <div className="flex items-center justify-between mb-1.5">
                <RiskBadge level={detail.risk_level} />
                <span className={cn("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset", STATUS_STYLE[detail.status])}>
                  {STATUS_LABEL[detail.status]}
                </span>
              </div>
              <h3 className="text-sm font-semibold text-slate-900 leading-snug">{detail.title}</h3>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">{detail.id}</p>
            </div>

            <div className="px-4 py-4 space-y-5">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">变更描述</p>
                <p className="text-xs text-slate-700 leading-relaxed">{detail.description}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-slate-50 border border-slate-100 p-2.5">
                  <p className="text-[10px] text-slate-400 mb-0.5">目标对象</p>
                  <p className="text-xs font-medium text-slate-700">{detail.target_object}</p>
                  <p className="text-[10px] text-slate-400">{detail.target_object_type}</p>
                </div>
                <div className="rounded-lg bg-slate-50 border border-slate-100 p-2.5">
                  <p className="text-[10px] text-slate-400 mb-0.5">风险评分</p>
                  <p className={cn("text-lg font-bold",
                    detail.risk_score >= 60 ? "text-red-600" :
                    detail.risk_score >= 30 ? "text-amber-600" : "text-emerald-600"
                  )}>{detail.risk_score}</p>
                  <p className="text-[10px] text-slate-400">/ 100</p>
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">关联信息</p>
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 text-xs">
                    <User className="h-3.5 w-3.5 text-slate-400" />
                    <span className="text-slate-500">申请人：</span>
                    <span className="text-slate-700 font-medium">{detail.requester}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <User className="h-3.5 w-3.5 text-slate-400" />
                    <span className="text-slate-500">审批人：</span>
                    <span className="text-slate-700 font-medium">{detail.assignee ?? "未指派"}</span>
                  </div>
                  {detail.incident_ref && (
                    <div className="flex items-center gap-2 text-xs">
                      <AlertTriangle className="h-3.5 w-3.5 text-slate-400" />
                      <span className="text-slate-500">关联事件：</span>
                      <Link href="/incidents" className="text-blue-600 hover:underline font-medium">{detail.incident_ref}</Link>
                    </div>
                  )}
                  {detail.change_analysis_ref && (
                    <div className="flex items-center gap-2 text-xs">
                      <FileText className="h-3.5 w-3.5 text-slate-400" />
                      <span className="text-slate-500">变更分析：</span>
                      <Link href="/change-impact" className="text-blue-600 hover:underline font-medium">{detail.change_analysis_ref}</Link>
                    </div>
                  )}
                  {detail.expires_at && (
                    <div className="flex items-center gap-2 text-xs">
                      <Clock className="h-3.5 w-3.5 text-slate-400" />
                      <span className="text-slate-500">过期时间：</span>
                      <span className="text-amber-600 font-medium">{formatDate(detail.expires_at)}</span>
                    </div>
                  )}
                </div>
              </div>

              {detail.decision_comment && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">审批意见</p>
                  <div className={cn("rounded-lg border px-3 py-2.5 text-xs",
                    detail.status === "approved" ? "bg-emerald-50 border-emerald-200 text-emerald-700" :
                    detail.status === "rejected" ? "bg-red-50 border-red-200 text-red-700" : "bg-slate-50 border-slate-100 text-slate-700"
                  )}>
                    {detail.decision_comment}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">
                    {detail.decided_by} · {detail.decided_at ? formatDate(detail.decided_at) : ""}
                  </p>
                </div>
              )}

              {detail.status === "pending" && (
                <div className="flex gap-2 pt-1">
                  <Button variant="primary" size="sm" className="flex-1">
                    <CheckCircle2 className="h-3.5 w-3.5" /> 通过
                  </Button>
                  <Button variant="secondary" size="sm" className="flex-1 text-red-600 border-red-200 hover:bg-red-50">
                    <XCircle className="h-3.5 w-3.5" /> 驳回
                  </Button>
                </div>
              )}

              <div className="flex gap-2 flex-wrap">
                {detail.tags.map((t) => (
                  <Badge key={t} variant="neutral">{t}</Badge>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
