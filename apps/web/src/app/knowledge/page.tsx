"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BarChart3, BookOpen, RefreshCw, Upload, Wand2 } from "lucide-react";
import type { KnowledgeImportJob } from "@opspilot/shared-types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type Envelope<T> = { success?: boolean; data?: T; error?: string };
type KnowledgeStats = {
  total: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  vmware_alert_knowledge: number;
  hit_count_total: number;
  negative_feedback_total: number;
};

const categories = ["resource", "ha_cluster", "vmotion_drs", "storage", "network", "vm_level"];

export default function KnowledgeOverviewPage() {
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [jobs, setJobs] = useState<KnowledgeImportJob[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiFetch<Envelope<KnowledgeStats>>("/api/v1/knowledge/stats"),
      apiFetch<Envelope<{ items: KnowledgeImportJob[] }>>("/api/v1/knowledge/import-jobs"),
    ])
      .then(([statsRes, jobsRes]) => {
        if (cancelled) return;
        setStats(statsRes.data ?? null);
        setJobs(jobsRes.data?.items ?? []);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load knowledge data");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader
        title="知识管理"
        description="结构化告警知识、证据约束、案例复用和人工反馈。"
        actions={
          <div className="flex gap-2">
            <Link href="/knowledge/test-alert-match">
              <Button variant="secondary" size="sm"><Wand2 className="h-3.5 w-3.5" />测试匹配</Button>
            </Link>
            <Link href="/knowledge/import">
              <Button size="sm"><Upload className="h-3.5 w-3.5" />导入知识</Button>
            </Link>
          </div>
        }
      />

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Metric label="总知识" value={stats?.total ?? 0} />
        <Metric label="Published" value={stats?.by_status?.published ?? 0} />
        <Metric label="Draft" value={stats?.by_status?.draft ?? 0} />
        <Metric label="Deprecated" value={stats?.by_status?.deprecated ?? 0} />
        <Metric label="VMware" value={stats?.vmware_alert_knowledge ?? 0} />
        <Metric label="负反馈" value={stats?.negative_feedback_total ?? 0} tone="danger" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><BarChart3 className="h-4 w-4 text-slate-400" />分类统计</CardTitle>
            <Link href="/knowledge/alert-items" className="text-xs font-medium text-blue-600 hover:underline">查看列表</Link>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {categories.map((category) => {
                const value = stats?.by_category?.[category] ?? 0;
                const pct = stats?.total ? Math.round((value / stats.total) * 100) : 0;
                return (
                  <div key={category}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="font-medium text-slate-700">{category}</span>
                      <span className="text-slate-500">{value}</span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-100">
                      <div className="h-2 rounded-full bg-blue-600" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><RefreshCw className="h-4 w-4 text-slate-400" />最近导入任务</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {jobs.slice(0, 6).map((job) => (
              <div key={job.id} className="rounded-lg border border-slate-200 p-3">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-xs text-slate-700">{job.id}</span>
                  <Badge variant={job.status === "completed" ? "success" : job.status === "failed" ? "danger" : "warning"}>{job.status}</Badge>
                </div>
                <div className="text-xs text-slate-500">{job.source_type} · {formatDate(job.started_at)}</div>
                <div className="mt-2 flex gap-3 text-xs">
                  <span className="text-emerald-700">created {job.created ?? job.articles_imported}</span>
                  <span className="text-blue-700">updated {job.updated ?? 0}</span>
                  <span className="text-red-700">failed {job.failed ?? job.articles_failed}</span>
                </div>
              </div>
            ))}
            {jobs.length === 0 && <div className="text-sm text-slate-500">暂无导入任务</div>}
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-wrap gap-2">
        <Link href="/knowledge/alert-items"><Button variant="secondary"><BookOpen className="h-4 w-4" />告警知识列表</Button></Link>
        <Link href="/knowledge/import"><Button variant="secondary"><Upload className="h-4 w-4" />导入与校验</Button></Link>
        <Link href="/knowledge/test-alert-match"><Button variant="secondary"><Wand2 className="h-4 w-4" />匹配实验台</Button></Link>
      </div>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone?: "danger" }) {
  return (
    <Card>
      <CardContent className="py-3">
        <div className="text-xs text-slate-500">{label}</div>
        <div className={tone === "danger" ? "mt-1 text-2xl font-semibold text-red-600" : "mt-1 text-2xl font-semibold text-slate-900"}>{value}</div>
      </CardContent>
    </Card>
  );
}
