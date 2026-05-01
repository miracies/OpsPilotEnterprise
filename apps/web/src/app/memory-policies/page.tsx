"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Save } from "lucide-react";
import type { MemoryPolicyRule } from "@opspilot/shared-types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";

type PoliciesEnvelope = { success: boolean; data?: { items?: MemoryPolicyRule[] }; error?: string };

const RETENTION_LABELS: Record<MemoryPolicyRule["retention_policy"], string> = {
  short_term: "短期",
  medium_term: "中期",
  long_term: "长期",
  permanent: "永久",
};

export default function MemoryPolicyPage() {
  const [items, setItems] = useState<MemoryPolicyRule[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const res = await apiFetch<PoliciesEnvelope>("/api/v1/memory-policies");
      setItems(res.data?.items ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载记忆策略失败");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  async function save() {
    setSaving(true);
    try {
      const res = await apiFetch<PoliciesEnvelope>("/api/v1/memory-policies", {
        method: "PUT",
        body: JSON.stringify(items),
      });
      setItems(res.data?.items ?? items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存记忆策略失败");
    } finally {
      setSaving(false);
    }
  }

  function update(index: number, patch: Partial<MemoryPolicyRule>) {
    setItems((current) => current.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="记忆策略"
        description="管理长期记忆写入规则、保留策略、置信度阈值和敏感信息拦截规则。"
        actions={
          <Button size="sm" onClick={save} disabled={saving}>
            <Save className="h-3.5 w-3.5" /> 保存
          </Button>
        }
      />
      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="grid gap-4">
        {items.map((item, index) => (
          <Card key={item.id}>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <CardTitle>{item.name}</CardTitle>
                <Badge variant={item.enabled ? "success" : "neutral"}>{item.enabled ? "已启用" : "已停用"}</Badge>
              </div>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-4">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={item.enabled} onChange={(event) => update(index, { enabled: event.target.checked })} />
                启用
              </label>
              <Field label="记忆类型">
                <input
                  className="h-9 w-full rounded-lg border border-slate-200 px-3 text-sm"
                  value={item.memory_type ?? ""}
                  onChange={(event) => update(index, { memory_type: event.target.value || null })}
                  placeholder="全部"
                />
              </Field>
              <Field label="最低置信度">
                <input
                  className="h-9 w-full rounded-lg border border-slate-200 px-3 text-sm"
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={item.min_confidence}
                  onChange={(event) => update(index, { min_confidence: Number(event.target.value) })}
                />
              </Field>
              <Field label="保留策略">
                <select
                  className="h-9 w-full rounded-lg border border-slate-200 px-3 text-sm"
                  value={item.retention_policy}
                  onChange={(event) => update(index, { retention_policy: event.target.value as MemoryPolicyRule["retention_policy"] })}
                >
                  <option value="short_term">{RETENTION_LABELS.short_term}</option>
                  <option value="medium_term">{RETENTION_LABELS.medium_term}</option>
                  <option value="long_term">{RETENTION_LABELS.long_term}</option>
                  <option value="permanent">{RETENTION_LABELS.permanent}</option>
                </select>
              </Field>
              <Field label="必填字段">
                <input
                  className="h-9 w-full rounded-lg border border-slate-200 px-3 text-sm"
                  value={item.required_fields.join(",")}
                  onChange={(event) => update(index, { required_fields: splitCsv(event.target.value) })}
                />
              </Field>
              <Field label="拦截模式">
                <input
                  className="h-9 w-full rounded-lg border border-slate-200 px-3 text-sm md:col-span-3"
                  value={item.blocked_patterns.join(",")}
                  onChange={(event) => update(index, { blocked_patterns: splitCsv(event.target.value) })}
                />
              </Field>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="space-y-1">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      {children}
    </label>
  );
}

function splitCsv(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}
