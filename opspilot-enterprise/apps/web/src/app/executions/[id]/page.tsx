"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Loader2, XCircle } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, RiskBadge, StatusBadge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type ExecutionDetail = {
  id: string;
  tool_name: string;
  action_type: string;
  environment: string;
  requester: string;
  status: string;
  incident_id: string | null;
  change_analysis_ref: string | null;
  approval_id: string | null;
  risk_level: string;
  risk_score: number;
  require_approval: boolean;
  policy: { reason?: string };
  parameters: Record<string, unknown>;
  result: Record<string, unknown>;
  targets: Array<{
    object_id: string;
    object_name: string;
    object_type: string;
    status: string;
    result: Record<string, unknown>;
  }>;
  steps: Array<{
    step_type: string;
    status: string;
    detail: Record<string, unknown>;
    created_at: string;
  }>;
  created_at: string;
  updated_at: string;
};

export default function ExecutionDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [data, setData] = useState<ExecutionDetail | null>(null);
  const [canceling, setCanceling] = useState(false);

  async function loadDetail() {
    if (!id) return;
    setLoading(true);
    const res = await apiFetch<{ success: boolean; data?: ExecutionDetail; error?: string }>(`/api/v1/executions/${id}`);
    if (!res.success || !res.data) {
      setErrorText(res.error || "load execution failed");
      setData(null);
    } else {
      setData(res.data);
      setErrorText(null);
    }
    setLoading(false);
  }

  useEffect(() => {
    loadDetail().catch((e) => setErrorText(e instanceof Error ? e.message : "load failed"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function onCancel() {
    if (!id) return;
    setCanceling(true);
    try {
      const res = await apiFetch<{ success: boolean; error?: string }>(`/api/v1/executions/${id}/cancel`, {
        method: "POST",
        body: "{}",
      });
      if (!res.success) {
        setErrorText(res.error || "cancel failed");
      } else {
        await loadDetail();
      }
    } catch (e) {
      setErrorText(e instanceof Error ? e.message : "cancel failed");
    } finally {
      setCanceling(false);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="执行单详情"
        description={id}
        actions={
          <div className="flex gap-2">
            <Link href="/executions">
              <Button variant="secondary" size="sm">返回列表</Button>
            </Link>
            <Button
              variant="secondary"
              size="sm"
              onClick={onCancel}
              disabled={canceling || !data || !["pending_approval", "dry_run_ready", "draft"].includes(data.status)}
            >
              {canceling ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
              取消执行
            </Button>
          </div>
        }
      />

      {errorText && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{errorText}</div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Loader2 className="h-4 w-4 animate-spin" /> 加载中...
        </div>
      )}

      {data && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>基础信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <StatusBadge status={data.status} />
                <RiskBadge level={data.risk_level} />
                <Badge variant={data.require_approval ? "warning" : "info"}>
                  {data.require_approval ? "需审批" : "自动执行"}
                </Badge>
              </div>
              <div>tool: {data.tool_name}</div>
              <div>requester: {data.requester}</div>
              <div>environment: {data.environment}</div>
              <div>approval_id: {data.approval_id ?? "-"}</div>
              <div>policy_reason: {data.policy?.reason ?? "-"}</div>
              <div>updated_at: {formatDate(data.updated_at)}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>目标对象</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {data.targets.map((target) => (
                <div key={`${target.object_type}-${target.object_id}`} className="rounded-md border border-slate-200 px-3 py-2 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-medium">{target.object_name}</div>
                    <StatusBadge status={target.status} />
                  </div>
                  <div className="text-xs text-slate-500">{target.object_type} / {target.object_id}</div>
                  <pre className="mt-1 overflow-auto rounded bg-slate-50 p-2 text-[11px] text-slate-700">
                    {JSON.stringify(target.result, null, 2)}
                  </pre>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>步骤时间线</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {data.steps.map((step, idx) => (
                <div key={`${step.step_type}-${idx}`} className="rounded-md border border-slate-200 px-3 py-2 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="neutral">{step.step_type}</Badge>
                    <StatusBadge status={step.status} />
                  </div>
                  <div className="text-xs text-slate-500 mt-1">{formatDate(step.created_at)}</div>
                  <pre className="mt-1 overflow-auto rounded bg-slate-50 p-2 text-[11px] text-slate-700">
                    {JSON.stringify(step.detail, null, 2)}
                  </pre>
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
