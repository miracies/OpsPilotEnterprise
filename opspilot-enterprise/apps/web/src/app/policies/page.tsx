"use client";

import { Lock } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export default function PoliciesPage() {
  return (
    <div>
      <PageHeader title="策略管理" description="OPA 策略配置与测试" />
      <EmptyState icon={Lock} title="策略管理（P1）" description="该模块将在第二阶段实现。" />
    </div>
  );
}
