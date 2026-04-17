"use client";

import type { IntentRecoveryRun } from "@opspilot/shared-types";

import { Badge, RiskBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function IntentRecoveryCard({ run }: { run: IntentRecoveryRun }) {
  const top = run.candidates?.slice(0, 3) ?? [];
  return (
    <Card className="mt-3 border-blue-200 bg-blue-50/40 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold text-blue-700">Intent Recovery</p>
          <p className="text-[11px] text-slate-500">run_id: {run.run_id}</p>
        </div>
        <Badge variant={run.decision === "recovered" ? "success" : run.decision === "clarify_required" ? "warning" : "danger"}>
          {run.decision}
        </Badge>
      </div>
      <div className="space-y-2 text-xs text-slate-700">
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
            {candidate.missing_slots.length > 0 && (
              <p className="mt-1 text-amber-700">缺少槽位：{candidate.missing_slots.join("、")}</p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
