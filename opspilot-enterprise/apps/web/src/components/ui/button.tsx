import { cn } from "@/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-1.5 rounded-lg text-sm font-medium",
    "transition-all duration-150 select-none",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1",
    "disabled:pointer-events-none disabled:opacity-50",
  ].join(" "),
  {
    variants: {
      variant: {
        primary:
          "bg-blue-600 text-white shadow-sm hover:bg-blue-700 active:bg-blue-800",
        secondary:
          "bg-white text-slate-700 border border-slate-300 shadow-sm hover:bg-slate-50 active:bg-slate-100",
        danger:
          "bg-red-600 text-white shadow-sm hover:bg-red-700 active:bg-red-800",
        ghost:
          "text-slate-600 hover:bg-slate-100 hover:text-slate-900 active:bg-slate-200",
        link:
          "text-blue-600 underline-offset-4 hover:underline p-0 h-auto",
      },
      size: {
        xs: "h-7  px-2.5 text-xs",
        sm: "h-8  px-3   text-xs",
        md: "h-9  px-4",
        lg: "h-10 px-5",
        icon: "h-8 w-8 p-0",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}
