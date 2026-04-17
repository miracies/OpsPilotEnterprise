"use client";

import Link from "next/link";
import type { ResumeCardData } from "@opspilot/shared-types";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function ResumeCard({ record }: { record: ResumeCardData }) {
  return (
    <Card className="mt-3 border-emerald-200 bg-emerald-50/40 p-3">
      <p className="text-xs font-semibold text-emerald-700">Resume</p>
      <div className="mt-2 space-y-1 text-xs text-slate-700">
        <p>checkpoint_id：{record.checkpoint_id}</p>
        <p>最近安全步骤：{record.last_safe_step ?? "无"}</p>
        <p>恢复入口：{record.resume_from ?? "无"}</p>
        <p>幂等键：{record.idempotency_key}</p>
      </div>
      <div className="mt-3">
        <Link href={`/runs/${record.run_id}`}>
          <Button size="sm" variant="secondary">查看 Run 审计</Button>
        </Link>
      </div>
    </Card>
  );
}
