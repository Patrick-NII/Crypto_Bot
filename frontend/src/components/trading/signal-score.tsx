"use client";

import { cn } from "@/lib/utils";

// ── Color helpers ──

function scoreColor(score: number): string {
  if (score >= 75) return "#22c55e";
  if (score >= 60) return "#4ade80";
  if (score >= 45) return "#8888a0";
  if (score >= 30) return "#f59e0b";
  return "#ef4444";
}

function scoreBg(score: number): string {
  if (score >= 75) return "rgba(34,197,94,0.12)";
  if (score >= 60) return "rgba(74,222,128,0.08)";
  if (score >= 45) return "rgba(136,136,160,0.06)";
  if (score >= 30) return "rgba(245,158,11,0.08)";
  return "rgba(239,68,68,0.08)";
}

function riskColor(risk: number): string {
  if (risk >= 70) return "#ef4444";
  if (risk >= 50) return "#f59e0b";
  return "#4ade80";
}

// ── Score gauge (compact for scanner list) ──

export function ScoreGauge({ score, size = "sm" }: { score: number; label?: string; size?: "sm" | "md" }) {
  const color = scoreColor(score);
  const pct = Math.max(0, Math.min(100, score));

  if (size === "sm") {
    return (
      <div className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5" style={{ background: scoreBg(score) }}>
        <span className="text-[12px] font-bold font-mono tabular-nums leading-none" style={{ color }}>{score}</span>
        <div className="w-[24px] h-[3px] rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
        </div>
      </div>
    );
  }
  return null;
}

// ── Actionability badge ──

const ACTIONABILITY_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  HIGH_CONVICTION: { label: "Forte conviction", color: "#22c55e", bg: "rgba(34,197,94,0.15)" },
  ACTIONABLE: { label: "Actionnable", color: "#4ade80", bg: "rgba(74,222,128,0.10)" },
  WATCH: { label: "A surveiller", color: "#f59e0b", bg: "rgba(245,158,11,0.10)" },
  IGNORE: { label: "Pas de signal", color: "#8888a0", bg: "rgba(136,136,160,0.06)" },
};

function ActionabilityBadge({ status }: { status: string }) {
  const config = ACTIONABILITY_CONFIG[status] ?? ACTIONABILITY_CONFIG.IGNORE;
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider"
      style={{ color: config.color, background: config.bg }}
    >
      {config.label}
    </span>
  );
}

// ── Dimension pill (inline compact) ──

function Dim({ label, value }: { label: string; value: number }) {
  const color = label === "Risque" ? riskColor(value) : scoreColor(value);
  return (
    <div className="flex items-center gap-1">
      <span className="text-[9px] text-[var(--text-muted)] uppercase tracking-tight">{label}</span>
      <span className="text-[11px] font-bold font-mono tabular-nums" style={{ color }}>{value}</span>
    </div>
  );
}

// ── Category icon ──

const CAT_ICONS: Record<string, string> = { momentum: "M", trend: "T", volume: "Vo", volatility: "V", structure: "S" };

// ── Signal Readout Panel ──

interface SignalReadoutProps {
  direction: number;
  directionLabel: string;
  confidence: number;
  risk: number;
  setupQuality: number;
  actionability: string;
  action: string;
  marketRegime: string;
  signalContext: string;
  subScores: Array<{ category: string; score: number; label: string }>;
  keyReasons: string[];
  contradictions?: Array<{ description: string; severity: string }>;
  tradePlan?: {
    side: string;
    entry_zone: string;
    invalidation_zone: string;
    target_zone: string;
    risk_reward: string;
    validity: string;
    execution_style?: string;
    style?: string;
  } | null;
  // Legacy compat (unused but accepted)
  score100?: number;
  label?: string;
  confidenceLevel?: string;
  mode?: string;
}

export function SignalReadout({
  direction, directionLabel, confidence, risk, setupQuality,
  actionability, marketRegime, signalContext,
  subScores, keyReasons, contradictions, tradePlan,
}: SignalReadoutProps) {
  const dirColor = scoreColor(direction);

  return (
    <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] overflow-hidden text-[var(--foreground)]">
      {/* Row 1: Direction + dimensions + actionability */}
      <div className="px-4 py-2 flex items-center justify-between gap-3 border-b border-white/[0.04]">
        <div className="flex items-center gap-3">
          <span className="text-[22px] font-bold font-mono tabular-nums leading-none" style={{ color: dirColor }}>
            {direction}
          </span>
          <div className="leading-tight">
            <span className="text-[12px] font-semibold" style={{ color: dirColor }}>{directionLabel}</span>
            <div className="flex items-center gap-1.5 mt-px">
              <span className="text-[8px] text-[var(--text-muted)] uppercase tracking-wider">{marketRegime}</span>
              {signalContext !== "mixed" && (
                <span className="text-[8px] text-[var(--text-muted)]">{signalContext.replace(/_/g, " ")}</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Dim label="Conf" value={confidence} />
          <Dim label="Risque" value={risk} />
          <Dim label="Setup" value={setupQuality} />
          <ActionabilityBadge status={actionability} />
        </div>
      </div>

      {/* Row 2: Sub-scores + Reasons + Trade plan */}
      <div className="px-4 py-2 flex flex-wrap gap-x-5 gap-y-1.5">
        {/* Sub-scores compact */}
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {subScores.map((ss) => {
            const c = scoreColor(ss.score);
            return (
              <div key={ss.category} className="flex items-center gap-1">
                <span className="text-[7px] font-bold rounded px-1 py-px" style={{ background: `${c}18`, color: c }}>
                  {CAT_ICONS[ss.category] ?? "?"}
                </span>
                <span className="text-[10px] text-[var(--text-muted)]">{ss.label}</span>
              </div>
            );
          })}
        </div>

        {/* Reasons */}
        <div className="flex-1 min-w-[200px]">
          {keyReasons.slice(0, 3).map((r, i) => (
            <p key={i} className="text-[10px] text-[var(--text-secondary)] leading-relaxed">
              <span className="text-[var(--text-muted)]">-</span> {r}
            </p>
          ))}
          {contradictions?.filter(c => c.severity === "strong").map((c, i) => (
            <p key={`w${i}`} className="text-[10px] text-[#f59e0b] leading-relaxed">! {c.description}</p>
          ))}
        </div>

        {/* Trade plan */}
        {tradePlan && tradePlan.side !== "none" && (
          <div className="min-w-[160px] rounded-lg px-2.5 py-1.5 text-[9px]" style={{ background: "rgba(255,255,255,0.02)" }}>
            <p className="text-[8px] uppercase tracking-wider text-[var(--text-muted)] mb-0.5">Plan {tradePlan.side}</p>
            <p className="text-[var(--text-secondary)]">Entree: {tradePlan.entry_zone}</p>
            <p className="text-[var(--text-secondary)]">Stop: {tradePlan.invalidation_zone}</p>
            <p className="text-[var(--text-secondary)]">Cible: {tradePlan.target_zone}</p>
            <p className="text-[var(--text-secondary)]">RR: {tradePlan.risk_reward} | {tradePlan.validity}</p>
          </div>
        )}
      </div>
    </div>
  );
}
