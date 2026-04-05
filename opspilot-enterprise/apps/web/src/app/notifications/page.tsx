"use client";

import { useState } from "react";
import {
  Bell, CheckCircle2, AlertTriangle, Clock,
  MessageSquare, Phone, Mail, Zap, Users, ChevronRight,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockNotifications, mockOnCallShifts } from "@/lib/mock-data";

const PRIORITY_STYLE: Record<string, string> = {
  urgent: "border-l-red-500 bg-red-50/30",
  high:   "border-l-orange-400 bg-orange-50/20",
  normal: "border-l-slate-300",
  low:    "border-l-slate-200",
};

const PRIORITY_BADGE: Record<string, string> = {
  urgent: "bg-red-50 text-red-700 ring-red-600/20",
  high:   "bg-orange-50 text-orange-700 ring-orange-600/20",
  normal: "bg-slate-100 text-slate-600 ring-slate-300",
  low:    "bg-slate-100 text-slate-500 ring-slate-200",
};

const PRIORITY_LABEL: Record<string, string> = {
  urgent: "紧急",
  high:   "高",
  normal: "普通",
  low:    "低",
};

const STATUS_LABEL: Record<string, string> = {
  pending:      "待发送",
  delivered:    "已送达",
  acknowledged: "已确认",
  escalated:    "已升级",
  timed_out:    "已超时",
};

const CHANNEL_ICONS: Record<string, React.ElementType> = {
  dingtalk: MessageSquare,
  wecom:    MessageSquare,
  email:    Mail,
  sms:      Phone,
  phone:    Phone,
  webhook:  Zap,
};

export default function NotificationsPage() {
  const [selected, setSelected] = useState<string | null>(mockNotifications[0]?.id ?? null);
  const detail = mockNotifications.find((n) => n.id === selected);

  const pending = mockNotifications.filter((n) => n.status !== "acknowledged").length;
  const escalated = mockNotifications.filter((n) => n.status === "escalated").length;

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <PageHeader
        title="值班通知中心"
        description="统一查看值班通知、告警升级、通知状态和处置响应情况"
        actions={
          <div className="flex items-center gap-2">
            {escalated > 0 && (
              <span className="text-xs text-red-600 font-medium bg-red-50 border border-red-200 rounded-md px-2 py-1">
                {escalated} 项已升级
              </span>
            )}
            {pending > 0 && (
              <span className="text-xs text-amber-600 font-medium bg-amber-50 border border-amber-200 rounded-md px-2 py-1">
                {pending} 项待处理
              </span>
            )}
          </div>
        }
      />

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Left: Notification list */}
        <div className="flex-1 flex flex-col min-h-0">
          <div className="rounded-xl border border-slate-200 bg-white overflow-y-auto shadow-[0_1px_3px_0_rgb(0_0_0/0.06)] flex-1">
            <div className="sticky top-0 bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">通知列表</span>
              <span className="text-xs text-slate-400">{mockNotifications.length} 条</span>
            </div>
            <div className="divide-y divide-slate-50">
              {mockNotifications.map((n) => (
                <div
                  key={n.id}
                  onClick={() => setSelected(n.id)}
                  className={cn(
                    "px-5 py-4 cursor-pointer border-l-2 transition-colors",
                    PRIORITY_STYLE[n.priority] ?? "",
                    selected === n.id ? "bg-blue-50/60" : "hover:bg-slate-50"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-full shrink-0 mt-0.5",
                      n.priority === "urgent" ? "bg-red-100" :
                      n.priority === "high" ? "bg-orange-100" : "bg-slate-100"
                    )}>
                      <Bell className={cn("h-3.5 w-3.5",
                        n.priority === "urgent" ? "text-red-600" :
                        n.priority === "high" ? "text-orange-600" : "text-slate-500"
                      )} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={cn("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold ring-1 ring-inset", PRIORITY_BADGE[n.priority])}>
                          {PRIORITY_LABEL[n.priority]}
                        </span>
                        {n.status === "escalated" && (
                          <span className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/20">
                            <AlertTriangle className="h-2.5 w-2.5" /> 已升级 {n.escalation_count}次
                          </span>
                        )}
                        {n.status === "acknowledged" && (
                          <span className="inline-flex items-center gap-1 text-[10px] text-emerald-600">
                            <CheckCircle2 className="h-3 w-3" /> 已确认
                          </span>
                        )}
                      </div>
                      <p className="text-sm font-medium text-slate-900 truncate">{n.title}</p>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-[11px] text-slate-400 flex items-center gap-1">
                          <Clock className="h-3 w-3" /> {formatDate(n.created_at)}
                        </span>
                        <div className="flex items-center gap-1">
                          {n.channels.map((ch) => {
                            const Icon = CHANNEL_ICONS[ch] ?? Bell;
                            return <Icon key={ch} className="h-3 w-3 text-slate-400" />;
                          })}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Detail + On-call */}
        <div className="w-72 shrink-0 space-y-3 overflow-y-auto">
          {/* Notification detail */}
          {detail && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-1.5">
                  <Bell className="h-3.5 w-3.5 text-slate-400" />
                  通知详情
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">通知内容</p>
                  <p className="text-xs text-slate-700 leading-relaxed">{detail.content}</p>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg bg-slate-50 border border-slate-100 p-2">
                    <p className="text-[10px] text-slate-400 mb-0.5">优先级</p>
                    <span className={cn("text-xs font-semibold", detail.priority === "urgent" ? "text-red-600" : detail.priority === "high" ? "text-orange-600" : "text-slate-700")}>{PRIORITY_LABEL[detail.priority]}</span>
                  </div>
                  <div className="rounded-lg bg-slate-50 border border-slate-100 p-2">
                    <p className="text-[10px] text-slate-400 mb-0.5">状态</p>
                    <span className="text-xs font-semibold text-slate-700">{STATUS_LABEL[detail.status]}</span>
                  </div>
                </div>

                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">触达渠道</p>
                  <div className="flex flex-wrap gap-1.5">
                    {detail.channels.map((ch) => {
                      const Icon = CHANNEL_ICONS[ch] ?? Bell;
                      return (
                        <span key={ch} className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                          <Icon className="h-3 w-3" /> {ch}
                        </span>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">接收人</p>
                  <div className="flex flex-wrap gap-1.5">
                    {detail.recipients.map((r) => (
                      <Badge key={r} variant="neutral">{r}</Badge>
                    ))}
                  </div>
                </div>

                {detail.next_escalation_at && (
                  <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
                    <p className="text-[11px] text-amber-700 flex items-center gap-1.5">
                      <AlertTriangle className="h-3 w-3" />
                      下次升级：{formatDate(detail.next_escalation_at)}
                    </p>
                  </div>
                )}

                {detail.status !== "acknowledged" && (
                  <Button variant="primary" size="sm" className="w-full">
                    <CheckCircle2 className="h-3.5 w-3.5" /> 确认处理
                  </Button>
                )}
              </CardContent>
            </Card>
          )}

          {/* On-call shifts */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <Users className="h-3.5 w-3.5 text-slate-400" /> 当前值班
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {mockOnCallShifts.map((shift) => (
                <div key={shift.id} className={cn(
                  "rounded-lg border p-3",
                  shift.active ? "border-emerald-200 bg-emerald-50/40" : "border-slate-100 bg-slate-50"
                )}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-semibold text-slate-700">{shift.team}</span>
                    {shift.active && <Badge variant="success" dot>值班中</Badge>}
                  </div>
                  <p className="text-xs text-slate-600 mb-2">{shift.name}</p>
                  <div className="flex flex-wrap gap-1">
                    {shift.members.map((m) => (
                      <Badge key={m} variant="neutral">{m}</Badge>
                    ))}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-2">
                    {formatDate(shift.start_at)} → {formatDate(shift.end_at)}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
