"use client";

import type { AuditTimelineData } from "@opspilot/shared-types";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";

export function AuditTimeline({ data }: { data: AuditTimelineData }) {
  const latestEvent = data.events[data.events.length - 1];
  return (
    <Card className="mt-3 border-slate-200 bg-slate-50/70 p-3">
      <details>
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-xs font-semibold text-slate-700">Audit Timeline</p>
              <Badge variant="neutral">{data.events.length} events</Badge>
            </div>
            <p className="mt-1 truncate text-[11px] text-slate-500">
              {latestEvent
                ? `最新：${latestEvent.event_type} · ${latestEvent.summary}`
                : `run_id: ${data.run_id}`}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-white/80 px-2 py-1 text-[11px] font-medium text-slate-600">
            展开审计
          </span>
        </summary>
        <div className="mt-3 space-y-2">
          <div className="rounded-lg border border-white bg-white/80 px-2 py-2 text-xs text-slate-600">
            run_id: {data.run_id}
          </div>
          {data.events.map((event) => (
            <div key={event.event_id} className="rounded-lg border border-white bg-white/80 px-2 py-2 text-xs text-slate-700">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-900">{event.event_type}</span>
                <span className="text-slate-400">{formatDate(event.created_at)}</span>
              </div>
              <p className="mt-1">{event.summary}</p>
            </div>
          ))}
        </div>
      </details>
    </Card>
  );
}
