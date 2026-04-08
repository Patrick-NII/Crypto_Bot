"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  ChevronDown,
  ChevronRight,
  Clock3,
  Radio,
  X,
} from "lucide-react";
import type { AutoDecision, AutoStatusExtended, TradeGroup } from "@/lib/types";
import { useAutoDecisions } from "@/hooks/use-auto-decisions";
import { useAutoTradeGroups } from "@/hooks/use-auto-trade-groups";
import { EmergencyStopButton } from "./emergency-stop-button";
import { cn } from "@/lib/utils";

interface AutoLogPanelProps {
  status: AutoStatusExtended | null;
  onClose?: () => void;
  onEmergencyStopped?: () => void;
}

type TabKey = "decisions" | "trade_groups";

function formatTimestamp(iso: string | undefined | null): string {
  if (!iso) return "--:--:--";
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

function formatDuration(seconds: number | undefined | null): string {
  if (!seconds || seconds < 0) return "-";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function useCycleCountdown(nextCycleAt: string | null | undefined): string {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  if (!nextCycleAt) return "-";
  const target = new Date(nextCycleAt).getTime();
  if (Number.isNaN(target)) return "-";
  const deltaMs = target - now;
  if (deltaMs <= 0) return "0:00";
  const s = Math.floor(deltaMs / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${(s % 60).toString().padStart(2, "0")}`;
}

function outcomeColor(outcome: string): string {
  if (outcome === "executed") return "bg-[var(--success)]/15 text-[var(--success)]";
  if (outcome === "dry_run") return "bg-[var(--page-accent)]/15 text-[var(--page-accent)]";
  if (outcome.startsWith("rejected")) return "bg-[var(--warning)]/15 text-[var(--warning)]";
  return "bg-[var(--glass-bg)] text-[var(--text-muted)]";
}

function SignalIndicatorsGrid({ signals }: { signals?: Record<string, unknown> }) {
  if (!signals) return null;
  const indicators = (signals.indicators as Array<Record<string, unknown>>) || [];
  if (indicators.length === 0) return null;
  return (
    <div className="mt-2 grid grid-cols-2 gap-1 text-[10px]">
      {indicators.slice(0, 6).map((ind, i) => (
        <div
          key={`${ind.name}-${i}`}
          className="rounded border border-[var(--glass-border)] px-1.5 py-0.5"
          style={{ background: "var(--glass-bg)" }}
        >
          <span className="font-semibold text-[var(--foreground)]">
            {String(ind.name)}
          </span>
          <span className="ml-1 text-[var(--text-muted)]">
            {typeof ind.value === "number"
              ? (ind.value as number).toFixed(2)
              : String(ind.value ?? "")}
          </span>
        </div>
      ))}
    </div>
  );
}

function DecisionRow({ decision }: { decision: AutoDecision }) {
  const [expanded, setExpanded] = useState(false);
  const isBuy = decision.action === "buy";
  const isSell = decision.action === "sell";
  return (
    <div
      className="rounded-lg border border-[var(--glass-border)] p-2"
      style={{ background: "var(--glass-bg)" }}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 text-left"
      >
        <span className="text-[10px] font-mono text-[var(--text-muted)]">
          {formatTimestamp(decision.decided_at)}
        </span>
        <span
          className={cn(
            "flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase",
            isBuy
              ? "bg-[var(--success)]/15 text-[var(--success)]"
              : isSell
                ? "bg-[var(--danger)]/15 text-[var(--danger)]"
                : "bg-[var(--glass-bg)] text-[var(--text-muted)]",
          )}
        >
          {isBuy ? (
            <ArrowUpRight className="h-2.5 w-2.5" />
          ) : isSell ? (
            <ArrowDownRight className="h-2.5 w-2.5" />
          ) : null}
          {decision.action}
        </span>
        <span className="text-[11px] font-semibold text-[var(--foreground)]">
          {decision.symbol}
        </span>
        <span
          className={cn(
            "ml-auto rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase",
            outcomeColor(decision.decision_outcome),
          )}
        >
          {decision.decision_outcome}
        </span>
        {expanded ? (
          <ChevronDown className="h-3 w-3 text-[var(--text-muted)]" />
        ) : (
          <ChevronRight className="h-3 w-3 text-[var(--text-muted)]" />
        )}
      </button>
      <div className="mt-1 flex items-center gap-2 text-[10px] text-[var(--text-muted)]">
        <span>conf {(Number(decision.confidence) * 100).toFixed(0)}%</span>
        {decision.regime ? <span>· {decision.regime}</span> : null}
        {decision.trade_group_id ? (
          <span className="font-mono">· #{decision.trade_group_id.slice(0, 8)}</span>
        ) : null}
      </div>
      {expanded && (
        <div className="mt-2 border-t border-[var(--glass-border)] pt-2 text-[11px] leading-5 text-[var(--text-secondary)]">
          {decision.reasoning ? (
            <p className="whitespace-pre-wrap">{decision.reasoning}</p>
          ) : (
            <p className="text-[var(--text-muted)]">(no reasoning recorded)</p>
          )}
          {decision.outcome_reason ? (
            <p className="mt-1 text-[10px] italic text-[var(--text-muted)]">
              Outcome: {decision.outcome_reason}
            </p>
          ) : null}
          <SignalIndicatorsGrid signals={decision.signals} />
        </div>
      )}
    </div>
  );
}

function TradeGroupRow({ group }: { group: TradeGroup }) {
  const pnlNum = group.realized_pnl ? Number(group.realized_pnl) : null;
  const pnlPctNum = group.realized_pnl_pct ? Number(group.realized_pnl_pct) : null;
  const isClosed = group.status === "closed";
  const positive = (pnlNum ?? 0) >= 0;
  return (
    <div
      className="rounded-lg border border-[var(--glass-border)] p-2"
      style={{ background: "var(--glass-bg)" }}
    >
      <div className="flex items-center gap-2 text-[11px]">
        <span className="font-mono text-[var(--text-muted)]">#{group.short_id}</span>
        <span className="font-semibold text-[var(--foreground)]">{group.symbol}</span>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase",
            group.status === "open"
              ? "bg-[var(--page-accent)]/15 text-[var(--page-accent)]"
              : "bg-[var(--glass-bg)] text-[var(--text-muted)]",
          )}
        >
          {group.status}
        </span>
        {isClosed && pnlNum !== null && (
          <span
            className={cn(
              "ml-auto text-[11px] font-bold",
              positive ? "text-[var(--success)]" : "text-[var(--danger)]",
            )}
          >
            {positive ? "+" : ""}
            {pnlNum.toFixed(2)}
            {pnlPctNum !== null ? ` (${positive ? "+" : ""}${pnlPctNum.toFixed(2)}%)` : ""}
          </span>
        )}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-[var(--text-muted)]">
        <span>entry {group.entry_price ?? "-"}</span>
        <span>· qty {Number(group.entry_quantity || 0).toFixed(6)}</span>
        {isClosed ? (
          <>
            <span>· exit {group.exit_price ?? "-"}</span>
            <span>· held {formatDuration(group.holding_seconds)}</span>
          </>
        ) : (
          <span>· {formatTimestamp(group.entry_time)}</span>
        )}
      </div>
    </div>
  );
}

export function AutoLogPanel({ status, onClose, onEmergencyStopped }: AutoLogPanelProps) {
  const [tab, setTab] = useState<TabKey>("decisions");
  const cycleCountdown = useCycleCountdown(status?.next_cycle_at);
  const enabled = Boolean(status?.enabled);

  const { decisions, loading: decisionsLoading } = useAutoDecisions({
    enabled,
    limit: 60,
    pollMs: 5000,
  });
  const { groups } = useAutoTradeGroups({
    enabled,
    limit: 30,
    pollMs: 10000,
  });

  const todayStats = useMemo(() => {
    if (!status) {
      return { trades: 0, pnl: "-", mode: "paper" };
    }
    return {
      trades: status.trades_today,
      pnl: status.realized_pnl_today,
      mode: status.mode,
    };
  }, [status]);

  return (
    <aside
      className="fixed right-0 top-0 z-40 flex h-full w-[360px] flex-col border-l border-[var(--glass-border)]"
      style={{ background: "var(--surface)", backdropFilter: "blur(24px) saturate(180%)" }}
    >
      {/* Header */}
      <div className="flex items-start justify-between border-b border-[var(--glass-border)] px-4 py-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Radio
              className={cn(
                "h-3.5 w-3.5",
                enabled ? "animate-pulse text-[var(--success)]" : "text-[var(--text-muted)]",
              )}
            />
            <h2 className="text-sm font-bold text-[var(--foreground)]">Auto-trading</h2>
            <span className="rounded bg-[var(--glass-bg)] px-1.5 py-0.5 text-[9px] font-semibold uppercase text-[var(--text-muted)]">
              {todayStats.mode}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-2 text-[10px] text-[var(--text-muted)]">
            <Clock3 className="h-3 w-3" />
            <span>Next cycle: {enabled ? cycleCountdown : "-"}</span>
            <span>· Trades {todayStats.trades}</span>
            <span>· P&L {todayStats.pnl}</span>
          </div>
          {status?.last_error && (
            <p className="mt-1 text-[10px] text-[var(--danger)]">{status.last_error}</p>
          )}
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-[var(--text-muted)] hover:bg-[var(--glass-bg)]"
            aria-label="Fermer"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Emergency stop */}
      {enabled && (
        <div className="border-b border-[var(--glass-border)] px-4 py-2">
          <EmergencyStopButton onStopped={onEmergencyStopped} compact className="w-full justify-center" />
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-[var(--glass-border)] px-4 text-xs">
        <button
          type="button"
          onClick={() => setTab("decisions")}
          className={cn(
            "border-b-2 px-2 py-2 font-semibold transition-colors",
            tab === "decisions"
              ? "border-[var(--page-accent)] text-[var(--foreground)]"
              : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-secondary)]",
          )}
        >
          Decisions
        </button>
        <button
          type="button"
          onClick={() => setTab("trade_groups")}
          className={cn(
            "border-b-2 px-2 py-2 font-semibold transition-colors",
            tab === "trade_groups"
              ? "border-[var(--page-accent)] text-[var(--foreground)]"
              : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-secondary)]",
          )}
        >
          Trades
        </button>
      </div>

      {/* Feed */}
      <div className="flex-1 space-y-2 overflow-y-auto px-4 py-3">
        {tab === "decisions" ? (
          decisions.length === 0 ? (
            <p className="py-8 text-center text-[11px] text-[var(--text-muted)]">
              {decisionsLoading ? "Chargement..." : "Aucune decision enregistree."}
            </p>
          ) : (
            decisions.map((d) => <DecisionRow key={d.id} decision={d} />)
          )
        ) : groups.length === 0 ? (
          <p className="py-8 text-center text-[11px] text-[var(--text-muted)]">
            Aucun trade group.
          </p>
        ) : (
          groups.map((g) => <TradeGroupRow key={g.id} group={g} />)
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-[var(--glass-border)] px-4 py-2 text-[10px] text-[var(--text-muted)]">
        <div className="flex items-center gap-2">
          <Activity className="h-3 w-3" />
          <span>Auto-trading log feed · polling 5s</span>
        </div>
      </div>
    </aside>
  );
}
