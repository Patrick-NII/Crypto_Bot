import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon?: LucideIcon;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function StatCard({ title, value, subtitle, icon: Icon, trend, className }: StatCardProps) {
  return (
    <div className={cn("liquid-glass-card p-5", className)}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">{title}</span>
        {Icon && <Icon className="h-4 w-4 accent-text opacity-60" />}
      </div>
      <p className="text-2xl font-bold font-mono text-[var(--foreground)]">{value}</p>
      {subtitle && (
        <p className={cn(
          "mt-1 text-sm font-medium",
          trend === "up" && "text-[#06d6a0]",
          trend === "down" && "text-[#ef4444]",
          !trend && "text-[var(--text-secondary)]",
        )}>
          {subtitle}
        </p>
      )}
    </div>
  );
}
