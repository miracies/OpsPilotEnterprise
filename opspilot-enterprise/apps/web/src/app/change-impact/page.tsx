"use client";

import { ArrowRightLeft, AlertTriangle, CheckCircle, ChevronRight } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge, RiskBadge, SeverityBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { mockChangeImpactResult } from "@/lib/mock-data";

const result = mockChangeImpactResult;

export default function ChangeImpactPage() {
  return (
    <div>
      <PageHeader
        title="变更影响分析"
        description="评估变更操作的影响范围、风险等级和回退方案"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm">重新分析</Button>
            <Button variant="primary" size="sm">发起执行申请</Button>
          </div>
        }
      />

      {/* Analysis Form (simplified) */}
      <Card className="mb-4">
        <CardContent>
          <div className="grid grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">变更对象</label>
              <p className="text-sm font-medium text-gray-900">{result.target.name}</p>
              <p className="text-xs text-gray-400">{result.target.type} / {result.target.id}</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">操作类型</label>
              <p className="text-sm font-medium text-gray-900">{result.action}</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">风险评分</label>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-amber-600">{result.risk_score}</span>
                <span className="text-xs text-gray-400">/ 100</span>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">风险等级</label>
              <RiskBadge level={result.risk_level} />
              <p className="text-xs text-gray-400 mt-1">审批建议: {result.approval_suggestion}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Impacted objects */}
        <Card>
          <CardHeader><CardTitle>影响对象</CardTitle></CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs text-gray-500">
                  <th className="pb-2 font-medium">对象</th>
                  <th className="pb-2 font-medium">影响类型</th>
                  <th className="pb-2 font-medium">严重性</th>
                </tr>
              </thead>
              <tbody>
                {result.impacted_objects.map((o) => (
                  <tr key={o.object_id} className="border-b border-gray-50">
                    <td className="py-2">
                      <p className="font-medium text-gray-900">{o.object_name}</p>
                      <p className="text-xs text-gray-400">{o.object_type}</p>
                    </td>
                    <td className="py-2 text-xs text-gray-600">{o.impact_type}</td>
                    <td className="py-2"><SeverityBadge severity={o.severity} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        {/* Dependency graph (simplified) */}
        <Card>
          <CardHeader><CardTitle>依赖关系</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {result.dependency_graph.map((node) => (
                <div key={node.id}>
                  <div className="flex items-center gap-2 font-medium text-sm text-gray-900 mb-2">
                    <ArrowRightLeft className="h-4 w-4 text-blue-500" />
                    {node.name} ({node.type})
                  </div>
                  <div className="ml-6 space-y-1">
                    {node.children.map((child) => (
                      <div key={child.id} className="flex items-center gap-2 text-xs text-gray-600">
                        <ChevronRight className="h-3 w-3 text-gray-400" />
                        <Badge variant="neutral">{child.type}</Badge>
                        {child.name}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Checks */}
        <Card>
          <CardHeader><CardTitle>前置检查项</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {result.checks_required.map((c, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span className="text-gray-700">{c}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Rollback plan */}
        <Card>
          <CardHeader><CardTitle>回退方案</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {result.rollback_plan.map((r, i) => (
                <div key={i} className="flex items-start gap-2 text-sm">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-medium text-gray-600">
                    {i + 1}
                  </span>
                  <span className="text-gray-700">{r}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
