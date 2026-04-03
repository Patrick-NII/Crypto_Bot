import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export type BadgeVariant = "default" | "success" | "danger" | "warning" | "info" | "accent" | "purple";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-[var(--glass-bg)] text-[var(--text-secondary)] border-[var(--glass-border)]",
  success: "bg-[#06d6a0]/12 text-[#06d6a0] border-[#06d6a0]/20",
  danger: "bg-[#ef4444]/12 text-[#ef4444] border-[#ef4444]/20",
  warning: "bg-[#f59e0b]/12 text-[#f59e0b] border-[#f59e0b]/20",
  info: "bg-[#3b82f6]/12 text-[#3b82f6] border-[#3b82f6]/20",
  accent: "accent-bg accent-text",
  purple: "bg-[#a855f7]/12 text-[#a855f7] border-[#a855f7]/20",
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
