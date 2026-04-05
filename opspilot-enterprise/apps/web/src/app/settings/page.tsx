"use client";

import { Settings } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export default function SettingsPage() {
  return (
    <div>
      <PageHeader title="系统配置" description="平台连接与参数配置" />
      <EmptyState icon={Settings} title="系统配置（P1）" description="该模块将在第二阶段实现。" />
    </div>
  );
}
