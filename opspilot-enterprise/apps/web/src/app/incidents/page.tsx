"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  Loader2,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  ShieldAlert,
  Wrench,
  XCircle,
} from "lucide-react";
import { type Incident, type IncidentAnalysisStep } from "@opspilot/shared-types";

import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { SeverityBadge, StatusBadge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type IncidentsEnvelope = { data?: { incidents?: Incident[] } };
type IncidentEnvelope = { data?: Incident };
type PreferenceMode = "suggest_only" | "low_risk_auto" | "full_auto";
type PreferenceEnvelope = { data?: { user_id?: string; auto_remediation_mode?: PreferenceMode } };

const DEFAULT_USER_ID = "ops-user";

const stageLabelMap: Record<string, string> = {
  plan: "意图识别中",
  tool_invoking: "调用资源中",
  assess: "证据评估中",
  decide_next: "决策下一步",
};

function stageMeta(step: IncidentAnalysisStep) {
  const label = stageLabelMap[step.stage] ?? step.stage;
  if (step.status === "failed") {
    return { label, icon: XCircle, cls: "text-red-600 bg-red-50 border-red-200" };
  }
  if (step.stage === "tool_invoking") {
    return { label, icon: Wrench, cls: "text-blue-600 bg-blue-50 border-blue-200" };
  }
  if (step.stage === "decide_next") {
    return { label, icon: Bot, cls: "text-violet-600 bg-violet-50 border-violet-200" };
  }
  return { label, icon: CheckCircle2, cls: "text-emerald-600 bg-emerald-50 border-emerald-200" };
}

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [modeSaving, setModeSaving] = useState(false);
  const [autoMode, setAutoMode] = useState<PreferenceMode>("low_risk_auto");

  const loadIncidents = useCallback(async () => {
    try {
      const res = await apiFetch<IncidentsEnvelope>("/api/v1/incidents");
      const items = res.data?.incidents ?? [];
      setIncidents(items);
      setSelectedId((prev) => prev ?? items[0]?.id ?? null);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载故障事件失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSelected = useCallback(async () => {
    if (!selectedId) {
      setSelected(null);
      return;
    }
    try {
      const res = await apiFetch<IncidentEnvelope>(`/api/v1/incidents/${selectedId}`);
      setSelected(res.data ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载事件详情失败");
    }
  }, [selectedId]);

  const loadPreferences = useCallback(async () => {
    try {
      const res = await apiFetch<PreferenceEnvelope>(
        `/api/v1/incidents/analysis-preferences?user_id=${encodeURIComponent(DEFAULT_USER_ID)}`
      );
      const mode = res.data?.auto_remediation_mode;
      if (mode) {
        setAutoMode(mode);
      }
    } catch {
      // ignore preference load error, keep default
    }
  }, []);

  useEffect(() => {
    void loadIncidents();
    void loadPreferences();
    const timer = setInterval(loadIncidents, 5000);
    return () => clearInterval(timer);
  }, [loadIncidents, loadPreferences]);

  useEffect(() => {
    void loadSelected();
    const timer = setInterval(loadSelected, 2000);
    return () => clearInterval(timer);
  }, [loadSelected]);

  const incidentRows = useMemo(() => incidents, [incidents]);
  const analysis = selected?.analysis;
  const allSteps = analysis?.analysis_process ?? [];
  const latestStep = allSteps.length > 0 ? allSteps[allSteps.length - 1] : null;
  const historySteps = allSteps.slice(0, Math.max(0, allSteps.length - 1));

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
    } catch (e) {
      setError(e instanceof Error ? e.message : "触发复分析失败");
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
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存自动处置偏好失败");
    } finally {
      setModeSaving(false);
    }
  };

  const analysisStatus = analysis?.status ?? "idle";
  const statusText =
    analysisStatus === "running"
      ? "分析中"
      : analysisStatus === "completed"
        ? "已完成"
        : analysisStatus === "failed"
          ? "失败"
          : "待分析";

  return (
    <div className="space-y-4">
      <PageHeader
        title="故障事件中心"
        description="实时查看 vCenter 与 K8s 事件，并跟踪自动分析过程与处置建议。"
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={loadIncidents}>
              <RefreshCw className="mr-1 h-4 w-4" />
              刷新
            </Button>
          </div>
        }
      />

      {loading && <div className="text-sm text-slate-500">正在加载事件...</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.3fr_1fr]">
        <div className="rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left">标题</th>
                <th className="px-3 py-2 text-left">级别</th>
                <th className="px-3 py-2 text-left">状态</th>
                <th className="px-3 py-2 text-left">更新时间</th>
              </tr>
            </thead>
            <tbody>
              {incidentRows.map((item) => (
                <tr
                  key={item.id}
                  className={`cursor-pointer border-t ${selectedId === item.id ? "bg-blue-50" : "hover:bg-slate-50"}`}
                  onClick={() => setSelectedId(item.id)}
                >
                  <td className="px-3 py-2">
                    <div className="font-medium text-slate-900">{item.title}</div>
                    <div className="font-mono text-xs text-slate-400">{item.id}</div>
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
                onClick={() => savePreference("suggest_only")}
              >
                仅建议
              </Button>
              <Button
                size="sm"
                variant={autoMode === "low_risk_auto" ? "primary" : "secondary"}
                disabled={modeSaving}
                onClick={() => savePreference("low_risk_auto")}
              >
                低风险自动执行
              </Button>
              <Button
                size="sm"
                variant={autoMode === "full_auto" ? "primary" : "secondary"}
                disabled={modeSaving}
                onClick={() => savePreference("full_auto")}
              >
                全自动
              </Button>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            {!selected && <div className="text-sm text-slate-500">暂无选中事件</div>}
            {selected && (
              <div className="space-y-4">
                <div>
                  <div className="mb-2 flex items-center gap-2">
                    <SeverityBadge severity={selected.severity} />
                    <StatusBadge status={selected.status} />
                  </div>
                  <h3 className="text-base font-semibold">{selected.title}</h3>
                  <p className="font-mono text-xs text-slate-400">{selected.id}</p>
                </div>

                <div className="rounded-lg border bg-slate-50 p-3 text-sm text-slate-700">
                  <div className="mb-1 flex items-center gap-1 text-xs text-slate-500">
                    <Clock3 className="h-3.5 w-3.5" />
                    首次发现 {formatDate(selected.first_seen_at)}
                  </div>
                  {selected.summary}
                </div>

                <div className="rounded-lg border p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="text-sm font-semibold text-slate-800">分析过程</div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500">{statusText}</span>
                      <Button size="sm" onClick={triggerReanalyze} disabled={analyzing}>
                        {analyzing ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-1 h-4 w-4" />}
                        重新分析
                      </Button>
                    </div>
                  </div>

                  <div className="mb-2 text-xs text-slate-500">
                    轮次 {analysis?.round ?? 0}/{analysis?.max_rounds ?? 5}，耗时{" "}
                    {analysis?.elapsed_ms ? `${Math.round(analysis.elapsed_ms / 1000)}s` : "-"}
                  </div>

                  {!latestStep && (
                    <div className="flex items-center gap-2 rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-600">
                      <PauseCircle className="h-4 w-4" />
                      暂无分析步骤
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
                    {analysis?.final_conclusion || "暂无结论"}
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">操作建议</div>
                  {(analysis?.recommended_actions ?? selected.recommended_actions).length === 0 && (
                    <div className="text-sm text-slate-500">暂无建议</div>
                  )}
                  {(analysis?.recommended_actions ?? selected.recommended_actions).map((x, i) => (
                    <div key={`${x}-${i}`} className="mb-1 flex items-start gap-2 text-sm text-slate-700">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-amber-500" />
                      <span>{x}</span>
                    </div>
                  ))}
                </div>

                {analysis?.next_decision && (
                  <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
                    <ShieldAlert className="h-4 w-4" />
                    下一步决策：{analysis.next_decision}
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
  const meta = stageMeta(step);
  const Icon = meta.icon;
  return (
    <div className={`rounded border p-2 ${meta.cls}`}>
      <div className="mb-1 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <Icon className="h-3.5 w-3.5" />
          <span>第 {step.round} 轮 · {meta.label}</span>
        </div>
        <span className="text-[11px] opacity-75">{formatDate(step.timestamp)}</span>
      </div>
      {(expanded || step.status === "failed") && (
        <div className="space-y-1 text-xs">
          {step.tool_name && <div>工具：{step.tool_name}</div>}
          <div>发现：{step.finding}</div>
          <div>决策：{step.decision}</div>
          {step.output_summary && <div>结果摘要：{step.output_summary}</div>}
        </div>
      )}
    </div>
  );
}
