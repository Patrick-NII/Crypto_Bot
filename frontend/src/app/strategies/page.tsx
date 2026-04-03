"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BrainCircuit,
  Zap,
  ChevronDown,
  ChevronUp,
  Settings2,
  BarChart3,
  Target,
} from "lucide-react";
import { strategiesApi } from "@/lib/api";
import type { Strategy, Signal } from "@/lib/types";
import { formatPercent, cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-white/5", className)} />;
}

function SignalDisplay({ signal }: { signal: Signal }) {
  const actionColor =
    signal.action === "buy"
      ? "text-success"
      : signal.action === "sell"
        ? "text-danger"
        : "text-warning";

  return (
    <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-accent-purple" />
          <span className="text-sm font-semibold text-white">
            Signal: {signal.symbol}
          </span>
        </div>
        <Badge
          variant={
            signal.action === "buy"
              ? "success"
              : signal.action === "sell"
                ? "danger"
                : "warning"
          }
        >
          {signal.action.toUpperCase()}
        </Badge>
      </div>
      <div className="mt-2 flex items-center gap-4 text-xs text-white/50">
        <span className={cn("font-semibold", actionColor)}>
          Confidence: {(signal.confidence * 100).toFixed(0)}%
        </span>
        <span>{signal.reason}</span>
      </div>
      {/* Confidence bar */}
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
        <div
          className={cn(
            "h-full rounded-full",
            signal.action === "buy"
              ? "bg-success"
              : signal.action === "sell"
                ? "bg-danger"
                : "bg-warning",
          )}
          style={{ width: `${signal.confidence * 100}%` }}
        />
      </div>
    </div>
  );
}

export default function StrategiesPage() {
  const [loading, setLoading] = useState(true);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [signals, setSignals] = useState<Record<string, Signal>>({});
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [signalSymbol, setSignalSymbol] = useState("BTC");

  // Parameter editing
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editParams, setEditParams] = useState<Record<string, string | number | boolean>>({});
  const [saving, setSaving] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const data = await strategiesApi.list();
      setStrategies(data);
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleGenerateSignal = async (strategyId: string) => {
    setGeneratingId(strategyId);
    try {
      const signal = await strategiesApi.generateSignal(strategyId, signalSymbol);
      setSignals((prev) => ({ ...prev, [strategyId]: signal }));
    } catch {
      // handle
    } finally {
      setGeneratingId(null);
    }
  };

  const handleSaveParams = async (strategyId: string) => {
    setSaving(true);
    try {
      await strategiesApi.updateParams(strategyId, editParams);
      setEditingId(null);
      fetchData();
    } catch {
      // handle
    } finally {
      setSaving(false);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
    setEditingId(null);
  };

  if (loading) {
    return (
      <div className="relative z-10 min-h-screen p-4 md:p-8">
        <h1 className="mb-8 text-3xl font-bold glow-text">Strategies</h1>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonBlock key={i} className="h-48" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="relative z-10 min-h-screen p-4 md:p-8">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-3xl font-bold glow-text">Strategies</h1>
        <div className="flex items-center gap-3">
          <BrainCircuit className="h-5 w-5 text-accent-purple" />
          <span className="text-sm text-white/50">
            {strategies.filter((s) => s.status === "active").length} active /{" "}
            {strategies.length} total
          </span>
        </div>
      </div>

      {strategies.length === 0 ? (
        <GlassCard>
          <div className="flex flex-col items-center gap-4 py-12">
            <BrainCircuit className="h-12 w-12 text-white/20" />
            <p className="text-sm text-white/40">
              No strategies configured yet
            </p>
          </div>
        </GlassCard>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {strategies.map((strategy) => {
            const isExpanded = expandedId === strategy.id;
            const isEditing = editingId === strategy.id;
            const signal = signals[strategy.id];

            return (
              <GlassCard key={strategy.id} hover className="flex flex-col">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-semibold text-white">
                        {strategy.name}
                      </h3>
                      <Badge
                        variant={
                          strategy.status === "active" ? "success" : "default"
                        }
                      >
                        {strategy.status}
                      </Badge>
                    </div>
                    <p className="mt-1 text-sm text-white/40">
                      {strategy.description}
                    </p>
                  </div>
                  <button
                    onClick={() => toggleExpand(strategy.id)}
                    className="ml-2 rounded-lg p-1.5 text-white/40 hover:bg-white/5 hover:text-white"
                  >
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </button>
                </div>

                {/* Performance indicators */}
                {strategy.performance && (
                  <div className="mt-4 grid grid-cols-3 gap-3">
                    <div className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-center">
                      <span className="block text-xs text-white/40">Win Rate</span>
                      <span className="text-sm font-bold text-white">
                        {formatPercent(strategy.performance.win_rate)}
                      </span>
                    </div>
                    <div className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-center">
                      <span className="block text-xs text-white/40">Sharpe</span>
                      <span className="text-sm font-bold text-white">
                        {strategy.performance.sharpe_ratio.toFixed(2)}
                      </span>
                    </div>
                    <div className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-center">
                      <span className="block text-xs text-white/40">Trades</span>
                      <span className="text-sm font-bold text-white">
                        {strategy.performance.total_trades}
                      </span>
                    </div>
                  </div>
                )}

                {/* Parameters (key list) */}
                <div className="mt-4 flex flex-wrap gap-2">
                  {Object.entries(strategy.parameters)
                    .slice(0, isExpanded ? undefined : 3)
                    .map(([key, val]) => (
                      <span
                        key={key}
                        className="rounded-md border border-white/5 bg-white/[0.03] px-2 py-1 text-xs text-white/50"
                      >
                        {key}: <span className="text-white/70">{String(val)}</span>
                      </span>
                    ))}
                  {!isExpanded &&
                    Object.keys(strategy.parameters).length > 3 && (
                      <span className="text-xs text-white/30">
                        +{Object.keys(strategy.parameters).length - 3} more
                      </span>
                    )}
                </div>

                {/* Generate Signal row */}
                <div className="mt-4 flex items-center gap-2">
                  <select
                    value={signalSymbol}
                    onChange={(e) => setSignalSymbol(e.target.value)}
                    className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-xs text-white outline-none"
                  >
                    {["BTC", "ETH", "SOL", "BNB", "XRP"].map((s) => (
                      <option key={s} value={s} className="bg-[#0a0a1a]">
                        {s}
                      </option>
                    ))}
                  </select>
                  <Button
                    size="sm"
                    onClick={() => handleGenerateSignal(strategy.id)}
                    loading={generatingId === strategy.id}
                  >
                    <Zap className="h-3 w-3" />
                    Generate Signal
                  </Button>
                </div>

                {/* Signal result */}
                {signal && <SignalDisplay signal={signal} />}

                {/* Expanded detail: editable parameters */}
                {isExpanded && (
                  <div className="mt-4 border-t border-white/5 pt-4">
                    <div className="flex items-center justify-between">
                      <h4 className="flex items-center gap-1.5 text-sm font-semibold text-white/70">
                        <Settings2 className="h-4 w-4" />
                        Parameters
                      </h4>
                      {!isEditing && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setEditingId(strategy.id);
                            setEditParams({ ...strategy.parameters });
                          }}
                        >
                          Edit
                        </Button>
                      )}
                    </div>

                    {isEditing ? (
                      <div className="mt-3 space-y-2">
                        {Object.entries(editParams).map(([key, val]) => (
                          <div
                            key={key}
                            className="flex items-center gap-2 text-sm"
                          >
                            <label className="w-32 text-xs text-white/40">
                              {key}
                            </label>
                            <input
                              type={typeof val === "number" ? "number" : "text"}
                              value={String(val)}
                              onChange={(e) =>
                                setEditParams((prev) => ({
                                  ...prev,
                                  [key]:
                                    typeof val === "number"
                                      ? Number(e.target.value)
                                      : e.target.value,
                                }))
                              }
                              className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-xs text-white outline-none focus:border-accent-purple"
                            />
                          </div>
                        ))}
                        <div className="flex gap-2 pt-2">
                          <Button
                            size="sm"
                            onClick={() => handleSaveParams(strategy.id)}
                            loading={saving}
                          >
                            Save
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setEditingId(null)}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="mt-3 space-y-1">
                        {Object.entries(strategy.parameters).map(
                          ([key, val]) => (
                            <div
                              key={key}
                              className="flex justify-between text-xs"
                            >
                              <span className="text-white/40">{key}</span>
                              <span className="font-mono text-white/70">
                                {String(val)}
                              </span>
                            </div>
                          ),
                        )}
                      </div>
                    )}

                    {/* Extended performance */}
                    {strategy.performance && (
                      <div className="mt-4">
                        <h4 className="flex items-center gap-1.5 text-sm font-semibold text-white/70">
                          <BarChart3 className="h-4 w-4" />
                          Performance Details
                        </h4>
                        <div className="mt-2 grid grid-cols-2 gap-2">
                          <div className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                            <span className="block text-xs text-white/40">
                              Avg Return
                            </span>
                            <span
                              className={cn(
                                "text-sm font-bold",
                                strategy.performance.avg_return >= 0
                                  ? "text-success"
                                  : "text-danger",
                              )}
                            >
                              {formatPercent(strategy.performance.avg_return)}
                            </span>
                          </div>
                          <div className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                            <span className="block text-xs text-white/40">
                              Max Drawdown
                            </span>
                            <span className="text-sm font-bold text-danger">
                              {formatPercent(-strategy.performance.max_drawdown)}
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </GlassCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
