"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Network, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import type { TopologyGraph } from "@opspilot/shared-types";

export default function TopologyPage() {
  const [incidentId, setIncidentId] = useState("");
  const [objectId, setObjectId] = useState("");
  const [graph, setGraph] = useState<TopologyGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const edgeCount = useMemo(() => graph?.edges?.length ?? 0, [graph]);
  const nodeCount = useMemo(() => graph?.nodes?.length ?? 0, [graph]);

  async function loadGraph() {
    setLoading(true);
    setError(null);
    try {
      const path = incidentId.trim()
        ? `/api/v1/topology/incidents/${encodeURIComponent(incidentId.trim())}`
        : `/api/v1/topology/graph?connection_id=conn-vcenter-prod${objectId.trim() ? `&object_id=${encodeURIComponent(objectId.trim())}` : ""}`;
      const res = await apiFetch<{ success: boolean; data?: TopologyGraph; error?: string }>(path);
      if (!res.success || !res.data) {
        throw new Error(res.error || "加载拓扑失败");
      }
      setGraph(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载拓扑失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadGraph();
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader
        title="拓扑视图"
        description="展示 vCenter 资源关系图（VM / Host / Cluster / Datastore）"
        actions={
          <Button size="sm" variant="secondary" onClick={() => void loadGraph()} disabled={loading}>
            <RefreshCw className="h-4 w-4" /> 刷新
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>过滤条件</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <input
            value={incidentId}
            onChange={(e) => setIncidentId(e.target.value)}
            placeholder="Incident ID（优先）"
            className="h-9 rounded border border-slate-200 px-3 text-sm"
          />
          <input
            value={objectId}
            onChange={(e) => setObjectId(e.target.value)}
            placeholder="Object ID（如 vm-123 / host-22）"
            className="h-9 rounded border border-slate-200 px-3 text-sm"
          />
          <Button onClick={() => void loadGraph()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Network className="h-4 w-4" />}
            加载拓扑
          </Button>
        </CardContent>
      </Card>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <Card>
        <CardHeader>
          <CardTitle>拓扑摘要</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3 text-sm">
            <Badge variant="neutral">Nodes: {nodeCount}</Badge>
            <Badge variant="neutral">Edges: {edgeCount}</Badge>
            <span className="text-slate-500">graph_id: {graph?.graph_id ?? "-"}</span>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <h4 className="mb-2 text-sm font-medium">节点</h4>
              <ul className="max-h-80 space-y-1 overflow-auto rounded border border-slate-200 p-2 text-xs">
                {(graph?.nodes ?? []).map((n) => (
                  <li key={n.id} className="flex items-center justify-between">
                    <span>{n.name} ({n.type})</span>
                    <Badge variant="neutral">{n.status ?? "unknown"}</Badge>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="mb-2 text-sm font-medium">关系</h4>
              <ul className="max-h-80 space-y-1 overflow-auto rounded border border-slate-200 p-2 text-xs">
                {(graph?.edges ?? []).map((e) => (
                  <li key={e.id}>
                    {e.source} --{e.relation}--&gt; {e.target}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

