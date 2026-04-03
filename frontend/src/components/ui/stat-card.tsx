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
    <GlassCard className={cn("flex flex-col gap-2 bg-[#14141b] border-[rgba(255,255,255,0.06)]", className)}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-[#8888a0]">
          {title}
        </span>
        {Icon && (
          <Icon className="h-4 w-4 text-[#06d6a0]" />
        )}
      </div>
      <p className="text-2xl font-bold tracking-tight text-white font-mono">{value}</p>
      {subtitle && (
        <p
          className={cn(
            "text-sm font-medium",
            trend === "up" && "text-[#06d6a0]",
            trend === "down" && "text-danger",
            trend === "neutral" && "text-[#8888a0]",
            !trend && "text-[#8888a0]",
          )}
        >
          {subtitle}
        </p>
      )}
    </GlassCard>
  );
}
