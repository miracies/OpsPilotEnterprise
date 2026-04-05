"use client";

import { ArrowUpCircle } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export default function UpgradePage() {
  return (
    <div>
      <PageHeader title="升级管理" description="平台与组件版本升级" />
      <EmptyState icon={ArrowUpCircle} title="升级管理（P1）" description="该模块将在第二阶段实现。" />
    </div>
  );
}
