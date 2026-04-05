"use client";

import { Archive } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export default function CasesPage() {
  return (
    <div>
      <PageHeader title="案例归档中心" description="故障案例归档与复盘" />
      <EmptyState icon={Archive} title="案例归档中心（P1）" description="该模块将在第二阶段实现。" />
    </div>
  );
}
