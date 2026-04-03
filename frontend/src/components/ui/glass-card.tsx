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
        "glass-card p-6 bg-[rgba(20,20,27,0.8)] border border-[rgba(255,255,255,0.06)] rounded-[12px] backdrop-blur-[12px]",
        hover && "transition-all duration-200 ease-out hover:-translate-y-0.5 hover:border-[rgba(6,214,160,0.3)]",
        className,
      )}
    >
      {children}
    </div>
  );
}
