"use client";

import { Play } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export default function ExecutionsPage() {
  return (
    <div>
      <PageHeader title="执行申请" description="变更执行申请与风险审批" />
      <EmptyState icon={Play} title="执行申请（P1）" description="该模块将在第二阶段实现。" />
    </div>
  );
}
