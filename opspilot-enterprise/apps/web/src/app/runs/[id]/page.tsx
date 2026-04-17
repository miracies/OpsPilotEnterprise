"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import type { AuditTimelineData, ResumeResponse } from "@opspilot/shared-types";

import { AuditTimeline } from "@/components/chat/AuditTimeline";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = params?.id;
  const [timeline, setTimeline] = useState<AuditTimelineData | null>(null);
  const [resumeResult, setResumeResult] = useState<ResumeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!runId) return;
    try {
      const res = await apiFetch<{ success: boolean; error?: string; data?: AuditTimelineData }>(`/api/v1/runs/${runId}/audit`);
      if (!res.success || !res.data) throw new Error(res.error || "加载审计失败");
      setTimeline(res.data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载审计失败");
    }
  }

  useEffect(() => {
    void load();
  }, [runId]);

  async function resume(mode: "continue" | "rollback") {
    if (!runId) return;
    const res = await apiFetch<{ success: boolean; error?: string; data?: ResumeResponse }>(`/api/v1/runs/${runId}/resume`, {
      method: "POST",
      body: JSON.stringify({ mode }),
    });
    if (!res.success || !res.data) {
      setError(res.error || "执行 resume 失败");
      return;
    }
    setResumeResult(res.data);
    await load();
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Run 审计" description="查看执行审计时间线，并从最近安全点继续或回滚。" />
      {error && <div className="text-sm text-red-600">{error}</div>}
      {timeline && <AuditTimeline data={timeline} />}
      <Card className="p-4">
        <p className="text-sm font-semibold text-slate-900">Resume 操作</p>
        <div className="mt-3 flex gap-2">
          <Button size="sm" onClick={() => void resume("continue")}>从断点继续</Button>
          <Button size="sm" variant="secondary" onClick={() => void resume("rollback")}>从安全点回滚</Button>
        </div>
        {resumeResult && (
          <div className="mt-3 text-sm text-slate-700">
            <p>状态：{resumeResult.status}</p>
            <p>结果：{resumeResult.message}</p>
          </div>
        )}
      </Card>
    </div>
  );
}
