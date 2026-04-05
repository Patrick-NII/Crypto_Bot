"use client";

import { useMemo } from "react";
import { Activity, Bot, Clock3, Sparkles, Target } from "lucide-react";
import { useTheme } from "@/components/providers/theme-provider";
import { SignalBadge, type SignalAction } from "./signal-badge";
import { cn } from "@/lib/utils";

export interface TradingSignalSnapshot {
  symbol: string;
  action: string;
  confidence: number;
  score: number;
  reasoning: string;
}

export interface AutoTradingStatusSnapshot {
  enabled: boolean;
  last_run: string | null;
  trades_today: number;
  total_pnl: number;
}

export interface AutoTradingHistoryTrade {
  symbol: string;
  action: string;
  amount_usd: number;
  confidence?: number;
  reason?: string;
  regime?: string;
  strategy?: string;
  price?: number;
}

export interface AutoTradingHistoryCandidate {
  symbol: string;
  action: string;
  confidence: number;
  regime?: string | null;
  price?: number | null;
}

export interface AutoTradingHistorySnapshot {
  timestamp: string;
  analysis: string;
  executed: number;
  trades: AutoTradingHistoryTrade[];
  recommendations?: number;
  provider?: string | null;
  model?: string | null;
  regime?: string;
  signals_scanned?: number;
  candidates?: AutoTradingHistoryCandidate[];
}

interface AutoTradingMonitorProps {
  selectedSymbol?: string;
  signals: TradingSignalSnapshot[];
  status: AutoTradingStatusSnapshot | null;
  history: AutoTradingHistorySnapshot[];
  loading?: boolean;
}

function formatTimestamp(value: string | null) {
  if (!value) return "Waiting";
  try {
    return new Date(value).toLocaleString([], {
      hour: "2-digit",
      minute: "2-digit",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "Waiting";
  }
}

function formatAnalysis(text: string) {
  const trimmed = text.trim();
  if (!trimmed) return "No analysis yet.";
  return trimmed.length > 120 ? `${trimmed.slice(0, 117)}...` : trimmed;
}

export function AutoTradingMonitor({
  selectedSymbol,
  signals,
  status,
  history,
  loading = false,
}: AutoTradingMonitorProps) {
  const { tradingMode } = useTheme();

  const sortedSignals = useMemo(
    () => [...signals].sort((a, b) => b.confidence - a.confidence),
    [signals],
  );

  const focusSignal = useMemo(() => {
    if (selectedSymbol) {
      const exact = sortedSignals.find((signal) => signal.symbol === selectedSymbol);
      if (exact) return exact;
    }
    return sortedSignals[0] ?? null;
  }, [selectedSymbol, sortedSignals]);

  const headlineSignals = sortedSignals.filter((signal) => signal.action !== "HOLD").slice(0, 4);

  return (
    <div className="space-y-4">
      <div>
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 accent-text" />
              <h3 className="text-sm font-semibold text-[var(--foreground)]">AI Trade Desk</h3>
            </div>
            <p className="mt-1 text-[13px] text-[var(--text-muted)]">
              {tradingMode === "auto"
                ? "The AI desk is supervising signals, execution state, and recent decisions."
                : "The AI desk stays advisory and keeps the operator informed in manual mode."}
            </p>
          </div>
          <div
            className={cn(
              "rounded-full px-2.5 py-1 text-[12px] font-semibold",
              status?.enabled
                ? "bg-[#22c55e]/12 text-[#22c55e]"
                : "bg-[var(--glass-bg)] text-[var(--text-muted)]",
            )}
          >
            {status?.enabled ? "AI Armed" : "AI Disarmed"}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <div className="mb-1 flex items-center gap-1.5 text-[var(--text-muted)]">
              <Activity className="h-3.5 w-3.5" />
              Status
            </div>
            <div className="text-sm font-semibold text-[var(--foreground)]">
              {loading ? "Loading..." : status?.enabled ? "Armed" : "Monitoring"}
            </div>
          </div>
          <div>
            <div className="mb-1 flex items-center gap-1.5 text-[var(--text-muted)]">
              <Clock3 className="h-3.5 w-3.5" />
              Last run
            </div>
            <div className="text-sm font-semibold text-[var(--foreground)]">
              {loading ? "Loading..." : formatTimestamp(status?.last_run ?? null)}
            </div>
          </div>
          <div>
            <div className="mb-1 flex items-center gap-1.5 text-[var(--text-muted)]">
              <Sparkles className="h-3.5 w-3.5" />
              Trades today
            </div>
            <div className="text-sm font-semibold text-[var(--foreground)]">
              {loading ? "..." : status?.trades_today ?? 0}
            </div>
          </div>
          <div>
            <div className="mb-1 flex items-center gap-1.5 text-[var(--text-muted)]">
              <Target className="h-3.5 w-3.5" />
              AI PnL
            </div>
            <div
              className={cn(
                "text-sm font-semibold",
                (status?.total_pnl ?? 0) >= 0 ? "text-[#22c55e]" : "text-[#ef4444]",
              )}
            >
              ${Number(status?.total_pnl ?? 0).toFixed(2)}
            </div>
          </div>
        </div>
      </div>

      {focusSignal && (
        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <div>
              <p className="text-[12px] uppercase tracking-[0.18em] text-[var(--text-muted)]">
                {selectedSymbol ? `${selectedSymbol} focus` : "Current focus"}
              </p>
              <p className="text-sm font-semibold text-[var(--foreground)]">{focusSignal.symbol}</p>
            </div>
            <SignalBadge
              action={focusSignal.action as SignalAction}
              confidence={focusSignal.confidence}
              size="sm"
              blink={tradingMode === "auto" && Boolean(status?.enabled)}
            />
          </div>
          <p className="text-xs leading-5 text-[var(--text-secondary)]">{focusSignal.reasoning}</p>
        </div>
      )}

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h4 className="text-[14px] font-semibold text-[var(--foreground)]">Priority Signals</h4>
          <span className="text-[12px] text-[var(--text-muted)]">Ranked by confidence</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {headlineSignals.length === 0 && !loading ? (
            <div className="col-span-2 text-[13px] text-[var(--text-muted)]">
              No actionable signals right now.
            </div>
          ) : (
            headlineSignals.map((signal) => (
              <div key={signal.symbol} className="rounded-xl px-3 py-2 hover:bg-[var(--glass-bg)]">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="text-[13px] font-semibold text-[var(--foreground)]">{signal.symbol}</span>
                  <SignalBadge action={signal.action as SignalAction} confidence={signal.confidence} size="sm" />
                </div>
                <p className="text-[12px] text-[var(--text-muted)]">
                  {Math.round(signal.confidence * 100)}% confidence
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h4 className="text-[14px] font-semibold text-[var(--foreground)]">Recent AI Activity</h4>
          <span className="text-[12px] text-[var(--text-muted)]">Latest cycles</span>
        </div>
        <div className="space-y-2">
          {history.length === 0 && !loading ? (
            <div className="text-[13px] text-[var(--text-muted)]">
              No AI activity has been recorded yet.
            </div>
          ) : (
            history.slice(0, 4).map((entry) => (
              <div key={`${entry.timestamp}-${entry.executed}`} className="rounded-xl px-3 py-2 hover:bg-[var(--glass-bg)]">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="text-[13px] font-semibold text-[var(--foreground)]">
                    {formatTimestamp(entry.timestamp)}
                  </span>
                  <span className="text-[12px] text-[var(--text-muted)]">
                    {entry.executed} executed
                  </span>
                </div>
                <p className="mb-2 text-[13px] leading-5 text-[var(--text-secondary)]">
                  {formatAnalysis(entry.analysis)}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {entry.trades.length === 0 ? (
                    <span className="text-[12px] text-[var(--text-muted)]">No trades placed</span>
                  ) : (
                    entry.trades.map((trade, index) => (
                      <span
                        key={`${trade.symbol}-${trade.action}-${index}`}
                        className="rounded-full bg-[var(--glass-bg)] px-2 py-1 text-[12px] text-[var(--text-secondary)]"
                      >
                        {trade.symbol} {trade.action} ${trade.amount_usd.toFixed(0)}
                      </span>
                    ))
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
