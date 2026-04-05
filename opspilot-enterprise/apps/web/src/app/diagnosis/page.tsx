"use client";

import { AlertTriangle, Clock, FileText, BookOpen, Archive, Bot, Wrench } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge, SeverityBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import { mockIncidents, mockEvidences, mockIncidentTimeline } from "@/lib/mock-data";

const incident = mockIncidents[0];
const evidences = mockEvidences.filter((e) => incident.evidence_refs.includes(e.evidence_id));

export default function DiagnosisPage() {
  return (
    <div>
      <PageHeader
        title="诊断工作台"
        description={incident.title}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm">导出报告</Button>
            <Button variant="primary" size="sm">发起执行申请</Button>
          </div>
        }
      />

      <div className="flex gap-4 h-[calc(100vh-12rem)]">
        {/* Left: Context */}
        <div className="w-64 shrink-0 space-y-4 overflow-y-auto">
          <Card>
            <CardHeader><CardTitle>事件摘要</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <SeverityBadge severity={incident.severity} />
                  <StatusBadge status={incident.status} />
                </div>
                <p className="text-gray-700">{incident.summary}</p>
                <p className="text-gray-400">{formatDate(incident.first_seen_at)}</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>受影响资源</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-1.5">
                {incident.affected_objects.map((o) => (
                  <div key={o.object_id} className="flex items-center gap-1.5 text-xs">
                    <span className="h-1.5 w-1.5 rounded-full bg-red-400 shrink-0" />
                    <Badge variant="neutral">{o.object_type}</Badge>
                    <span className="text-gray-700 truncate">{o.object_name}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>相关告警</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-1 text-xs text-gray-600">
                <p>CPU &gt; 95% 持续 30min</p>
                <p>CPU ready time &gt; 10%</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Center: Analysis */}
        <div className="flex-1 overflow-y-auto space-y-4">
          <Card>
            <CardHeader><CardTitle>根因候选</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-3">
                {incident.root_cause_candidates.map((rc, i) => (
                  <div key={rc.id} className="rounded-lg border border-gray-100 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700">
                          {i + 1}
                        </span>
                        <Badge variant="info">{rc.category}</Badge>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className="h-2 w-24 rounded-full bg-gray-200">
                          <div
                            className="h-2 rounded-full bg-blue-500"
                            style={{ width: `${rc.confidence * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500">{(rc.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                    <p className="text-sm text-gray-900">{rc.description}</p>
                    <p className="text-xs text-gray-400 mt-1">关联证据: {rc.evidence_refs.length} 条</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>证据时间线</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-0">
                {mockIncidentTimeline.map((entry, i) => (
                  <div key={i} className="flex gap-3 pb-4 last:pb-0">
                    <div className="flex flex-col items-center">
                      <div className={`h-2 w-2 rounded-full mt-1.5 ${
                        entry.type === "event" ? "bg-red-400" :
                        entry.type === "analysis" ? "bg-blue-400" :
                        entry.type === "notification" ? "bg-amber-400" :
                        entry.type === "action" ? "bg-green-400" : "bg-gray-400"
                      }`} />
                      {i < mockIncidentTimeline.length - 1 && <div className="w-px flex-1 bg-gray-200 mt-1" />}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm text-gray-900">{entry.summary}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-gray-400">{formatDate(entry.timestamp)}</span>
                        {entry.agent && <Badge variant="neutral">{entry.agent}</Badge>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>建议动作</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2">
                {incident.recommended_actions.map((a, i) => (
                  <div key={i} className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2">
                    <span className="text-sm text-gray-700">{a}</span>
                    <Button variant="ghost" size="sm">执行</Button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: Aux */}
        <div className="w-72 shrink-0 overflow-y-auto space-y-4">
          <Card>
            <CardHeader><CardTitle><BookOpen className="inline h-4 w-4 mr-1" />知识库命中</CardTitle></CardHeader>
            <CardContent>
              {evidences.filter((e) => e.source_type === "kb").map((e) => (
                <div key={e.evidence_id} className="rounded border border-gray-100 p-2 text-xs mb-2">
                  <p className="font-medium text-gray-700">{e.summary}</p>
                  <p className="text-gray-400 mt-0.5">置信度: {(e.confidence * 100).toFixed(0)}%</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle><Archive className="inline h-4 w-4 mr-1" />相似案例</CardTitle></CardHeader>
            <CardContent>
              <div className="rounded border border-gray-100 p-2 text-xs">
                <p className="font-medium text-gray-700">CASE-20260320: 类似 Java GC 风暴导致主机 CPU 飙升</p>
                <p className="text-gray-400 mt-0.5">2026-03-20 | 相似度 82%</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle><Bot className="inline h-4 w-4 mr-1" />Agent 轨迹</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-1.5 text-xs">
                {["IntentAgent", "EvidenceCollectionAgent", "KBRetrievalAgent", "RCAAgent", "NotificationAgent"].map((a) => (
                  <div key={a} className="flex items-center gap-2">
                    <Wrench className="h-3 w-3 text-gray-400" />
                    <span className="text-gray-700">{a}</span>
                    <Badge variant="success" className="ml-auto">done</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle><FileText className="inline h-4 w-4 mr-1" />证据列表</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2">
                {evidences.map((e) => (
                  <div key={e.evidence_id} className="rounded border border-gray-100 p-2 text-xs">
                    <div className="flex items-center gap-1 mb-0.5">
                      <Badge variant="neutral">{e.source_type}</Badge>
                      <span className="ml-auto text-gray-400">{(e.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <p className="text-gray-700">{e.summary}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
