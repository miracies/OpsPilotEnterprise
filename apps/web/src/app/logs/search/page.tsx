"use client";

import { useState } from "react";
import { ExternalLink, FileSearch, Loader2, Plus, Search } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import type { LogItem, LogSearchResponse } from "@opspilot/shared-types";

export default function LogSearchPage() {
  const [query, setQuery] = useState("overallStatus OR vmkernel OR hostd");
  const [host, setHost] = useState("");
  const [vm, setVm] = useState("");
  const [datastore, setDatastore] = useState("");
  const [component, setComponent] = useState("hostd,vpxa,vmkernel,vpxd");
  const [severity, setSeverity] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [items, setItems] = useState<LogItem[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");

  async function runSearch() {
    setLoading(true);
    setStatus("");
    try {
      const filters: Record<string, unknown> = {};
      if (host) filters.host = host;
      if (vm) filters.object_name = vm;
      if (datastore) filters.datastore = datastore;
      if (component) filters.component = component.split(",").map((x) => x.trim()).filter(Boolean);
      if (severity) filters.severity = severity.split(",").map((x) => x.trim()).filter(Boolean);
      const res = await apiFetch<{ success: boolean; data?: LogSearchResponse; error?: string }>("/api/v1/logs/search", {
        method: "POST",
        body: JSON.stringify({
          backend: "opensearch",
          time_range: from || to ? { from: from || undefined, to: to || undefined } : undefined,
          filters,
          query,
          limit: 100,
        }),
      });
      if (!res.success) {
        setStatus(res.error || "日志检索失败");
        setItems([]);
        return;
      }
      setItems(res.data?.items ?? []);
      setStatus(`检索到 ${res.data?.total ?? 0} 条日志`);
    } finally {
      setLoading(false);
    }
  }

  async function addEvidence(item: LogItem) {
    const res = await apiFetch<{ success: boolean; data?: { evidence_refs: string[] }; error?: string }>("/api/v1/logs/evidence", {
      method: "POST",
      body: JSON.stringify({ incident_id: "manual-log-search", log_ids: [item.log_id], comment: "Added from log search page" }),
    });
    setStatus(res.success ? `已加入证据：${res.data?.evidence_refs?.join(", ")}` : res.error || "加入证据失败");
  }

  return (
    <div className="space-y-4">
      <PageHeader title="日志检索" description="检索 vCenter / ESXi 原始日志，保留 raw message，并可加入 RCA 证据链。" />

      <Card>
        <CardHeader>
          <CardTitle>查询条件</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 lg:grid-cols-3">
            <input className="form-input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="关键词或 OpenSearch query string" />
            <input className="form-input" value={host} onChange={(e) => setHost(e.target.value)} placeholder="Host / ESXi" />
            <input className="form-input" value={vm} onChange={(e) => setVm(e.target.value)} placeholder="VM name / MoID" />
            <input className="form-input" value={datastore} onChange={(e) => setDatastore(e.target.value)} placeholder="Datastore" />
            <input className="form-input" value={component} onChange={(e) => setComponent(e.target.value)} placeholder="hostd,vpxa,vmkernel,vpxd" />
            <input className="form-input" value={severity} onChange={(e) => setSeverity(e.target.value)} placeholder="warning,error" />
            <input className="form-input" value={from} onChange={(e) => setFrom(e.target.value)} placeholder="From ISO time" />
            <input className="form-input" value={to} onChange={(e) => setTo(e.target.value)} placeholder="To ISO time" />
          </div>
          <div className="flex items-center gap-3">
            <Button variant="primary" size="sm" onClick={() => void runSearch()} disabled={loading}>
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
              检索
            </Button>
            {status && <span className="text-xs text-slate-500">{status}</span>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>原始日志</CardTitle>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <FileSearch className="h-4 w-4" /> 暂无日志。请先配置日志平台并执行检索。
            </div>
          ) : (
            <div className="space-y-2">
              {items.map((item) => (
                <div key={item.log_id} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="neutral">{item.backend}</Badge>
                    {item.component && <Badge variant="info">{item.component}</Badge>}
                    {item.severity && <Badge variant="warning">{item.severity}</Badge>}
                    <span className="font-mono text-xs text-slate-500">{item.timestamp}</span>
                    <span className="text-xs text-slate-500">{item.source}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-800">{item.message}</p>
                  {expanded === item.log_id && (
                    <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-100">{item.raw_message}</pre>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button variant="secondary" size="xs" onClick={() => setExpanded(expanded === item.log_id ? null : item.log_id)}>
                      {expanded === item.log_id ? "收起原文" : "查看原文"}
                    </Button>
                    <Button variant="secondary" size="xs" onClick={() => void addEvidence(item)}>
                      <Plus className="h-3 w-3" /> 加入证据
                    </Button>
                    {(item.external_links ?? []).map((link) => (
                      <a key={link.url} href={link.url} target="_blank" rel="noreferrer" className="inline-flex h-7 items-center gap-1 rounded-md border border-slate-200 px-2 text-xs text-blue-700 hover:bg-blue-50">
                        <ExternalLink className="h-3 w-3" /> {link.title}
                      </a>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <style>{`
        .form-input { height: 34px; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0 10px; font-size: 13px; outline: none; }
        .form-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,.15); }
      `}</style>
    </div>
  );
}
