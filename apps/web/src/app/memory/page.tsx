"use client";

import { useEffect, useMemo, useState } from "react";
import { Archive, CheckCircle2, GitMerge, RefreshCcw, Search, Trash2 } from "lucide-react";
import type { MemoryItem, MemorySearchHit } from "@opspilot/shared-types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type MemoryListEnvelope = { success: boolean; data?: { items?: MemoryItem[]; total?: number }; error?: string };
type MemorySearchEnvelope = { success: boolean; data?: { hits?: MemorySearchHit[] }; error?: string };
type MemoryItemEnvelope = { success: boolean; data?: MemoryItem; error?: string };

const MEMORY_TYPES = ["", "vmware_incident_memory", "incident_memory", "resource_memory", "change_memory", "knowledge_memory", "user_memory"];
const STATUSES = ["active", "downgraded", "archived", "invalid", "expired", "duplicate", "deleted"];
const MEMORY_TYPE_LABELS: Record<string, string> = {
  "": "全部类型",
  vmware_incident_memory: "VMware 故障记忆",
  incident_memory: "故障记忆",
  resource_memory: "资源记忆",
  change_memory: "变更记忆",
  knowledge_memory: "知识记忆",
  user_memory: "用户记忆",
};
const STATUS_LABELS: Record<string, string> = {
  active: "有效",
  downgraded: "已降权",
  archived: "已归档",
  invalid: "无效",
  expired: "已过期",
  duplicate: "重复",
  deleted: "已删除",
};

export default function MemoryCenterPage() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [selected, setSelected] = useState<MemoryItem | null>(null);
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [tag, setTag] = useState("");
  const [status, setStatus] = useState("active");
  const [mergeTarget, setMergeTarget] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      if (query.trim()) {
        const body = {
          tenant_id: "default",
          query,
          top_k: 20,
          filters: {
            memory_type: type || null,
            tags: tag ? [tag] : [],
            status,
          },
        };
        const res = await apiFetch<MemorySearchEnvelope>("/api/v1/memories/search", {
          method: "POST",
          body: JSON.stringify(body),
        });
        const next = res.data?.hits?.map((hit) => hit.memory) ?? [];
        setItems(next);
        setSelected((prev) => next.find((item) => item.id === prev?.id) ?? next[0] ?? null);
      } else {
        const params = new URLSearchParams({ tenant_id: "default", status });
        if (type) params.set("type", type);
        if (tag) params.set("tag", tag);
        const res = await apiFetch<MemoryListEnvelope>(`/api/v1/memories?${params.toString()}`);
        const next = res.data?.items ?? [];
        setItems(next);
        setSelected((prev) => next.find((item) => item.id === prev?.id) ?? next[0] ?? null);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载记忆失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const tags = useMemo(() => Array.from(new Set(items.flatMap((item) => item.tags))).slice(0, 20), [items]);

  async function setMemoryStatus(memory: MemoryItem, nextStatus: string) {
    const res = await apiFetch<MemoryItemEnvelope>(`/api/v1/memories/${memory.id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: nextStatus, reason: "在记忆中心更新状态" }),
    });
    if (res.success && res.data) {
      setSelected(res.data);
      await load();
    }
  }

  async function mergeSelected() {
    if (!selected || !mergeTarget.trim()) return;
    await apiFetch(`/api/v1/memories/${selected.id}/merge`, {
      method: "POST",
      body: JSON.stringify({
        target_memory_id: mergeTarget.trim(),
        merge_reason: "在记忆中心手动合并",
        merge_strategy: "append_evidence",
      }),
    });
    setMergeTarget("");
    await load();
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="记忆中心"
        description="统一管理长期运维记忆、证据、治理状态，以及图关系增强的故障上下文。"
        actions={
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            <RefreshCcw className="h-3.5 w-3.5" /> 刷新
          </Button>
        }
      />

      <Card>
        <CardContent className="grid gap-3 p-3 md:grid-cols-[1.5fr_1fr_1fr_1fr_auto]">
          <div className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 px-3">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              className="w-full bg-transparent text-sm outline-none"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="按现象、根因、资源或动作搜索"
            />
          </div>
          <select className="h-9 rounded-lg border border-slate-200 px-3 text-sm" value={type} onChange={(event) => setType(event.target.value)}>
            {MEMORY_TYPES.map((item) => <option key={item || "all"} value={item}>{MEMORY_TYPE_LABELS[item] ?? item}</option>)}
          </select>
          <select className="h-9 rounded-lg border border-slate-200 px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
            {STATUSES.map((item) => <option key={item} value={item}>{STATUS_LABELS[item] ?? item}</option>)}
          </select>
          <input
            className="h-9 rounded-lg border border-slate-200 px-3 text-sm"
            value={tag}
            onChange={(event) => setTag(event.target.value)}
            list="memory-tags"
            placeholder="标签"
          />
          <datalist id="memory-tags">
            {tags.map((item) => <option key={item} value={item} />)}
          </datalist>
          <Button size="sm" onClick={load} disabled={loading}>应用</Button>
        </CardContent>
      </Card>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
        <Card>
          <CardHeader>
            <CardTitle>记忆条目（{items.length}）</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {items.length === 0 && <div className="text-sm text-slate-500">未找到记忆条目。</div>}
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSelected(item)}
                className={`w-full rounded-lg border p-3 text-left transition ${selected?.id === item.id ? "border-blue-300 bg-blue-50" : "border-slate-200 bg-white hover:bg-slate-50"}`}
              >
                <div className="mb-1 flex items-start justify-between gap-3">
                  <div className="font-medium text-slate-900">{item.title}</div>
                  <Badge variant={item.status === "active" ? "success" : "neutral"}>{STATUS_LABELS[item.status] ?? item.status}</Badge>
                </div>
                <p className="line-clamp-2 text-sm text-slate-600">{item.summary}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  <Badge variant="neutral">{MEMORY_TYPE_LABELS[item.memory_type] ?? item.memory_type}</Badge>
                  <Badge variant="neutral">置信度 {Math.round(item.confidence * 100)}%</Badge>
                  {item.tags.slice(0, 4).map((itemTag) => <Badge key={itemTag} variant="neutral">{itemTag}</Badge>)}
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>记忆详情</CardTitle>
          </CardHeader>
          <CardContent>
            {!selected ? (
              <div className="text-sm text-slate-500">请选择一条记忆。</div>
            ) : (
              <div className="space-y-4">
                <div>
                  <div className="text-xs text-slate-400">{selected.id}</div>
                  <h2 className="mt-1 text-base font-semibold text-slate-900">{selected.title}</h2>
                  <p className="mt-2 text-sm text-slate-700">{selected.summary}</p>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-slate-600">
                  <Info label="来源" value={`${selected.source}${selected.source_id ? ` / ${selected.source_id}` : ""}`} />
                  <Info label="更新时间" value={formatDate(selected.updated_at)} />
                  <Info label="重要性" value={selected.importance} />
                  <Info label="保留策略" value={selected.retention_policy} />
                </div>
                <Section title="实体" values={selected.entities.map((e) => `${e.entity_type}:${e.entity_name || e.entity_id || "-"}`)} />
                <Section title="证据" values={selected.evidence_refs.map((e) => `${e.evidence_type || "evidence"}:${e.evidence_id}`)} />
                <Section title="图关系" values={selected.relations.map((r) => `${r.relation_type} -> ${r.target_type}:${r.target_id}`)} />
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setMemoryStatus(selected, "active")}>
                    <CheckCircle2 className="h-3.5 w-3.5" /> 标记有效
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setMemoryStatus(selected, "archived")}>
                    <Archive className="h-3.5 w-3.5" /> 归档
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setMemoryStatus(selected, "deleted")}>
                    <Trash2 className="h-3.5 w-3.5" /> 删除
                  </Button>
                </div>
                <div className="flex gap-2">
                  <input
                    className="h-9 min-w-0 flex-1 rounded-lg border border-slate-200 px-3 text-sm"
                    value={mergeTarget}
                    onChange={(event) => setMergeTarget(event.target.value)}
                    placeholder="目标记忆 ID"
                  />
                  <Button size="sm" variant="secondary" onClick={mergeSelected}>
                    <GitMerge className="h-3.5 w-3.5" /> 合并
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2">
      <div className="text-[11px] text-slate-400">{label}</div>
      <div className="mt-1 break-words text-xs text-slate-700">{value || "-"}</div>
    </div>
  );
}

function Section({ title, values }: { title: string; values: string[] }) {
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-slate-500">{title}</div>
      <div className="space-y-1">
        {values.length === 0 && <div className="text-xs text-slate-400">暂无</div>}
        {values.map((value) => (
          <div key={value} className="rounded bg-slate-50 px-2 py-1 text-xs text-slate-600">{value}</div>
        ))}
      </div>
    </div>
  );
}
