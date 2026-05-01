"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Loader2,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  ShieldAlert,
  Wrench,
  XCircle,
} from "lucide-react";
import { type ApprovalRequest, type Incident, type IncidentAnalysisStep } from "@opspilot/shared-types";

import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Badge, SeverityBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";

type IncidentsEnvelope = { data?: { incidents?: Incident[] } };
type IncidentEnvelope = { data?: Incident };
type PreferenceMode = "suggest_only" | "low_risk_auto" | "full_auto";
type PreferenceEnvelope = { data?: { user_id?: string; auto_remediation_mode?: PreferenceMode } };
type ApprovalsEnvelope = { success?: boolean; error?: string; data?: { items?: ApprovalRequest[] } };
type NextStepType = "diagnose" | "execute_with_approval" | "view_approval" | "wait_for_more_evidence" | "reanalyze";
type NextStepInfo = {
  type: NextStepType;
  label: string;
  description: string;
  helperText?: string;
};
type RelatedIncidentRole = "suspected_root_cause" | "symptom" | "related";

const DEFAULT_USER_ID = "ops-user";

const STAGE_LABEL_MAP: Record<string, string> = {
  target_resolution: "目标识别",
  evidence_planning: "证据规划",
  evidence_collection: "证据采集",
  hypothesis_generation: "候选根因生成",
  hypothesis_scoring: "候选根因评分",
  counter_evidence_check: "反证检查",
  conclusion_gate: "结论门禁",
  recommendation_planning: "建议规划",
  tool_invoking: "工具调用",
  decide_next: "下一步决策",
  plan: "意图识别",
  assess: "证据评估",
};

function stepMeta(step: IncidentAnalysisStep) {
  const label = STAGE_LABEL_MAP[step.stage] ?? step.stage;
  if (step.status === "failed") {
    return { label, icon: XCircle, cls: "border-red-200 bg-red-50 text-red-700" };
  }
  if (step.status === "running") {
    return { label, icon: Loader2, cls: "border-blue-200 bg-blue-50 text-blue-700", spin: true };
  }
  if (step.stage === "tool_invoking" || step.stage === "evidence_collection") {
    return { label, icon: Wrench, cls: "border-sky-200 bg-sky-50 text-sky-700" };
  }
  if (step.stage === "decide_next" || step.stage === "conclusion_gate") {
    return { label, icon: Bot, cls: "border-violet-200 bg-violet-50 text-violet-700" };
  }
  return { label, icon: CheckCircle2, cls: "border-emerald-200 bg-emerald-50 text-emerald-700" };
}

function analysisStatusText(status?: string) {
  if (status === "running") return "分析中";
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  return "待分析";
}

function safeList(value?: string[] | null) {
  return Array.isArray(value) ? value : [];
}

function includesAny(value: string, keywords: string[]) {
  return keywords.some((keyword) => value.includes(keyword));
}

function normalizeRecommendationText(value: string) {
  if (value.includes("对照异常时间窗核对最近变更、迁移、重启或配置调整")) {
    return "建议在诊断工作台核对最近变更、迁移、重启和配置调整记录。";
  }
  return value;
}

function normalizeDecisionText(value?: string) {
  if (!value) return "";
  if (includesAny(value, ["继续采集证据", "继续分析", "补证据", "补充证据"])) {
    return "先补充证据，再决定是否执行处置。";
  }
  if (includesAny(value, ["状态变化触发复分析", "继续观察", "等待状态变化", "观察"])) {
    return "先观察当前状态，若状态变化可重新分析。";
  }
  if (includesAny(value, ["需要人工", "审批"])) {
    return "当前不建议直接执行，请先确认风险并按需发起执行申请。";
  }
  return value;
}

function isEvidenceCollectionDecision(value?: string) {
  if (!value) return false;
  return includesAny(value, ["继续采集证据", "继续分析", "补证据", "补充证据"]);
}

function isObservationDecision(value?: string) {
  if (!value) return false;
  return includesAny(value, ["状态变化", "继续观察", "等待", "观察"]);
}

function recommendationSuggestsWrite(item: string) {
  return includesAny(item.toLowerCase(), [
    "重启",
    "迁移",
    "扩容",
    "缩容",
    "执行",
    "切换",
    "隔离",
    "重置",
    "关机",
    "开机",
    "power",
    "restart",
    "reboot",
    "migrate",
    "scale",
    "snapshot",
    "vmotion",
  ]);
}

function buildDiagnosisHref(incident: Incident) {
  const target = incident.affected_objects?.[0];
  const params = new URLSearchParams();
  params.set("incident_id", incident.id);
  if (target?.object_id) params.set("target_id", target.object_id);
  if (target?.object_name) params.set("target_name", target.object_name);
  if (target?.object_type) params.set("target_type", target.object_type);
  return `/diagnosis?${params.toString()}`;
}

function buildExecutionHref(incident: Incident) {
  const target = incident.affected_objects?.[0];
  const params = new URLSearchParams();
  params.set("incident_id", incident.id);
  if (target?.object_id) params.set("target_id", target.object_id);
  if (target?.object_name) params.set("target_name", target.object_name);
  if (target?.object_type) params.set("target_type", target.object_type);
  return `/executions?${params.toString()}`;
}

function inferRelatedRole(title: string): RelatedIncidentRole {
  const lower = title.toLowerCase();
  if (lower.includes("not responding") || lower.includes("未响应")) {
    return "suspected_root_cause";
  }
  if (lower.includes("cannot synchronize") || lower.includes("无法同步") || lower.includes("overallstatus = red")) {
    return "symptom";
  }
  return "related";
}

function relatedRoleMeta(role: RelatedIncidentRole) {
  if (role === "suspected_root_cause") {
    return { label: "疑似主因", variant: "danger" as const };
  }
  if (role === "symptom") {
    return { label: "关联症状", variant: "warning" as const };
  }
  return { label: "关联事件", variant: "neutral" as const };
}

function deriveNextStep(
  incident: Incident,
  recommendations: string[],
  pendingApproval?: ApprovalRequest | null,
): NextStepInfo {
  const decision = incident.analysis?.next_decision ?? "";
  const hasWriteRecommendation = recommendations.some(recommendationSuggestsWrite);

  if (pendingApproval) {
    return {
      type: "view_approval",
      label: "进入诊断工作台",
      description: "当前事件已经存在待审批执行单，建议先查看诊断证据和审批状态，再决定是否继续推进处置。",
      helperText: "如审批通过，后续可以直接在审批中心继续处理。",
    };
  }

  if (isObservationDecision(decision)) {
    return {
      type: "wait_for_more_evidence",
      label: "进入诊断工作台",
      description: "建议先观察当前状态，并在诊断工作台持续核对主机事件、连接状态和最近变更。",
      helperText: "如果对象状态变化或新增告警，再重新分析会更准确。",
    };
  }

  if (!isEvidenceCollectionDecision(decision) && hasWriteRecommendation) {
    return {
      type: "execute_with_approval",
      label: "进入诊断工作台",
      description: "当前已经形成可处置建议。建议先在诊断工作台复核证据，再决定是否发起执行申请。",
      helperText: "只有确认根因和影响范围后，再进入执行申请或审批会更稳妥。",
    };
  }

  return {
    type: "diagnose",
    label: "进入诊断工作台",
    description: "建议先进入诊断工作台，补充主机事件、连接状态、最近变更等证据，再决定是否执行处置。",
    helperText: "当前阶段以补证据和缩小根因为主，不建议直接跳过诊断。",
  };
}

export default function IncidentsPage() {
  const router = useRouter();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [modeSaving, setModeSaving] = useState(false);
  const [autoMode, setAutoMode] = useState<PreferenceMode>("low_risk_auto");

  const loadIncidents = useCallback(async () => {
    try {
      const res = await apiFetch<IncidentsEnvelope>("/api/v1/incidents?view=summary&limit=50");
      const items = res.data?.incidents ?? [];
      setIncidents(items);
      setSelectedId((prev) => {
        if (prev && items.some((item) => item.id === prev)) {
          return prev;
        }
        return items[0]?.id ?? null;
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载故障事件失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSelected = useCallback(async () => {
    if (!selectedId) {
      setSelected(null);
      setDetailLoading(false);
      return;
    }
    setDetailLoading(true);
    try {
      const res = await apiFetch<IncidentEnvelope>(`/api/v1/incidents/${selectedId}`);
      setSelected(res.data ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载故障事件详情失败");
    } finally {
      setDetailLoading(false);
    }
  }, [selectedId]);

  const loadPreferences = useCallback(async () => {
    try {
      const res = await apiFetch<PreferenceEnvelope>(
        `/api/v1/incidents/analysis-preferences?user_id=${encodeURIComponent(DEFAULT_USER_ID)}`,
      );
      if (res.data?.auto_remediation_mode) {
        setAutoMode(res.data.auto_remediation_mode);
      }
    } catch {
      // Keep the default mode when preferences are temporarily unavailable.
    }
  }, []);

  const loadPendingApprovals = useCallback(async () => {
    try {
      const res = await apiFetch<ApprovalsEnvelope>("/api/v1/approvals?status=pending");
      if (res.success === false) {
        throw new Error(res.error || "加载待审批列表失败");
      }
      setPendingApprovals(res.data?.items ?? []);
    } catch {
      setPendingApprovals([]);
    }
  }, []);

  useEffect(() => {
    void loadIncidents();
    void loadPreferences();
    void loadPendingApprovals();
    const timer = setInterval(() => {
      void loadIncidents();
      void loadPendingApprovals();
    }, 15000);
    return () => clearInterval(timer);
  }, [loadIncidents, loadPendingApprovals, loadPreferences]);

  useEffect(() => {
    void loadSelected();
  }, [loadSelected]);

  const selectedPollingStatus = selected?.status ?? incidents.find((item) => item.id === selectedId)?.status;

  useEffect(() => {
    if (!selectedId) return undefined;
    if (selectedPollingStatus && !["new", "analyzing", "pending_action"].includes(selectedPollingStatus)) {
      return undefined;
    }
    const timer = setInterval(() => void loadSelected(), 5000);
    return () => clearInterval(timer);
  }, [loadSelected, selectedId, selectedPollingStatus]);

  const analysis = selected?.analysis;
  const steps = analysis?.analysis_process ?? [];
  const latestStep = steps.length > 0 ? steps[steps.length - 1] : null;
  const historySteps = steps.slice(0, Math.max(0, steps.length - 1));
  const recommendations = analysis?.recommended_actions ?? selected?.recommended_actions ?? [];
  const incidentRows = useMemo(() => incidents, [incidents]);
  const pendingApprovalForSelected = useMemo(
    () => pendingApprovals.find((approval) => approval.incident_ref === selected?.id) ?? null,
    [pendingApprovals, selected?.id],
  );
  const nextStep = useMemo(
    () => (selected ? deriveNextStep(selected, recommendations, pendingApprovalForSelected) : null),
    [pendingApprovalForSelected, recommendations, selected],
  );
  const relatedIncidents = useMemo(() => {
    if (!selected) return [];
    const selectedObjectId = selected.validation_summary?.object_id ?? selected.affected_objects?.[0]?.object_id ?? "";
    const selectedObjectName = (
      selected.validation_summary?.object_name ?? selected.affected_objects?.[0]?.object_name ?? ""
    ).toLowerCase();
    const rank: Record<RelatedIncidentRole, number> = {
      suspected_root_cause: 0,
      symptom: 1,
      related: 2,
    };

    return incidents
      .filter((item) => {
        const objectId = item.validation_summary?.object_id ?? item.affected_objects?.[0]?.object_id ?? "";
        const objectName = (item.validation_summary?.object_name ?? item.affected_objects?.[0]?.object_name ?? "").toLowerCase();
        return Boolean(
          (selectedObjectId && objectId && selectedObjectId === objectId) ||
            (selectedObjectName && objectName && selectedObjectName === objectName),
        );
      })
      .map((item) => ({ incident: item, role: inferRelatedRole(item.title) }))
      .sort((a, b) => rank[a.role] - rank[b.role]);
  }, [incidents, selected]);

  const triggerReanalyze = async () => {
    if (!selectedId) return;
    setAnalyzing(true);
    try {
      await apiFetch(`/api/v1/incidents/${selectedId}/analyze`, {
        method: "POST",
        body: JSON.stringify({ mode: "manual", user_id: DEFAULT_USER_ID }),
      });
      await loadSelected();
      await loadIncidents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "触发重新分析失败");
    } finally {
      setAnalyzing(false);
    }
  };

  const savePreference = async (mode: PreferenceMode) => {
    setAutoMode(mode);
    setModeSaving(true);
    try {
      await apiFetch("/api/v1/incidents/analysis-preferences", {
        method: "PUT",
        body: JSON.stringify({ user_id: DEFAULT_USER_ID, auto_remediation_mode: mode }),
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存自动处置偏好失败");
    } finally {
      setModeSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="故障事件中心"
        description="实时查看 vCenter 与 K8s 故障事件，跟踪自动分析过程、根因证据和处置建议。"
        actions={
          <Button variant="secondary" size="sm" onClick={() => void loadIncidents()}>
            <RefreshCw className="mr-1 h-4 w-4" />
            刷新
          </Button>
        }
      />

      {loading && <div className="text-sm text-slate-500">正在加载故障事件...</div>}
      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.25fr_1fr]">
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-3 py-2 text-left font-medium">标题</th>
                <th className="px-3 py-2 text-left font-medium">级别</th>
                <th className="px-3 py-2 text-left font-medium">状态</th>
                <th className="px-3 py-2 text-left font-medium">更新时间</th>
              </tr>
            </thead>
            <tbody>
              {!loading && incidentRows.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center text-sm text-slate-500">
                    当前没有故障事件。
                  </td>
                </tr>
              )}
              {incidentRows.map((item) => (
                <tr
                  key={item.id}
                  className={`cursor-pointer border-t ${selectedId === item.id ? "bg-blue-50" : "hover:bg-slate-50"}`}
                  onClick={() => {
                    if (item.id !== selectedId) {
                      setSelected(null);
                    }
                    setSelectedId(item.id);
                  }}
                >
                  <td className="px-3 py-2">
                    <div className="font-medium text-slate-900">{item.title}</div>
                    <div className="mt-1 font-mono text-xs text-slate-400">{item.id}</div>
                  </td>
                  <td className="px-3 py-2">
                    <SeverityBadge severity={item.severity} />
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-500">{formatDate(item.last_updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-3 text-sm font-semibold text-slate-800">自动处置偏好</div>
            <div className="grid grid-cols-1 gap-2">
              <Button
                size="sm"
                variant={autoMode === "suggest_only" ? "primary" : "secondary"}
                disabled={modeSaving}
                onClick={() => void savePreference("suggest_only")}
              >
                仅建议
              </Button>
              <Button
                size="sm"
                variant={autoMode === "low_risk_auto" ? "primary" : "secondary"}
                disabled={modeSaving}
                onClick={() => void savePreference("low_risk_auto")}
              >
                低风险自动执行
              </Button>
              <Button
                size="sm"
                variant={autoMode === "full_auto" ? "primary" : "secondary"}
                disabled={modeSaving}
                onClick={() => void savePreference("full_auto")}
              >
                全自动
              </Button>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            {detailLoading && !selected && (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                正在加载故障详情...
              </div>
            )}

            {!detailLoading && !selected && <div className="text-sm text-slate-500">暂无选中的故障事件。</div>}

            {selected && (
              <div className="space-y-4">
                <div>
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={selected.severity} />
                    <StatusBadge status={selected.status} />
                    {selected.conclusion_status && (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                        结论状态：{selected.conclusion_status}
                      </span>
                    )}
                  </div>
                  <h3 className="text-base font-semibold text-slate-900">{selected.title}</h3>
                  <p className="mt-1 font-mono text-xs text-slate-400">{selected.id}</p>
                </div>

                <div className="rounded-lg border bg-slate-50 p-3 text-sm text-slate-700">
                  <div className="mb-1 flex items-center gap-1 text-xs text-slate-500">
                    <Clock3 className="h-3.5 w-3.5" />
                    首次发现 {formatDate(selected.first_seen_at)}
                  </div>
                  <div>{selected.summary}</div>
                  {selected.last_seen_at && (
                    <div className="mt-2 text-xs text-slate-500">最近确认 {formatDate(selected.last_seen_at)}</div>
                  )}
                </div>

                {selected.validation_summary && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">状态校验</div>
                    <div className="grid gap-1 text-sm">
                      <div>对象：{selected.validation_summary.object_name ?? selected.validation_summary.object_id ?? "-"}</div>
                      <div>校验结论：{selected.validation_summary.status ?? "-"}</div>
                      <div>校验依据：{selected.validation_summary.reason ?? "-"}</div>
                      {selected.correlation_key && <div>关联键：{selected.correlation_key}</div>}
                      {selected.reopen_count !== undefined && <div>重开次数：{selected.reopen_count}</div>}
                    </div>
                  </div>
                )}

                {nextStep && (
                  <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">下一步操作</div>
                        <div className="mt-1 text-xs text-slate-600">{nextStep.description}</div>
                      </div>
                      <Badge variant="info">诊断优先</Badge>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" onClick={() => router.push(buildDiagnosisHref(selected))}>
                        <ExternalLink className="h-3.5 w-3.5" />
                        {nextStep.label}
                      </Button>

                      {nextStep.type === "view_approval" && pendingApprovalForSelected && (
                        <Button size="sm" variant="secondary" onClick={() => router.push("/approvals")}>
                          查看审批单
                        </Button>
                      )}

                      {nextStep.type === "execute_with_approval" && (
                        <Button size="sm" variant="secondary" onClick={() => router.push(buildExecutionHref(selected))}>
                          发起执行申请
                        </Button>
                      )}
                    </div>

                    {nextStep.helperText && <div className="mt-3 text-xs text-slate-600">{nextStep.helperText}</div>}
                  </div>
                )}

                {relatedIncidents.length > 0 && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">关联事件关系</div>
                    <div className="space-y-2">
                      {relatedIncidents.map(({ incident, role }) => {
                        const meta = relatedRoleMeta(role);
                        return (
                          <div
                            key={incident.id}
                            className={`rounded border px-3 py-2 text-sm ${
                              incident.id === selected.id ? "border-blue-200 bg-white" : "border-slate-200 bg-white/80"
                            }`}
                          >
                            <div className="mb-1 flex flex-wrap items-center gap-2">
                              <Badge variant={meta.variant}>{meta.label}</Badge>
                              <SeverityBadge severity={incident.severity} />
                              <StatusBadge status={incident.status} />
                            </div>
                            <div className="font-medium text-slate-800">{incident.title}</div>
                            <div className="mt-1 text-xs text-slate-500">
                              {incident.id === selected.id ? "当前查看事件" : `最近更新 ${formatDate(incident.last_updated_at)}`}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="rounded-lg border p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-semibold text-slate-800">分析过程</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {analysisStatusText(analysis?.status)} · 轮次 {analysis?.round ?? 0}/{analysis?.max_rounds ?? 5}
                        {analysis?.elapsed_ms ? ` · 已耗时 ${Math.round(analysis.elapsed_ms / 1000)}s` : ""}
                      </div>
                    </div>
                    <Button size="sm" onClick={() => void triggerReanalyze()} disabled={analyzing}>
                      {analyzing ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-1 h-4 w-4" />}
                      重新分析
                    </Button>
                  </div>

                  {!latestStep && (
                    <div className="flex items-center gap-2 rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-600">
                      <PauseCircle className="h-4 w-4" />
                      暂无分析步骤。
                    </div>
                  )}

                  {latestStep && (
                    <div className="space-y-2">
                      <div className="text-xs font-medium text-slate-500">最新步骤</div>
                      <StepCard step={latestStep} expanded />
                    </div>
                  )}

                  {historySteps.length > 0 && (
                    <details className="mt-3 rounded border border-slate-200 bg-slate-50 p-2">
                      <summary className="cursor-pointer text-xs font-medium text-slate-600">
                        历史步骤（{historySteps.length}）已折叠
                      </summary>
                      <div className="mt-2 space-y-2">
                        {historySteps
                          .slice()
                          .reverse()
                          .map((step, idx) => (
                            <StepCard key={`${step.timestamp}-${idx}`} step={step} />
                          ))}
                      </div>
                    </details>
                  )}
                </div>

                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">最终结论</div>
                  <div className="rounded-lg border bg-slate-50 p-3 text-sm text-slate-700">
                    {analysis?.final_conclusion || "当前还没有生成最终结论。"}
                  </div>
                </div>

                {(selected.evidence_sufficiency || selected.counter_evidence_result || (selected.hypotheses && selected.hypotheses.length > 0)) && (
                  <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                    <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">证据与候选根因</div>
                    {selected.evidence_sufficiency && (
                      <div className="space-y-1">
                        <div>
                          证据充分性 {(selected.evidence_sufficiency.sufficiency_score ?? 0).toFixed(2)} / 新鲜度 {(selected.evidence_sufficiency.freshness_score ?? 0).toFixed(2)}
                        </div>
                        {safeList(selected.evidence_sufficiency.missing_critical_evidence).length > 0 && (
                          <div className="text-amber-700">
                            缺失关键证据：{safeList(selected.evidence_sufficiency.missing_critical_evidence).join("、")}
                          </div>
                        )}
                      </div>
                    )}
                    {selected.counter_evidence_result && (
                      <div>
                        反证结果：{selected.counter_evidence_result.status}，{selected.counter_evidence_result.summary}
                      </div>
                    )}
                    {selected.hypotheses && selected.hypotheses.length > 0 && (
                      <div className="space-y-2">
                        <div className="font-medium text-slate-600">候选根因对比</div>
                        {selected.hypotheses.slice(0, 3).map((item) => (
                          <div key={item.id} className="rounded border border-slate-200 bg-white px-2 py-2">
                            <div className="font-medium text-slate-800">
                              {item.summary}（置信度 {(item.confidence ?? 0).toFixed(2)}）
                            </div>
                            {safeList(item.missing_evidence).length > 0 && (
                              <div className="mt-1 text-amber-700">缺口：{safeList(item.missing_evidence).join("、")}</div>
                            )}
                            {item.why && <div className="mt-1 text-slate-500">说明：{item.why}</div>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">操作建议</div>
                  {recommendations.length === 0 ? (
                    <div className="text-sm text-slate-500">当前暂无建议动作。</div>
                  ) : (
                    recommendations.map((item, idx) => (
                      <div key={`${item}-${idx}`} className="mb-1 flex items-start gap-2 text-sm text-slate-700">
                        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-amber-500" />
                        <span>{normalizeRecommendationText(item)}</span>
                      </div>
                    ))
                  )}
                </div>

                {analysis?.next_decision && (
                  <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
                    <ShieldAlert className="h-4 w-4" />
                    下一步建议：{normalizeDecisionText(analysis.next_decision)}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StepCard({ step, expanded = false }: { step: IncidentAnalysisStep; expanded?: boolean }) {
  const meta = stepMeta(step);
  const Icon = meta.icon;
  return (
    <div className={`rounded border p-2 ${meta.cls}`}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <Icon className={`h-3.5 w-3.5 ${meta.spin ? "animate-spin" : ""}`} />
          <span>
            第 {step.round} 轮 · {meta.label}
          </span>
        </div>
        <span className="text-[11px] opacity-75">{formatDate(step.timestamp)}</span>
      </div>
      {(expanded || step.status === "failed") && (
        <div className="space-y-1 text-xs">
          {step.goal && <div>目标：{step.goal}</div>}
          {step.tool_name && <div>工具：{step.tool_name}</div>}
          {safeList(step.selected_tools).length > 0 && <div>本轮工具：{safeList(step.selected_tools).join("、")}</div>}
          <div>发现：{step.finding}</div>
          <div>决策：{step.decision}</div>
          {safeList(step.evidence_found).length > 0 && <div>已获证据：{safeList(step.evidence_found).join("、")}</div>}
          {safeList(step.evidence_missing).length > 0 && (
            <div className="text-amber-700">缺失证据：{safeList(step.evidence_missing).join("、")}</div>
          )}
          {safeList(step.contradictions).length > 0 && (
            <div className="text-rose-700">矛盾证据：{safeList(step.contradictions).join("、")}</div>
          )}
          {step.output_summary && <div>结果摘要：{step.output_summary}</div>}
          {step.why && <div className="text-slate-500">原因：{step.why}</div>}
        </div>
      )}
    </div>
  );
}
