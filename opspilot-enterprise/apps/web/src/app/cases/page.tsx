"use client";

import { useEffect, useState } from "react";
import { type CaseArchive } from "@opspilot/shared-types";

import { PageHeader } from "@/components/ui/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type CasesEnvelope = { data?: { items?: CaseArchive[] } };

export default function CasesPage() {
  const [items, setItems] = useState<CaseArchive[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCases = async () => {
    try {
      const res = await apiFetch<CasesEnvelope>("/api/v1/cases");
      setItems(res.data?.items ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load cases");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
    const timer = setInterval(loadCases, 8000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader
        title="案例归档"
        description="展示闭环自动归档生成的复盘案例。"
        actions={
          <Button variant="secondary" size="sm" onClick={loadCases}>
            刷新
          </Button>
        }
      />
      {loading && <div className="text-sm text-slate-500">正在加载案例...</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}

      <div className="rounded-xl border border-slate-200 bg-white p-3">
        {items.length === 0 && <div className="text-sm text-slate-500">暂无归档案例</div>}
        <div className="space-y-2">
          {items.map((c) => (
            <div key={c.id} className="rounded-lg border border-slate-200 p-3">
              <div className="mb-1 flex items-center justify-between gap-2">
                <div className="font-medium">{c.title}</div>
                <Badge variant="neutral">{c.category}</Badge>
              </div>
              <div className="mb-1 text-sm text-slate-700">{c.summary}</div>
              <div className="text-xs text-slate-500">
                归档时间: {c.archived_at ? formatDate(c.archived_at) : "-"} · 严重级别: {c.severity}
              </div>
              <div className="mt-2 grid gap-1 text-xs text-slate-600">
                <div>根因: {c.root_cause_summary}</div>
                <div>处置: {c.resolution_summary}</div>
                <div>复盘建议: {c.lessons_learned}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
