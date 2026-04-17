"use client";

import type { AuditTimelineData } from "@opspilot/shared-types";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";

export function AuditTimeline({ data }: { data: AuditTimelineData }) {
  return (
    <Card className="mt-3 border-slate-200 bg-slate-50/70 p-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs font-semibold text-slate-700">Audit Timeline</p>
        <Badge variant="neutral">{data.run_id}</Badge>
      </div>
      <div className="space-y-2">
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
    </Card>
  );
}
