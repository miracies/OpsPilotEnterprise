"use client";

import {
  ArrowRightLeft, ChevronRight, CheckCircle2,
  RotateCcw, Play, AlertTriangle, ShieldAlert,
  Network, ShieldCheck, Archive,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge, RiskBadge, SeverityBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { mockChangeImpactResult } from "@/lib/mock-data";
import Link from "next/link";

const result = mockChangeImpactResult;

const RISK_SCORE_COLOR = (score: number) =>
  score >= 80 ? "text-red-600" :
  score >= 50 ? "text-amber-600" :
  score >= 30 ? "text-blue-600" : "text-emerald-600";

const RISK_SCORE_BG = (score: number) =>
  score >= 80 ? "bg-red-50 border-red-200" :
  score >= 50 ? "bg-amber-50 border-amber-200" :
  score >= 30 ? "bg-blue-50 border-blue-200" : "bg-emerald-50 border-emerald-200";

export default function ChangeImpactPage() {
  return (
    <div>
      <PageHeader
        title="变更影响分析"
        description="评估变更操作的影响范围、风险等级和回退方案"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm">
              <RotateCcw className="h-3.5 w-3.5" />
              重新分析
            </Button>
            <Button variant="primary" size="sm">
              <Play className="h-3.5 w-3.5" />
              发起执行申请
            </Button>
          </div>
        }
      />

      {/* Risk Hero Card */}
      <Card className={cn("mb-5 border-2", RISK_SCORE_BG(result.risk_score))}>
        <CardContent className="py-5">
          <div className="flex items-center gap-8">
            {/* Score */}
            <div className="flex flex-col items-center shrink-0 px-4">
              <p className={cn("text-5xl font-black leading-none", RISK_SCORE_COLOR(result.risk_score))}>
                {result.risk_score}
              </p>
              <p className="text-xs text-slate-500 mt-1.5 font-medium">风险评分 / 100</p>
              <div className="mt-2">
                <RiskBadge level={result.risk_level} />
              </div>
            </div>

            {/* Divider */}
            <div className="w-px h-16 bg-slate-200 shrink-0" />

            {/* Meta */}
            <div className="grid grid-cols-3 gap-6 flex-1">
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">变更对象</p>
                <p className="text-sm font-semibold text-slate-900">{result.target.name}</p>
                <p className="text-[11px] text-slate-400 font-mono mt-0.5">{result.target.type} / {result.target.id}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">操作类型</p>
                <p className="text-sm font-semibold text-slate-900">{result.action}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">审批建议</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <ShieldAlert className="h-4 w-4 text-amber-500" />
                  <span className="text-sm font-semibold text-slate-900">{result.approval_suggestion}</span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Impacted objects */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
              影响对象
            </CardTitle>
            <Badge variant="warning" dot>{result.impacted_objects.length} 个受影响</Badge>
          </CardHeader>
          <div>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100">
                  <th className="px-5 py-2.5 text-left text-xs font-semibold text-slate-500">对象名称</th>
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500">影响类型</th>
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 w-16">严重性</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {result.impacted_objects.map((o) => (
                  <tr
                    key={o.object_id}
                    className="hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-5 py-3">
                      <p className="font-medium text-slate-900">{o.object_name}</p>
                      <p className="text-[11px] text-slate-400">{o.object_type}</p>
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-600">{o.impact_type}</td>
                    <td className="px-3 py-3"><SeverityBadge severity={o.severity} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Dependency graph */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Network className="h-3.5 w-3.5 text-blue-500" />
              依赖关系
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {result.dependency_graph.map((node) => (
              <div key={node.id} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <ArrowRightLeft className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                  <span className="text-sm font-semibold text-slate-900">{node.name}</span>
                  <Badge variant="neutral">{node.type}</Badge>
                </div>
                {node.children.length > 0 && (
                  <div className="ml-5 space-y-1.5 border-l-2 border-slate-200 pl-3">
                    {node.children.map((child) => (
                      <div key={child.id} className="flex items-center gap-2">
                        <ChevronRight className="h-3 w-3 text-slate-400 shrink-0" />
                        <Badge variant="neutral">{child.type}</Badge>
                        <span className="text-xs text-slate-700">{child.name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Second Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Pre-checks */}
        <Card>
          <CardHeader>
            <CardTitle>前置检查项</CardTitle>
            <span className="text-[11px] text-slate-400">{result.checks_required.length} 项</span>
          </CardHeader>
          <CardContent className="space-y-2">
            {result.checks_required.map((c, i) => (
              <div
                key={i}
                className="flex items-start gap-2.5 rounded-lg bg-slate-50 border border-slate-100 px-3 py-2.5"
              >
                <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                <span className="text-sm text-slate-700">{c}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Rollback plan */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <RotateCcw className="h-3.5 w-3.5 text-slate-400" />
              回退方案
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {result.rollback_plan.map((r, i) => (
              <div
                key={i}
                className="flex items-start gap-2.5 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2.5 hover:border-amber-200 hover:bg-amber-50/30 transition-colors group"
              >
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-100 text-[11px] font-bold text-amber-700 mt-0.5">
                  {i + 1}
                </span>
                <span className="text-sm text-slate-700 leading-relaxed">{r}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Cross-page CTAs */}
        <div className="rounded-xl border border-blue-100 bg-blue-50/40 p-4">
          <p className="text-xs font-semibold text-blue-700 mb-3">分析完成后的下一步</p>
          <div className="flex flex-wrap gap-2">
            {result.approval_suggestion === "required" && (
              <Link href="/approvals">
                <Button variant="primary" size="sm">
                  <ShieldCheck className="h-3.5 w-3.5" /> 发起审批申请
                </Button>
              </Link>
            )}
            <Link href="/cases">
              <Button variant="secondary" size="sm">
                <Archive className="h-3.5 w-3.5" /> 查看相似案例
              </Button>
            </Link>
            <Link href="/policies">
              <Button variant="secondary" size="sm">
                <ShieldAlert className="h-3.5 w-3.5" /> 检查策略规则
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
