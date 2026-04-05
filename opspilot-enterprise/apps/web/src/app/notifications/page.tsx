"use client";

import { Bell } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export default function NotificationsPage() {
  return (
    <div>
      <PageHeader title="值班通知中心" description="值班通知与告警升级状态" />
      <EmptyState icon={Bell} title="值班通知中心（P1）" description="该模块将在第二阶段实现。" />
    </div>
  );
}
