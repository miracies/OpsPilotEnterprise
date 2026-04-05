"use client";

import { useState } from "react";
import {
  PackageCheck, Upload, RotateCcw, CheckCircle2,
  Download, Loader2, Clock, AlertTriangle, Zap,
  ChevronRight, Server, Info,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge, RiskBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockUpgradePackages, mockDeploymentHistory } from "@/lib/mock-data";

const STATUS_META: Record<string, { icon: React.ElementType; cls: string; label: string }> = {
  available:   { icon: Download,     cls: "bg-blue-50 text-blue-700",     label: "可下载" },
  downloading: { icon: Loader2,      cls: "bg-sky-50 text-sky-700",       label: "下载中" },
  ready:       { icon: PackageCheck, cls: "bg-emerald-50 text-emerald-700", label: "待部署" },
  deploying:   { icon: Loader2,      cls: "bg-amber-50 text-amber-700",    label: "部署中" },
  deployed:    { icon: CheckCircle2, cls: "bg-slate-100 text-slate-600",   label: "已部署" },
  failed:      { icon: AlertTriangle, cls: "bg-red-50 text-red-700",      label: "失败" },
  rolled_back: { icon: RotateCcw,    cls: "bg-slate-100 text-slate-500",   label: "已回滚" },
};

const ENV_STYLE: Record<string, string> = {
  production: "bg-red-50 text-red-700 ring-red-600/20",
  staging:    "bg-amber-50 text-amber-700 ring-amber-600/20",
  dev:        "bg-slate-100 text-slate-600 ring-slate-300",
};

export default function UpgradePage() {
  const [selected, setSelected] = useState<string | null>(mockUpgradePackages[0]?.id ?? null);
  const detail = mockUpgradePackages.find((p) => p.id === selected);

  const readyCount = mockUpgradePackages.filter((p) => p.status === "ready" || p.status === "available").length;

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <PageHeader
        title="升级管理"
        description="OpsPilot 版本包管理、部署记录与一键回滚"
        actions={
          readyCount > 0 ? (
            <span className="text-xs text-emerald-600 font-medium bg-emerald-50 border border-emerald-200 rounded-md px-2 py-1">
              {readyCount} 个新版本可用
            </span>
          ) : undefined
        }
      />

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Package list */}
        <div className="flex-1 flex flex-col min-h-0">
          <div className="rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)] flex-1">
            <div className="sticky top-0 bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">版本包</span>
              <span className="text-xs text-slate-400">{mockUpgradePackages.length} 个</span>
            </div>
            <div className="divide-y divide-slate-50">
              {mockUpgradePackages.map((pkg) => {
                const meta = STATUS_META[pkg.status] ?? STATUS_META.available;
                const Icon = meta.icon;
                return (
                  <div
                    key={pkg.id}
                    onClick={() => setSelected(pkg.id)}
                    className={cn(
                      "px-5 py-4 cursor-pointer transition-colors",
                      selected === pkg.id ? "bg-blue-50" : "hover:bg-slate-50",
                      (pkg.status === "ready" || pkg.status === "available") ? "border-l-2 border-l-emerald-400" : ""
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div className={cn("h-11 w-11 rounded-xl flex items-center justify-center shrink-0 mt-0.5", meta.cls)}>
                        <Icon className={cn("h-5 w-5", pkg.status === "deploying" ? "animate-spin" : "")} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold", meta.cls)}>
                            {meta.label}
                          </span>
                          <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold ring-1 ring-inset", ENV_STYLE[pkg.environment])}>
                            {pkg.environment}
                          </span>
                          <RiskBadge level={pkg.risk_level} />
                        </div>
                        <div className="flex items-center gap-2">
                          <p className="text-base font-bold text-slate-900">v{pkg.version}</p>
                          <span className="text-xs text-slate-400">{pkg.release_name}</span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5 truncate">{pkg.description}</p>
                        <div className="flex items-center gap-3 mt-1.5 text-[11px] text-slate-400">
                          <span className="flex items-center gap-1"><Server className="h-3 w-3" />{pkg.target}</span>
                          <span>{pkg.package_size_mb} MB</span>
                          {pkg.requires_restart && <span className="text-amber-600">需重启</span>}
                          {pkg.requires_approval && <span className="text-purple-600">需审批</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Deployment history */}
          <div className="mt-3 rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
            <div className="px-5 py-3 border-b border-slate-200">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">部署历史</p>
            </div>
            <div className="divide-y divide-slate-50">
              {mockDeploymentHistory.map((dep) => {
                const meta = STATUS_META[dep.status] ?? STATUS_META.deployed;
                const Icon = meta.icon;
                return (
                  <div key={dep.id} className="px-5 py-3 flex items-center gap-4">
                    <Icon className={cn("h-4 w-4 shrink-0", meta.cls.split(" ")[1])} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-slate-800">v{dep.package_version}</p>
                      <p className="text-[11px] text-slate-400">{dep.environment} · {dep.deployed_by} · {formatDate(dep.started_at)}</p>
                    </div>
                    {dep.rollback_available && (
                      <Button variant="secondary" size="xs">
                        <RotateCcw className="h-3 w-3" /> 回滚
                      </Button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Package detail */}
        {detail && (
          <div className="w-80 shrink-0 rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
            <div className="px-4 py-3 border-b border-slate-100">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xl font-bold text-slate-900">v{detail.version}</span>
                <span className={cn("inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold", STATUS_META[detail.status]?.cls)}>
                  {STATUS_META[detail.status]?.label}
                </span>
              </div>
              <p className="text-sm font-semibold text-slate-700">{detail.release_name}</p>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">{detail.id}</p>
            </div>

            <div className="px-4 py-4 space-y-4">
              <p className="text-xs text-slate-700 leading-relaxed">{detail.description}</p>

              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">变更日志</p>
                <ul className="space-y-1.5">
                  {detail.changelog.map((line, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-slate-700">
                      <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-blue-400 shrink-0" />
                      {line}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-lg bg-slate-50 border border-slate-100 p-2.5">
                  <p className="text-[10px] text-slate-400 mb-0.5">目标服务</p>
                  <p className="text-xs font-medium text-slate-700">{detail.target}</p>
                </div>
                <div className="rounded-lg bg-slate-50 border border-slate-100 p-2.5">
                  <p className="text-[10px] text-slate-400 mb-0.5">包大小</p>
                  <p className="text-xs font-medium text-slate-700">{detail.package_size_mb} MB</p>
                </div>
                <div className="rounded-lg bg-slate-50 border border-slate-100 p-2.5">
                  <p className="text-[10px] text-slate-400 mb-0.5">环境</p>
                  <p className="text-xs font-medium text-slate-700">{detail.environment}</p>
                </div>
                <div className="rounded-lg bg-slate-50 border border-slate-100 p-2.5">
                  <p className="text-[10px] text-slate-400 mb-0.5">风险等级</p>
                  <RiskBadge level={detail.risk_level} />
                </div>
              </div>

              {(detail.requires_restart || detail.requires_approval) && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2.5 space-y-1">
                  {detail.requires_restart && (
                    <p className="text-xs text-amber-700 flex items-center gap-1.5">
                      <AlertTriangle className="h-3 w-3" /> 部署后需要重启服务
                    </p>
                  )}
                  {detail.requires_approval && (
                    <p className="text-xs text-amber-700 flex items-center gap-1.5">
                      <Info className="h-3 w-3" /> 部署前需要申请审批
                    </p>
                  )}
                </div>
              )}

              {detail.rollback_version && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">回滚版本</p>
                  <p className="text-sm font-mono text-slate-600">v{detail.rollback_version}</p>
                </div>
              )}

              {detail.deployed_at && (
                <div className="text-[11px] text-slate-400">
                  <p>部署时间：{formatDate(detail.deployed_at)}</p>
                  {detail.deployed_by && <p>部署人：{detail.deployed_by}</p>}
                </div>
              )}

              {(detail.status === "ready" || detail.status === "available") && (
                <div className="flex gap-2 pt-1 border-t border-slate-100">
                  {detail.requires_approval ? (
                    <Button variant="secondary" size="sm" className="flex-1 text-amber-700 border-amber-200 hover:bg-amber-50">
                      <Upload className="h-3.5 w-3.5" /> 发起审批
                    </Button>
                  ) : (
                    <Button variant="primary" size="sm" className="flex-1">
                      <Zap className="h-3.5 w-3.5" /> 立即部署
                    </Button>
                  )}
                </div>
              )}

              {detail.status === "deployed" && detail.rollback_version && (
                <Button variant="secondary" size="sm" className="w-full text-slate-600">
                  <RotateCcw className="h-3.5 w-3.5" /> 回滚到 v{detail.rollback_version}
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
