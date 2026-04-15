"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  FileText, BookOpen, Archive, Wrench,
  CheckCircle2, Clock, Radio, AlertCircle,
  Download, Play, Bot, ShieldCheck, Loader2, MessageSquare,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge, SeverityBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { mockIncidents, mockEvidences, mockIncidentTimeline } from "@/lib/mock-data";
import Link from "next/link";

interface DiagnosisData {
  diagnosis_id: string;
  session_id?: string;
  description: string;
  assistant_message: string;
  root_cause_candidates: Array<{ description: string; confidence: number; category?: string }>;
  evidence_refs: string[];
  evidences: Array<{ evidence_id: string; source_type: string; summary: string; confidence: number; timestamp: string }>;
  recommended_actions: string[];
  tool_traces: Array<{ tool_name: string; gateway: string; input_summary: string; output_summary: string; duration_ms: number; status: string; timestamp: string }>;
  created_at?: string;
}

const IPV4_RE = /\b(?:\d{1,3}\.){3}\d{1,3}\b/;

const TIMELINE_COLORS: Record<string, string> = {
  event: "bg-red-500 ring-red-100",
  analysis: "bg-blue-500 ring-blue-100",
  notification: "bg-amber-500 ring-amber-100",
  action: "bg-emerald-500 ring-emerald-100",
};
const TIMELINE_TEXT: Record<string, string> = {
  event: "text-red-600",
  analysis: "text-blue-600",
  notification: "text-amber-600",
  action: "text-emerald-600",
};
const TIMELINE_LABEL: Record<string, string> = {
  event: "事件",
  analysis: "AI分析",
  notification: "通知",
  action: "执行",
};

export default function DiagnosisPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const diagnosisId = searchParams.get("diagnosis_id");
  const [diagData, setDiagData] = useState<DiagnosisData | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionRunningIndex, setActionRunningIndex] = useState<number | null>(null);
  const [actionExecResult, setActionExecResult] = useState<{
    action: string;
    status: "success" | "error";
    summary: string;
    detail?: unknown;
    tool_name?: string;
    ts: string;
  } | null>(null);

  useEffect(() => {
    if (!diagnosisId) return;
    setLoading(true);
    apiFetch<{ success: boolean; data: DiagnosisData }>(`/api/v1/chat/diagnoses/${diagnosisId}`)
      .then((res) => {
        if (res.success) setDiagData(res.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [diagnosisId]);

  // Choose data source: API diagnosis or mock fallback
  const useMock = !diagnosisId || !diagData;
  const incident = useMock ? mockIncidents[0] : null;
  const evidences = useMock
    ? mockEvidences.filter((e) => incident!.evidence_refs.includes(e.evidence_id))
    : diagData!.evidences;
  const rootCauseCandidates = useMock
    ? incident!.root_cause_candidates
    : diagData!.root_cause_candidates.map((rc, i) => ({
        id: `rc-${i}`,
        description: rc.description,
        confidence: rc.confidence,
        category: rc.category ?? "unknown",
        evidence_refs: diagData!.evidence_refs,
      }));
  const recommendedActions = useMock
    ? incident!.recommended_actions
    : diagData!.recommended_actions;
  const toolTraces = useMock ? [] : diagData!.tool_traces;
  const title = useMock ? incident!.title : diagData!.description;
  const diagId = useMock ? undefined : diagData!.diagnosis_id;
  const sessionId = useMock ? undefined : diagData!.session_id;
  const incidentId = useMock ? incident?.id : undefined;
  const primaryTarget = useMock ? incident?.affected_objects?.[0] : undefined;
  const executionHref = (() => {
    const query = new URLSearchParams();
    if (incidentId) query.set("incident_id", incidentId);
    if (sessionId) query.set("session_id", sessionId);
    if (primaryTarget) {
      query.set(
        "targets",
        JSON.stringify([
          {
            object_id: primaryTarget.object_id,
            object_name: primaryTarget.object_name,
            object_type: primaryTarget.object_type,
          },
        ])
      );
    }
    return `/executions?${query.toString()}`;
  })();

  function buildExecutionHrefForAction(actionText: string): string {
    const query = new URLSearchParams();
    if (incidentId) query.set("incident_id", incidentId);
    if (sessionId) query.set("session_id", sessionId);

    const lower = actionText.toLowerCase();
    let toolName = "vmware.create_snapshot";
    if (
      lower.includes("host") ||
      actionText.includes("主机") ||
      actionText.includes("硬件") ||
      actionText.includes("连接")
    ) {
      toolName = "vmware.get_host_detail";
    } else if (lower.includes("vm") || actionText.includes("虚拟机")) {
      toolName = "vmware.get_vm_detail";
    } else if (
      lower.includes("pod") ||
      lower.includes("deployment") ||
      actionText.includes("容器")
    ) {
      toolName = "k8s.get_workload_status";
    }
    query.set("tool_name", toolName);

    if (primaryTarget) {
      query.set(
        "targets",
        JSON.stringify([
          {
            object_id: primaryTarget.object_id,
            object_name: primaryTarget.object_name,
            object_type: primaryTarget.object_type,
          },
        ])
      );
    }
    return `/executions?${query.toString()}`;
  }

  function classifyReadAction(actionText: string): { tool_name: string; mode: "single_host" | "nonhealthy_hosts" } | null {
    const lower = actionText.toLowerCase();
    if (
      lower.includes("host") ||
      actionText.includes("主机") ||
      actionText.includes("硬件") ||
      actionText.includes("连接")
    ) {
      if (actionText.includes("非健康") || lower.includes("unhealthy")) {
        return { tool_name: "vmware.get_host_detail", mode: "nonhealthy_hosts" };
      }
      return { tool_name: "vmware.get_host_detail", mode: "single_host" };
    }
    if (lower.includes("vm") || actionText.includes("虚拟机")) {
      return { tool_name: "vmware.get_vm_detail", mode: "single_host" };
    }
    if (lower.includes("pod") || lower.includes("deployment") || actionText.includes("容器")) {
      return { tool_name: "k8s.get_workload_status", mode: "single_host" };
    }
    return null;
  }

  async function invokeReadAction(actionText: string, index: number) {
    setActionRunningIndex(index);
    setActionExecResult(null);
    try {
      const matched = classifyReadAction(actionText);
      if (!matched) {
        router.push(buildExecutionHrefForAction(actionText));
        return;
      }

      if (matched.tool_name === "vmware.get_host_detail" && matched.mode === "nonhealthy_hosts") {
        const inventory = await apiFetch<{ success: boolean; data?: { hosts?: Array<Record<string, unknown>> }; error?: string }>(
          "/api/v1/resources/vcenter/inventory?connection_id=conn-vcenter-prod"
        );
        if (!inventory.success) {
          throw new Error(inventory.error || "获取 vCenter 资源失败");
        }
        const hosts = (inventory.data?.hosts || []) as Array<Record<string, unknown>>;
        const unhealthyHosts = hosts.filter((h) => {
          const s = String(h.overall_status || "").toLowerCase();
          const c = String(h.connection_state || "").toLowerCase();
          return (s && s !== "green") || (c && c !== "connected");
        });
        if (unhealthyHosts.length === 0) {
          setActionExecResult({
            action: actionText,
            status: "success",
            summary: "未发现非健康主机，连接与总体状态均正常。",
            detail: { nonhealthy_count: 0 },
            tool_name: "vmware.get_vcenter_inventory",
            ts: new Date().toISOString(),
          });
          return;
        }
        const sample = unhealthyHosts.slice(0, 5);
        const results = await Promise.all(
          sample.map(async (h) => {
            const hostId = String(h.host_id || "");
            const hostName = String(h.name || hostId);
            const resp = await apiFetch<{ success: boolean; data?: unknown; error?: string }>(
              "/api/v1/tools/vmware.get_host_detail/invoke",
              {
                method: "POST",
                body: JSON.stringify({ input: { host_id: hostId } }),
              }
            );
            return {
              host_id: hostId,
              host_name: hostName,
              success: !!resp.success,
              data: resp.data,
              error: resp.error,
            };
          })
        );
        const okCount = results.filter((r) => r.success).length;
        setActionExecResult({
          action: actionText,
          status: okCount > 0 ? "success" : "error",
          summary: `已检查 ${sample.length} 台非健康主机，成功 ${okCount} 台，失败 ${sample.length - okCount} 台。`,
          detail: { checked_hosts: results, total_nonhealthy: unhealthyHosts.length },
          tool_name: matched.tool_name,
          ts: new Date().toISOString(),
        });
        return;
      }

      const input: Record<string, unknown> = {};
      if (primaryTarget?.object_id) {
        if (matched.tool_name === "vmware.get_host_detail") {
          input.host_id = primaryTarget.object_id;
        } else if (matched.tool_name === "vmware.get_vm_detail") {
          input.vm_id = primaryTarget.object_id;
        }
      }

      if (matched.tool_name === "vmware.get_host_detail" && !input.host_id) {
        const inventory = await apiFetch<{ success: boolean; data?: { hosts?: Array<Record<string, unknown>> }; error?: string }>(
          "/api/v1/resources/vcenter/inventory?connection_id=conn-vcenter-prod"
        );
        if (!inventory.success) {
          throw new Error(inventory.error || "获取 vCenter 资源失败");
        }
        const hosts = (inventory.data?.hosts || []) as Array<Record<string, unknown>>;
        const text = `${title} ${diagData?.description || ""} ${actionText}`;
        const ip = text.match(IPV4_RE)?.[0];
        if (ip) {
          const m = hosts.find((h) => String(h.name || "").includes(ip));
          if (m?.host_id) input.host_id = String(m.host_id);
        }
        if (!input.host_id) {
          const m = hosts.find((h) => {
            const s = String(h.overall_status || "").toLowerCase();
            const c = String(h.connection_state || "").toLowerCase();
            return (s && s !== "green") || (c && c !== "connected");
          });
          if (m?.host_id) input.host_id = String(m.host_id);
        }
        if (!input.host_id && hosts[0]?.host_id) {
          input.host_id = String(hosts[0].host_id);
        }
        if (!input.host_id) {
          throw new Error("未识别到可检查的主机，请先在诊断中指定主机。");
        }
      }
      const response = await apiFetch<{ success: boolean; data?: unknown; error?: string }>(
        `/api/v1/tools/${matched.tool_name}/invoke`,
        {
          method: "POST",
          body: JSON.stringify({ input }),
        }
      );
      const summary =
        response.success
          ? "读取动作执行成功，已回填结果。"
          : (response.error || "读取动作执行失败").replace(
              /upstream returned non-JSON \(status 500\).*/i,
              "工具执行失败：目标参数缺失或上游服务异常，请重试。"
            );
      setActionExecResult({
        action: actionText,
        status: response.success ? "success" : "error",
        summary,
        detail: response.data,
        tool_name: matched.tool_name,
        ts: new Date().toISOString(),
      });
    } catch (err) {
      setActionExecResult({
        action: actionText,
        status: "error",
        summary: err instanceof Error ? err.message : "读取动作执行失败",
        ts: new Date().toISOString(),
      });
    } finally {
      setActionRunningIndex(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        <span className="ml-3 text-sm text-slate-500">加载诊断数据...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <PageHeader
        title="诊断工作台"
        description={
          <span className="flex items-center gap-2">
            {title}
            {diagId && <Badge variant="neutral" className="font-mono text-[10px]">{diagId}</Badge>}
          </span>
        }
        actions={
          <div className="flex gap-2">
            {sessionId && (
              <Link href={`/chat`}>
                <Button variant="secondary" size="sm">
                  <MessageSquare className="h-3.5 w-3.5" />
                  返回会话
                </Button>
              </Link>
            )}
            <Button variant="secondary" size="sm">
              <Download className="h-3.5 w-3.5" />
              导出报告
            </Button>
            <Button variant="primary" size="sm" onClick={() => router.push(executionHref)}>
              <Play className="h-3.5 w-3.5" />
              发起执行申请
            </Button>
          </div>
        }
      />

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Left Column: Context */}
        <div className="w-56 shrink-0 space-y-3 overflow-y-auto">
          {useMock && incident && (
            <>
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

              <Card>
                <CardHeader>
                  <CardTitle>相关告警</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1.5">
                  {["CPU > 95% 鎸佺画 30min", "CPU ready time > 10%"].map((alert) => (
                    <div key={alert} className="flex items-start gap-1.5 text-xs text-slate-700">
                      <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0 mt-0.5" />
                      {alert}
                    </div>
                  ))}
                </CardContent>
              </Card>
            </>
          )}

          {!useMock && (
            <Card>
              <CardHeader>
                <CardTitle>诊断信息</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5">
                <p className="text-xs text-slate-700 leading-relaxed">{diagData!.description}</p>
                {diagData!.created_at && (
                  <p className="text-[11px] text-slate-400 flex items-center gap-1">
                    <Clock className="h-3 w-3" /> {formatDate(diagData!.created_at)}
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Center Column: Analysis */}
        <div className="flex-1 min-w-0 overflow-y-auto space-y-4">
          {/* Root cause candidates */}
          <Card>
            <CardHeader>
              <CardTitle>根因候选</CardTitle>
              <span className="text-xs text-slate-400">AI 可解释性输出</span>
            </CardHeader>
            <CardContent className="space-y-3">
              {rootCauseCandidates.map((rc, i) => (
                <div
                  key={rc.id ?? i}
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
                  {"evidence_refs" in rc && (
                    <div className="flex items-center gap-2 mt-2">
                      <FileText className="h-3 w-3 text-slate-400" />
                      <span className="text-xs text-slate-500">关联证据 {(rc as { evidence_refs: string[] }).evidence_refs.length} 条</span>
                    </div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Timeline - show for mock mode */}
          {useMock && (
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
                      )} />
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
          )}

          {/* Tool traces - show for API mode */}
          {!useMock && toolTraces.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>工具调用轨迹</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {toolTraces.map((t, i) => (
                  <div key={i} className="flex items-center gap-2 rounded-md bg-slate-900 px-3 py-2 font-mono text-[11px]">
                    <Wrench className="h-3 w-3 text-slate-400 shrink-0" />
                    <span className="text-blue-400 font-semibold">{t.tool_name}</span>
                    <span className="text-slate-500">&rarr;</span>
                    <span className="text-slate-300 flex-1 truncate">{t.output_summary}</span>
                    <span className="text-slate-500 shrink-0">{t.duration_ms}ms</span>
                    {t.status === "success"
                      ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                      : <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
                    }
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Recommended actions */}
          <Card>
            <CardHeader>
              <CardTitle>建议动作</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {recommendedActions.map((a, i) => (
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
                  <Button
                    variant="ghost"
                    size="xs"
                    className="opacity-0 group-hover:opacity-100 transition-opacity text-blue-600 hover:bg-blue-100"
                    disabled={actionRunningIndex === i}
                    onClick={() => void invokeReadAction(a, i)}
                  >
                    {actionRunningIndex === i ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />} 执行
                  </Button>
                </div>
              ))}
              {actionExecResult && (
                <div className={cn(
                  "rounded-lg border px-3 py-2 text-xs space-y-1",
                  actionExecResult.status === "success"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-red-200 bg-red-50 text-red-700"
                )}>
                  <div className="font-semibold">最近执行：{actionExecResult.action}</div>
                  <div>工具：{actionExecResult.tool_name ?? "N/A"}</div>
                  <div>结果：{actionExecResult.summary}</div>
                  <div>时间：{formatDate(actionExecResult.ts)}</div>
                  {actionExecResult.detail != null && (
                    <pre className="max-h-40 overflow-auto rounded bg-white/60 p-2 text-[11px] text-slate-700">
                      {JSON.stringify(actionExecResult.detail, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Aux */}
        <div className="w-64 shrink-0 overflow-y-auto space-y-3">
          {/* Evidence list */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5 text-slate-400" /> 关联证据
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {evidences.length === 0 ? (
                <p className="text-xs text-slate-400">暂无关联证据</p>
              ) : evidences.map((e) => (
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

          {/* KB hits */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <BookOpen className="h-3.5 w-3.5 text-slate-400" /> 知识库命中
              </CardTitle>
            </CardHeader>
            <CardContent>
              {useMock ? (
                evidences.filter((e) => e.source_type === "kb").length === 0 ? (
                  <p className="text-xs text-slate-400">无命中结果</p>
                ) : evidences.filter((e) => e.source_type === "kb").map((e) => (
                  <div key={e.evidence_id} className="evidence-block">
                    <p className="font-semibold text-slate-700 mb-0.5">{e.summary}</p>
                    <p className="text-slate-400 mt-1">置信度 {(e.confidence * 100).toFixed(0)}%</p>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-400">无命中结果</p>
              )}
            </CardContent>
          </Card>

          {/* P1 Cross-page CTAs */}
          <div className="rounded-xl border border-blue-100 bg-blue-50/40 p-4">
            <p className="text-xs font-semibold text-blue-700 mb-3">诊断完成后的快捷操作</p>
            <div className="flex flex-wrap gap-2">
              <Link href="/agents">
                <Button variant="secondary" size="sm">
                  <Bot className="h-3.5 w-3.5" /> 查看 Agent 执行记录
                </Button>
              </Link>
              <Link href="/cases">
                <Button variant="secondary" size="sm">
                  <Archive className="h-3.5 w-3.5" /> 相似历史案例
                </Button>
              </Link>
              <Link href="/knowledge">
                <Button variant="secondary" size="sm">
                  <BookOpen className="h-3.5 w-3.5" /> 相关知识库
                </Button>
              </Link>
              <Link href={executionHref}>
                <Button variant="primary" size="sm">
                  <ShieldCheck className="h-3.5 w-3.5" /> 发起修复审批
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


