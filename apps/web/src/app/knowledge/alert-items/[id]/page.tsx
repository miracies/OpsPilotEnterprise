"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, ShieldAlert, Wand2 } from "lucide-react";
import type { AlertKnowledge } from "@opspilot/shared-types";

import { Badge, SeverityBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type Envelope<T> = { data?: T; error?: string };

export default function AlertKnowledgeDetailPage() {
  const [item, setItem] = useState<AlertKnowledge | null>(null);
  const [error, setError] = useState<string | null>(null);
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);

  useEffect(() => {
    apiFetch<Envelope<AlertKnowledge>>(`/api/v1/knowledge/alert-items/${encodeURIComponent(id)}`)
      .then((res) => setItem(res.data ?? null))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load alert knowledge"));
  }, [id]);

  if (error) return <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>;
  if (!item) return <div className="text-sm text-slate-500">正在加载知识详情...</div>;

  return (
    <div className="space-y-4">
      <PageHeader
        title={item.alert_name}
        description={item.id}
        actions={
          <div className="flex gap-2">
            <Link href="/knowledge/alert-items"><Button variant="secondary" size="sm"><ArrowLeft className="h-3.5 w-3.5" />返回</Button></Link>
            <Link href={`/knowledge/test-alert-match?alert=${encodeURIComponent(item.alert_name)}`}><Button size="sm"><Wand2 className="h-3.5 w-3.5" />测试匹配</Button></Link>
          </div>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>基本信息</CardTitle></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              <Info label="Vendor" value={item.vendor} />
              <Info label="Domain" value={item.domain} />
              <Info label="Version" value={item.version} />
              <div><div className="mb-1 text-xs text-slate-500">Category</div><Badge variant="info">{item.category}</Badge></div>
              <div><div className="mb-1 text-xs text-slate-500">Severity</div><SeverityBadge severity={item.severity} /></div>
              <div><div className="mb-1 text-xs text-slate-500">Status</div><Badge variant={item.status === "published" ? "success" : "neutral"}>{item.status}</Badge></div>
            </CardContent>
          </Card>

          <Section title="症状" items={item.symptoms} />
          <Section title="可能原因" items={item.possible_causes} />
          <Section title="诊断步骤" items={item.diagnostic_steps} />
          <Section title="处置建议" items={item.remediation} />

          <Card>
            <CardHeader><CardTitle>Decision Tree</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {item.decision_tree.map((rule, idx) => (
                <div key={`${rule.condition}-${idx}`} className="rounded-lg border border-slate-200 p-3">
                  <div className="text-xs font-semibold text-slate-500">IF</div>
                  <div className="font-mono text-sm text-slate-800">{rule.condition}</div>
                  <div className="mt-2 text-xs font-semibold text-slate-500">THEN</div>
                  <div className="text-sm text-slate-800">{rule.conclusion}</div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {rule.required_evidence.map((e) => <Badge key={e} variant="neutral">{e}</Badge>)}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>证据约束</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <TagBlock title="必需证据" values={item.evidence_required} variant="warning" />
              <TagBlock title="可选证据" values={item.evidence_optional} variant="neutral" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><ShieldAlert className="h-4 w-4 text-slate-400" />自动化动作</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <TagBlock title="Safe actions" values={item.automation.safe_actions} variant="success" />
              <TagBlock title="Approval actions" values={item.automation.approval_actions} variant="danger" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>匹配与来源</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <TagBlock title="Aliases" values={item.aliases} variant="neutral" />
              <TagBlock title="Match keywords" values={item.match_keywords} variant="info" />
              <TagBlock title="Negative keywords" values={item.negative_keywords} variant="danger" />
              <TagBlock title="Related cases" values={item.case_refs} variant="success" />
              <TagBlock title="Knowledge refs" values={item.knowledge_refs} variant="neutral" />
              <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                <div className="font-medium text-slate-800">{item.source.title}</div>
                <div>{item.source.type} · trust {(item.source.trust_score * 100).toFixed(0)}%</div>
                <div>updated {formatDate(item.updated_at)}</div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string | number }) {
  return <div><div className="mb-1 text-xs text-slate-500">{label}</div><div className="text-sm font-medium text-slate-900">{value}</div></div>;
}

function Section({ title, items }: { title: string; items: string[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent><ul className="space-y-2 text-sm text-slate-700">{items.map((item) => <li key={item} className="rounded-lg bg-slate-50 px-3 py-2">{item}</li>)}</ul></CardContent>
    </Card>
  );
}

function TagBlock({ title, values, variant }: { title: string; values: string[]; variant: "success" | "warning" | "danger" | "neutral" | "info" }) {
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</div>
      <div className="flex flex-wrap gap-1.5">{values.length ? values.map((value) => <Badge key={value} variant={variant}>{value}</Badge>) : <span className="text-xs text-slate-400">None</span>}</div>
    </div>
  );
}
