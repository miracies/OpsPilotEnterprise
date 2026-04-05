"use client";

import {
  FileText, BookOpen, Archive, Wrench,
  CheckCircle2, Clock, Radio, AlertCircle,
  Download, Play,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge, SeverityBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockIncidents, mockEvidences, mockIncidentTimeline } from "@/lib/mock-data";

const incident = mockIncidents[0];
const evidences = mockEvidences.filter((e) => incident.evidence_refs.includes(e.evidence_id));

const TIMELINE_COLORS: Record<string, string> = {
  event:        "bg-red-500 ring-red-100",
  analysis:     "bg-blue-500 ring-blue-100",
  notification: "bg-amber-500 ring-amber-100",
  action:       "bg-emerald-500 ring-emerald-100",
};
const TIMELINE_TEXT: Record<string, string> = {
  event:        "text-red-600",
  analysis:     "text-blue-600",
  notification: "text-amber-600",
  action:       "text-emerald-600",
};
const TIMELINE_LABEL: Record<string, string> = {
  event:        "事件",
  analysis:     "AI分析",
  notification: "通知",
  action:       "执行",
};

const AGENT_LIST = [
  { name: "IntentAgent",            status: "done" },
  { name: "EvidenceCollectionAgent", status: "done" },
  { name: "KBRetrievalAgent",       status: "done" },
  { name: "RCAAgent",               status: "done" },
  { name: "NotificationAgent",      status: "done" },
];

export default function DiagnosisPage() {
  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <PageHeader
        title="诊断工作台"
        description={incident.title}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm">
              <Download className="h-3.5 w-3.5" />
              导出报告
            </Button>
            <Button variant="primary" size="sm">
              <Play className="h-3.5 w-3.5" />
              发起执行申请
            </Button>
          </div>
        }
      />

      <div className="flex gap-4 flex-1 min-h-0">
        {/* ── Left Column: Context ─────────── */}
        <div className="w-56 shrink-0 space-y-3 overflow-y-auto">
          {/* Incident summary */}
          <Card>
            <CardHeader>
              <CardTitle>事件摘要</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              <div className="flex items-center gap-1.5">
                <SeverityBadge severity={incident.severity} />
                <StatusBadge status={incident.status} />
              </div>
              <p className="text-xs text-slate-700 leading-relaxed">{incident.summary}</p>
              <p className="text-[11px] text-slate-400 flex items-center gap-1">
                <Clock className="h-3 w-3" /> {formatDate(incident.first_seen_at)}
              </p>
            </CardContent>
          </Card>

          {/* Affected resources */}
          <Card>
            <CardHeader>
              <CardTitle>受影响资源</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {incident.affected_objects.map((o) => (
                <div key={o.object_id} className="flex items-center gap-1.5 rounded-md bg-slate-50 px-2 py-1.5">
                  <Radio className="h-2.5 w-2.5 text-red-400 shrink-0" />
                  <Badge variant="neutral">{o.object_type}</Badge>
                  <span className="text-xs text-slate-700 truncate">{o.object_name}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Related alerts */}
          <Card>
            <CardHeader>
              <CardTitle>相关告警</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {[
                "CPU > 95% 持续 30min",
                "CPU ready time > 10%",
              ].map((alert) => (
                <div key={alert} className="flex items-start gap-1.5 text-xs text-slate-700">
                  <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0 mt-0.5" />
                  {alert}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* ── Center Column: Analysis ──────── */}
        <div className="flex-1 min-w-0 overflow-y-auto space-y-4">
          {/* Root cause candidates */}
          <Card>
            <CardHeader>
              <CardTitle>根因候选</CardTitle>
              <span className="text-xs text-slate-400">AI 可解释性输出</span>
            </CardHeader>
            <CardContent className="space-y-3">
              {incident.root_cause_candidates.map((rc, i) => (
                <div
                  key={rc.id}
                  className={cn(
                    "rounded-xl border p-4",
                    i === 0
                      ? "border-blue-200 bg-blue-50/50"
                      : "border-slate-100 bg-slate-50/50"
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold",
                        i === 0 ? "bg-blue-600 text-white" : "bg-slate-200 text-slate-600"
                      )}>
                        {i + 1}
                      </span>
                      <Badge variant={i === 0 ? "default" : "neutral"}>{rc.category}</Badge>
                      {i === 0 && (
                        <Badge variant="info" className="text-[10px]">最高置信</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-1.5 rounded-full bg-slate-200 overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
                            i === 0 ? "bg-blue-500" : "bg-slate-400"
                          )}
                          style={{ width: `${rc.confidence * 100}%` }}
                        />
                      </div>
                      <span className={cn(
                        "text-xs font-semibold w-8 text-right",
                        i === 0 ? "text-blue-700" : "text-slate-500"
                      )}>
                        {(rc.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <p className="text-sm text-slate-900 leading-relaxed">{rc.description}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <FileText className="h-3 w-3 text-slate-400" />
                    <span className="text-xs text-slate-500">关联证据 {rc.evidence_refs.length} 条</span>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Timeline */}
          <Card>
            <CardHeader>
              <CardTitle>证据时间线</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="relative pl-6">
                {mockIncidentTimeline.map((entry, i) => (
                  <div key={i} className="relative pb-5 last:pb-0">
                    {i < mockIncidentTimeline.length - 1 && (
                      <span className="absolute left-[-17px] top-5 w-px h-full bg-slate-100" />
                    )}
                    <span className={cn(
                      "absolute left-[-21px] top-0.5 h-4 w-4 rounded-full flex items-center justify-center ring-4",
                      TIMELINE_COLORS[entry.type] ?? "bg-slate-400 ring-slate-100"
                    )}>
                    </span>
                    <div>
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className={cn(
                          "text-[10px] font-semibold uppercase tracking-wide",
                          TIMELINE_TEXT[entry.type] ?? "text-slate-500"
                        )}>
                          {TIMELINE_LABEL[entry.type] ?? entry.type}
                        </span>
                        {entry.agent && <Badge variant="neutral">{entry.agent}</Badge>}
                      </div>
                      <p className="text-sm text-slate-900">{entry.summary}</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">{formatDate(entry.timestamp)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Recommended actions */}
          <Card>
            <CardHeader>
              <CardTitle>建议动作</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {incident.recommended_actions.map((a, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2.5 hover:border-blue-200 hover:bg-blue-50/40 transition-colors group"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-[10px] font-bold text-blue-700">
                      {i + 1}
                    </span>
                    <span className="text-sm text-slate-700">{a}</span>
                  </div>
                  <Button variant="ghost" size="xs" className="opacity-0 group-hover:opacity-100 transition-opacity text-blue-600 hover:bg-blue-100">
                    <Play className="h-3 w-3" /> 执行
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* ── Right Column: Aux ────────────── */}
        <div className="w-64 shrink-0 overflow-y-auto space-y-3">
          {/* Agent trace */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <Wrench className="h-3.5 w-3.5 text-slate-400" /> Agent 轨迹
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {AGENT_LIST.map((a, i) => (
                <div key={a.name} className="flex items-center gap-2 py-1 border-b border-slate-50 last:border-0">
                  <div className="flex items-center justify-center h-5 w-5 rounded-full bg-slate-100 text-[10px] font-bold text-slate-500 shrink-0">
                    {i + 1}
                  </div>
                  <span className="text-xs text-slate-700 flex-1 font-mono">{a.name}</span>
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                </div>
              ))}
            </CardContent>
          </Card>

          {/* KB hits */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <BookOpen className="h-3.5 w-3.5 text-slate-400" /> 知识库命中
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {evidences.filter((e) => e.source_type === "kb").length === 0 ? (
                <p className="text-xs text-slate-400">无命中结果</p>
              ) : evidences.filter((e) => e.source_type === "kb").map((e) => (
                <div key={e.evidence_id} className="evidence-block">
                  <p className="font-semibold text-slate-700 mb-0.5">{e.summary}</p>
                  <p className="text-slate-400 mt-1">置信度: {(e.confidence * 100).toFixed(0)}%</p>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Similar cases */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <Archive className="h-3.5 w-3.5 text-slate-400" /> 相似案例
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="evidence-block">
                <p className="font-semibold text-slate-700 mb-1">CASE-20260320</p>
                <p className="text-slate-600">类似 Java GC 风暴导致主机 CPU 飙升</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-slate-400">2026-03-20</span>
                  <Badge variant="info">相似度 82%</Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Evidence list */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5 text-slate-400" /> 关联证据
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {evidences.map((e) => (
                <div key={e.evidence_id} className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
                  <div className="flex items-center justify-between mb-1.5">
                    <Badge variant="neutral">{e.source_type}</Badge>
                    <div className="flex items-center gap-1.5">
                      <div className="h-1 w-12 rounded-full bg-slate-200 overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${e.confidence * 100}%` }} />
                      </div>
                      <span className="text-[11px] text-slate-500">{(e.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-700 leading-relaxed">{e.summary}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
