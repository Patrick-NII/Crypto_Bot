"use client";

import { cn } from "@/lib/utils";

interface LoadingProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

const sizeMap = { sm: "h-6 w-6", md: "h-10 w-10", lg: "h-16 w-16" };

export function Loading({ size = "md", className, label }: LoadingProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3", className)} role="status">
      <div className={cn("relative", sizeMap[size])}>
        <div className={cn("absolute inset-0 rounded-full border-2 border-[var(--glass-border)]", sizeMap[size])} />
        <div className={cn("absolute inset-0 animate-spin-slow rounded-full border-2 border-transparent border-t-[var(--page-accent)]", sizeMap[size])} />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="h-1.5 w-1.5 rounded-full animate-pulse-glow" style={{ background: "var(--page-accent)" }} />
        </div>
      </div>
      {label && <p className="text-sm text-[var(--text-secondary)] font-medium">{label}</p>}
      <span className="sr-only">{label ?? "Loading..."}</span>
    </div>
  );
}
