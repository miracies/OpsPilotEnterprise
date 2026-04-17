"use client";

import { useState } from "react";
import type { ApprovalRecord } from "@opspilot/shared-types";

import { RiskBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

export function ApprovalCard({
  record,
  onResolved,
}: {
  record: ApprovalRecord;
  onResolved?: (payload: Record<string, unknown>) => void;
}) {
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function decide(decision: "approved" | "rejected") {
    setSubmitting(true);
    try {
      const res = await apiFetch<{ data?: Record<string, unknown> }>(`/api/v1/interactions/approve/${record.approval_id}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision, scope: record.allowed_scopes[0], comment: comment || null, approved_by: "web-user" }),
      });
      setResult(decision === "approved" ? "已提交审批通过" : "已提交审批驳回");
      if (res.data && onResolved) {
        onResolved(res.data);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="mt-3 border-orange-200 bg-orange-50/40 p-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-orange-700">Approval</p>
          <p className="text-sm text-slate-900">{record.summary}</p>
        </div>
        <RiskBadge level={record.risk_level} />
      </div>
      <div className="mt-3 space-y-2 text-xs text-slate-700">
        <p>环境：{record.resource_scope.environment}</p>
        <p>目标：{record.resource_scope.resources.map((item) => item.name || item.id).join("、") || "未指定"}</p>
        <p>计划步骤：{record.plan_steps.join(" -> ") || "未生成"}</p>
        <p>回滚方案：{record.rollback_plan.join("；") || "未提供"}</p>
        <p>授权范围：{record.allowed_scopes.join(" / ")}</p>
      </div>
      <textarea
        className="mt-3 min-h-[72px] w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500"
        value={comment}
        disabled={submitting || !!result}
        onChange={(event) => setComment(event.target.value)}
        placeholder="填写审批意见（驳回时建议必填）"
      />
      <div className="mt-3 flex gap-2">
        <Button size="sm" disabled={submitting || !!result} onClick={() => void decide("approved")}>提交审批</Button>
        <Button size="sm" variant="secondary" disabled={submitting || !!result} onClick={() => void decide("rejected")}>拒绝</Button>
      </div>
      {result && <p className="mt-2 text-xs text-emerald-700">{result}</p>}
    </Card>
  );
}
