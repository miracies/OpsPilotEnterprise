"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Eye, RefreshCw, Search, Trash2, Wand2 } from "lucide-react";
import type { AlertKnowledge } from "@opspilot/shared-types";

import { Badge, SeverityBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";

type Envelope<T> = { data?: T; error?: string };
type ListData = { items: AlertKnowledge[]; total: number; page: number; page_size: number };

const categoryOptions = ["", "resource", "ha_cluster", "vmotion_drs", "storage", "network", "vm_level"];
const severityOptions = ["", "info", "warning", "critical"];
const statusOptions = ["", "published", "draft", "deprecated"];

export default function AlertKnowledgeListPage() {
  const [items, setItems] = useState<AlertKnowledge[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("published");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 12;

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    if (q) params.set("q", q);
    if (category) params.set("category", category);
    if (severity) params.set("severity", severity);
    if (status) params.set("status", status);
    return params.toString();
  }, [category, page, q, severity, status]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<Envelope<ListData>>(`/api/v1/knowledge/alert-items?${query}`);
      setItems(res.data?.items ?? []);
      setTotal(res.data?.total ?? 0);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alert knowledge");
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    load();
  }, [load]);

  const deprecate = async (id: string) => {
    await apiFetch(`/api/v1/knowledge/alert-items/${encodeURIComponent(id)}/deprecate`, { method: "POST" });
    load();
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="告警知识"
        description="按 VMware 告警对象管理结构化诊断知识。"
        actions={
          <div className="flex gap-2">
            <Link href="/knowledge/test-alert-match"><Button variant="secondary" size="sm"><Wand2 className="h-3.5 w-3.5" />测试匹配</Button></Link>
            <Button variant="secondary" size="sm" onClick={load} disabled={loading}><RefreshCw className="h-3.5 w-3.5" />刷新</Button>
          </div>
        }
      />

      <Card>
        <CardContent className="flex flex-wrap items-center gap-2 py-3">
          <div className="relative min-w-64 flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="搜索名称、别名、标签或证据" className="h-9 w-full rounded-lg border border-slate-200 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <Select value={category} onChange={setCategory} options={categoryOptions} label="全部分类" />
          <Select value={severity} onChange={setSeverity} options={severityOptions} label="全部级别" />
          <Select value={status} onChange={setStatus} options={statusOptions} label="全部状态" />
        </CardContent>
      </Card>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="grid grid-cols-[minmax(260px,1.4fr)_120px_100px_100px_90px_150px] border-b border-slate-100 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-500">
          <div>AlertKnowledge</div><div>分类</div><div>级别</div><div>状态</div><div>命中</div><div>操作</div>
        </div>
        {items.map((item) => (
          <div key={item.id} className="grid grid-cols-[minmax(260px,1.4fr)_120px_100px_100px_90px_150px] items-center gap-2 border-b border-slate-100 px-4 py-3 text-sm last:border-b-0">
            <div className="min-w-0">
              <div className="truncate font-medium text-slate-900">{item.alert_name}</div>
              <div className="mt-0.5 truncate font-mono text-xs text-slate-500">{item.id}</div>
              <div className="mt-1 flex flex-wrap gap-1">{item.tags.slice(0, 4).map((tag) => <Badge key={tag} variant="neutral">{tag}</Badge>)}</div>
            </div>
            <Badge variant="info">{item.category}</Badge>
            <SeverityBadge severity={item.severity} />
            <Badge variant={item.status === "published" ? "success" : item.status === "deprecated" ? "neutral" : "warning"}>{item.status}</Badge>
            <span className="text-slate-700">{item.hit_count}</span>
            <div className="flex gap-1">
              <Link href={`/knowledge/alert-items/${encodeURIComponent(item.id)}`}><Button variant="ghost" size="icon" title="查看"><Eye className="h-4 w-4" /></Button></Link>
              <Link href={`/knowledge/test-alert-match?alert=${encodeURIComponent(item.alert_name)}`}><Button variant="ghost" size="icon" title="测试"><Wand2 className="h-4 w-4" /></Button></Link>
              <Button variant="ghost" size="icon" title="废弃" onClick={() => deprecate(item.id)} disabled={item.status === "deprecated"}><Trash2 className="h-4 w-4" /></Button>
            </div>
          </div>
        ))}
        {items.length === 0 && <div className="px-4 py-8 text-center text-sm text-slate-500">暂无匹配知识</div>}
      </div>

      <div className="flex items-center justify-between text-sm text-slate-600">
        <span>共 {total} 条</span>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>上一页</Button>
          <Button variant="secondary" size="sm" disabled={page * pageSize >= total} onClick={() => setPage((p) => p + 1)}>下一页</Button>
        </div>
      </div>
    </div>
  );
}

function Select({ value, onChange, options, label }: { value: string; onChange: (value: string) => void; options: string[]; label: string }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none focus:ring-2 focus:ring-blue-500">
      {options.map((option) => <option key={option || "all"} value={option}>{option || label}</option>)}
    </select>
  );
}
