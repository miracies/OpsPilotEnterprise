import { Card, CardContent } from "./card";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: string;
  className?: string;
  accentColor?: string;
}

export function MetricCard({
  title,
  value,
  icon: Icon,
  trend,
  className,
  accentColor = "text-blue-600",
}: MetricCardProps) {
  return (
    <Card className={cn("hover:shadow-md transition-shadow", className)}>
      <CardContent className="flex items-center gap-4">
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gray-50",
            accentColor
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-gray-500 truncate">{title}</p>
          <p className="text-xl font-bold text-gray-900">{value}</p>
          {trend && <p className="text-xs text-gray-400">{trend}</p>}
        </div>
      </CardContent>
    </Card>
  );
}
