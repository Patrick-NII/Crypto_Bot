import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type BadgeVariant = "default" | "success" | "danger" | "warning" | "info" | "turquoise" | "lime" | "purple";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-[#1a1a24] text-[#8888a0] border-[rgba(255,255,255,0.06)]",
  success: "bg-[#06d6a0]/15 text-[#06d6a0] border-[#06d6a0]/25",
  danger: "bg-danger/15 text-danger border-danger/25",
  warning: "bg-[#c6f135]/15 text-[#c6f135] border-[#c6f135]/25",
  info: "bg-[#3b82f6]/15 text-[#3b82f6] border-[#3b82f6]/25",
  turquoise: "bg-[#06d6a0]/15 text-[#06d6a0] border-[#06d6a0]/25",
  lime: "bg-[#c6f135]/15 text-[#0d0d12] border-[#c6f135]/25 bg-[#c6f135]/20",
  purple: "bg-[#a855f7]/15 text-[#a855f7] border-[#a855f7]/25",
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
