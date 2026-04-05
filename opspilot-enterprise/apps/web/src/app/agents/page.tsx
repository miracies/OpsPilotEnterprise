"use client";

import { useState } from "react";
import {
  Bot, CheckCircle2, XCircle, Loader2, Clock,
  Zap, ChevronRight, Activity, Network, BarChart3,
  AlertCircle,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockAgentRuns } from "@/lib/mock-data";
import Link from "next/link";

const STATUS_META: Record<string, { icon: React.ElementType; cls: string; label: string }> = {
  completed: { icon: CheckCircle2, cls: "bg-emerald-100 text-emerald-700", label: "已完成" },
  running:   { icon: Loader2,      cls: "bg-blue-100 text-blue-700",       label: "运行中" },
  failed:    { icon: XCircle,      cls: "bg-red-100 text-red-700",         label: "失败" },
  queued:    { icon: Clock,        cls: "bg-slate-100 text-slate-600",     label: "排队中" },
  cancelled: { icon: XCircle,      cls: "bg-slate-100 text-slate-500",     label: "已取消" },
};

const STEP_STATUS: Record<string, { icon: React.ElementType; cls: string }> = {
  done:    { icon: CheckCircle2, cls: "text-emerald-600" },
  running: { icon: Loader2,      cls: "text-blue-600 animate-spin" },
  waiting: { icon: Clock,        cls: "text-slate-400" },
  failed:  { icon: XCircle,      cls: "text-red-600" },
  skipped: { icon: AlertCircle,  cls: "text-slate-400" },
};

export default function AgentsPage() {
  const [selected, setSelected] = useState<string>(mockAgentRuns[0]?.id ?? "");
  const detail = mockAgentRuns.find((r) => r.id === selected);

  const running = mockAgentRuns.filter((r) => r.status === "running").length;
  const totalTools = mockAgentRuns.reduce((acc, r) => acc + r.total_tool_calls, 0);

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <PageHeader
        title="SubAgent 运行视图"
        description="实时监控 AI Agent 执行流程、工具调用、阶段耗时与输入输出摘要"
        actions={
          running > 0 ? (
            <span className="text-xs text-blue-600 font-medium bg-blue-50 border border-blue-200 rounded-md px-2 py-1 flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
              {running} 个运行中
            </span>
          ) : undefined
        }
      />

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Run list */}
        <div className="w-80 shrink-0 rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          <div className="sticky top-0 bg-slate-50 border-b border-slate-200 px-4 py-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">执行记录</p>
          </div>
          <div className="divide-y divide-slate-50">
            {mockAgentRuns.map((run) => {
              const meta = STATUS_META[run.status] ?? STATUS_META.queued;
              const StatusIcon = meta.icon;
              return (
                <div
                  key={run.id}
                  onClick={() => setSelected(run.id)}
                  className={cn(
                    "px-4 py-3 cursor-pointer transition-colors",
                    selected === run.id ? "bg-blue-50" : "hover:bg-slate-50",
                    run.status === "running" ? "border-l-2 border-l-blue-400" : ""
                  )}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold", meta.cls)}>
                      <StatusIcon className={cn("h-2.5 w-2.5", run.status === "running" ? "animate-spin" : "")} />
                      {meta.label}
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono">{run.id}</span>
                  </div>
                  <p className="text-xs font-medium text-slate-800 truncate">
                    <code className="bg-slate-100 rounded px-1 py-0.5 text-[10px]">{run.intent}</code>
                  </p>
                  <div className="flex items-center gap-3 mt-1.5">
                    <span className="text-[11px] text-slate-400 flex items-center gap-1">
                      <Zap className="h-3 w-3" /> {run.total_tool_calls} 工具调用
                    </span>
                    {run.total_duration_ms && (
                      <span className="text-[11px] text-slate-400">{(run.total_duration_ms / 1000).toFixed(1)}s</span>
                    )}
                    <span className="text-[11px] text-slate-400">{run.trigger}</span>
                  </div>
                  {run.incident_ref && (
                    <p className="text-[11px] text-slate-400 mt-0.5">→ {run.incident_ref}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Run detail */}
        {detail && (
          <div className="flex-1 rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
            {/* Header */}
            <div className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={cn("flex h-9 w-9 items-center justify-center rounded-xl", STATUS_META[detail.status]?.cls)}>
                    <Bot className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">
                      <code className="bg-slate-100 px-1.5 py-0.5 rounded text-sm">{detail.intent}</code>
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">{detail.id} · 触发方式：{detail.trigger}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1"><Zap className="h-3 w-3 text-slate-400" />{detail.total_tool_calls} 工具调用</span>
                  {detail.total_duration_ms && (
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3 text-slate-400" />{(detail.total_duration_ms / 1000).toFixed(1)}s</span>
                  )}
                  {detail.incident_ref && (
                    <Link href="/incidents" className="text-blue-600 hover:underline flex items-center gap-1">
                      <AlertCircle className="h-3 w-3" />{detail.incident_ref}
                    </Link>
                  )}
                </div>
              </div>
              {detail.output_summary && (
                <p className="mt-2 text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">{detail.output_summary}</p>
              )}
            </div>

            {/* Steps timeline */}
            <div className="px-6 py-5">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">执行阶段 ({detail.steps.length})</p>
              <div className="relative">
                {/* Vertical line */}
                <div className="absolute left-[19px] top-5 bottom-5 w-px bg-slate-200" />

                <div className="space-y-4">
                  {detail.steps.map((step, idx) => {
                    const statusMeta = STEP_STATUS[step.status] ?? STEP_STATUS.waiting;
                    const StepIcon = statusMeta.icon;

                    return (
                      <div key={step.step_id} className="relative flex gap-4">
                        {/* Dot */}
                        <div className={cn(
                          "relative z-10 flex h-10 w-10 items-center justify-center rounded-full border-2 bg-white shrink-0",
                          step.status === "done" ? "border-emerald-200" :
                          step.status === "running" ? "border-blue-300" :
                          step.status === "failed" ? "border-red-200" : "border-slate-200"
                        )}>
                          <StepIcon className={cn("h-4 w-4", statusMeta.cls)} />
                        </div>

                        {/* Content */}
                        <div className="flex-1 rounded-xl border border-slate-200 bg-slate-50/50 p-4">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <p className="text-sm font-semibold text-slate-800">{step.agent_name}</p>
                              <Badge variant="neutral">Step {idx + 1}</Badge>
                              {step.tool_calls > 0 && (
                                <span className="text-[11px] text-slate-500 flex items-center gap-1">
                                  <Zap className="h-3 w-3 text-blue-400" />{step.tool_calls} tools
                                </span>
                              )}
                            </div>
                            {step.duration_ms != null && (
                              <span className="text-[11px] text-slate-400">{step.duration_ms}ms</span>
                            )}
                          </div>

                          <div className="space-y-2">
                            <div>
                              <p className="text-[10px] text-slate-400 mb-0.5 uppercase tracking-wider">输入</p>
                              <code className="block text-xs bg-[var(--bg-code)] border border-slate-200 rounded px-2.5 py-1.5 font-mono text-slate-700 break-all">{step.input_summary}</code>
                            </div>
                            {step.output_summary && (
                              <div>
                                <p className="text-[10px] text-slate-400 mb-0.5 uppercase tracking-wider">输出</p>
                                <code className="block text-xs bg-emerald-50/50 border border-emerald-100 rounded px-2.5 py-1.5 font-mono text-emerald-700 break-all">{step.output_summary}</code>
                              </div>
                            )}
                            {step.error && (
                              <div>
                                <p className="text-[10px] text-red-400 mb-0.5 uppercase tracking-wider">错误</p>
                                <code className="block text-xs bg-red-50 border border-red-100 rounded px-2.5 py-1.5 font-mono text-red-700 break-all">{step.error}</code>
                              </div>
                            )}
                          </div>

                          {(step.started_at || step.completed_at) && (
                            <div className="flex items-center gap-4 mt-2 text-[11px] text-slate-400">
                              {step.started_at && <span>开始：{formatDate(step.started_at)}</span>}
                              {step.completed_at && <span>结束：{formatDate(step.completed_at)}</span>}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
