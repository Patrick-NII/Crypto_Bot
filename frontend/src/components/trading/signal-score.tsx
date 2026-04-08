"use client";

import { cn } from "@/lib/utils";

// ── Color helpers ──

function scoreColor(score: number): string {
  if (score >= 90) return "#16a34a";
  if (score >= 75) return "#22c55e";
  if (score >= 65) return "#eab308";
  if (score >= 50) return "#f59e0b";
  if (score >= 35) return "#ef4444";
  if (score >= 20) return "#dc2626";
  return "#991b1b";
}

function scoreBg(score: number): string {
  if (score >= 90) return "rgba(22,163,74,0.14)";
  if (score >= 75) return "rgba(34,197,94,0.12)";
  if (score >= 65) return "rgba(234,179,8,0.12)";
  if (score >= 50) return "rgba(245,158,11,0.12)";
  if (score >= 35) return "rgba(239,68,68,0.10)";
  if (score >= 20) return "rgba(220,38,38,0.12)";
  return "rgba(153,27,27,0.14)";
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
        <span className="text-[14px] font-bold font-mono tabular-nums leading-none" style={{ color }}>{score}</span>
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
  HIGH_CONVICTION: { label: "Valide", color: "#22c55e", bg: "rgba(34,197,94,0.15)" },
  ACTIONABLE: { label: "Actionnable", color: "#4ade80", bg: "rgba(74,222,128,0.10)" },
  WATCH: { label: "Sous surveillance", color: "#f59e0b", bg: "rgba(245,158,11,0.10)" },
  IGNORE: { label: "Filtre", color: "#8888a0", bg: "rgba(136,136,160,0.06)" },
};

function ActionabilityBadge({ status }: { status: string }) {
  const config = ACTIONABILITY_CONFIG[status] ?? ACTIONABILITY_CONFIG.IGNORE;
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-[12px] font-bold uppercase tracking-wider"
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
      <span className="text-[12px] text-[var(--text-muted)] uppercase tracking-tight">{label}</span>
      <span className="text-[13px] font-bold font-mono tabular-nums" style={{ color }}>{value}</span>
    </div>
  );
}

// ── Category icon ──

const CAT_ICONS: Record<string, string> = { momentum: "M", trend: "T", volume: "Vo", volatility: "V", structure: "S" };

// ── Signal Readout Panel ──

interface SignalReadoutProps {
  className?: string;
  direction: number;
  directionLabel: string;
  confidence: number;
  reliability?: number;
  risk: number;
  setupQuality: number;
  regimeFit?: number;
  confirmationScore?: number;
  executionRisk?: number;
  published?: boolean;
  actionability: string;
  action: string;
  marketRegime: string;
  signalContext: string;
  horizon?: string;
  setupType?: string;
  expectedHoldingWindow?: string;
  subScores: Array<{ category: string; score: number; label: string }>;
  keyReasons: string[];
  notTradeReasons?: string[];
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
  className,
  direction, directionLabel, confidence, reliability = 50, risk, setupQuality,
  executionRisk = risk, published = true,
  actionability, marketRegime, signalContext,
  horizon, setupType, expectedHoldingWindow,
  subScores, keyReasons, notTradeReasons = [], contradictions, tradePlan,
}: SignalReadoutProps) {
  const dirColor = scoreColor(direction);
  const blockers = [
    ...notTradeReasons.slice(0, 2),
    ...(contradictions ?? []).filter((item) => item.severity === "strong").map((item) => item.description),
  ].slice(0, 3);

  return (
    <div className={cn("flex min-h-0 flex-col overflow-hidden rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] text-[var(--foreground)]", className)}>
      {/* Row 1: Direction + dimensions + actionability */}
      <div className="shrink-0 border-b border-white/[0.04] px-4 py-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
            <span className="text-[24px] font-bold font-mono tabular-nums leading-none" style={{ color: dirColor }}>
              {direction}
            </span>
            <div className="leading-tight">
              <span className="text-[14px] font-semibold" style={{ color: dirColor }}>{directionLabel}</span>
            <div className="flex items-center gap-1.5 mt-px">
                <span className="text-[11px] text-[var(--text-muted)] uppercase tracking-wider">{marketRegime}</span>
                {signalContext !== "mixed" && (
                  <span className="text-[11px] text-[var(--text-muted)]">{signalContext.replace(/_/g, " ")}</span>
                )}
                {horizon ? <span className="text-[11px] text-[var(--text-muted)]">{horizon}</span> : null}
                {setupType ? <span className="text-[11px] text-[var(--text-muted)]">{setupType}</span> : null}
              </div>
            </div>
          </div>
        <div className="flex items-center gap-3">
          <Dim label="Indice" value={confidence} />
          <Dim label="Fiab" value={reliability} />
          <Dim label={published ? "Risque" : "Exec"} value={published ? risk : executionRisk} />
          <Dim label="Setup" value={setupQuality} />
          <ActionabilityBadge status={actionability} />
        </div>
        </div>
      </div>

      <div className="shrink-0 border-b border-white/[0.04] px-4 py-2">
        <div className="grid gap-2 md:grid-cols-4">
          <div className="rounded-lg px-2.5 py-2" style={{ background: "rgba(255,255,255,0.02)" }}>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">Contexte</p>
            <p className="mt-1 text-[13px] text-[var(--text-secondary)]">{marketRegime.toLowerCase().replace(/_/g, " ")}</p>
          </div>
          <div className="rounded-lg px-2.5 py-2" style={{ background: "rgba(255,255,255,0.02)" }}>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">Trigger</p>
            <p className="mt-1 text-[13px] text-[var(--text-secondary)]">{setupType ?? "Contexte mixte"}</p>
          </div>
          <div className="rounded-lg px-2.5 py-2" style={{ background: "rgba(255,255,255,0.02)" }}>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">Risque d&apos;execution</p>
            <p className="mt-1 text-[13px] text-[var(--text-secondary)]">{executionRisk}/100</p>
          </div>
          <div className="rounded-lg px-2.5 py-2" style={{ background: "rgba(255,255,255,0.02)" }}>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">Fenetre</p>
            <p className="mt-1 text-[13px] text-[var(--text-secondary)]">{expectedHoldingWindow ?? "Scalp court terme"}</p>
          </div>
        </div>
      </div>

      {/* Row 2: Sub-scores + Why/Why not + Trade plan */}
      <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto px-4 py-3">
        <div className="grid gap-3 md:grid-cols-[1.1fr_1fr_auto]">
        <div>
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Pourquoi cette opportunite</p>
          <div className="flex flex-wrap gap-x-3 gap-y-1 mb-2">
          {subScores.map((ss) => {
            const c = scoreColor(ss.score);
            return (
              <div key={ss.category} className="flex items-center gap-1">
                <span className="text-[11px] font-bold rounded px-1 py-px" style={{ background: `${c}18`, color: c }}>
                  {CAT_ICONS[ss.category] ?? "?"}
                </span>
                <span className="text-[12px] text-[var(--text-muted)]">{ss.label}</span>
              </div>
            );
          })}
          </div>
          {keyReasons.slice(0, 3).map((r, i) => (
            <p key={i} className="text-[12px] text-[var(--text-secondary)] leading-relaxed">
              <span className="text-[var(--text-muted)]">-</span> {r}
            </p>
          ))}
        </div>

        <div className="min-w-[200px]">
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Pourquoi pas</p>
          {blockers.length > 0 ? blockers.map((reason) => (
            <p key={reason} className="text-[12px] text-[#f59e0b] leading-relaxed">
              ! {reason}
            </p>
          )) : (
            <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed">
              - Aucun blocage majeur remonte dans le contexte actuel.
            </p>
          )}
        </div>

        {tradePlan && tradePlan.side !== "none" && (
          <div className="min-w-[160px] rounded-lg px-2.5 py-1.5 text-[12px]" style={{ background: "rgba(255,255,255,0.02)" }}>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-0.5">Plan {tradePlan.side}</p>
            <p className="text-[var(--text-secondary)]">Entree: {tradePlan.entry_zone}</p>
            <p className="text-[var(--text-secondary)]">Stop: {tradePlan.invalidation_zone}</p>
            <p className="text-[var(--text-secondary)]">Cible: {tradePlan.target_zone}</p>
            <p className="text-[var(--text-secondary)]">RR: {tradePlan.risk_reward} | {tradePlan.validity}</p>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
