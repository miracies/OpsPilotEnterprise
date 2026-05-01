"use client";

import { useState } from "react";
import { CheckCircle2, FileJson, Upload } from "lucide-react";
import type { AlertKnowledge } from "@opspilot/shared-types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";

type Envelope<T> = { data?: T; error?: string };
type ValidateData = { valid: boolean; items: AlertKnowledge[]; total: number; errors: string[]; created: number; updated: number };
type ImportResult = { job_id: string; status: string; created: number; updated: number; failed: number; total: number; errors: string[] };

const sample = `{"id":"demo.vmware.alert.v1","alert_name":"Demo VMware Alert","vendor":"vmware","domain":"virtualization","category":"resource","severity":"warning","aliases":["demo alert"],"symptoms":["Demo symptom"],"possible_causes":["Demo cause"],"diagnostic_steps":["Collect demo evidence"],"decision_tree":[{"condition":"demo.metric > 0","conclusion":"Demo conclusion","confidence_delta":0.1,"required_evidence":["demo.metric"]}],"evidence_required":["demo.metric","demo.event"],"evidence_optional":[],"remediation":["Review demo runbook"],"automation":{"safe_actions":["vmware.collect_demo"],"approval_actions":[]},"source":{"type":"manual","title":"Demo import","trust_score":0.8},"status":"draft","version":"1.0.0","trust_score":0.8,"hit_count":0,"case_refs":[],"knowledge_refs":[],"tags":["vmware","demo"],"match_keywords":["demo alert"],"negative_keywords":[],"created_at":"2026-04-30T00:00:00Z","updated_at":"2026-04-30T00:00:00Z"}`;

export default function KnowledgeImportPage() {
  const [content, setContent] = useState(sample);
  const [contentType, setContentType] = useState<"json" | "jsonl" | "prometheus_rules">("jsonl");
  const [sourceType, setSourceType] = useState("manual");
  const [validation, setValidation] = useState<ValidateData | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const validate = async () => {
    setBusy(true);
    try {
      const res = await apiFetch<Envelope<ValidateData>>("/api/v1/knowledge/import/validate", {
        method: "POST",
        body: JSON.stringify({ content, content_type: contentType, source_type: sourceType, publish: false, upsert: true }),
      });
      setValidation(res.data ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setBusy(false);
    }
  };

  const commit = async () => {
    if (!validation?.items.length) return;
    setBusy(true);
    try {
      const res = await apiFetch<Envelope<ImportResult>>("/api/v1/knowledge/alert-items:bulk-import", {
        method: "POST",
        body: JSON.stringify({ items: validation.items, source_type: sourceType, upsert: true }),
      });
      setResult(res.data ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="导入知识" description="粘贴 JSON、JSONL 或 Prometheus rule YAML，先校验再导入。" />
      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><FileJson className="h-4 w-4 text-slate-400" />导入内容</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <select value={contentType} onChange={(e) => setContentType(e.target.value as typeof contentType)} className="h-9 rounded-lg border border-slate-200 px-3 text-sm">
                <option value="jsonl">JSONL</option>
                <option value="json">JSON</option>
                <option value="prometheus_rules">Prometheus rules YAML</option>
              </select>
              <input value={sourceType} onChange={(e) => setSourceType(e.target.value)} className="h-9 rounded-lg border border-slate-200 px-3 text-sm" placeholder="source_type" />
              <label className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700">
                <Upload className="h-4 w-4" />上传
                <input type="file" className="hidden" onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  file.text().then(setContent);
                }} />
              </label>
            </div>
            <textarea value={content} onChange={(e) => setContent(e.target.value)} className="min-h-[430px] w-full rounded-lg border border-slate-200 p-3 font-mono text-xs outline-none focus:ring-2 focus:ring-blue-500" />
            <div className="flex gap-2">
              <Button variant="secondary" onClick={validate} disabled={busy}>Dry-run 校验</Button>
              <Button onClick={commit} disabled={busy || !validation?.valid || !validation.items.length}><CheckCircle2 className="h-4 w-4" />确认导入</Button>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>校验结果</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {!validation && <div className="text-sm text-slate-500">尚未校验</div>}
              {validation && (
                <>
                  <Badge variant={validation.valid ? "success" : "danger"}>{validation.valid ? "valid" : "invalid"}</Badge>
                  <div className="grid grid-cols-3 gap-2 text-center text-sm">
                    <Box label="total" value={validation.total} />
                    <Box label="created" value={validation.created} />
                    <Box label="updated" value={validation.updated} />
                  </div>
                  <div className="space-y-1 text-xs text-red-700">{validation.errors.map((err) => <div key={err} className="rounded bg-red-50 p-2">{err}</div>)}</div>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>导入结果</CardTitle></CardHeader>
            <CardContent>
              {!result && <div className="text-sm text-slate-500">暂无导入结果</div>}
              {result && (
                <div className="space-y-2 text-sm">
                  <div className="font-mono text-xs text-slate-700">{result.job_id}</div>
                  <Badge variant={result.failed ? "warning" : "success"}>{result.status}</Badge>
                  <div>created {result.created} · updated {result.updated} · failed {result.failed}</div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Box({ label, value }: { label: string; value: number }) {
  return <div className="rounded-lg bg-slate-50 p-2"><div className="text-xs text-slate-500">{label}</div><div className="text-lg font-semibold text-slate-900">{value}</div></div>;
}
