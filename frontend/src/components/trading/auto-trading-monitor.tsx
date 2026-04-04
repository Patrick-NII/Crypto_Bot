"use client";

import { useEffect, useState } from "react";
import { useTheme } from "@/components/providers/theme-provider";
import { signalsApi } from "@/lib/api";
import { SignalBadge, type SignalAction } from "./signal-badge";
import { cn } from "@/lib/utils";
import { Bot, Activity, Clock, Zap, Pause, Play } from "lucide-react";

interface LogEntry {
  time: string;
  message: string;
  type: "info" | "signal" | "trade" | "error";
  symbol?: string;
  action?: SignalAction;
}

interface SignalData {
  symbol: string;
  action: string;
  confidence: number;
  score: number;
  reasoning: string;
}

export function AutoTradingMonitor() {
  const { tradingMode } = useTheme();
  const [signals, setSignals] = useState<SignalData[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [paused, setPaused] = useState(false);
  const [cycleCount, setCycleCount] = useState(0);

  const addLog = (msg: string, type: LogEntry["type"] = "info", symbol?: string, action?: SignalAction) => {
    setLogs((prev) => [
      { time: new Date().toLocaleTimeString(), message: msg, type, symbol, action },
      ...prev.slice(0, 49),
    ]);
  };

  // Fetch signals on mount and every 60s
  useEffect(() => {
    const fetchSignals = async () => {
      setLoading(true);
      addLog("Scanning market... fetching signals for top 10 assets");
      try {
        const data = await signalsApi.getAllSignals();
        setSignals(data);
        setCycleCount((c) => c + 1);

        // Generate log entries from signals
        const strong = data.filter((s) => s.action === "STRONG_BUY" || s.action === "STRONG_SELL");
        const buys = data.filter((s) => s.action === "BUY" || s.action === "ACCUMULATE");
        const sells = data.filter((s) => s.action === "SELL" || s.action === "REDUCE");

        addLog(`Analysis complete: ${data.length} assets scanned`, "info");

        strong.forEach((s) => {
          addLog(
            `${s.action === "STRONG_BUY" ? "STRONG BUY" : "STRONG SELL"} signal on ${s.symbol} — confidence ${Math.round(s.confidence * 100)}%`,
            "signal",
            s.symbol,
            s.action as SignalAction,
          );
        });

        if (tradingMode === "auto" && !paused) {
          strong.forEach((s) => {
            if (s.confidence > 0.5) {
              addLog(
                `AUTO-EXECUTE: ${s.action === "STRONG_BUY" ? "Buying" : "Selling"} ${s.symbol} (paper)`,
                "trade",
                s.symbol,
                s.action as SignalAction,
              );
            }
          });
        }

        if (buys.length > 0) addLog(`${buys.length} buy signals: ${buys.map((s) => s.symbol).join(", ")}`, "info");
        if (sells.length > 0) addLog(`${sells.length} sell signals: ${sells.map((s) => s.symbol).join(", ")}`, "info");
      } catch {
        addLog("Failed to fetch signals", "error");
      }
      setLoading(false);
    };

    fetchSignals();
    const interval = setInterval(() => {
      if (!paused) fetchSignals();
    }, 60000);

    return () => clearInterval(interval);
  }, [tradingMode, paused]);

  const LOG_COLORS = {
    info: "text-[var(--text-muted)]",
    signal: "text-[#f59e0b]",
    trade: "text-[#22c55e]",
    error: "text-[#ef4444]",
  };

  return (
    <div className="space-y-4">
      {/* Signal Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        {loading && signals.length === 0 ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl" style={{ background: "var(--glass-bg)" }} />
          ))
        ) : (
          signals.slice(0, 10).map((sig) => (
            <div
              key={sig.symbol}
              className="liquid-glass-card p-3 flex flex-col items-center gap-1.5"
            >
              <span className="text-[11px] font-bold text-[var(--foreground)]">{sig.symbol}</span>
              <SignalBadge
                action={sig.action as SignalAction}
                confidence={sig.confidence}
                size="sm"
                blink={tradingMode === "auto"}
              />
            </div>
          ))
        )}
      </div>

      {/* Auto-Trading Log Window */}
      <div className="liquid-glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 accent-text" />
            <h3 className="text-[13px] font-semibold text-[var(--foreground)]">
              {tradingMode === "auto" ? "Auto-Trading" : "Signal"} Monitor
            </h3>
            <span className="text-[10px] text-[var(--text-muted)]">Cycle #{cycleCount}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={cn(
              "flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
              tradingMode === "auto" ? "bg-[#22c55e]/12 text-[#22c55e]" : "bg-[var(--glass-bg)] text-[var(--text-muted)]",
            )}>
              <Activity className="h-3 w-3" />
              {tradingMode === "auto" ? "AUTO" : "MANUAL"}
            </div>
            <button
              onClick={() => setPaused(!paused)}
              className="rounded-lg p-1 text-[var(--text-muted)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)]"
            >
              {paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>

        {/* Log entries */}
        <div className="h-48 overflow-y-auto space-y-0.5 font-mono text-[11px] rounded-xl p-2" style={{ background: "var(--bg)" }}>
          {logs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-[var(--text-muted)]">
              Waiting for first scan...
            </div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="flex items-start gap-2 py-0.5">
                <span className="text-[var(--text-muted)] flex-shrink-0">{log.time}</span>
                {log.type === "trade" && <Zap className="h-3 w-3 text-[#22c55e] flex-shrink-0 mt-0.5" />}
                {log.type === "signal" && <Activity className="h-3 w-3 text-[#f59e0b] flex-shrink-0 mt-0.5" />}
                {log.type === "error" && <span className="text-[#ef4444] flex-shrink-0">!</span>}
                <span className={LOG_COLORS[log.type]}>{log.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
