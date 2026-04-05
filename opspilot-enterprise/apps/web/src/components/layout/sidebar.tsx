"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  MessageSquare,
  AlertTriangle,
  Stethoscope,
  ArrowRightLeft,
  Play,
  ShieldCheck,
  Bell,
  FileSearch,
  Archive,
  BookOpen,
  Lock,
  Settings,
  ArrowUpCircle,
  Bot,
  ClipboardList,
} from "lucide-react";

const navGroups = [
  {
    label: "概览",
    items: [
      { href: "/", label: "驾驶舱", icon: LayoutDashboard },
      { href: "/chat", label: "AI 对话", icon: MessageSquare },
    ],
  },
  {
    label: "故障与诊断",
    items: [
      { href: "/incidents", label: "故障事件", icon: AlertTriangle },
      { href: "/diagnosis", label: "诊断工作台", icon: Stethoscope },
    ],
  },
  {
    label: "变更与执行",
    items: [
      { href: "/change-impact", label: "变更分析", icon: ArrowRightLeft },
      { href: "/executions", label: "执行申请", icon: Play },
      { href: "/approvals", label: "审批中心", icon: ShieldCheck },
    ],
  },
  {
    label: "运营",
    items: [
      { href: "/notifications", label: "值班通知", icon: Bell },
      { href: "/audit", label: "审计中心", icon: ClipboardList },
      { href: "/evidence", label: "证据中心", icon: FileSearch },
      { href: "/cases", label: "案例归档", icon: Archive },
    ],
  },
  {
    label: "平台",
    items: [
      { href: "/knowledge", label: "知识管理", icon: BookOpen },
      { href: "/policies", label: "策略管理", icon: Lock },
      { href: "/agents", label: "Agent 视图", icon: Bot },
      { href: "/settings", label: "系统配置", icon: Settings },
      { href: "/upgrade", label: "升级管理", icon: ArrowUpCircle },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-56 flex-col border-r border-gray-200 bg-white">
      <div className="flex h-14 items-center gap-2 border-b border-gray-200 px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white text-xs font-bold">
          OP
        </div>
        <span className="text-sm font-bold text-gray-900">OpsPilot</span>
        <span className="text-[10px] text-gray-400 ml-auto">v0.1</span>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {navGroups.map((group) => (
          <div key={group.label}>
            <p className="px-2 mb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
                        active
                          ? "bg-blue-50 text-blue-700 font-medium"
                          : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                      )}
                    >
                      <item.icon className="h-4 w-4 shrink-0" />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
