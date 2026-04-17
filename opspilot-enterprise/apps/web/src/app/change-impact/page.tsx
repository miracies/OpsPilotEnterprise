"use client";

import { type ReactNode, useMemo, useState } from "react";
import {
  AlertTriangle,
  Loader2,
  Play,
  RotateCcw,
  ShieldAlert,
  CheckCircle2,
  Network,
} from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, RiskBadge, SeverityBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

type ChangeImpactResponse = {
  request_id: string;
  success: boolean;
  message: string;
  data?: {
    analysis_id: string;
    target: {
      target_type: string;
      target_id: string;
      environment: string;
    };
    action: string;
    risk_score: number;
    risk_level: "critical" | "high" | "medium" | "low";
    impacted_objects: Array<{
      object_type: string;
      object_id: string;
      object_name: string;
      impact_type: string;
      severity: "critical" | "high" | "medium" | "low" | "info";
    }>;
    checks_required: string[];
    rollback_plan: string[];
    approval_suggestion: "required" | "recommended" | "not_required";
    dependency_graph: Array<{
      id: string;
      name: string;
      type: string;
      children: Array<{ id: string; name: string; type: string }>;
    }>;
    evidence_sufficiency?: {
      required_evidence_types: string[];
      present_evidence_types: string[];
      missing_critical_evidence: string[];
      sufficiency_score: number;
      freshness_score: number;
    };
    conclusion_status?: "confirmed" | "probable" | "insufficient_evidence" | "contradicted";
    counter_evidence_result?: {
      status: "refuted" | "not_refuted" | "inconclusive";
      checked_hypothesis_id?: string | null;
      summary: string;
      evidence_refs: string[];
    };
    hypotheses?: Array<{
      summary: string;
      category: string;
      confidence: number;
      missing_evidence?: string[];
    }>;
  };
  error?: string;
};

const riskScoreColor = (score: number) =>
  score >= 80 ? "text-red-600" :
  score >= 60 ? "text-amber-600" :
  score >= 35 ? "text-blue-600" : "text-emerald-600";

const riskScoreBg = (score: number) =>
  score >= 80 ? "bg-red-50 border-red-200" :
  score >= 60 ? "bg-amber-50 border-amber-200" :
  score >= 35 ? "bg-blue-50 border-blue-200" : "bg-emerald-50 border-emerald-200";

export default function ChangeImpactPage() {
  const [changeType, setChangeType] = useState("infrastructure");
  const [targetType, setTargetType] = useState("HostSystem");
  const [targetId, setTargetId] = useState("10.0.80.11");
  const [requestedAction, setRequestedAction] = useState("检查并调整主机资源配置");
  const [environment, setEnvironment] = useState("prod");
  const [changeWindow, setChangeWindow] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ChangeImpactResponse["data"] | null>(null);

  const executionHref = useMemo(() => {
    if (!result) return "/executions";
    const action = result.action.toLowerCase();
    const targetType = result.target.target_type.toLowerCase();
    const hostRestart =
      targetType.includes("host") &&
      (action.includes("restart") || action.includes("reboot") || result.action.includes("重启"));
    const toolName = hostRestart
      ? "vmware.host_restart"
      : action.includes("迁移") || action.includes("migrate")
        ? "vmware.vm_migrate"
        : "vmware.vm_guest_restart";
    const targets = JSON.stringify([
      {
        object_id: result.target.target_id,
        object_name: result.target.target_id,
        object_type: result.target.target_type,
      },
    ]);
    return `/executions?tool_name=${encodeURIComponent(toolName)}&change_analysis_ref=${encodeURIComponent(result.analysis_id)}&targets=${encodeURIComponent(targets)}`;
  }, [result]);

  const runAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = {
        change_type: changeType,
        target_type: targetType,
        target_id: targetId,
        requested_action: requestedAction,
        environment,
        change_window: changeWindow || undefined,
      };
      const resp = await apiFetch<ChangeImpactResponse>("/api/v1/change-impact/analyze", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!resp.success || !resp.data) {
        throw new Error(resp.error || "变更影响分析失败");
      }
      setResult(resp.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "变更影响分析失败");
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setChangeType("infrastructure");
    setTargetType("HostSystem");
    setTargetId("10.0.80.11");
    setRequestedAction("检查并调整主机资源配置");
    setEnvironment("prod");
    setChangeWindow("");
    setResult(null);
    setError(null);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="变更影响分析"
        description="基于真实 vCenter / Kubernetes 数据，评估变更风险、影响范围与审批建议。"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={resetForm}>
              <RotateCcw className="h-3.5 w-3.5" />
              重置
            </Button>
            <Button variant="primary" size="sm" onClick={runAnalysis} disabled={loading}>
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              发起分析
            </Button>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>分析请求</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field label="变更类型">
              <input className="w-full rounded border px-2 py-1.5 text-sm" value={changeType} onChange={(e) => setChangeType(e.target.value)} />
            </Field>
            <Field label="目标类型">
              <select className="w-full rounded border px-2 py-1.5 text-sm" value={targetType} onChange={(e) => setTargetType(e.target.value)}>
                <option value="HostSystem">HostSystem</option>
                <option value="VirtualMachine">VirtualMachine</option>
                <option value="ClusterComputeResource">ClusterComputeResource</option>
                <option value="Deployment">Deployment</option>
              </select>
            </Field>
            <Field label="目标对象">
              <input className="w-full rounded border px-2 py-1.5 text-sm" value={targetId} onChange={(e) => setTargetId(e.target.value)} />
            </Field>
            <Field label="环境">
              <select className="w-full rounded border px-2 py-1.5 text-sm" value={environment} onChange={(e) => setEnvironment(e.target.value)}>
                <option value="prod">prod</option>
                <option value="staging">staging</option>
                <option value="test">test</option>
              </select>
            </Field>
            <Field label="变更动作">
              <input className="w-full rounded border px-2 py-1.5 text-sm" value={requestedAction} onChange={(e) => setRequestedAction(e.target.value)} />
            </Field>
            <Field label="变更窗口（可选）">
              <input className="w-full rounded border px-2 py-1.5 text-sm" value={changeWindow} onChange={(e) => setChangeWindow(e.target.value)} placeholder="例如 2026-04-16 23:00-01:00" />
            </Field>
          </div>
          {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
        </CardContent>
      </Card>

      {result && (
        <>
          <Card className={cn("border-2", riskScoreBg(result.risk_score))}>
            <CardContent className="py-5">
              <div className="flex flex-wrap items-center gap-6">
                <div>
                  <div className={cn("text-4xl font-black", riskScoreColor(result.risk_score))}>{result.risk_score}</div>
                  <div className="text-xs text-slate-500">风险评分 / 100</div>
                </div>
                <RiskBadge level={result.risk_level} />
                <Badge variant="warning" dot>
                  审批建议：{result.approval_suggestion}
                </Badge>
                <div className="text-sm text-slate-700">
                  目标：{result.target.target_type} / {result.target.target_id}
                </div>
                <div className="text-sm text-slate-700">动作：{result.action}</div>
              </div>
            </CardContent>
          </Card>

          {(result.conclusion_status || result.evidence_sufficiency || (result.hypotheses && result.hypotheses.length > 0)) && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-slate-600" />
                  分析约束与证据门禁
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-slate-700">
                {result.conclusion_status && (
                  <div>
                    <span className="font-medium text-slate-500">结论状态：</span>
                    {result.conclusion_status}
                  </div>
                )}
                {result.evidence_sufficiency && (
                  <>
                    <div>
                      <span className="font-medium text-slate-500">证据充分性：</span>
                      {(result.evidence_sufficiency.sufficiency_score ?? 0).toFixed(2)}
                      {" / "}
                      新鲜度 {(result.evidence_sufficiency.freshness_score ?? 0).toFixed(2)}
                    </div>
                    {result.evidence_sufficiency.missing_critical_evidence.length > 0 && (
                      <div className="text-amber-700">
                        缺失关键证据：{result.evidence_sufficiency.missing_critical_evidence.join("、")}
                      </div>
                    )}
                  </>
                )}
                {result.counter_evidence_result && (
                  <div>
                    <span className="font-medium text-slate-500">反证结果：</span>
                    {result.counter_evidence_result.status}，{result.counter_evidence_result.summary}
                  </div>
                )}
                {result.hypotheses && result.hypotheses.length > 0 && (
                  <div className="space-y-1">
                    <div className="font-medium text-slate-500">候选影响假设</div>
                    {result.hypotheses.slice(0, 3).map((item, index) => (
                      <div key={`${item.category}-${index}`} className="rounded border bg-slate-50 p-2">
                        <div className="font-medium text-slate-900">
                          {item.summary} ({(item.confidence ?? 0).toFixed(2)})
                        </div>
                        {item.missing_evidence && item.missing_evidence.length > 0 && (
                          <div className="text-xs text-amber-700">缺口：{item.missing_evidence.join("、")}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                  受影响对象
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {result.impacted_objects.length === 0 && <div className="text-sm text-slate-500">无</div>}
                {result.impacted_objects.map((item) => (
                  <div key={`${item.object_type}-${item.object_id}`} className="rounded border bg-slate-50 p-2">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium text-slate-900">{item.object_name}</div>
                      <SeverityBadge severity={item.severity} />
                    </div>
                    <div className="text-xs text-slate-500">{item.object_type} / {item.object_id}</div>
                    <div className="text-xs text-slate-600">影响类型：{item.impact_type}</div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Network className="h-4 w-4 text-blue-500" />
                  依赖关系
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {result.dependency_graph.length === 0 && <div className="text-sm text-slate-500">无</div>}
                {result.dependency_graph.map((node) => (
                  <div key={node.id} className="rounded border bg-slate-50 p-2">
                    <div className="text-sm font-semibold">{node.name} <span className="text-xs text-slate-500">({node.type})</span></div>
                    {node.children.length > 0 && (
                      <div className="mt-1 space-y-1 border-l-2 border-slate-200 pl-2">
                        {node.children.map((child) => (
                          <div key={child.id} className="text-xs text-slate-700">
                            {child.name} ({child.type})
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                  前置检查
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {result.checks_required.map((c, i) => (
                  <div key={i} className="rounded border bg-slate-50 p-2 text-sm text-slate-700">{c}</div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-slate-600" />
                  回滚方案
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {result.rollback_plan.map((r, i) => (
                  <div key={i} className="rounded border bg-slate-50 p-2 text-sm text-slate-700">{i + 1}. {r}</div>
                ))}
              </CardContent>
            </Card>
          </div>

          <div className="rounded-xl border border-blue-100 bg-blue-50/40 p-4">
            <div className="mb-2 text-sm font-semibold text-blue-800">下一步</div>
            <div className="flex gap-2">
              <Link href={executionHref}>
                <Button variant="primary" size="sm">发起执行申请</Button>
              </Link>
              <Link href="/policies">
                <Button variant="secondary" size="sm">查看策略</Button>
              </Link>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1 text-xs font-medium text-slate-600">{label}</div>
      {children}
    </label>
  );
}
