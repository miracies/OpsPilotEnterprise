"use client";

import { BookOpen } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export default function KnowledgePage() {
  return (
    <div>
      <PageHeader title="知识管理" description="运维知识文档与 KB 管理" />
      <EmptyState icon={BookOpen} title="知识管理（P1）" description="该模块将在第二阶段实现。" />
    </div>
  );
}
