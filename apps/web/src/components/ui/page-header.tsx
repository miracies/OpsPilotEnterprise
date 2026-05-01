import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn("flex items-center justify-between mb-6", className)}>
      <div className="min-w-0">
        <h1 className="text-lg font-semibold text-slate-900 leading-none">{title}</h1>
        {description && (
          <p className="mt-1.5 text-sm text-slate-500">{description}</p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 shrink-0 ml-4">{actions}</div>
      )}
    </div>
  );
}
