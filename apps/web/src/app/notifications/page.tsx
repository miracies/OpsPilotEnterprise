"use client";

import { useEffect, useState } from "react";
import { type NotificationItem, type OnCallShift } from "@opspilot/shared-types";

import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type NotificationsEnvelope = { data?: { items?: NotificationItem[] } };
type OncallEnvelope = { data?: { items?: OnCallShift[] } };

export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [oncall, setOncall] = useState<OnCallShift[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [n, o] = await Promise.all([
        apiFetch<NotificationsEnvelope>("/api/v1/notifications"),
        apiFetch<OncallEnvelope>("/api/v1/oncall/shifts"),
      ]);
      setItems(n.data?.items ?? []);
      setOncall(o.data?.items ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load notifications");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 5000);
    return () => clearInterval(timer);
  }, []);

  const acknowledge = async (id: string) => {
    await apiFetch(`/api/v1/notifications/${id}/acknowledge`, { method: "POST" });
    await loadData();
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="通知中心"
        description="展示当前闭环通知与值班信息。"
        actions={
          <Button variant="secondary" size="sm" onClick={loadData}>
            刷新
          </Button>
        }
      />

      {loading && <div className="text-sm text-slate-500">正在加载通知...</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="rounded-xl border border-slate-200 bg-white p-3">
          {items.length === 0 && <div className="text-sm text-slate-500">暂无通知</div>}
          <div className="space-y-2">
            {items.map((n) => (
              <div key={n.id} className="rounded-lg border border-slate-200 p-3">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <div className="font-medium">{n.title}</div>
                  <Badge variant="neutral">{n.priority}</Badge>
                </div>
                <div className="mb-2 text-sm text-slate-700">{n.content}</div>
                <div className="mb-2 text-xs text-slate-500">
                  状态: {n.status} · 时间: {formatDate(n.created_at)}
                </div>
                {n.status !== "acknowledged" && (
                  <Button size="sm" onClick={() => acknowledge(n.id)}>
                    确认
                  </Button>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="mb-2 text-sm font-semibold">当前值班</div>
          {oncall.map((s) => (
            <div key={s.id} className="mb-2 rounded-lg border border-slate-200 p-2">
              <div className="font-medium">{s.team}</div>
              <div className="text-xs text-slate-500">{s.name}</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {s.members.map((m) => (
                  <Badge key={m} variant="neutral">{m}</Badge>
                ))}
              </div>
              <div className="mt-1 text-xs text-slate-400">
                {formatDate(s.start_at)} - {formatDate(s.end_at)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
