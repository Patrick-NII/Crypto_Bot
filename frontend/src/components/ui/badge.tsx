import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type BadgeVariant = "default" | "success" | "danger" | "warning" | "info" | "purple";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-white/10 text-white/70 border-white/10",
  success: "bg-success/15 text-success border-success/25",
  danger: "bg-danger/15 text-danger border-danger/25",
  warning: "bg-warning/15 text-warning border-warning/25",
  info: "bg-info/15 text-info border-info/25",
  purple: "bg-accent-purple/15 text-accent-purple border-accent-purple/25",
};

export function Badge({ children, variant = "default", className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        variantStyles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
