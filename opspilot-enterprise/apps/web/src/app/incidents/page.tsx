"use client";

import { useState } from "react";
import {
  Bot, ChevronRight, Upload, ExternalLink,
  AlertTriangle, Clock, MapPin,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Badge, SeverityBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockIncidents } from "@/lib/mock-data";
import Link from "next/link";

const SEVERITY_BAR: Record<string, string> = {
  critical: "border-l-red-500",
  high:     "border-l-orange-400",
  medium:   "border-l-amber-400",
  low:      "border-l-emerald-400",
  info:     "border-l-slate-300",
};

const STATUS_TABS = [
  { key: "all",            label: "全部" },
  { key: "analyzing",      label: "分析中" },
  { key: "pending_action", label: "待处理" },
  { key: "resolved",       label: "已解决" },
];

export default function IncidentsPage() {
  const [selected, setSelected] = useState<string | null>(mockIncidents[0]?.id ?? null);
  const [filter, setFilter] = useState("all");

  const filtered =
    filter === "all" ? mockIncidents : mockIncidents.filter((i) => i.status === filter);
  const detail = mockIncidents.find((i) => i.id === selected);

  const counts: Record<string, number> = {
    all:            mockIncidents.length,
    analyzing:      mockIncidents.filter((i) => i.status === "analyzing").length,
    pending_action: mockIncidents.filter((i) => i.status === "pending_action").length,
    resolved:       mockIncidents.filter((i) => i.status === "resolved").length,
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      {/* Header + Filters */}
      <PageHeader
        title="故障事件中心"
        description="集中管理告警聚合后的故障事件"
        actions={
          <Button variant="secondary" size="sm">
            <Upload className="h-3.5 w-3.5" />
            导入事件
          </Button>
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
              filter === tab.key
                ? "bg-blue-100 text-blue-700"
                : "bg-slate-100 text-slate-500"
            )}>
              {counts[tab.key]}
            </span>
          </button>
        ))}
      </div>

      {/* Main content */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* Table */}
        <div className="flex-1 rounded-xl border border-slate-200 bg-white overflow-hidden shadow-[0_1px_3px_0_rgb(0_0_0/0.06)] flex flex-col">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500">事件标题</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-slate-500 w-16">级别</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-slate-500 w-20">状态</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-slate-500 w-24">来源系统</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-slate-500 w-32">首次发现</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-slate-500 w-10">AI</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filtered.map((inc) => (
                <tr
                  key={inc.id}
                  onClick={() => setSelected(inc.id)}
                  className={cn(
                    "cursor-pointer transition-colors border-l-2",
                    SEVERITY_BAR[inc.severity] ?? "border-l-transparent",
                    selected === inc.id
                      ? "bg-blue-50 border-l-blue-500!"
                      : "hover:bg-slate-50"
                  )}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900 text-sm truncate max-w-[240px]">{inc.title}</p>
                    <p className="text-[11px] text-slate-400 mt-0.5 font-mono">{inc.id}</p>
                  </td>
                  <td className="px-3 py-3"><SeverityBadge severity={inc.severity} /></td>
                  <td className="px-3 py-3"><StatusBadge status={inc.status} /></td>
                  <td className="px-3 py-3 text-xs text-slate-500">{inc.source}</td>
                  <td className="px-3 py-3">
                    <span className="flex items-center gap-1 text-xs text-slate-500">
                      <Clock className="h-3 w-3 text-slate-300" />
                      {formatDate(inc.first_seen_at)}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    {inc.ai_analysis_triggered && (
                      <Bot className="h-4 w-4 text-blue-500" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Detail Panel */}
        {detail && (
          <div className="w-80 shrink-0 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
            {/* Panel Header */}
            <div className={cn(
              "px-4 py-3 border-b border-slate-100 border-l-4",
              SEVERITY_BAR[detail.severity] ?? ""
            )}>
              <div className="flex items-center justify-between mb-1.5">
                <SeverityBadge severity={detail.severity} />
                <StatusBadge status={detail.status} />
              </div>
              <h3 className="text-sm font-semibold text-slate-900 leading-snug">{detail.title}</h3>
              <p className="text-[11px] text-slate-400 mt-0.5 font-mono">{detail.id}</p>
            </div>

            <div className="px-4 py-4 space-y-5">
              {/* Summary */}
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">事件摘要</p>
                <p className="text-xs text-slate-700 leading-relaxed">{detail.summary}</p>
                <p className="text-[11px] text-slate-400 mt-1.5 flex items-center gap-1">
                  <Clock className="h-3 w-3" /> {formatDate(detail.first_seen_at)}
                </p>
              </div>

              {/* Affected objects */}
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">受影响对象</p>
                <div className="space-y-1.5">
                  {detail.affected_objects.map((o) => (
                    <div key={o.object_id} className="flex items-center gap-2 rounded-md bg-slate-50 px-2.5 py-1.5">
                      <MapPin className="h-3 w-3 text-slate-400 shrink-0" />
                      <Badge variant="neutral">{o.object_type}</Badge>
                      <span className="text-xs text-slate-700 truncate">{o.object_name}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Root cause candidates */}
              {detail.root_cause_candidates.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">根因候选</p>
                  <div className="space-y-2">
                    {detail.root_cause_candidates.map((rc) => (
                      <div key={rc.id} className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
                        <div className="flex items-center justify-between mb-1.5">
                          <Badge variant="info">{rc.category}</Badge>
                          <div className="flex items-center gap-1.5">
                            <div className="h-1 w-16 rounded-full bg-slate-200 overflow-hidden">
                              <div className="h-full bg-blue-500 rounded-full" style={{ width: `${rc.confidence * 100}%` }} />
                            </div>
                            <span className="text-[11px] font-semibold text-slate-600">{(rc.confidence * 100).toFixed(0)}%</span>
                          </div>
                        </div>
                        <p className="text-xs text-slate-700">{rc.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommended actions */}
              {detail.recommended_actions.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">建议动作</p>
                  <ul className="space-y-1">
                    {detail.recommended_actions.map((a, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-xs text-slate-700">
                        <ChevronRight className="h-3.5 w-3.5 text-slate-400 mt-0.5 shrink-0" />
                        {a}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* CTA */}
              <Link href={`/diagnosis?incident=${detail.id}`} className="block">
                <Button variant="primary" size="sm" className="w-full">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  进入诊断工作台
                  <ExternalLink className="h-3 w-3 ml-auto" />
                </Button>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
