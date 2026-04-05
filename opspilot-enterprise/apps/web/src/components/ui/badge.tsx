"use client";

import { cn } from "@/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset select-none",
  {
    variants: {
      variant: {
        default:  "bg-blue-50   text-blue-700   ring-blue-600/20",
        success:  "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
        warning:  "bg-amber-50  text-amber-700   ring-amber-600/20",
        danger:   "bg-red-50    text-red-700     ring-red-600/20",
        neutral:  "bg-slate-100 text-slate-600   ring-slate-600/15",
        info:     "bg-sky-50    text-sky-700     ring-sky-600/20",
        orange:   "bg-orange-50 text-orange-700  ring-orange-600/20",
        purple:   "bg-violet-50 text-violet-700  ring-violet-600/20",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  dot?: boolean;
}

export function Badge({ className, variant, dot, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props}>
      {dot && (
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full shrink-0",
            variant === "success" ? "bg-emerald-500" :
            variant === "warning" ? "bg-amber-500" :
            variant === "danger"  ? "bg-red-500" :
            variant === "info"    ? "bg-sky-500" :
            variant === "orange"  ? "bg-orange-500" :
            variant === "purple"  ? "bg-violet-500" :
            "bg-blue-500"
          )}
        />
      )}
      {children}
    </span>
  );
}

const SEVERITY_LABEL: Record<string, string> = {
  critical: "严重",
  high:     "高",
  medium:   "中",
  low:      "低",
  info:     "信息",
};

const SEVERITY_VARIANT: Record<string, BadgeProps["variant"]> = {
  critical: "danger",
  high:     "orange",
  medium:   "warning",
  low:      "success",
  info:     "neutral",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <Badge variant={SEVERITY_VARIANT[severity] ?? "neutral"} dot>
      {SEVERITY_LABEL[severity] ?? severity}
    </Badge>
  );
}

const STATUS_LABEL: Record<string, string> = {
  new:            "新建",
  analyzing:      "分析中",
  pending_action: "待处理",
  resolved:       "已解决",
  archived:       "已归档",
  pending:        "待审批",
  approved:       "已通过",
  rejected:       "已驳回",
};

const STATUS_VARIANT: Record<string, BadgeProps["variant"]> = {
  new:            "info",
  analyzing:      "default",
  pending_action: "warning",
  resolved:       "success",
  archived:       "neutral",
  pending:        "warning",
  approved:       "success",
  rejected:       "danger",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={STATUS_VARIANT[status] ?? "neutral"} dot>
      {STATUS_LABEL[status] ?? status}
    </Badge>
  );
}

const RISK_LABEL: Record<string, string> = {
  critical: "极高风险",
  high:     "高风险",
  medium:   "中风险",
  low:      "低风险",
};

const RISK_VARIANT: Record<string, BadgeProps["variant"]> = {
  critical: "danger",
  high:     "orange",
  medium:   "warning",
  low:      "success",
};

export function RiskBadge({ level }: { level: string }) {
  return (
    <Badge variant={RISK_VARIANT[level] ?? "neutral"} dot>
      {RISK_LABEL[level] ?? level}
    </Badge>
  );
}
