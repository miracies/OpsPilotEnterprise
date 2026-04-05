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
  { name: "KB", value: 12 },
  { name: "案例", value: 7 },
];
const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#6b7280"];

export default function DashboardPage() {
  return (
    <div>
      <PageHeader
        title="AIOps 驾驶舱"
        description="全局运维态势总览"
        actions={
          <Button variant="secondary" size="sm">
            <Clock className="h-4 w-4" /> 今日
          </Button>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        <MetricCard title="活跃故障" value={2} icon={AlertTriangle} accentColor="text-red-600" />
        <MetricCard title="严重告警" value={1} icon={Activity} accentColor="text-orange-600" />
        <MetricCard title="待审批" value={3} icon={ShieldCheck} accentColor="text-amber-600" />
        <MetricCard title="当前值班" value={2} icon={Users} accentColor="text-green-600" />
        <MetricCard title="今日 AI 诊断" value={12} icon={Stethoscope} accentColor="text-blue-600" />
        <MetricCard title="归档案例" value={5} icon={Archive} accentColor="text-purple-600" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <Card>
          <CardHeader>
            <CardTitle>故障趋势 (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={trendData}>
                <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>证据来源分布</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-center">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={sourceData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}>
                  {sourceData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>重点事件</CardTitle>
              <Link href="/incidents" className="text-xs text-blue-600 hover:underline">查看全部</Link>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <tbody>
                {mockIncidents.slice(0, 3).map((inc) => (
                  <tr key={inc.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-5 py-3">
                      <Link href={`/incidents/${inc.id}`} className="font-medium text-gray-900 hover:text-blue-600">{inc.title}</Link>
                      <p className="text-xs text-gray-400 mt-0.5">{inc.id}</p>
                    </td>
                    <td className="px-3 py-3"><SeverityBadge severity={inc.severity} /></td>
                    <td className="px-3 py-3"><StatusBadge status={inc.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>效率指标</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "平均诊断时长", value: "4.2 min", icon: TrendingUp },
                { label: "平均审批时长", value: "18 min", icon: Clock },
                { label: "AI 建议采纳率", value: "78%", icon: Stethoscope },
                { label: "自动化执行成功率", value: "96%", icon: Activity },
              ].map((m) => (
                <div key={m.label} className="flex items-center gap-3 rounded-md bg-gray-50 p-3">
                  <m.icon className="h-4 w-4 text-gray-400" />
                  <div>
                    <p className="text-xs text-gray-500">{m.label}</p>
                    <p className="text-sm font-semibold text-gray-900">{m.value}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
