"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { MetricResult } from "@opspilot/shared-types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function formatPct(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)}%` : "N/A";
}

function statusVariant(status?: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "异常") return "danger";
  if (status === "偏高") return "warning";
  if (status === "正常") return "success";
  return "neutral";
}

export function MetricResultCard({
  result,
  onAction,
  actionPending,
}: {
  result: MetricResult;
  onAction?: (prompt: string) => void;
  actionPending?: boolean;
}) {
  const [expandedHost, setExpandedHost] = useState<string | null>(null);
  const topHosts = result.top_hosts ?? [];
  const hostSeries = result.host_series ?? [];
  const nextActionItems = useMemo(() => {
    if (result.next_action_items && result.next_action_items.length > 0) {
      return result.next_action_items;
    }
    return (result.next_actions ?? []).map((label) => ({ label, prompt: label }));
  }, [result.next_action_items, result.next_actions]);
  const selectedHost = useMemo(
    () => hostSeries.find((item) => (item.host_id || item.name) === expandedHost) ?? hostSeries[0],
    [expandedHost, hostSeries],
  );
  const selectedHostKey = selectedHost ? selectedHost.host_id || selectedHost.name : null;
  const hostChartData = useMemo(() => {
    if (!selectedHost) return [];
    const cpu = selectedHost.cpu_series ?? [];
    const memory = selectedHost.memory_series ?? [];
    const count = Math.max(cpu.length, memory.length);
    return Array.from({ length: count }, (_, idx) => ({
      timestamp: cpu[idx]?.timestamp ?? memory[idx]?.timestamp ?? "",
      cpu: cpu[idx]?.value ?? null,
      memory: memory[idx]?.value ?? null,
    })).filter((item) => item.timestamp);
  }, [selectedHost]);

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-slate-800">CPU / 内存趋势</p>
          <p className="text-[11px] text-slate-500">
            范围：{result.window} · 来源：{result.source}
          </p>
        </div>
        <Badge variant={statusVariant(result.status)} dot>
          {result.status ?? "指标结果"}
        </Badge>
      </div>

      {result.series.length > 0 && (
        <div className="h-56 rounded-md border border-slate-200 bg-white p-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={result.series} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="timestamp" tickFormatter={formatTime} tick={{ fontSize: 11 }} minTickGap={24} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
              <Tooltip labelFormatter={(value) => formatTime(String(value))} formatter={(value, name) => [`${Number(value).toFixed(1)}%`, name]} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="cpu_avg" name="CPU平均" stroke="#2563eb" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="cpu_max" name="CPU峰值" stroke="#7c3aed" dot={false} strokeWidth={1.8} />
              <Line type="monotone" dataKey="memory_avg" name="内存平均" stroke="#d97706" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="memory_max" name="内存峰值" stroke="#dc2626" dot={false} strokeWidth={1.8} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {topHosts.length > 0 && (
        <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
          <div className="grid grid-cols-[minmax(120px,1fr)_70px_70px_70px_70px] gap-2 border-b border-slate-100 bg-slate-50 px-3 py-2 text-[11px] font-medium text-slate-500">
            <span>负载最高主机</span>
            <span>CPU当前</span>
            <span>CPU峰值</span>
            <span>内存当前</span>
            <span>内存峰值</span>
          </div>
          {topHosts.map((host) => {
            const key = host.host_id || host.name;
            return (
              <button
                key={key}
                type="button"
                onClick={() => setExpandedHost(key)}
                className={cn(
                  "grid w-full grid-cols-[minmax(120px,1fr)_70px_70px_70px_70px] gap-2 px-3 py-2 text-left text-[11px] hover:bg-slate-50",
                  selectedHostKey === key ? "bg-blue-50/70" : "bg-white",
                )}
              >
                <span className="truncate font-medium text-slate-700">{host.name}</span>
                <span className="text-slate-600">{formatPct(host.cpu_current)}</span>
                <span className="text-slate-600">{formatPct(host.cpu_peak)}</span>
                <span className="text-slate-600">{formatPct(host.memory_current)}</span>
                <span className="text-slate-600">{formatPct(host.memory_peak)}</span>
              </button>
            );
          })}
        </div>
      )}

      {selectedHost && hostChartData.length > 0 && (
        <details className="rounded-md border border-slate-200 bg-white p-2" open>
          <summary className="cursor-pointer select-none px-1 text-xs font-medium text-slate-700">
            异常主机明细：{selectedHost.name}
          </summary>
          <div className="mt-2 h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={hostChartData} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="timestamp" tickFormatter={formatTime} tick={{ fontSize: 11 }} minTickGap={24} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                <Tooltip labelFormatter={(value) => formatTime(String(value))} formatter={(value, name) => [`${Number(value).toFixed(1)}%`, name]} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="cpu" name="CPU" stroke="#2563eb" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="memory" name="内存" stroke="#d97706" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </details>
      )}

      {(result.insights?.length || nextActionItems.length) && (
        <div className="space-y-2">
          {result.insights && result.insights.length > 0 && (
            <div className="space-y-1 text-[11px] text-slate-600">
              {result.insights.map((item) => (
                <p key={item}>{item}</p>
              ))}
            </div>
          )}
          {nextActionItems.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {nextActionItems.slice(0, 4).map((item) => (
                <Button
                  key={`${item.label}-${item.prompt}`}
                  size="sm"
                  variant="secondary"
                  className="h-7 text-[11px]"
                  disabled={actionPending || !onAction}
                  onClick={() => onAction?.(item.prompt || item.label)}
                  title={item.prompt || item.label}
                >
                  {item.label}
                </Button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
