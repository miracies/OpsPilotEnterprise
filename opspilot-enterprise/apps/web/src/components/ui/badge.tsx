"use client";

import { cn } from "@/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";

const badgeVariants = cva(
  "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
  {
    variants: {
      variant: {
        default: "bg-blue-50 text-blue-700 ring-blue-600/20",
        success: "bg-green-50 text-green-700 ring-green-600/20",
        warning: "bg-amber-50 text-amber-700 ring-amber-600/20",
        danger: "bg-red-50 text-red-700 ring-red-600/20",
        neutral: "bg-gray-50 text-gray-700 ring-gray-600/20",
        info: "bg-cyan-50 text-cyan-700 ring-cyan-600/20",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, BadgeProps["variant"]> = {
    critical: "danger",
    high: "danger",
    medium: "warning",
    low: "info",
    info: "neutral",
  };
  return <Badge variant={map[severity] ?? "neutral"}>{severity}</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, BadgeProps["variant"]> = {
    new: "info",
    analyzing: "default",
    pending_action: "warning",
    resolved: "success",
    archived: "neutral",
    pending: "warning",
    approved: "success",
    rejected: "danger",
  };
  return <Badge variant={map[status] ?? "neutral"}>{status}</Badge>;
}

export function RiskBadge({ level }: { level: string }) {
  const map: Record<string, BadgeProps["variant"]> = {
    critical: "danger",
    high: "danger",
    medium: "warning",
    low: "success",
  };
  return <Badge variant={map[level] ?? "neutral"}>风险: {level}</Badge>;
}
