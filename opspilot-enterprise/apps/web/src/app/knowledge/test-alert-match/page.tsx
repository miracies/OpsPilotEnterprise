"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Play, SearchCheck } from "lucide-react";
import type { AlertMatchResponse } from "@opspilot/shared-types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";

type Envelope<T> = { data?: T; error?: string };

export default function TestAlertMatchPage() {
  const params = useSearchParams();
  const [alertName, setAlertName] = useState(params.get("alert") ?? "Host Memory Usage");
  const [summary, setSummary] = useState("host esxi-07 memory usage > 90% but active memory is low");
  const [category, setCategory] = useState("");
  const [labels, setLabels] = useState('{"cluster":"prod-a"}');
  const [present, setPresent] = useState("metric");
  const [result, setResult] = useState<AlertMatchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      const res = await apiFetch<Envelope<AlertMatchResponse>>("/api/v1/knowledge/alert-match", {
        method: "POST",
        body: JSON.stringify({
          alert_name: alertName,
          summary,
          vendor: "VMware",
          category: category || undefined,
          labels: labels ? JSON.parse(labels) : {},
          evidence_present: present.split(",").map((x) => x.trim()).filter(Boolean),
          top_k: 5,
        }),
      });
      setResult(res.data ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Alert match failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="告警匹配测试" description="验证 AlertKnowledge 命中、证据缺口和动作分类。" />
      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="grid gap-4 lg:grid-cols-[420px_1fr]">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><SearchCheck className="h-4 w-4 text-slate-400" />输入上下文</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Field label="alert_name" value={alertName} onChange={setAlertName} />
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-500">summary</label>
              <textarea value={summary} onChange={(e) => setSummary(e.target.value)} className="h-24 w-full rounded-lg border border-slate-200 p-2 text-sm outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <Field label="category hint" value={category} onChange={setCategory} />
            <Field label="labels JSON" value={labels} onChange={setLabels} mono />
            <Field label="present evidence, comma separated" value={present} onChange={setPresent} />
            <Button onClick={run} disabled={busy}><Play className="h-4 w-4" />运行匹配</Button>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>匹配结果</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {!result && <div className="text-sm text-slate-500">尚未运行</div>}
              {result?.matches.map((match) => (
                <div key={match.item.id} className="rounded-lg border border-slate-200 p-3">
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium text-slate-900">{match.item.alert_name}</div>
                      <div className="font-mono text-xs text-slate-500">{match.item.id}</div>
                    </div>
                    <Badge variant="info">{Math.round(match.relevance_score * 100)}%</Badge>
                  </div>
                  <div className="mb-2 text-xs text-slate-600">{match.why_selected}</div>
                  <TagLine title="matched" values={match.matched_fields} />
                  <TagLine title="missing" values={match.missing_critical_evidence.length ? match.missing_critical_evidence : match.missing_evidence} variant="warning" />
                </div>
              ))}
            </CardContent>
          </Card>

          {result && (
            <div className="grid gap-4 xl:grid-cols-2">
              <SummaryCard title="Required evidence" values={result.required_evidence_types} variant="warning" />
              <SummaryCard title="Safe actions" values={result.safe_actions} variant="success" />
              <SummaryCard title="Approval actions" values={result.approval_actions} variant="danger" />
              <SummaryCard title="Similar cases" values={(result.similar_cases ?? []).map((item) => String(item.title ?? item.id ?? "case"))} variant="neutral" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, mono }: { label: string; value: string; onChange: (value: string) => void; mono?: boolean }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-500">{label}</label>
      <input value={value} onChange={(e) => onChange(e.target.value)} className={`h-9 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:ring-2 focus:ring-blue-500 ${mono ? "font-mono" : ""}`} />
    </div>
  );
}

function TagLine({ title, values, variant = "neutral" }: { title: string; values: string[]; variant?: "neutral" | "warning" | "success" | "danger" | "info" }) {
  return <div className="mt-2 flex flex-wrap items-center gap-1.5"><span className="text-xs font-semibold text-slate-500">{title}</span>{values.map((value) => <Badge key={value} variant={variant}>{value}</Badge>)}</div>;
}

function SummaryCard({ title, values, variant }: { title: string; values: string[]; variant: "neutral" | "warning" | "success" | "danger" }) {
  return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent><div className="flex flex-wrap gap-1.5">{values.length ? values.map((value) => <Badge key={value} variant={variant}>{value}</Badge>) : <span className="text-sm text-slate-500">None</span>}</div></CardContent></Card>;
}
