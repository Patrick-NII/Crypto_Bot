import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}

export function GlassCard({ children, className, hover = true }: GlassCardProps) {
  return (
    <div className={cn(hover ? "liquid-glass-card" : "liquid-glass", "p-6", className)}>
      {children}
    </div>
  );
}
