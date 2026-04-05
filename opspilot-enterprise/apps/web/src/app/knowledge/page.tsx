"use client";

import { useState } from "react";
import {
  BookOpen, Search, Upload, RefreshCw, CheckCircle2,
  AlertCircle, Clock, Loader2, Star, Tag, ExternalLink,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockKnowledgeArticles, mockKnowledgeImportJobs } from "@/lib/mock-data";

const SOURCE_STYLE: Record<string, string> = {
  manual:       "bg-slate-100 text-slate-600",
  runbook:      "bg-blue-50 text-blue-700",
  confluence:   "bg-sky-50 text-sky-700",
  gitlab:       "bg-orange-50 text-orange-700",
  ai_generated: "bg-purple-50 text-purple-700",
  case_derived: "bg-emerald-50 text-emerald-700",
};

const SOURCE_LABEL: Record<string, string> = {
  manual:       "手动",
  runbook:      "Runbook",
  confluence:   "Confluence",
  gitlab:       "GitLab",
  ai_generated: "AI 生成",
  case_derived: "案例派生",
};

const STATUS_STYLE: Record<string, string> = {
  published: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  draft:     "bg-slate-100 text-slate-600 ring-slate-300",
  archived:  "bg-slate-100 text-slate-500 ring-slate-200",
  reviewing: "bg-amber-50 text-amber-700 ring-amber-600/20",
};

const STATUS_LABEL: Record<string, string> = {
  published: "已发布",
  draft:     "草稿",
  archived:  "已归档",
  reviewing: "审核中",
};

const JOB_META: Record<string, { icon: React.ElementType; cls: string; label: string }> = {
  completed: { icon: CheckCircle2, cls: "text-emerald-600", label: "已完成" },
  running:   { icon: Loader2,      cls: "text-blue-600 animate-spin", label: "导入中" },
  queued:    { icon: Clock,        cls: "text-slate-500", label: "排队中" },
  failed:    { icon: AlertCircle,  cls: "text-red-600", label: "失败" },
};

export default function KnowledgePage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selected, setSelected] = useState<string | null>(mockKnowledgeArticles[0]?.id ?? null);

  const filtered = mockKnowledgeArticles.filter((a) => {
    if (statusFilter !== "all" && a.status !== statusFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return a.title.toLowerCase().includes(q) || a.tags.some((t) => t.toLowerCase().includes(q));
    }
    return true;
  });

  const detail = mockKnowledgeArticles.find((a) => a.id === selected);

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <PageHeader
        title="知识管理"
        description="运维知识库：Runbook、最佳实践与 AI 生成知识条目管理"
        actions={
          <Button variant="primary" size="sm">
            <Upload className="h-3.5 w-3.5" /> 导入知识
          </Button>
        }
      />

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Article list + filters */}
        <div className="flex-1 flex flex-col min-h-0">
          {/* Filter bar */}
          <div className="flex items-center gap-3 mb-3">
            <div className="relative flex-1 max-w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="搜索标题、标签..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full h-9 pl-8 pr-3 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div className="flex items-center gap-1.5">
              {["all", "published", "reviewing", "draft"].map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                    statusFilter === s
                      ? "bg-blue-600 text-white shadow-sm"
                      : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
                  )}
                >
                  {s === "all" ? "全部" : STATUS_LABEL[s]}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)] flex-1">
            <div className="divide-y divide-slate-50">
              {filtered.map((art) => (
                <div
                  key={art.id}
                  onClick={() => setSelected(art.id)}
                  className={cn(
                    "px-5 py-4 cursor-pointer transition-colors",
                    selected === art.id ? "bg-blue-50" : "hover:bg-slate-50"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className="h-9 w-9 rounded-lg bg-blue-50 flex items-center justify-center shrink-0 mt-0.5">
                      <BookOpen className="h-4 w-4 text-blue-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold", SOURCE_STYLE[art.source])}>
                          {SOURCE_LABEL[art.source] ?? art.source}
                        </span>
                        <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold ring-1 ring-inset", STATUS_STYLE[art.status])}>
                          {STATUS_LABEL[art.status]}
                        </span>
                        <span className="text-[10px] text-slate-400">v{art.version}</span>
                        <span className="ml-auto text-[10px] text-slate-400 flex items-center gap-1">
                          <Star className="h-2.5 w-2.5 text-amber-400 fill-amber-300" /> {art.hit_count} 次引用
                        </span>
                      </div>
                      <p className="text-sm font-medium text-slate-900 truncate">{art.title}</p>
                      <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{art.content_summary}</p>
                      <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                        {art.tags.slice(0, 5).map((t) => (
                          <Badge key={t} variant="neutral">{t}</Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Detail + Import jobs */}
        <div className="w-72 shrink-0 space-y-3 overflow-y-auto">
          {detail && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-1.5">
                  <BookOpen className="h-3.5 w-3.5 text-slate-400" /> 知识详情
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">内容摘要</p>
                  <p className="text-xs text-slate-700 leading-relaxed">{detail.content_summary}</p>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg bg-slate-50 border border-slate-100 p-2">
                    <p className="text-[10px] text-slate-400 mb-0.5">置信度</p>
                    <p className="text-sm font-bold text-blue-600">{(detail.confidence_score * 100).toFixed(0)}%</p>
                  </div>
                  <div className="rounded-lg bg-slate-50 border border-slate-100 p-2">
                    <p className="text-[10px] text-slate-400 mb-0.5">引用次数</p>
                    <p className="text-sm font-bold text-amber-600">{detail.hit_count}</p>
                  </div>
                </div>

                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">来源 & 版本</p>
                  <div className="flex items-center gap-2">
                    <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold", SOURCE_STYLE[detail.source])}>
                      {SOURCE_LABEL[detail.source]}
                    </span>
                    <span className="text-xs text-slate-500">v{detail.version}</span>
                    <span className="text-xs text-slate-400">by {detail.author}</span>
                  </div>
                </div>

                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">标签</p>
                  <div className="flex flex-wrap gap-1.5">
                    {detail.tags.map((t) => (
                      <Badge key={t} variant="neutral">{t}</Badge>
                    ))}
                  </div>
                </div>

                {detail.related_incident_ids.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">关联故障</p>
                    <div className="flex flex-wrap gap-1.5">
                      {detail.related_incident_ids.map((id) => (
                        <a key={id} href="/incidents" className="text-[11px] text-blue-600 bg-blue-50 rounded px-1.5 py-0.5 font-mono hover:underline">{id}</a>
                      ))}
                    </div>
                  </div>
                )}

                <div className="text-[11px] text-slate-400 space-y-0.5">
                  <p>创建：{formatDate(detail.created_at)}</p>
                  <p>更新：{formatDate(detail.updated_at)}</p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Import jobs */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <RefreshCw className="h-3.5 w-3.5 text-slate-400" /> 导入任务
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {mockKnowledgeImportJobs.map((job) => {
                const meta = JOB_META[job.status] ?? JOB_META.queued;
                const Icon = meta.icon;
                return (
                  <div key={job.id} className="rounded-lg border border-slate-100 bg-slate-50/50 p-3">
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <Icon className={cn("h-3.5 w-3.5", meta.cls)} />
                        <span className="text-xs font-semibold text-slate-700">{SOURCE_LABEL[job.source_type]}</span>
                      </div>
                      <span className="text-[10px] text-slate-400">{job.id}</span>
                    </div>
                    <p className="text-[11px] text-slate-400 truncate mb-1.5">{job.source_url}</p>
                    <div className="flex items-center gap-3 text-[11px]">
                      <span className="text-emerald-600">↑ {job.articles_imported} 导入</span>
                      {job.articles_failed > 0 && <span className="text-red-500">✗ {job.articles_failed} 失败</span>}
                      <span className="text-slate-400 ml-auto">{formatDate(job.started_at)}</span>
                    </div>
                  </div>
                );
              })}
              <Button variant="secondary" size="sm" className="w-full">
                <Upload className="h-3.5 w-3.5" /> 新建导入任务
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
