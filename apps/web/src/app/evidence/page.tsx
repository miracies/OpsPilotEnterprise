"use client";

import { useEffect, useMemo, useState } from "react";
import { FileSearch, Loader2, RefreshCcw, AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";

type IncidentItem = { id: string; title?: string };

type EvidenceItem = {
  evidence_id: string;
  source_type: string;
  summary: string;
  confidence: number;
  timestamp: string;
};

type SourceStat = {
  source_type: string;
  count: number;
  avg_confidence: number;
};

type Coverage = {
  expected_sources?: string[];
  present_sources?: string[];
  missing_sources?: string[];
};

type EvidenceError = {
  source: string;
  message: string;
  code?: string;
};

export default function EvidencePage() {
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [incidentId, setIncidentId] = useState("");
  const [evidences, setEvidences] = useState<EvidenceItem[]>([]);
  const [stats, setStats] = useState<SourceStat[]>([]);
  const [coverage, setCoverage] = useState<Coverage>({});
  const [errors, setErrors] = useState<EvidenceError[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    apiFetch<{ success: boolean; data?: IncidentItem[]; error?: string }>("/api/v1/incidents")
      .then((res) => {
        if (!res.success) {
          setErrorMsg(res.error || "加载事件列表失败");
          return;
        }
        const items = res.data ?? [];
        setIncidents(items);
        if (items.length > 0) {
          setIncidentId(items[0].id);
        }
      })
      .catch(() => setErrorMsg("加载事件列表失败"));
  }, []);

  const canAggregate = useMemo(() => Boolean(incidentId) && !loading, [incidentId, loading]);

  async function aggregate() {
    if (!incidentId) return;
    setLoading(true);
    setErrorMsg("");
    try {
      const res = await apiFetch<{
        success: boolean;
        data?: {
          evidences?: EvidenceItem[];
          source_stats?: SourceStat[];
          coverage?: Coverage;
          errors?: EvidenceError[];
        };
        error?: string;
      }>("/api/v1/evidence/aggregate", {
        method: "POST",
        body: JSON.stringify({ incident_id: incidentId }),
      });

      if (!res.success) {
        setErrorMsg(res.error || "证据聚合失败");
        setEvidences([]);
        setStats([]);
        setCoverage({});
        setErrors([]);
        return;
      }

      const data = res.data ?? {};
      setEvidences(data.evidences ?? []);
      setStats(data.source_stats ?? []);
      setCoverage(data.coverage ?? {});
      setErrors(data.errors ?? []);
    } catch {
      setErrorMsg("证据聚合失败，请稍后重试");
      setEvidences([]);
      setStats([]);
      setCoverage({});
      setErrors([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="证据中心"
        description="聚合实时 Metrics / Events / Topology / Knowledge 证据，不使用 mock。"
        actions={
          <div className="flex items-center gap-2">
            <select
              value={incidentId}
              onChange={(e) => setIncidentId(e.target.value)}
              className="h-8 rounded border border-slate-200 px-2 text-xs"
            >
              {incidents.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.id}
                </option>
              ))}
            </select>
            <Button size="sm" variant="secondary" onClick={() => void aggregate()} disabled={!canAggregate}>
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCcw className="h-3.5 w-3.5" />}
              聚合
            </Button>
          </div>
        }
      />

      {errorMsg && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-center gap-2 py-3 text-sm text-amber-800">
            <AlertTriangle className="h-4 w-4" />
            {errorMsg}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>来源统计</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {stats.length === 0 ? (
            <div className="text-sm text-slate-500">暂无统计，请先执行聚合。</div>
          ) : (
            stats.map((s) => (
              <Badge key={s.source_type} variant="neutral">
                {s.source_type}: {s.count} (avg {s.avg_confidence.toFixed(2)})
              </Badge>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>覆盖率</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm text-slate-700">
          <div>期望来源: {(coverage.expected_sources ?? []).join(",") || "-"}</div>
          <div>已覆盖来源: {(coverage.present_sources ?? []).join(",") || "-"}</div>
          <div className="text-amber-700">缺失来源: {(coverage.missing_sources ?? []).join(",") || "无"}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>证据列表</CardTitle>
        </CardHeader>
        <CardContent>
          {evidences.length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <FileSearch className="h-4 w-4" /> 暂无证据数据
            </div>
          ) : (
            <ul className="space-y-2">
              {evidences.map((e) => (
                <li key={e.evidence_id} className="rounded border border-slate-200 p-3 text-sm">
                  <div className="mb-1 flex items-center gap-2">
                    <Badge variant="neutral">{e.source_type}</Badge>
                    <span className="font-mono text-xs text-slate-500">{e.evidence_id}</span>
                  </div>
                  <div className="text-slate-700">{e.summary}</div>
                  <div className="mt-1 text-xs text-slate-500">confidence={e.confidence}</div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>聚合错误</CardTitle>
        </CardHeader>
        <CardContent>
          {errors.length === 0 ? (
            <div className="text-sm text-slate-500">无错误</div>
          ) : (
            <ul className="list-disc space-y-1 pl-5 text-sm text-amber-700">
              {errors.map((e, i) => (
                <li key={`${e.source}-${i}`}>
                  {e.source}: {e.message}
                  {e.code ? ` (${e.code})` : ""}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
