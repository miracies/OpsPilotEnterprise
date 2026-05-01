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
import { type Incident } from "@opspilot/shared-types";
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

interface IncidentDetailData {
  id: string;
  title?: string;
  status?: Incident["status"];
  severity?: Incident["severity"];
  summary?: string;
  first_seen_at?: string;
  last_updated_at?: string;
  affected_objects?: Incident["affected_objects"];
  root_cause?: Incident["root_cause"] | null;
  root_cause_candidates?: Incident["root_cause_candidates"];
  recommended_actions?: string[];
  evidence_refs?: string[];
  analysis?: {
    status?: string;
    final_conclusion?: string;
    recommended_actions?: string[];
    analysis_process?: Array<{
      stage?: string;
      tool_name?: string;
      input_summary?: string;
      output_summary?: string;
      finding?: string;
      decision?: string;
      timestamp?: string;
      status?: string;
    }>;
  };
  memory_context?: {
    similar_incidents?: Array<{ memory?: { id: string; title: string; summary: string }; score?: number }>;
    recommended_actions?: string[];
    risk_signals?: string[];
    status?: string;
  };
  memory_write?: {
    status?: string;
    should_write_memory?: boolean;
    memory_items?: Array<{ id: string; title: string; summary: string }>;
    error?: string;
  };
  details?: {
    memory_context?: {
      similar_incidents?: Array<{ memory?: { id: string; title: string; summary: string }; score?: number }>;
      recommended_actions?: string[];
      risk_signals?: string[];
      status?: string;
    };
    memory_write?: {
      status?: string;
      should_write_memory?: boolean;
      memory_items?: Array<{ id: string; title: string; summary: string }>;
      error?: string;
    };
  };
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
  const incidentIdParam = searchParams.get("incident_id");
  const targetIdParam = searchParams.get("target_id");
  const targetNameParam = searchParams.get("target_name");
  const targetTypeParam = searchParams.get("target_type");
  const summaryParam = searchParams.get("summary");
  const missingEvidenceParam = searchParams.get("missing_evidence");
  const recommendedActionsParam = searchParams.get("recommended_actions");
  const [diagData, setDiagData] = useState<DiagnosisData | null>(null);
  const [incidentDetail, setIncidentDetail] = useState<IncidentDetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [incidentLoading, setIncidentLoading] = useState(false);
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

  useEffect(() => {
    if (!incidentIdParam) return;
    setIncidentLoading(true);
    apiFetch<{ success: boolean; data?: IncidentDetailData }>(`/api/v1/incidents/${incidentIdParam}`)
      .then((res) => setIncidentDetail(res.data ?? null))
      .catch(() => setIncidentDetail(null))
      .finally(() => setIncidentLoading(false));
  }, [incidentIdParam]);

  const incidentDiagnosis: DiagnosisData | null = incidentDetail
    ? {
        diagnosis_id: `incident-${incidentDetail.id}`,
        description: incidentDetail.title || incidentDetail.summary || targetNameParam || "故障事件诊断",
        assistant_message:
          incidentDetail.analysis?.final_conclusion ||
          incidentDetail.root_cause?.summary ||
          incidentDetail.summary ||
          "已从故障事件中心加载诊断上下文。",
        root_cause_candidates:
          incidentDetail.root_cause_candidates?.length
            ? incidentDetail.root_cause_candidates.map((rc) => ({
                description: rc.description,
                confidence: rc.confidence,
                category: rc.category ?? "unknown",
              }))
            : incidentDetail.root_cause
              ? [
                  {
                    description: incidentDetail.root_cause.summary,
                    confidence: incidentDetail.root_cause.confidence,
                    category: "root_cause",
                  },
                ]
              : [],
        evidence_refs: incidentDetail.evidence_refs ?? incidentDetail.root_cause?.evidence_refs ?? [],
        evidences: (incidentDetail.evidence_refs ?? []).map((ref) => ({
          evidence_id: ref,
          source_type: "evidence",
          summary: `诊断证据引用：${ref}`,
          confidence: 0.7,
          timestamp: incidentDetail.last_updated_at || new Date().toISOString(),
        })),
        recommended_actions: incidentDetail.analysis?.recommended_actions ?? incidentDetail.recommended_actions ?? [],
        tool_traces: (incidentDetail.analysis?.analysis_process ?? [])
          .filter((step) => step.tool_name || step.output_summary || step.finding)
          .map((step) => ({
            tool_name: step.tool_name || step.stage || "analysis",
            gateway: "event-ingestion",
            input_summary: step.input_summary || step.decision || "",
            output_summary: step.output_summary || step.finding || step.decision || "",
            duration_ms: 0,
            status: step.status === "failed" ? "failed" : "success",
            timestamp: step.timestamp || incidentDetail.last_updated_at || new Date().toISOString(),
          })),
        created_at: incidentDetail.analysis?.analysis_process?.[0]?.timestamp || incidentDetail.first_seen_at,
      }
    : null;
  const activeDiagnosis = diagData ?? incidentDiagnosis;

  // Choose data source: chat diagnosis, incident analysis, or legacy demo fallback only for bare /diagnosis.
  const useMock = !incidentIdParam && !diagnosisId && !activeDiagnosis;
  const incident = useMock ? mockIncidents[0] : null;
  const evidences = useMock
    ? mockEvidences.filter((e) => incident!.evidence_refs.includes(e.evidence_id))
    : activeDiagnosis?.evidences ?? [];
  const rootCauseCandidates = useMock
    ? incident!.root_cause_candidates
    : (activeDiagnosis?.root_cause_candidates ?? []).map((rc, i) => ({
        id: `rc-${i}`,
        description: rc.description,
        confidence: rc.confidence,
        category: rc.category ?? "unknown",
        evidence_refs: activeDiagnosis?.evidence_refs ?? [],
      }));
  const recommendedActions = useMock
    ? incident!.recommended_actions
    : activeDiagnosis?.recommended_actions ?? [];
  const prefilledMissingEvidence = (missingEvidenceParam ? missingEvidenceParam.split("||") : []).filter(Boolean);
  const prefilledRecommendedActions = (recommendedActionsParam ? recommendedActionsParam.split("||") : []).filter(Boolean);
  const mergedRecommendedActions = prefilledRecommendedActions.length > 0
    ? Array.from(new Set([...prefilledRecommendedActions, ...recommendedActions]))
    : recommendedActions;
  const toolTraces = useMock ? [] : activeDiagnosis?.tool_traces ?? [];
  const title = useMock ? incident!.title : (activeDiagnosis?.description || incidentDetail?.title || targetNameParam || "诊断工作台");
  const diagId = useMock ? undefined : activeDiagnosis?.diagnosis_id;
  const sessionId = useMock ? undefined : activeDiagnosis?.session_id;
  const incidentId = useMock ? incident?.id : (incidentIdParam || undefined);
  const memoryContext = incidentDetail?.details?.memory_context ?? incidentDetail?.memory_context;
  const memoryWrite = incidentDetail?.details?.memory_write ?? incidentDetail?.memory_write;
  const primaryTarget = useMock
    ? incident?.affected_objects?.[0]
    : (incidentDetail?.affected_objects?.[0] ??
      (targetIdParam && targetNameParam && targetTypeParam
        ? { object_id: targetIdParam, object_name: targetNameParam, object_type: targetTypeParam }
        : undefined));
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
        const text = `${title} ${activeDiagnosis?.description || ""} ${actionText}`;
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

  if (loading || incidentLoading) {
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
                  <p className="text-xs text-slate-700 leading-relaxed">{activeDiagnosis?.description || summaryParam || "已接收诊断上下文。"}</p>
                  {activeDiagnosis?.created_at && (
                    <p className="text-[11px] text-slate-400 flex items-center gap-1">
                      <Clock className="h-3 w-3" /> {formatDate(activeDiagnosis.created_at)}
                    </p>
                  )}
                </CardContent>
              </Card>
          )}
        </div>

        {/* Center Column: Analysis */}
        <div className="flex-1 min-w-0 overflow-y-auto space-y-4">
          {(incidentId || primaryTarget || prefilledMissingEvidence.length > 0 || prefilledRecommendedActions.length > 0 || summaryParam) && (
            <Card>
              <CardHeader>
                <CardTitle>来自故障事件中心的上下文</CardTitle>
                <span className="text-xs text-slate-400">已自动带入事件、目标对象、缺失证据和建议动作</span>
              </CardHeader>
              <CardContent className="space-y-3">
                {(incidentId || primaryTarget) && (
                  <div className="grid gap-2 rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm text-slate-700 md:grid-cols-2">
                    {incidentId && <div>关联事件：<span className="font-mono text-xs text-slate-500">{incidentId}</span></div>}
                    {primaryTarget && (
                      <div>
                        目标对象：{primaryTarget.object_name}
                        <Badge variant="neutral" className="ml-2">{primaryTarget.object_type}</Badge>
                      </div>
                    )}
                  </div>
                )}
                {summaryParam && (
                  <div className="rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm text-slate-700">
                    <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-blue-700">当前结论摘要</div>
                    <div>{summaryParam}</div>
                  </div>
                )}
                {prefilledMissingEvidence.length > 0 && (
                  <div>
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">建议补充的证据</div>
                    <div className="flex flex-wrap gap-2">
                      {prefilledMissingEvidence.map((item) => (
                        <Badge key={item} variant="warning">{item}</Badge>
                      ))}
                    </div>
                  </div>
                )}
                {prefilledRecommendedActions.length > 0 && (
                  <div>
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">事件中心传入的建议动作</div>
                    <div className="space-y-1">
                      {prefilledRecommendedActions.map((item, index) => (
                        <div key={`${item}-${index}`} className="text-sm text-slate-700">
                          {index + 1}. {item}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Root cause candidates */}
          <Card>
            <CardHeader>
              <CardTitle>根因候选</CardTitle>
              <span className="text-xs text-slate-400">AI 可解释性输出</span>
            </CardHeader>
            <CardContent className="space-y-3">
              {rootCauseCandidates.length === 0 ? (
                <p className="text-xs text-slate-400">暂无根因候选，请先在故障事件中心触发分析。</p>
              ) : rootCauseCandidates.map((rc, i) => (
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
              {mergedRecommendedActions.map((a, i) => (
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
              {memoryContext?.similar_incidents && memoryContext.similar_incidents.length > 0 ? (
                <div className="space-y-2">
                  {memoryContext.similar_incidents.slice(0, 3).map((hit) => (
                    <div key={hit.memory?.id ?? String(hit.score)} className="evidence-block">
                      <p className="font-semibold text-slate-700 mb-1">{hit.memory?.title ?? "Historical memory"}</p>
                      <p className="text-slate-600">{hit.memory?.summary ?? "-"}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <Badge variant="info">score {Math.round((hit.score ?? 0) * 100)}%</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400">暂无相似历史故障</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <Archive className="h-3.5 w-3.5 text-slate-400" /> Memory Write
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {!memoryWrite ? (
                <p className="text-xs text-slate-400">等待诊断完成后写入长期记忆</p>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <Badge variant={memoryWrite.status === "written" ? "success" : "neutral"}>{memoryWrite.status ?? "unknown"}</Badge>
                    <span className="text-xs text-slate-500">should write: {String(memoryWrite.should_write_memory)}</span>
                  </div>
                  {memoryWrite.error && <p className="text-xs text-red-600">{memoryWrite.error}</p>}
                  {(memoryWrite.memory_items ?? []).map((item) => (
                    <div key={item.id} className="rounded-lg border border-slate-100 bg-slate-50 p-2 text-xs">
                      <div className="font-semibold text-slate-700">{item.title}</div>
                      <div className="mt-1 text-slate-500">{item.summary}</div>
                    </div>
                  ))}
                </>
              )}
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


