"use client";

import { useState } from "react";
import type { ClarifyRecord } from "@opspilot/shared-types";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

export function ClarifyCard({
  record,
  onResolved,
}: {
  record: ClarifyRecord;
  onResolved?: (payload: Record<string, unknown>) => void;
}) {
  const [freeText, setFreeText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  async function submit(selectedChoice?: string) {
    setSubmitting(true);
    try {
      const res = await apiFetch<{ data?: Record<string, unknown> }>(`/api/v1/interactions/clarify/${record.interaction_id}/answer`, {
        method: "POST",
        body: JSON.stringify({ selected_choice: selectedChoice ?? null, free_text: freeText || null, responded_by: "web-user" }),
      });
      setDone(selectedChoice ?? (freeText || "已提交"));
      if (res.data && onResolved) {
        onResolved(res.data);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="mt-3 border-amber-200 bg-amber-50/40 p-3">
      <p className="text-xs font-semibold text-amber-700">需要补充信息</p>
      <p className="mt-1 text-sm text-slate-800">{record.question}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {record.choices.map((choice) => (
          <Button key={choice} size="sm" variant="secondary" disabled={submitting || !!done} onClick={() => void submit(choice)}>
            {choice}
          </Button>
        ))}
      </div>
      {record.allow_free_text && (
        <div className="mt-3 space-y-2">
          <textarea
            className="min-h-[72px] w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500"
            value={freeText}
            disabled={submitting || !!done}
            onChange={(event) => setFreeText(event.target.value)}
            placeholder="也可以直接输入更明确的目标或环境"
          />
          <Button size="sm" disabled={submitting || !!done || !freeText.trim()} onClick={() => void submit()}>
            提交补充信息
          </Button>
        </div>
      )}
      {done && <p className="mt-2 text-xs text-emerald-700">已提交：{done}</p>}
    </Card>
  );
}
