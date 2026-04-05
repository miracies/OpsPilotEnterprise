"use client";

import { Bell, Search, User } from "lucide-react";

export function Topbar() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6">
      <div className="flex items-center gap-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="搜索事件、对象、知识..."
            className="h-8 w-72 rounded-md border border-gray-200 bg-gray-50 pl-9 pr-3 text-sm placeholder:text-gray-400 focus:border-blue-300 focus:outline-none focus:ring-1 focus:ring-blue-300"
          />
        </div>
        <span className="rounded-md bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
          生产环境
        </span>
      </div>
      <div className="flex items-center gap-4">
        <button className="relative text-gray-500 hover:text-gray-700">
          <Bell className="h-5 w-5" />
          <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] text-white">
            3
          </span>
        </button>
        <div className="flex items-center gap-2 text-sm text-gray-700">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100 text-blue-700">
            <User className="h-4 w-4" />
          </div>
          <span>admin</span>
        </div>
      </div>
    </header>
  );
}
