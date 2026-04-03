import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}

export function GlassCard({ children, className, hover }: GlassCardProps) {
  return (
    <div
      className={cn(
        "glass-card p-6",
        hover && "transition-all duration-200 hover:scale-[1.01] hover:border-white/20",
        className,
      )}
    >
      {children}
    </div>
  );
}
