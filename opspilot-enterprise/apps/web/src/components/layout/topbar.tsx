"use client";

import { Bell, Search, ChevronDown } from "lucide-react";

export function Topbar() {
  return (
    <header className="flex h-[54px] items-center justify-between border-b border-slate-200 bg-white px-5 shrink-0">
      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="搜索事件、对象、知识..."
            className="h-8 w-64 rounded-lg border border-slate-200 bg-slate-50 pl-8.5 pr-3 text-[13px] text-slate-700 placeholder:text-slate-400
                       focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
          />
        </div>
        {/* Env badge */}
        <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          生产环境
        </span>
      </div>

      <div className="flex items-center gap-2">
        {/* Notification bell */}
        <button className="relative flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors">
          <Bell className="h-4 w-4" />
          <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white ring-2 ring-white">
            3
          </span>
        </button>

        {/* User */}
        <button className="flex items-center gap-2 rounded-lg px-2 py-1 text-sm text-slate-700 hover:bg-slate-100 transition-colors">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-white text-xs font-semibold">
            A
          </div>
          <span className="text-[13px] font-medium">admin</span>
          <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
        </button>
      </div>
    </header>
  );
}
