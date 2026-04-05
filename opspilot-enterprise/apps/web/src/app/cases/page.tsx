"use client";

import { useState } from "react";
import {
  Archive, BookOpen, Tag, TrendingDown, AlertTriangle,
  CheckCircle2, BarChart, ChevronRight, ExternalLink, Lightbulb,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge, SeverityBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockCaseArchives, mockKnowledgeArticles } from "@/lib/mock-data";
import Link from "next/link";

const CATEGORY_LABEL: Record<string, string> = {
  performance:    "性能",
  availability:   "可用性",
  capacity:       "容量",
  change_failure: "变更失败",
  security:       "安全",
  network:        "网络",
  other:          "其他",
};

const CATEGORY_COLOR: Record<string, string> = {
  performance:    "bg-orange-50 text-orange-700",
  availability:   "bg-red-50 text-red-700",
  capacity:       "bg-purple-50 text-purple-700",
  change_failure: "bg-amber-50 text-amber-700",
  security:       "bg-pink-50 text-pink-700",
  network:        "bg-sky-50 text-sky-700",
  other:          "bg-slate-100 text-slate-600",
};

export default function CasesPage() {
  const [selected, setSelected] = useState<string | null>(mockCaseArchives[0]?.id ?? null);
  const [categoryFilter, setCategoryFilter] = useState("all");

  const filtered = categoryFilter === "all"
    ? mockCaseArchives
    : mockCaseArchives.filter((c) => c.category === categoryFilter);

  const detail = mockCaseArchives.find((c) => c.id === selected);

  const categories = ["all", ...Array.from(new Set(mockCaseArchives.map((c) => c.category)))];

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <PageHeader
        title="案例归档中心"
        description="历史故障案例沉淀、知识复用与相似事件智能关联"
        actions={
          <Link href="/knowledge">
            <Button variant="secondary" size="sm">
              <BookOpen className="h-3.5 w-3.5" /> 查看知识库
            </Button>
          </Link>
        }
      />

      {/* Category filters */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(cat)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
              categoryFilter === cat
                ? "bg-blue-600 text-white shadow-sm"
                : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
            )}
          >
            {cat === "all" ? "全部" : CATEGORY_LABEL[cat] ?? cat}
          </button>
        ))}
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Case list */}
        <div className="flex-1 rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          <div className="sticky top-0 bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">案例列表</span>
            <span className="text-xs text-slate-400">{filtered.length} 个案例</span>
          </div>
          <div className="divide-y divide-slate-50">
            {filtered.map((c) => (
              <div
                key={c.id}
                onClick={() => setSelected(c.id)}
                className={cn(
                  "px-5 py-4 cursor-pointer transition-colors",
                  selected === c.id ? "bg-blue-50" : "hover:bg-slate-50"
                )}
              >
                <div className="flex items-start gap-3">
                  <div className="h-10 w-10 rounded-xl bg-slate-100 flex items-center justify-center shrink-0 mt-0.5">
                    <Archive className="h-4.5 w-4.5 text-slate-400" style={{ height: "18px", width: "18px" }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold", CATEGORY_COLOR[c.category])}>
                        {CATEGORY_LABEL[c.category] ?? c.category}
                      </span>
                      <SeverityBadge severity={c.severity as never} />
                      {c.similarity_score != null && (
                        <span className="text-[10px] text-purple-600 bg-purple-50 rounded px-1.5 py-0.5 font-medium">
                          相似度 {(c.similarity_score * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-medium text-slate-900 truncate">{c.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{c.summary}</p>
                    <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                      {c.tags.slice(0, 4).map((t) => (
                        <Badge key={t} variant="neutral">{t}</Badge>
                      ))}
                      <span className="text-[11px] text-slate-400 ml-auto">
                        {c.archived_at ? formatDate(c.archived_at) : ""}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Detail */}
        {detail && (
          <div className="w-80 shrink-0 rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
            <div className="px-4 py-3 border-b border-slate-100">
              <div className="flex items-center justify-between mb-1.5">
                <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold", CATEGORY_COLOR[detail.category])}>
                  {CATEGORY_LABEL[detail.category]}
                </span>
                <SeverityBadge severity={detail.severity as never} />
              </div>
              <h3 className="text-sm font-semibold text-slate-900 leading-snug">{detail.title}</h3>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">{detail.id}</p>
            </div>

            <div className="px-4 py-4 space-y-5">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">事件摘要</p>
                <p className="text-xs text-slate-700 leading-relaxed">{detail.summary}</p>
              </div>

              <div className="rounded-xl bg-amber-50/60 border border-amber-200/70 p-3">
                <p className="text-xs font-semibold text-amber-700 flex items-center gap-1.5 mb-1.5">
                  <AlertTriangle className="h-3 w-3" /> 根因摘要
                </p>
                <p className="text-xs text-amber-800 leading-relaxed">{detail.root_cause_summary}</p>
              </div>

              <div className="rounded-xl bg-emerald-50/60 border border-emerald-200/70 p-3">
                <p className="text-xs font-semibold text-emerald-700 flex items-center gap-1.5 mb-1.5">
                  <CheckCircle2 className="h-3 w-3" /> 处置摘要
                </p>
                <p className="text-xs text-emerald-800 leading-relaxed">{detail.resolution_summary}</p>
              </div>

              <div className="rounded-xl bg-blue-50/60 border border-blue-200/70 p-3">
                <p className="text-xs font-semibold text-blue-700 flex items-center gap-1.5 mb-1.5">
                  <Lightbulb className="h-3 w-3" /> 经验教训
                </p>
                <p className="text-xs text-blue-800 leading-relaxed">{detail.lessons_learned}</p>
              </div>

              {detail.knowledge_refs.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">关联知识条目</p>
                  <div className="space-y-1.5">
                    {detail.knowledge_refs.map((kbId) => {
                      const kb = mockKnowledgeArticles.find((k) => k.id === kbId);
                      return (
                        <Link key={kbId} href="/knowledge" className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 hover:bg-blue-50 hover:border-blue-200 transition-colors">
                          <BookOpen className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                          <span className="text-xs text-slate-700 flex-1 truncate">{kb?.title ?? kbId}</span>
                          <ExternalLink className="h-3 w-3 text-slate-400" />
                        </Link>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-lg bg-slate-50 border border-slate-100 p-2">
                  <p className="text-[10px] text-slate-400 mb-0.5">归档人</p>
                  <p className="text-xs font-medium text-slate-700">{detail.author}</p>
                </div>
                <div className="rounded-lg bg-slate-50 border border-slate-100 p-2">
                  <p className="text-[10px] text-slate-400 mb-0.5">引用次数</p>
                  <p className="text-sm font-bold text-blue-600">{detail.hit_count}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {detail.tags.map((t) => (
                  <Badge key={t} variant="neutral">{t}</Badge>
                ))}
              </div>

              <div className="border-t border-slate-100 pt-3 flex gap-2">
                <Link href="/chat" className="flex-1">
                  <Button variant="secondary" size="sm" className="w-full">
                    在 AI 对话中引用
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
