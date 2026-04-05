"use client";

import { ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export default function ApprovalsPage() {
  return (
    <div>
      <PageHeader title="审批中心" description="待审批执行请求与高风险操作" />
      <EmptyState icon={ShieldCheck} title="审批中心（P1）" description="该模块将在第二阶段实现。" />
    </div>
  );
}
