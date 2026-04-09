"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, Database, Loader2, RefreshCcw, Server, ShieldAlert } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { MetricCard } from "@/components/ui/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { ConnectionProfile, VCenterInventory, VCenterOverview } from "@opspilot/shared-types";

export default function VCenterResourcesPage() {
  const [connections, setConnections] = useState<ConnectionProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [overview, setOverview] = useState<VCenterOverview | null>(null);
  const [inventory, setInventory] = useState<VCenterInventory | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingData, setLoadingData] = useState(false);

  useEffect(() => {
    apiFetch<{ data: ConnectionProfile[] }>("/api/v1/connections?type=vcenter").then((r) => {
      const data = r.data ?? [];
      setConnections(data);
      if (data[0] && !selectedId) setSelectedId(data[0].id);
      setLoading(false);
    });
  }, [selectedId]);

  async function fetchData(connectionId: string) {
    if (!connectionId) return;
    setLoadingData(true);
    try {
      const [overviewRes, inventoryRes] = await Promise.all([
        apiFetch<{ data: VCenterOverview }>(`/api/v1/resources/vcenter/overview?connection_id=${connectionId}`),
        apiFetch<{ data: VCenterInventory }>(`/api/v1/resources/vcenter/inventory?connection_id=${connectionId}`),
      ]);
      setOverview(overviewRes.data ?? null);
      setInventory(inventoryRes.data ?? null);
    } finally {
      setLoadingData(false);
    }
  }

  useEffect(() => {
    if (selectedId) fetchData(selectedId);
  }, [selectedId]);

  const selectedConnection = useMemo(
    () => connections.find((conn) => conn.id === selectedId) ?? null,
    [connections, selectedId],
  );

  if (loading) {
    return <div className="flex h-64 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="vCenter 资源"
        description="基于真实 vCenter 连接采集集群、主机、虚拟机与数据存储状态"
        actions={
          <div className="flex items-center gap-2">
            <select
              className="h-8 rounded-lg border border-slate-200 bg-white px-3 text-xs"
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
            >
              {connections.map((conn) => (
                <option key={conn.id} value={conn.id}>{conn.display_name}</option>
              ))}
            </select>
            <Button variant="secondary" size="sm" onClick={() => selectedId && fetchData(selectedId)} disabled={!selectedId || loadingData}>
              <RefreshCcw className="h-3.5 w-3.5" /> 刷新
            </Button>
          </div>
        }
      />

      {selectedConnection && (
        <div className="grid grid-cols-4 gap-3">
          <MetricCard title="集群数" value={overview?.summary.cluster_count ?? 0} icon={Server} accent="blue" />
          <MetricCard title="主机数" value={overview?.summary.host_count ?? 0} icon={Server} accent="green" />
          <MetricCard title="虚拟机数" value={overview?.summary.vm_count ?? 0} icon={Database} accent="purple" />
          <MetricCard title="异常主机/VM" value={`${overview?.summary.unhealthy_host_count ?? 0}/${overview?.summary.unhealthy_vm_count ?? 0}`} icon={ShieldAlert} accent="red" />
        </div>
      )}

      {loadingData ? (
        <div className="flex h-64 items-center justify-center rounded-xl border border-slate-200 bg-white">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : overview && inventory ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>连接摘要</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-4 gap-4 text-sm">
              <Info label="连接" value={overview.connection.connection_name} />
              <Info label="Endpoint" value={overview.connection.endpoint} mono />
              <Info label="vCenter" value={overview.vcenter} />
              <Info label="采集时间" value={formatDate(overview.generated_at)} />
            </CardContent>
          </Card>

          <div className="grid grid-cols-2 gap-4">
            <TableCard
              title="集群"
              columns={["名称", "主机数", "状态"]}
              rows={overview.clusters.map((cluster: any) => [
                cluster.name,
                String(cluster.host_count ?? 0),
                <StatusBadge key={`${cluster.cluster_id}-status`} status={String(cluster.overall_status ?? "gray")} />,
              ])}
            />
            <TableCard
              title="主机"
              columns={["名称", "CPU 使用", "内存使用", "状态"]}
              rows={overview.hosts.map((host: any) => [
                host.name,
                `${host.cpu_usage_mhz ?? 0} MHz`,
                `${host.memory_usage_mb ?? 0} MB`,
                <StatusBadge key={`${host.host_id}-status`} status={String(host.overall_status ?? "gray")} />,
              ])}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <TableCard
              title="虚拟机"
              columns={["名称", "电源状态"]}
              rows={(inventory.virtual_machines ?? []).slice(0, 20).map((vm: any) => [
                vm.name,
                <Badge key={`${vm.vm_id}-power`} variant={vm.power_state === "poweredOn" ? "success" : "warning"}>{vm.power_state}</Badge>,
              ])}
            />
            <TableCard
              title="数据存储"
              columns={["名称", "类型", "总容量(GB)", "空闲(GB)"]}
              rows={(inventory.datastores ?? []).map((ds: any) => [
                ds.name,
                ds.type,
                String(ds.capacity_gb ?? 0),
                String(ds.free_gb ?? 0),
              ])}
            />
          </div>
        </>
      ) : (
        <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50">
          <AlertTriangle className="mb-3 h-10 w-10 text-slate-300" />
          <p className="text-sm text-slate-500">请选择一个 vCenter 连接加载真实资源状态</p>
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

function StatusBadge({ status }: { status: string }) {
  const variant = status === "green" ? "success" : status === "yellow" ? "warning" : status === "red" ? "danger" : "neutral";
  return <Badge variant={variant}>{status}</Badge>;
}
