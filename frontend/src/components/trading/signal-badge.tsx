"use client";

import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus, Plus, AlertTriangle, Zap, ShieldCheck } from "lucide-react";

export type SignalAction =
  | "STRONG_BUY"
  | "BUY"
  | "ACCUMULATE"
  | "HOLD"
  | "REDUCE"
  | "SELL"
  | "STRONG_SELL";

interface SignalBadgeProps {
  action: SignalAction;
  confidence: number;
  size?: "sm" | "md" | "lg";
  blink?: boolean;
  showConfidence?: boolean;
}

const ACTION_CONFIG: Record<
  SignalAction,
  { label: string; color: string; bgColor: string; glowColor: string; icon: typeof TrendingUp }
> = {
  STRONG_BUY: {
    label: "Achat Fort",
    color: "text-[#22c55e]",
    bgColor: "bg-[#22c55e]/15",
    glowColor: "shadow-[0_0_12px_rgba(34,197,94,0.5)]",
    icon: Zap,
  },
  BUY: {
    label: "Acheter",
    color: "text-[#22c55e]",
    bgColor: "bg-[#22c55e]/12",
    glowColor: "shadow-[0_0_8px_rgba(34,197,94,0.3)]",
    icon: TrendingUp,
  },
  ACCUMULATE: {
    label: "Renforcer",
    color: "text-[#f59e0b]",
    bgColor: "bg-[#f59e0b]/12",
    glowColor: "shadow-[0_0_8px_rgba(245,158,11,0.3)]",
    icon: Plus,
  },
  HOLD: {
    label: "Conserver",
    color: "text-[var(--text-secondary)]",
    bgColor: "bg-[var(--glass-bg)]",
    glowColor: "",
    icon: ShieldCheck,
  },
  REDUCE: {
    label: "Alléger",
    color: "text-[#f59e0b]",
    bgColor: "bg-[#f59e0b]/12",
    glowColor: "shadow-[0_0_8px_rgba(245,158,11,0.3)]",
    icon: Minus,
  },
  SELL: {
    label: "Vendre",
    color: "text-[#ef4444]",
    bgColor: "bg-[#ef4444]/12",
    glowColor: "shadow-[0_0_8px_rgba(239,68,68,0.3)]",
    icon: TrendingDown,
  },
  STRONG_SELL: {
    label: "Liquider",
    color: "text-[#ef4444]",
    bgColor: "bg-[#ef4444]/15",
    glowColor: "shadow-[0_0_12px_rgba(239,68,68,0.5)]",
    icon: AlertTriangle,
  },
};

const SIZE_STYLES = {
  sm: "px-2 py-0.5 text-[10px] gap-1",
  md: "px-3 py-1 text-[12px] gap-1.5",
  lg: "px-4 py-2 text-[14px] gap-2",
};

const ICON_SIZES = { sm: "h-3 w-3", md: "h-3.5 w-3.5", lg: "h-4.5 w-4.5" };

export function SignalBadge({ action, confidence, size = "md", blink = true, showConfidence = true }: SignalBadgeProps) {
  const config = ACTION_CONFIG[action] ?? ACTION_CONFIG.HOLD;
  const Icon = config.icon;
  const shouldBlink = blink && (action === "STRONG_BUY" || action === "BUY" || action === "STRONG_SELL" || action === "SELL");

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full font-semibold border transition-all",
        config.bgColor,
        config.color,
        config.glowColor,
        SIZE_STYLES[size],
        shouldBlink && "animate-pulse",
        "border-current/20",
      )}
    >
      <Icon className={ICON_SIZES[size]} />
      <span>{config.label}</span>
      {showConfidence && confidence > 0 && (
        <span className="opacity-70">{Math.round(confidence * 100)}%</span>
      )}
    </div>
  );
}

interface IndicatorBarProps {
  name: string;
  value: number;
  signal: number; // -1 to +1
  description: string;
}

export function IndicatorBar({ name, signal, description }: IndicatorBarProps) {
  const pct = ((signal + 1) / 2) * 100; // 0% = strong sell, 100% = strong buy
  const color = signal > 0.2 ? "#22c55e" : signal < -0.2 ? "#ef4444" : "var(--text-muted)";

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium text-[var(--foreground)]">{name}</span>
        <span className="text-[10px]" style={{ color }}>{signal > 0 ? "+" : ""}{(signal * 100).toFixed(0)}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full" style={{ background: "var(--glass-border)" }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <p className="text-[9px] text-[var(--text-muted)]">{description}</p>
    </div>
  );
}
