"use client";

import { Bot } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export default function AgentsPage() {
  return (
    <div>
      <PageHeader title="SubAgent 运行视图" description="Agent 编排与执行轨迹" />
      <EmptyState icon={Bot} title="SubAgent 运行视图（P1）" description="该模块将在第二阶段实现。" />
    </div>
  );
}
