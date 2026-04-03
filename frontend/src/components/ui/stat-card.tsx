import { cn } from "@/lib/utils";
import { GlassCard } from "./glass-card";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon?: LucideIcon;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  className,
}: StatCardProps) {
  return (
    <GlassCard className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-white/50">
          {title}
        </span>
        {Icon && (
          <Icon className="h-4 w-4 text-accent-purple" />
        )}
      </div>
      <p className="text-2xl font-bold tracking-tight text-white">{value}</p>
      {subtitle && (
        <p
          className={cn(
            "text-sm font-medium",
            trend === "up" && "text-success",
            trend === "down" && "text-danger",
            trend === "neutral" && "text-white/50",
            !trend && "text-white/50",
          )}
        >
          {subtitle}
        </p>
      )}
    </GlassCard>
  );
}
