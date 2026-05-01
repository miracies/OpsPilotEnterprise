"use client";

import {
  AlertTriangle,
  Activity,
  ShieldCheck,
  Users,
  Stethoscope,
  Archive,
  TrendingUp,
  Clock,
  ArrowRight,
} from "lucide-react";
import { MetricCard } from "@/components/ui/metric-card";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { SeverityBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { mockIncidents } from "@/lib/mock-data";
import Link from "next/link";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const trendData = [
  { hour: "03:00", count: 2 },
  { hour: "04:00", count: 1 },
  { hour: "05:00", count: 3 },
  { hour: "06:00", count: 2 },
  { hour: "07:00", count: 5 },
  { hour: "08:00", count: 8 },
  { hour: "09:00", count: 4 },
];

const sourceData = [
  { name: "事件", value: 35 },
  { name: "指标", value: 28 },
  { name: "日志", value: 18 },
  { name: "KB",   value: 12 },
  { name: "案例", value: 7 },
];
const COLORS = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6", "#64748b"];

const efficiencyMetrics = [
  { label: "平均诊断时长", value: "4.2 min", icon: Stethoscope, trend: "-12% vs 昨日", up: true },
  { label: "平均审批时长", value: "18 min",  icon: Clock,        trend: "+2% vs 昨日",  up: false },
  { label: "AI 建议采纳率", value: "78%",    icon: TrendingUp,   trend: "+5% vs 昨日",  up: true },
  { label: "自动化执行成功", value: "96%",   icon: Activity,     trend: "稳定",          up: null },
];

export default function DashboardPage() {
  return (
    <div>
      <PageHeader
        title="AIOps 驾驶舱"
        description="全局运维态势总览 · 今日实时数据"
        actions={
          <Button variant="secondary" size="sm">
            <Clock className="h-3.5 w-3.5" />
            今日
          </Button>
        }
      />

      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
        <MetricCard
          title="活跃故障"
          value={2}
          icon={AlertTriangle}
          accent="red"
          trend="较昨日 +1"
          trendDir="up"
          trendColor="negative"
        />
        <MetricCard
          title="严重告警"
          value={1}
          icon={Activity}
          accent="orange"
          trend="未变化"
          trendDir="flat"
        />
        <MetricCard
          title="待审批"
          value={3}
          icon={ShieldCheck}
          accent="amber"
          trend="2 项超时"
          trendColor="negative"
        />
        <MetricCard
          title="当前值班"
          value={2}
          icon={Users}
          accent="green"
          trend="正常"
          trendColor="positive"
        />
        <MetricCard
          title="今日 AI 诊断"
          value={12}
          icon={Stethoscope}
          accent="blue"
          trend="完成率 91%"
          trendColor="positive"
        />
        <MetricCard
          title="归档案例"
          value={5}
          icon={Archive}
          accent="purple"
          trend="本周累计 18"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <Card>
          <CardHeader>
            <CardTitle>故障趋势（近 7h）</CardTitle>
          </CardHeader>
          <CardContent className="pt-3">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={trendData} barSize={22}>
                <XAxis
                  dataKey="hour"
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  axisLine={false}
                  tickLine={false}
                  width={24}
                />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0", boxShadow: "0 4px 12px rgb(0 0 0 / 0.08)" }}
                  cursor={{ fill: "#f1f5f9" }}
                />
                <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>证据来源分布</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-4">
            <ResponsiveContainer width="55%" height={180}>
              <PieChart>
                <Pie
                  data={sourceData}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={72}
                  dataKey="value"
                  paddingAngle={2}
                >
                  {sourceData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-2">
              {sourceData.map((d, i) => (
                <div key={d.name} className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full shrink-0" style={{ background: COLORS[i] }} />
                  <span className="text-xs text-slate-600 flex-1">{d.name}</span>
                  <span className="text-xs font-medium text-slate-700">{d.value}%</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Incident Table */}
        <Card>
          <CardHeader>
            <CardTitle>重点事件</CardTitle>
            <Link href="/incidents" className="flex items-center gap-0.5 text-xs text-blue-600 hover:text-blue-700 font-medium">
              查看全部 <ArrowRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <div>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100 text-left">
                  <th className="px-5 py-2.5 text-xs font-medium text-slate-500">事件</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500 w-16">级别</th>
                  <th className="px-3 py-2.5 text-xs font-medium text-slate-500 w-20">状态</th>
                </tr>
              </thead>
              <tbody>
                {mockIncidents.slice(0, 4).map((inc, idx) => (
                  <tr
                    key={inc.id}
                    className={`
                      border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors
                      ${inc.severity === "critical" ? "severity-critical" : inc.severity === "high" ? "severity-high" : ""}
                    `}
                  >
                    <td className="px-5 py-3">
                      <Link href={`/incidents/${inc.id}`} className="font-medium text-slate-900 hover:text-blue-600 text-sm leading-snug block truncate max-w-[200px]">
                        {inc.title}
                      </Link>
                      <p className="text-[11px] text-slate-400 mt-0.5 font-mono">{inc.id}</p>
                    </td>
                    <td className="px-3 py-3">
                      <SeverityBadge severity={inc.severity} />
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge status={inc.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Efficiency */}
        <Card>
          <CardHeader>
            <CardTitle>效率指标</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              {efficiencyMetrics.map((m) => (
                <div
                  key={m.label}
                  className="rounded-lg bg-slate-50 border border-slate-100 p-3"
                >
                  <div className="flex items-center gap-1.5 mb-2">
                    <m.icon className="h-3.5 w-3.5 text-slate-400" />
                    <p className="text-xs text-slate-500">{m.label}</p>
                  </div>
                  <p className="text-lg font-bold text-slate-900 leading-none">{m.value}</p>
                  {m.trend && (
                    <p className={`text-[11px] mt-1.5 ${m.up === true ? "text-emerald-600" : m.up === false ? "text-red-500" : "text-slate-400"}`}>
                      {m.trend}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
