"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, Boxes, Loader2, RefreshCcw, ShieldAlert, Waypoints } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { MetricCard } from "@/components/ui/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import type { ConnectionProfile, K8sOverview, K8sWorkloadStatus } from "@opspilot/shared-types";

export default function K8sResourcesPage() {
  const [connections, setConnections] = useState<ConnectionProfile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [namespace, setNamespace] = useState("");
  const [overview, setOverview] = useState<K8sOverview | null>(null);
  const [workloads, setWorkloads] = useState<K8sWorkloadStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingData, setLoadingData] = useState(false);

  useEffect(() => {
    apiFetch<{ data: ConnectionProfile[] }>("/api/v1/connections?type=kubeconfig").then((r) => {
      const data = r.data ?? [];
      setConnections(data);
      if (data[0] && !selectedId) setSelectedId(data[0].id);
      setLoading(false);
    });
  }, [selectedId]);

  async function fetchData(connectionId: string, ns?: string) {
    if (!connectionId) return;
    setLoadingData(true);
    try {
      const [overviewRes, workloadRes] = await Promise.all([
        apiFetch<{ data: K8sOverview }>(`/api/v1/resources/k8s/overview?connection_id=${connectionId}`),
        apiFetch<{ data: K8sWorkloadStatus }>(`/api/v1/resources/k8s/workloads?connection_id=${connectionId}${ns ? `&namespace=${encodeURIComponent(ns)}` : ""}`),
      ]);
      setOverview(overviewRes.data ?? null);
      setWorkloads(workloadRes.data ?? null);
    } finally {
      setLoadingData(false);
    }
  }

  useEffect(() => {
    if (selectedId) fetchData(selectedId, namespace || undefined);
  }, [selectedId, namespace]);

  const namespaces = useMemo(() => (workloads?.namespaces ?? []).map((item: any) => item.name).filter(Boolean), [workloads]);

  if (loading) {
    return <div className="flex h-64 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="K8s 资源"
        description="基于真实 kubeconfig 连接采集集群节点、命名空间、Pod 与 Deployment 状态"
        actions={
          <div className="flex items-center gap-2">
            <select className="h-8 rounded-lg border border-slate-200 bg-white px-3 text-xs" value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
              {connections.map((conn) => <option key={conn.id} value={conn.id}>{conn.display_name}</option>)}
            </select>
            <select className="h-8 rounded-lg border border-slate-200 bg-white px-3 text-xs" value={namespace} onChange={(e) => setNamespace(e.target.value)}>
              <option value="">全部命名空间</option>
              {namespaces.map((ns) => <option key={ns} value={ns}>{ns}</option>)}
            </select>
            <Button variant="secondary" size="sm" onClick={() => selectedId && fetchData(selectedId, namespace || undefined)} disabled={!selectedId || loadingData}>
              <RefreshCcw className="h-3.5 w-3.5" /> 刷新
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-4 gap-3">
        <MetricCard title="节点数" value={overview?.summary.node_count ?? 0} icon={Waypoints} accent="blue" />
        <MetricCard title="Pod 数" value={overview?.summary.pod_count ?? 0} icon={Boxes} accent="green" />
        <MetricCard title="Deployment 数" value={overview?.summary.deployment_count ?? 0} icon={Boxes} accent="purple" />
        <MetricCard title="异常节点/Pod" value={`${overview?.summary.unhealthy_node_count ?? 0}/${overview?.summary.unhealthy_pod_count ?? 0}`} icon={ShieldAlert} accent="red" />
      </div>

      {loadingData ? (
        <div className="flex h-64 items-center justify-center rounded-xl border border-slate-200 bg-white">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : overview && workloads ? (
        <>
          <Card>
            <CardHeader><CardTitle>集群摘要</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-4 gap-4 text-sm">
              <Info label="连接" value={overview.connection.connection_name} />
              <Info label="Cluster Version" value={overview.cluster_version} />
              <Info label="当前命名空间" value={workloads.namespace || "全部"} />
              <Info label="Endpoint" value={overview.connection.endpoint} mono />
            </CardContent>
          </Card>

          <div className="grid grid-cols-2 gap-4">
            <TableCard
              title="节点"
              columns={["名称", "Ready", "Kubelet", "OS"]}
              rows={(workloads.nodes ?? []).map((node: any) => [
                node.node_name,
                <Badge key={`${node.node_name}-ready`} variant={node.ready ? "success" : "danger"}>{node.ready ? "Ready" : "NotReady"}</Badge>,
                node.kubelet_version,
                node.os_image,
              ])}
            />
            <TableCard
              title="Deployment"
              columns={["命名空间", "名称", "副本", "状态"]}
              rows={(workloads.deployments ?? []).map((dep: any) => [
                dep.namespace,
                dep.name,
                `${dep.replicas_available ?? 0}/${dep.replicas_desired ?? 0}`,
                <Badge key={`${dep.namespace}-${dep.name}`} variant={dep.ready ? "success" : "warning"}>{dep.ready ? "Healthy" : "Degraded"}</Badge>,
              ])}
            />
          </div>

          <TableCard
            title="Pod"
            columns={["命名空间", "名称", "Phase", "Node", "Ready", "重启次数"]}
            rows={(workloads.pods ?? []).slice(0, 50).map((pod: any) => [
              pod.namespace,
              pod.pod_name,
              pod.phase,
              pod.node_name || "—",
              <Badge key={`${pod.namespace}-${pod.pod_name}-ready`} variant={pod.ready ? "success" : "warning"}>{pod.ready ? "Ready" : "NotReady"}</Badge>,
              String(pod.restart_count ?? 0),
            ])}
          />
        </>
      ) : (
        <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50">
          <AlertTriangle className="mb-3 h-10 w-10 text-slate-300" />
          <p className="text-sm text-slate-500">请选择一个 K8s 连接加载真实资源状态</p>
        </div>
      )}
    </div>
  );
}

function TableCard({ title, columns, rows }: { title: string; columns: string[]; rows: Array<Array<ReactNode>> }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              {columns.map((column) => <th key={column} className="px-2 py-2">{column}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row, idx) => (
              <tr key={idx}>
                {row.map((cell, cellIdx) => <td key={cellIdx} className="px-2 py-2">{cell}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function Info({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs text-slate-400">{label}</p>
      <p className={mono ? "mt-1 break-all font-mono text-xs text-slate-700" : "mt-1 text-sm text-slate-700"}>{value}</p>
    </div>
  );
}
