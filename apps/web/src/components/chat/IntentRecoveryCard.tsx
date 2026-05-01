"use client";

import type { ExecutionIntent, IntentRecoveryRun, RiskContext } from "@opspilot/shared-types";

import { Badge, RiskBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function IntentRecoveryCard({
  run,
  executionIntent,
  riskContext,
  memoryRefs,
  evidenceRefs,
}: {
  run: IntentRecoveryRun;
  executionIntent?: ExecutionIntent | null;
  riskContext?: RiskContext | null;
  memoryRefs?: string[];
  evidenceRefs?: string[];
}) {
  const top = run.candidates?.slice(0, 3) ?? [];
  const selected = run.chosen_intent ?? top[0];
  const missingSlots = selected?.missing_slots ?? [];
  return (
    <Card className="mt-3 border-blue-200 bg-blue-50/40 p-3">
      <details>
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-xs font-semibold text-blue-700">Intent Recovery</p>
              <Badge variant={run.decision === "recovered" ? "success" : run.decision === "clarify_required" ? "warning" : "danger"}>
                {run.decision}
              </Badge>
            </div>
            <p className="mt-1 truncate text-[11px] text-slate-500">
              {selected?.intent_code ?? "未命中意图"} · run_id: {run.run_id}
              {missingSlots.length > 0 ? ` · 缺少槽位：${missingSlots.join("、")}` : ""}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-white/80 px-2 py-1 text-[11px] font-medium text-blue-700">
            展开详情
          </span>
        </summary>
      <div className="mt-3 space-y-2 text-xs text-slate-700">
        {executionIntent && (
          <div className="rounded-lg border border-white bg-white/80 p-2">
            <p className="font-medium text-slate-900">执行意图：{executionIntent.mode}</p>
            <p className="mt-1 text-slate-600">{executionIntent.reason}</p>
            {executionIntent.guardrails?.length > 0 && (
              <p className="mt-1 text-amber-700">门禁：{executionIntent.guardrails.join("、")}</p>
            )}
          </div>
        )}

        {riskContext && (
          <div className="rounded-lg border border-white bg-white/80 p-2 text-slate-700">
            <p>环境：{riskContext.environment}</p>
            <p>范围：{riskContext.resource_scope}</p>
            <p>对象数：{riskContext.object_count}</p>
          </div>
        )}

        {top.map((candidate) => (
          <div key={candidate.intent_code} className="rounded-lg border border-white bg-white/80 p-2">
            <div className="flex items-center justify-between gap-2">
              <p className="font-medium text-slate-900">{candidate.intent_code}</p>
              <div className="flex items-center gap-2">
                {candidate.inferred_risk_level && <RiskBadge level={candidate.inferred_risk_level} />}
                <span className="font-mono text-[11px] text-slate-500">{candidate.score.toFixed(2)}</span>
              </div>
            </div>
            <p className="mt-1 text-slate-600">{candidate.description}</p>
            {candidate.target_object_raw && (
              <p className="mt-1 text-slate-600">
                目标对象：{candidate.target_object_raw}
                {candidate.target_object_resolved ? ` -> ${candidate.target_object_resolved}` : ""}
              </p>
            )}
            {candidate.target_type && (
              <p className="mt-1 text-slate-500">
                对象类型：{candidate.target_type} | 解析置信度：{candidate.resolution_confidence.toFixed(2)}
              </p>
            )}
            {candidate.missing_slots.length > 0 && (
              <p className="mt-1 text-amber-700">缺少槽位：{candidate.missing_slots.join("、")}</p>
            )}
            {!candidate.target_object_resolved && candidate.target_object_raw && candidate.resolution_refs.length === 0 && (
              <p className="mt-1 text-amber-700">已识别目标对象 mention，但当前连接未解析到匹配对象。</p>
            )}
          </div>
        ))}

        {(memoryRefs?.length || evidenceRefs?.length) && (
          <div className="rounded-lg border border-white bg-white/80 p-2 text-slate-700">
            {memoryRefs && memoryRefs.length > 0 && <p>记忆命中：{memoryRefs.join("、")}</p>}
            {evidenceRefs && evidenceRefs.length > 0 && <p className="mt-1">证据引用：{evidenceRefs.join("、")}</p>}
          </div>
        )}
      </div>
      </details>
    </Card>
  );
}
