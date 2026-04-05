import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: string;
  trendDir?: "up" | "down" | "flat";
  trendColor?: "positive" | "negative" | "neutral";
  className?: string;
  accent?: "blue" | "red" | "amber" | "green" | "purple" | "orange";
}

const accentMap = {
  blue:   { icon: "bg-blue-50 text-blue-600",   bar: "bg-blue-600" },
  red:    { icon: "bg-red-50 text-red-600",     bar: "bg-red-500" },
  amber:  { icon: "bg-amber-50 text-amber-600", bar: "bg-amber-500" },
  green:  { icon: "bg-emerald-50 text-emerald-600", bar: "bg-emerald-500" },
  purple: { icon: "bg-violet-50 text-violet-600", bar: "bg-violet-500" },
  orange: { icon: "bg-orange-50 text-orange-600", bar: "bg-orange-500" },
};

export function MetricCard({
  title,
  value,
  icon: Icon,
  trend,
  trendDir,
  trendColor = "neutral",
  className,
  accent = "blue",
}: MetricCardProps) {
  const colors = accentMap[accent];
  const TrendIcon = trendDir === "up" ? TrendingUp : trendDir === "down" ? TrendingDown : Minus;

  return (
    <div
      className={cn(
        "rounded-xl border border-slate-200 bg-white px-4 py-4",
        "shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]",
        "hover:shadow-[0_4px_12px_0_rgb(0_0_0/0.09)] transition-shadow duration-200",
        className
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <p className="text-xs font-medium text-slate-500">{title}</p>
        <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", colors.icon)}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <p className="text-2xl font-bold text-slate-900 leading-none">{value}</p>
      {trend && (
        <div className={cn(
          "flex items-center gap-1 mt-2 text-xs",
          trendColor === "positive" ? "text-emerald-600" :
          trendColor === "negative" ? "text-red-500" :
          "text-slate-400"
        )}>
          {trendDir && <TrendIcon className="h-3 w-3" />}
          <span>{trend}</span>
        </div>
      )}
    </div>
  );
}
