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
    <aside className="flex h-full w-[220px] shrink-0 flex-col border-r border-slate-200 bg-white">
      {/* Brand */}
      <div className="flex h-[54px] items-center gap-2.5 px-4 border-b border-slate-100">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-white text-[11px] font-extrabold tracking-tight shrink-0">
          OP
        </div>
        <div className="leading-none">
          <span className="text-[13px] font-bold text-slate-900 tracking-tight">OpsPilot</span>
          <span className="block text-[10px] text-slate-400 mt-0.5">Enterprise</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-5">
        {navGroups.map((group) => (
          <div key={group.label}>
            <p className="px-2 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
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
                        "flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-all duration-150",
                        active
                          ? "bg-blue-50 text-blue-700 font-semibold shadow-[inset_2px_0_0_0_#2563eb] pl-[10px]"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                      )}
                    >
                      <item.icon className={cn("h-3.5 w-3.5 shrink-0", active ? "text-blue-600" : "text-slate-400")} />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-100 px-4 py-3">
        <p className="text-[10px] text-slate-400">v0.2.0-P1</p>
      </div>
    </aside>
  );
}
