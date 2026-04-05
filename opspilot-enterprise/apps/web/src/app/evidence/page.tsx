"use client";

import { FileSearch } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export default function EvidencePage() {
  return (
    <div>
      <PageHeader title="证据中心" description="证据存储、分类与交叉引用" />
      <EmptyState icon={FileSearch} title="证据中心（P1）" description="该模块将在第二阶段实现。" />
    </div>
  );
}
