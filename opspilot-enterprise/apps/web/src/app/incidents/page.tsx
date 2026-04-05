"use client";

import { useState } from "react";
import { AlertTriangle, Search, Bot, ChevronRight } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge, SeverityBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockIncidents, mockEvidences } from "@/lib/mock-data";
import Link from "next/link";

const statusCounts = {
  all: mockIncidents.length,
  new: mockIncidents.filter((i) => i.status === "new").length,
  analyzing: mockIncidents.filter((i) => i.status === "analyzing").length,
  pending_action: mockIncidents.filter((i) => i.status === "pending_action").length,
  resolved: mockIncidents.filter((i) => i.status === "resolved").length,
};

export default function IncidentsPage() {
  const [selected, setSelected] = useState<string | null>(mockIncidents[0]?.id ?? null);
  const [filter, setFilter] = useState("all");

  const filtered = filter === "all" ? mockIncidents : mockIncidents.filter((i) => i.status === filter);
  const detail = mockIncidents.find((i) => i.id === selected);

  return (
    <div>
      <PageHeader
        title="故障事件中心"
        description="集中管理告警聚合后的故障事件"
        actions={<Button variant="secondary" size="sm">导入事件</Button>}
      />

      {/* Stats */}
      <div className="flex gap-2 mb-4">
        {[
          { key: "all", label: "全部", count: statusCounts.all },
          { key: "analyzing", label: "分析中", count: statusCounts.analyzing },
          { key: "pending_action", label: "待处理", count: statusCounts.pending_action },
          { key: "resolved", label: "已解决", count: statusCounts.resolved },
        ].map((s) => (
          <button
            key={s.key}
            onClick={() => setFilter(s.key)}
            className={cn(
              "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              filter === s.key ? "bg-blue-50 text-blue-700" : "text-gray-500 hover:bg-gray-50"
            )}
          >
            {s.label} ({s.count})
          </button>
        ))}
      </div>

      <div className="flex gap-4 h-[calc(100vh-14rem)]">
        {/* Table */}
        <Card className="flex-1 overflow-hidden">
          <CardContent className="p-0 h-full overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs text-gray-500">
                  <th className="px-4 py-2 font-medium">事件</th>
                  <th className="px-3 py-2 font-medium">级别</th>
                  <th className="px-3 py-2 font-medium">状态</th>
                  <th className="px-3 py-2 font-medium">来源</th>
                  <th className="px-3 py-2 font-medium">时间</th>
                  <th className="px-3 py-2 font-medium">AI</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((inc) => (
                  <tr
                    key={inc.id}
                    onClick={() => setSelected(inc.id)}
                    className={cn(
                      "border-b border-gray-100 cursor-pointer transition-colors",
                      selected === inc.id ? "bg-blue-50" : "hover:bg-gray-50"
                    )}
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-900 truncate max-w-xs">{inc.title}</p>
                      <p className="text-xs text-gray-400">{inc.id}</p>
                    </td>
                    <td className="px-3 py-3"><SeverityBadge severity={inc.severity} /></td>
                    <td className="px-3 py-3"><StatusBadge status={inc.status} /></td>
                    <td className="px-3 py-3 text-xs text-gray-500">{inc.source}</td>
                    <td className="px-3 py-3 text-xs text-gray-500">{formatDate(inc.first_seen_at)}</td>
                    <td className="px-3 py-3">
                      {inc.ai_analysis_triggered && <Bot className="h-4 w-4 text-blue-500" />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        {/* Preview */}
        {detail && (
          <Card className="w-96 shrink-0 overflow-y-auto">
            <CardContent>
              <div className="flex items-center justify-between mb-3">
                <SeverityBadge severity={detail.severity} />
                <StatusBadge status={detail.status} />
              </div>
              <h3 className="text-sm font-semibold text-gray-900 mb-1">{detail.title}</h3>
              <p className="text-xs text-gray-500 mb-4">{detail.summary}</p>

              <div className="space-y-4">
                <div>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">受影响对象</h4>
                  <div className="space-y-1">
                    {detail.affected_objects.map((o) => (
                      <div key={o.object_id} className="flex items-center gap-2 text-xs">
                        <Badge variant="neutral">{o.object_type}</Badge>
                        <span className="text-gray-700">{o.object_name}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {detail.root_cause_candidates.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">根因候选</h4>
                    <div className="space-y-2">
                      {detail.root_cause_candidates.map((rc) => (
                        <div key={rc.id} className="rounded bg-gray-50 p-2 text-xs">
                          <div className="flex justify-between mb-0.5">
                            <Badge variant="info">{rc.category}</Badge>
                            <span className="text-gray-500">{(rc.confidence * 100).toFixed(0)}%</span>
                          </div>
                          <p className="text-gray-700">{rc.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {detail.recommended_actions.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">建议动作</h4>
                    <ul className="space-y-1 text-xs text-gray-700">
                      {detail.recommended_actions.map((a, i) => (
                        <li key={i} className="flex items-start gap-1">
                          <ChevronRight className="h-3 w-3 text-gray-400 mt-0.5 shrink-0" />
                          {a}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <Link href={`/diagnosis?incident=${detail.id}`}>
                  <Button variant="primary" size="sm" className="w-full mt-2">
                    进入诊断工作台
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
