"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Play,
  Plus,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, RiskBadge, StatusBadge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type ExecutionTarget = {
  object_id: string;
  object_name: string;
  object_type: string;
  metadata: Record<string, unknown>;
};

type ToolItem = {
  name: string;
  display_name: string;
  action_type: "read" | "write" | "dangerous";
  risk_level: "low" | "medium" | "high" | "critical";
};

type DryRunResult = {
  can_submit: boolean;
  require_approval: boolean;
  policy: {
    allowed: boolean;
    require_approval: boolean;
    reason: string;
    matched_policies: string[];
    source?: string;
  };
  action_type: string;
  risk_level: string;
  risk_score: number;
  capability: "single" | "batch";
  target_results: Array<{
    object_id: string;
    object_name: string;
    status: "ok" | "error";
    message: string;
    preview?: Record<string, unknown>;
  }>;
  warnings: string[];
};

type ExecutionListItem = {
  id: string;
  tool_name: string;
  action_type: string;
  environment: string;
  requester: string;
  status: string;
  incident_id: string | null;
  approval_id: string | null;
  risk_level: string;
  risk_score: number;
  updated_at: string;
};

function parseTargets(raw: string | null): ExecutionTarget[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((x) => x && x.object_id && x.object_name && x.object_type)
      .map((x) => ({
        object_id: String(x.object_id),
        object_name: String(x.object_name),
        object_type: String(x.object_type),
        metadata: typeof x.metadata === "object" && x.metadata ? x.metadata : {},
      }));
  } catch {
    return [];
  }
}

export default function ExecutionsPage() {
  const searchParams = useSearchParams();
  const initialTargets = useMemo(() => {
    const fromList = parseTargets(searchParams.get("targets"));
    if (fromList.length > 0) return fromList;
    const objectId = searchParams.get("target_id");
    const objectName = searchParams.get("target_name");
    const objectType = searchParams.get("target_type");
    if (!objectId || !objectName || !objectType) return [];
    return [{ object_id: objectId, object_name: objectName, object_type: objectType, metadata: {} }];
  }, [searchParams]);

  const [toolName, setToolName] = useState(searchParams.get("tool_name") || searchParams.get("action") || "vmware.create_snapshot");
  const [environment, setEnvironment] = useState(searchParams.get("environment") || "prod");
  const [requester, setRequester] = useState(searchParams.get("requester") || "ops-user");
  const [incidentId, setIncidentId] = useState(searchParams.get("incident_id") || "");
  const [changeRef, setChangeRef] = useState(searchParams.get("change_analysis_ref") || "");
  const [sessionId] = useState(searchParams.get("session_id") || "");
  const [targets, setTargets] = useState<ExecutionTarget[]>(
    initialTargets.length > 0
      ? initialTargets
      : [{ object_id: "", object_name: "", object_type: "", metadata: {} }]
  );
  const [parametersText, setParametersText] = useState("{}");
  const [dryRunResult, setDryRunResult] = useState<DryRunResult | null>(null);
  const [tools, setTools] = useState<ToolItem[]>([]);
  const [loadingTools, setLoadingTools] = useState(false);
  const [dryRunning, setDryRunning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [recentExecutions, setRecentExecutions] = useState<ExecutionListItem[]>([]);
  const [submitResult, setSubmitResult] = useState<{ execution_id: string; status: string; approval_id?: string | null } | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);

  const sortedTools = useMemo(() => {
    const priority: Record<ToolItem["action_type"], number> = {
      dangerous: 0,
      write: 1,
      read: 2,
    };
    return [...tools].sort((a, b) => {
      const d = priority[a.action_type] - priority[b.action_type];
      if (d !== 0) return d;
      return a.name.localeCompare(b.name);
    });
  }, [tools]);

  async function loadRecentExecutions() {
    const res = await apiFetch<{ success: boolean; data: { items: ExecutionListItem[] } }>("/api/v1/executions?limit=8");
    if (res.success) setRecentExecutions(res.data.items || []);
  }

  useEffect(() => {
    setLoadingTools(true);
    apiFetch<{ success: boolean; data: ToolItem[] }>("/api/v1/tools")
      .then((res) => {
        if (!res.success) return;
        setTools(res.data || []);
      })
      .catch(() => {})
      .finally(() => setLoadingTools(false));

    loadRecentExecutions().catch(() => {});
  }, []);

  useEffect(() => {
    if (tools.length === 0) return;
    if (!tools.some((t) => t.name === toolName)) {
      setToolName(tools[0].name);
    }
  }, [tools, toolName]);

  const selectedTool = tools.find((t) => t.name === toolName);

  function updateTarget(index: number, key: keyof ExecutionTarget, value: string) {
    setTargets((prev) => prev.map((t, i) => (i === index ? { ...t, [key]: value } : t)));
  }

  function addTarget() {
    setTargets((prev) => [...prev, { object_id: "", object_name: "", object_type: "", metadata: {} }]);
  }

  function removeTarget(index: number) {
    setTargets((prev) => (prev.length === 1 ? prev : prev.filter((_, i) => i !== index)));
  }

  function buildPayload() {
    let parameters: Record<string, unknown> = {};
    if (parametersText.trim()) parameters = JSON.parse(parametersText);
    return {
      tool_name: toolName,
      action_type: selectedTool?.action_type || "write",
      targets: targets.filter((t) => t.object_id && t.object_name && t.object_type),
      parameters,
      environment,
      requester,
      incident_id: incidentId || null,
      change_analysis_ref: changeRef || null,
      session_id: sessionId || null,
    };
  }

  async function onDryRun() {
    setErrorText(null);
    setSubmitResult(null);
    setDryRunning(true);
    try {
      const payload = buildPayload();
      const res = await apiFetch<{ success: boolean; data?: { dry_run_result: DryRunResult }; error?: string }>(
        "/api/v1/executions/dry-run",
        { method: "POST", body: JSON.stringify(payload) }
      );
      if (!res.success || !res.data) {
        setErrorText(res.error || "dry-run failed");
        return;
      }
      setDryRunResult(res.data.dry_run_result);
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : "dry-run failed");
    } finally {
      setDryRunning(false);
    }
  }

  async function onSubmit() {
    setErrorText(null);
    setSubmitting(true);
    try {
      const payload = buildPayload();
      const res = await apiFetch<{
        success: boolean;
        data?: { execution_id: string; status: string; approval_id?: string | null; dry_run_result: DryRunResult };
        error?: string;
      }>("/api/v1/executions/submit", { method: "POST", body: JSON.stringify(payload) });
      if (!res.success || !res.data) {
        setErrorText(res.error || "submit failed");
        return;
      }
      setDryRunResult(res.data.dry_run_result);
      setSubmitResult({
        execution_id: res.data.execution_id,
        status: res.data.status,
        approval_id: res.data.approval_id,
      });
      await loadRecentExecutions();
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : "submit failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="执行申请" description="执行动作 dry-run、风险评估与审批提交" />

      {errorText && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{errorText}</div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>执行动作表单</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <label className="text-xs text-slate-600">
                  Action Tool
                  <select className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" value={toolName} onChange={(e) => setToolName(e.target.value)}>
                    {loadingTools && <option>loading...</option>}
                    {!loadingTools && sortedTools.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.name} [{t.action_type}]
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs text-slate-600">
                  Environment
                  <select className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" value={environment} onChange={(e) => setEnvironment(e.target.value)}>
                    <option value="prod">prod</option>
                    <option value="test">test</option>
                  </select>
                </label>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <label className="text-xs text-slate-600">Requester
                  <input className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" value={requester} onChange={(e) => setRequester(e.target.value)} />
                </label>
                <label className="text-xs text-slate-600">Incident Ref
                  <input className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" value={incidentId} onChange={(e) => setIncidentId(e.target.value)} />
                </label>
                <label className="text-xs text-slate-600">Change Ref
                  <input className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" value={changeRef} onChange={(e) => setChangeRef(e.target.value)} />
                </label>
              </div>
              <label className="block text-xs text-slate-600">Parameters(JSON)
                <textarea className="mt-1 h-24 w-full rounded-md border border-slate-300 px-2 py-2 font-mono text-xs" value={parametersText} onChange={(e) => setParametersText(e.target.value)} />
              </label>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>目标对象列表</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {targets.map((target, idx) => (
                <div key={idx} className="grid grid-cols-1 gap-2 rounded-lg border border-slate-200 p-3 md:grid-cols-10">
                  <input className="rounded-md border border-slate-300 px-2 py-2 text-sm md:col-span-3" placeholder="object_id" value={target.object_id} onChange={(e) => updateTarget(idx, "object_id", e.target.value)} />
                  <input className="rounded-md border border-slate-300 px-2 py-2 text-sm md:col-span-3" placeholder="object_name" value={target.object_name} onChange={(e) => updateTarget(idx, "object_name", e.target.value)} />
                  <input className="rounded-md border border-slate-300 px-2 py-2 text-sm md:col-span-3" placeholder="object_type" value={target.object_type} onChange={(e) => updateTarget(idx, "object_type", e.target.value)} />
                  <button className="inline-flex items-center justify-center rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50 md:col-span-1" onClick={() => removeTarget(idx)}>
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
              <Button variant="secondary" size="sm" onClick={addTarget}><Plus className="h-3.5 w-3.5" />添加目标</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>dry-run 结果</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {!dryRunResult && <p className="text-sm text-slate-500">尚未执行 dry-run。</p>}
              {dryRunResult && (
                <>
                  <div className="flex items-center gap-2">
                    <Badge variant={dryRunResult.can_submit ? "success" : "danger"}>{dryRunResult.can_submit ? "可提交" : "不可提交"}</Badge>
                    <Badge variant={dryRunResult.require_approval ? "warning" : "info"}>{dryRunResult.require_approval ? "需审批" : "无需审批"}</Badge>
                    <Badge variant="neutral">能力: {dryRunResult.capability}</Badge>
                  </div>
                  {dryRunResult.target_results.map((item) => (
                    <div key={item.object_id} className="rounded-md border border-slate-200 px-3 py-2 text-sm">
                      <div className="flex items-center gap-2">
                        {item.status === "ok" ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertTriangle className="h-4 w-4 text-red-600" />}
                        <span className="font-medium">{item.object_name}</span>
                        <span className="text-slate-500">{item.message}</span>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>风险展示</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex items-center gap-2"><span className="text-slate-500">Tool Risk:</span><RiskBadge level={selectedTool?.risk_level ?? "medium"} /></div>
              <div className="rounded-md bg-slate-50 p-2 text-xs text-slate-700">
                <div>allowed: {String(dryRunResult?.policy?.allowed ?? false)}</div>
                <div>require_approval: {String(dryRunResult?.policy?.require_approval ?? false)}</div>
                <div>reason: {dryRunResult?.policy?.reason ?? "-"}</div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>审批流展示</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div>Requester: {requester}</div>
              <div>Assignee: ops-lead</div>
              <div className="rounded-md bg-slate-50 p-2 text-xs">
                {dryRunResult?.require_approval
                  ? "策略判定：需要审批，提交后进入审批中心。"
                  : "策略判定：无需审批，提交后自动执行。"}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>提交</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              <Button variant="secondary" className="w-full" onClick={onDryRun} disabled={dryRunning}>
                {dryRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}执行 dry-run
              </Button>
              <Button variant="primary" className="w-full" onClick={onSubmit} disabled={submitting || !dryRunResult}>
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                {dryRunResult?.require_approval ? "提交审批" : "提交并执行"}
              </Button>
              {submitResult && (
                <div className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-2 text-xs text-emerald-700 space-y-1">
                  <div>execution_id: {submitResult.execution_id}</div>
                  <div>status: {submitResult.status}</div>
                  {submitResult.approval_id && <div>approval_id: {submitResult.approval_id}</div>}
                  <Link href={`/executions/${submitResult.execution_id}`} className="inline-flex items-center gap-1 text-emerald-700 underline">
                    查看详情 <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>最近执行单</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {recentExecutions.length === 0 ? (
            <p className="text-sm text-slate-500">暂无执行记录</p>
          ) : (
            recentExecutions.map((item) => (
              <div key={item.id} className="rounded-md border border-slate-200 px-3 py-2 text-sm flex items-center justify-between gap-2">
                <div className="space-y-1">
                  <div className="font-medium">{item.tool_name}</div>
                  <div className="text-xs text-slate-500">{item.id} · {item.environment} · {formatDate(item.updated_at)}</div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={item.status} />
                  <RiskBadge level={item.risk_level} />
                  <Link href={`/executions/${item.id}`}>
                    <Button size="sm" variant="secondary">详情</Button>
                  </Link>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
