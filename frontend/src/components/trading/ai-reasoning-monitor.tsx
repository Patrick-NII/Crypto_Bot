"use client";

import { useEffect, useRef, useState } from "react";
import {
  Brain,
  ChevronDown,
  ChevronUp,
  Eye,
  Loader2,
  MessageSquare,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { AutoTradingHistorySnapshot } from "./auto-trading-monitor";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ReasoningStep {
  id: string;
  timestamp: string;
  phase: "observe" | "think" | "decide" | "execute" | "reflect";
  title: string;
  content: string;
  symbol?: string;
  confidence?: number;
}

export interface MonitorEntry {
  cycle_id: string;
  timestamp: string;
  model: string;
  steps: ReasoningStep[];
  summary: string;
  trades_count: number;
  regime?: string;
}

/* ------------------------------------------------------------------ */
/*  Transform backend history into monitor entries                     */
/* ------------------------------------------------------------------ */

export function transformHistoryToMonitorEntries(
  history: AutoTradingHistorySnapshot[],
): MonitorEntry[] {
  return history.map((entry, idx) => {
    const ts = entry.timestamp;
    const prefix = `cycle-${idx}`;
    const candidates = entry.candidates ?? [];
    const trades = entry.trades ?? [];
    const scanned = entry.signals_scanned ?? candidates.length;
    const model = entry.model ?? entry.provider ?? "AI";
    const regime = entry.regime ?? "unknown";

    const steps: ReasoningStep[] = [];

    // 1. OBSERVE
    const candidateList =
      candidates.length > 0
        ? candidates
            .slice(0, 5)
            .map(
              (c) =>
                `${c.symbol} ${c.action} (${Math.round(c.confidence * 100)}%${c.price ? ` @ $${c.price.toLocaleString()}` : ""})`,
            )
            .join(" | ")
        : "Aucun candidat qualifiant";
    steps.push({
      id: `${prefix}-observe`,
      timestamp: ts,
      phase: "observe",
      title: `${scanned} signaux scann\u00e9s`,
      content: candidateList,
      confidence: candidates.length > 0 ? candidates[0].confidence : undefined,
    });

    // 2. THINK
    steps.push({
      id: `${prefix}-think`,
      timestamp: ts,
      phase: "think",
      title: `R\u00e9gime de march\u00e9 : ${regime}`,
      content: entry.analysis || "Pas d\u2019analyse disponible pour ce cycle.",
    });

    // 3. DECIDE
    const reco = entry.recommendations ?? trades.length;
    const selected = trades.length;
    steps.push({
      id: `${prefix}-decide`,
      timestamp: ts,
      phase: "decide",
      title: `${reco} recommandation${reco > 1 ? "s" : ""} \u00e9valu\u00e9e${reco > 1 ? "s" : ""}, ${selected} s\u00e9lectionn\u00e9e${selected > 1 ? "s" : ""}`,
      content:
        trades.length > 0
          ? trades
              .map(
                (t) =>
                  `${t.symbol} ${t.action.toUpperCase()} $${t.amount_usd.toFixed(0)}${t.confidence ? ` (${Math.round(t.confidence * 100)}%)` : ""}${t.strategy ? ` [${t.strategy}]` : ""}`,
              )
              .join(" | ")
          : "Aucun trade retenu pour ce cycle.",
    });

    // 4. EXECUTE (only if trades happened)
    if (trades.length > 0) {
      const totalUsd = trades.reduce((s, t) => s + (t.amount_usd ?? 0), 0);
      steps.push({
        id: `${prefix}-execute`,
        timestamp: ts,
        phase: "execute",
        title: `${entry.executed} trade${entry.executed > 1 ? "s" : ""} ex\u00e9cut\u00e9${entry.executed > 1 ? "s" : ""} \u2014 $${totalUsd.toFixed(0)}`,
        content: trades
          .map(
            (t) =>
              `${t.symbol}: ${t.reason ?? t.action}${t.price ? ` @ $${t.price.toLocaleString()}` : ""}`,
          )
          .join(" | "),
      });
    }

    // 5. REFLECT
    steps.push({
      id: `${prefix}-reflect`,
      timestamp: ts,
      phase: "reflect",
      title: `Cycle termin\u00e9 \u2014 r\u00e9gime ${regime}`,
      content:
        trades.length > 0
          ? `${trades.length} op\u00e9ration${trades.length > 1 ? "s" : ""} plac\u00e9e${trades.length > 1 ? "s" : ""}. Prochain scan dans ~5 min.`
          : "Aucune op\u00e9ration. March\u00e9 en observation. Prochain scan dans ~5 min.",
    });

    return {
      cycle_id: `${prefix}-${ts}`,
      timestamp: ts,
      model,
      steps,
      summary: entry.analysis || "Cycle sans analyse.",
      trades_count: entry.executed,
      regime,
    };
  });
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const PHASE_META: Record<
  ReasoningStep["phase"],
  { label: string; icon: typeof Brain; color: string; bg: string }
> = {
  observe: { label: "Observe", icon: Eye, color: "text-blue-400", bg: "bg-blue-400/10" },
  think: { label: "Think", icon: Brain, color: "text-purple-400", bg: "bg-purple-400/10" },
  decide: { label: "Decide", icon: Zap, color: "text-amber-400", bg: "bg-amber-400/10" },
  execute: { label: "Execute", icon: Sparkles, color: "text-emerald-400", bg: "bg-emerald-400/10" },
  reflect: { label: "Reflect", icon: MessageSquare, color: "text-cyan-400", bg: "bg-cyan-400/10" },
};

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "--:--:--";
  }
}

/* ------------------------------------------------------------------ */
/*  Step row                                                           */
/* ------------------------------------------------------------------ */

function StepRow({ step }: { step: ReasoningStep }) {
  const meta = PHASE_META[step.phase] ?? PHASE_META.think;
  const Icon = meta.icon;

  return (
    <div className="flex gap-2.5 py-1.5">
      {/* icon */}
      <div className={cn("flex h-5 w-5 shrink-0 items-center justify-center rounded-md mt-0.5", meta.bg)}>
        <Icon className={cn("h-3 w-3", meta.color)} />
      </div>

      {/* content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={cn("text-[10px] font-bold uppercase tracking-widest", meta.color)}>
            {meta.label}
          </span>
          {step.symbol && (
            <span className="text-[10px] font-semibold text-[var(--foreground)] bg-[var(--glass-bg)] px-1 py-0.5 rounded">
              {step.symbol}
            </span>
          )}
          {step.confidence != null && (
            <span className="text-[10px] text-[var(--text-muted)]">
              {Math.round(step.confidence * 100)}%
            </span>
          )}
        </div>
        <p className="text-[11px] font-medium text-[var(--foreground)]">{step.title}</p>
        <p className="text-[11px] leading-relaxed text-[var(--text-secondary)] line-clamp-2">{step.content}</p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Cycle block                                                        */
/* ------------------------------------------------------------------ */

function CycleBlock({ entry }: { entry: MonitorEntry }) {
  const [expanded, setExpanded] = useState(false);
  const visibleSteps = expanded ? entry.steps : entry.steps.slice(0, 3);

  return (
    <div className="border-b border-white/[0.04] last:border-0 py-2.5">
      {/* header */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between gap-2 mb-1 group"
      >
        <div className="flex items-center gap-2 min-w-0">
          <Brain className="h-3 w-3 text-[var(--accent)] shrink-0" />
          <span className="text-[11px] font-semibold text-[var(--foreground)]">
            {formatTime(entry.timestamp)}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">{entry.model}</span>
          {entry.regime && entry.regime !== "unknown" && (
            <span className={cn(
              "text-[9px] font-bold uppercase px-1.5 py-0.5 rounded",
              entry.regime.includes("bull") || entry.regime.includes("risk-on")
                ? "bg-emerald-500/10 text-emerald-400"
                : entry.regime.includes("bear") || entry.regime.includes("risk-off")
                  ? "bg-red-500/10 text-red-400"
                  : "bg-amber-500/10 text-amber-400",
            )}>
              {entry.regime}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {entry.trades_count > 0 && (
            <span className="text-[10px] font-semibold text-[var(--success)]">
              {entry.trades_count} trade{entry.trades_count > 1 ? "s" : ""}
            </span>
          )}
          {expanded ? (
            <ChevronUp className="h-3 w-3 text-[var(--text-muted)]" />
          ) : (
            <ChevronDown className="h-3 w-3 text-[var(--text-muted)]" />
          )}
        </div>
      </button>

      {/* steps */}
      <div className="pl-5 space-y-0.5">
        {visibleSteps.map((step) => (
          <StepRow key={step.id} step={step} />
        ))}
        {!expanded && entry.steps.length > 3 && (
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="text-[10px] text-[var(--accent)] hover:underline py-1"
          >
            +{entry.steps.length - 3} \u00e9tapes
          </button>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component — 4 states                                          */
/* ------------------------------------------------------------------ */

interface AIReasoningMonitorProps {
  entries: MonitorEntry[];
  loading?: boolean;
  tradingMode: "manual" | "auto";
  armed?: boolean;
}

export function AIReasoningMonitor({
  entries,
  loading = false,
  tradingMode,
  armed = false,
}: AIReasoningMonitorProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries, autoScroll]);

  function handleScroll() {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  }

  /* ---- STATE A: Manual mode — compact bar ---- */
  if (tradingMode === "manual") {
    return (
      <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-4 py-3 flex items-center justify-between opacity-60">
        <div className="flex items-center gap-2.5">
          <Brain className="h-4 w-4 text-[var(--text-muted)]" />
          <span className="text-[12px] font-semibold text-[var(--text-muted)]">AI Reasoning Monitor</span>
        </div>
        <span className="rounded-full bg-white/[0.04] px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
          Off
        </span>
      </div>
    );
  }

  /* ---- STATE B: Auto mode, disarmed ---- */
  if (!armed) {
    return (
      <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-bg)] p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4 text-[var(--text-muted)]" />
            <h3 className="text-sm font-semibold text-[var(--foreground)]">AI Reasoning Monitor</h3>
          </div>
          <span className="rounded-full bg-white/[0.04] px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
            Standby
          </span>
        </div>
        <div className="py-6 text-center">
          <ShieldCheck className="h-7 w-7 mx-auto mb-2 text-[var(--text-muted)] opacity-25" />
          <p className="text-[12px] text-[var(--text-muted)]">
            Armez l&apos;autopilote pour d&eacute;marrer le monitoring AI.
          </p>
          <p className="text-[11px] text-[var(--text-muted)] mt-1 opacity-60">
            Observe &rarr; Think &rarr; Decide &rarr; Execute &rarr; Reflect
          </p>
        </div>
      </div>
    );
  }

  /* ---- STATE C & D: Auto + armed (empty or with data) ---- */
  return (
    <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-bg)] p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--accent)]/15 shadow-[0_0_10px_var(--accent-glow)]">
            <Brain className="h-3.5 w-3.5 text-[var(--accent)] animate-pulse" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[var(--foreground)]">AI Reasoning Monitor</h3>
            <p className="text-[10px] text-[var(--text-muted)]">
              Suivi en direct de la r&eacute;flexion du mod&egrave;le
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {entries.length > 0 && (
            <span className="text-[10px] text-[var(--text-muted)]">
              {entries.length} cycle{entries.length > 1 ? "s" : ""}
            </span>
          )}
          <span className="rounded-full bg-[var(--accent)]/12 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[var(--accent)] flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
            Live
          </span>
        </div>
      </div>

      {/* Body */}
      {entries.length === 0 && !loading ? (
        /* STATE C: waiting */
        <div className="py-6 text-center">
          <Loader2 className="h-5 w-5 mx-auto mb-2 text-[var(--accent)] animate-spin opacity-40" />
          <p className="text-[12px] text-[var(--text-muted)]">En attente du prochain cycle AI...</p>
          <p className="text-[10px] text-[var(--text-muted)] mt-1 opacity-50">
            Les cycles s&apos;ex&eacute;cutent toutes les ~5 minutes
          </p>
        </div>
      ) : (
        /* STATE D: active with data */
        <>
          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="max-h-[380px] overflow-y-auto custom-scrollbar pr-1"
          >
            {entries.map((entry) => (
              <CycleBlock key={entry.cycle_id} entry={entry} />
            ))}
          </div>

          {/* Footer */}
          <div className="mt-2 pt-2 border-t border-white/[0.04] flex items-center justify-between text-[10px] text-[var(--text-muted)]">
            <span>
              {entries.reduce((s, e) => s + e.trades_count, 0)} trade{entries.reduce((s, e) => s + e.trades_count, 0) > 1 ? "s" : ""} total
            </span>
            <span>
              {entries.length} cycle{entries.length > 1 ? "s" : ""} enregistr&eacute;{entries.length > 1 ? "s" : ""}
            </span>
            {autoScroll ? (
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
                Auto-scroll
              </span>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setAutoScroll(true);
                  if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
                }}
                className="text-[var(--accent)] hover:underline"
              >
                Aller en bas
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
