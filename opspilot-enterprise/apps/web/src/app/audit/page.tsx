"use client";

import { ClipboardList } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export default function AuditPage() {
  return (
    <div>
      <PageHeader title="审计中心" description="操作审计记录与策略命中" />
      <EmptyState icon={ClipboardList} title="审计中心（P1）" description="该模块将在第二阶段实现。" />
    </div>
  );
}
