"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart3,
  TrendingUp,
  Target,
  AlertTriangle,
  Activity,
  Shield,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { analyticsApi } from "@/lib/api";
import type {
  AnalyticsMetrics,
  EquityPoint,
  StrategyComparison,
  TradingActivity,
  RiskMetrics,
} from "@/lib/types";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/glass-card";
import { StatCard } from "@/components/ui/stat-card";
import { Badge } from "@/components/ui/badge";

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-white/5", className)} />;
}

// Heatmap cell color intensity
function heatmapColor(count: number, max: number) {
  if (count === 0) return "bg-white/[0.02]";
  const intensity = count / (max || 1);
  if (intensity < 0.25) return "bg-accent-purple/10";
  if (intensity < 0.5) return "bg-accent-purple/25";
  if (intensity < 0.75) return "bg-accent-purple/40";
  return "bg-accent-purple/60";
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

export default function AnalyticsPage() {
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState<AnalyticsMetrics | null>(null);
  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([]);
  const [strategyComparison, setStrategyComparison] = useState<
    StrategyComparison[]
  >([]);
  const [tradingActivity, setTradingActivity] = useState<TradingActivity[]>([]);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [met, eq, strat, act, risk] = await Promise.allSettled([
        analyticsApi.getMetrics(),
        analyticsApi.getEquityCurve(),
        analyticsApi.getStrategyComparison(),
        analyticsApi.getTradingActivity(),
        analyticsApi.getRiskMetrics(),
      ]);

      if (met.status === "fulfilled") setMetrics(met.value);
      if (eq.status === "fulfilled") setEquityCurve(eq.value);
      if (strat.status === "fulfilled") setStrategyComparison(strat.value);
      if (act.status === "fulfilled") setTradingActivity(act.value);
      if (risk.status === "fulfilled") setRiskMetrics(risk.value);
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Build heatmap grid from activity data
  const activityMap = new Map<string, number>();
  let maxActivity = 0;
  tradingActivity.forEach((a) => {
    const key = `${a.day}-${a.hour}`;
    activityMap.set(key, a.count);
    if (a.count > maxActivity) maxActivity = a.count;
  });

  if (loading) {
    return (
      <div className="relative z-10 min-h-screen p-4 md:p-8">
        <h1 className="mb-8 text-3xl font-bold glow-text">Analytics</h1>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonBlock key={i} className="h-24" />
          ))}
        </div>
        <SkeletonBlock className="mt-6 h-80" />
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <SkeletonBlock className="h-64" />
          <SkeletonBlock className="h-64" />
        </div>
      </div>
    );
  }

  return (
    <div className="relative z-10 min-h-screen p-4 md:p-8">
      <h1 className="mb-8 text-3xl font-bold glow-text">Analytics</h1>

      {/* Top Row: Key Metrics */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Sharpe Ratio"
          value={metrics?.sharpe_ratio?.toFixed(2) ?? "-"}
          subtitle={
            metrics?.sharpe_ratio !== undefined
              ? metrics.sharpe_ratio >= 1
                ? "Good"
                : "Below target"
              : undefined
          }
          trend={
            metrics?.sharpe_ratio !== undefined
              ? metrics.sharpe_ratio >= 1
                ? "up"
                : "down"
              : "neutral"
          }
          icon={BarChart3}
        />
        <StatCard
          title="Win Rate"
          value={
            metrics?.win_rate !== undefined
              ? formatPercent(metrics.win_rate)
              : "-"
          }
          trend={
            metrics?.win_rate !== undefined
              ? metrics.win_rate >= 50
                ? "up"
                : "down"
              : "neutral"
          }
          icon={Target}
        />
        <StatCard
          title="Max Drawdown"
          value={
            metrics?.max_drawdown !== undefined
              ? formatPercent(-metrics.max_drawdown)
              : "-"
          }
          trend="down"
          icon={AlertTriangle}
        />
        <StatCard
          title="Total P&L"
          value={
            metrics?.total_pnl !== undefined
              ? formatCurrency(metrics.total_pnl)
              : "-"
          }
          trend={
            metrics?.total_pnl !== undefined
              ? metrics.total_pnl >= 0
                ? "up"
                : "down"
              : "neutral"
          }
          icon={TrendingUp}
        />
      </div>

      {/* Equity Curve Chart */}
      <GlassCard className="mb-6">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
          <Activity className="h-5 w-5 text-accent-purple" />
          Equity Curve
        </h2>
        {equityCurve.length === 0 ? (
          <div className="flex h-64 items-center justify-center">
            <p className="text-sm text-white/40">No equity data available</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={equityCurve}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.05)"
              />
              <XAxis
                dataKey="date"
                tick={{ fill: "rgba(255,255,255,0.3)", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "rgba(255,255,255,0.05)" }}
              />
              <YAxis
                tick={{ fill: "rgba(255,255,255,0.3)", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "rgba(255,255,255,0.05)" }}
                tickFormatter={(v: number) =>
                  `$${(v / 1000).toFixed(0)}k`
                }
              />
              <RechartsTooltip
                contentStyle={{
                  background: "rgba(10,10,26,0.95)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "0.5rem",
                  color: "#fff",
                  fontSize: "12px",
                }}
                formatter={(value) => [formatCurrency(Number(value)), "Equity"]}
              />
              <defs>
                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#a855f7" stopOpacity={0.8} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.3} />
                </linearGradient>
              </defs>
              <Line
                type="monotone"
                dataKey="value"
                stroke="url(#equityGrad)"
                strokeWidth={2}
                dot={false}
                activeDot={{
                  r: 4,
                  fill: "#a855f7",
                  stroke: "#fff",
                  strokeWidth: 1,
                }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </GlassCard>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Strategy Comparison Table */}
        <GlassCard>
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <BarChart3 className="h-5 w-5 text-accent-blue" />
            Strategy Comparison
          </h2>
          {strategyComparison.length === 0 ? (
            <p className="text-sm text-white/40">No strategy data available</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wider text-white/40">
                    <th className="pb-3 pr-3">Strategy</th>
                    <th className="pb-3 pr-3 text-right">Trades</th>
                    <th className="pb-3 pr-3 text-right">Win Rate</th>
                    <th className="pb-3 pr-3 text-right">P&L</th>
                    <th className="pb-3 text-right">Sharpe</th>
                  </tr>
                </thead>
                <tbody>
                  {strategyComparison.map((s) => (
                    <tr
                      key={s.name}
                      className="border-b border-white/5 transition-colors hover:bg-white/[0.02]"
                    >
                      <td className="py-3 pr-3 font-semibold text-white">
                        {s.name}
                      </td>
                      <td className="py-3 pr-3 text-right font-mono text-white/70">
                        {s.trades}
                      </td>
                      <td
                        className={cn(
                          "py-3 pr-3 text-right font-mono font-semibold",
                          s.win_rate >= 50 ? "text-success" : "text-danger",
                        )}
                      >
                        {formatPercent(s.win_rate)}
                      </td>
                      <td
                        className={cn(
                          "py-3 pr-3 text-right font-mono font-semibold",
                          s.pnl >= 0 ? "text-success" : "text-danger",
                        )}
                      >
                        {formatCurrency(s.pnl)}
                      </td>
                      <td className="py-3 text-right font-mono text-white/70">
                        {s.sharpe.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCard>

        {/* Risk Metrics Panel */}
        <GlassCard>
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <Shield className="h-5 w-5 text-accent-cyan" />
            Risk Metrics
          </h2>
          {!riskMetrics && !metrics ? (
            <p className="text-sm text-white/40">No risk data available</p>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
                  <span className="block text-xs text-white/40">
                    Value at Risk (95%)
                  </span>
                  <span className="text-lg font-bold text-danger">
                    {metrics?.var_95 !== undefined
                      ? formatPercent(-metrics.var_95)
                      : riskMetrics
                        ? formatPercent(-riskMetrics.portfolio_var)
                        : "-"}
                  </span>
                </div>
                <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
                  <span className="block text-xs text-white/40">
                    Volatility
                  </span>
                  <span className="text-lg font-bold text-warning">
                    {metrics?.volatility !== undefined
                      ? formatPercent(metrics.volatility)
                      : riskMetrics
                        ? formatPercent(riskMetrics.portfolio_volatility)
                        : "-"}
                  </span>
                </div>
                <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
                  <span className="block text-xs text-white/40">
                    Sortino Ratio
                  </span>
                  <span className="text-lg font-bold text-white">
                    {metrics?.sortino_ratio?.toFixed(2) ?? "-"}
                  </span>
                </div>
                <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
                  <span className="block text-xs text-white/40">
                    Calmar Ratio
                  </span>
                  <span className="text-lg font-bold text-white">
                    {metrics?.calmar_ratio?.toFixed(2) ?? "-"}
                  </span>
                </div>
              </div>

              {/* Position risk breakdown */}
              {riskMetrics?.position_risk &&
                riskMetrics.position_risk.length > 0 && (
                  <div>
                    <h3 className="mb-2 text-sm font-medium text-white/50">
                      Position Risk Breakdown
                    </h3>
                    <div className="space-y-2">
                      {riskMetrics.position_risk.map((pr) => (
                        <div
                          key={pr.symbol}
                          className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2"
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-white">
                              {pr.symbol}
                            </span>
                            <Badge variant="purple">
                              {(pr.weight * 100).toFixed(1)}%
                            </Badge>
                          </div>
                          <div className="flex gap-4 text-xs">
                            <span className="text-white/40">
                              VaR:{" "}
                              <span className="text-danger">
                                {formatPercent(-pr.var_contribution)}
                              </span>
                            </span>
                            <span className="text-white/40">
                              Vol:{" "}
                              <span className="text-warning">
                                {formatPercent(pr.volatility)}
                              </span>
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
            </div>
          )}
        </GlassCard>
      </div>

      {/* Trading Activity Heatmap */}
      <GlassCard className="mt-6">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
          <Activity className="h-5 w-5 text-accent-purple" />
          Trading Activity Heatmap
        </h2>
        {tradingActivity.length === 0 ? (
          <p className="text-sm text-white/40">No activity data available</p>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[600px]">
              {/* Hour labels */}
              <div className="mb-1 flex">
                <div className="w-10 shrink-0" />
                {HOURS.filter((h) => h % 3 === 0).map((h) => (
                  <div
                    key={h}
                    className="text-xs text-white/30"
                    style={{ width: `${100 / 8}%` }}
                  >
                    {h.toString().padStart(2, "0")}:00
                  </div>
                ))}
              </div>
              {/* Day rows */}
              {DAYS.map((day) => (
                <div key={day} className="mb-1 flex items-center gap-1">
                  <span className="w-10 shrink-0 text-xs text-white/30">
                    {day}
                  </span>
                  <div className="flex flex-1 gap-0.5">
                    {HOURS.map((hour) => {
                      const count = activityMap.get(`${day}-${hour}`) ?? 0;
                      return (
                        <div
                          key={hour}
                          className={cn(
                            "flex-1 rounded-sm transition-colors",
                            heatmapColor(count, maxActivity),
                          )}
                          style={{ aspectRatio: "1" }}
                          title={`${day} ${hour}:00 - ${count} trades`}
                        />
                      );
                    })}
                  </div>
                </div>
              ))}
              {/* Legend */}
              <div className="mt-3 flex items-center gap-2 justify-end">
                <span className="text-xs text-white/30">Less</span>
                {["bg-white/[0.02]", "bg-accent-purple/10", "bg-accent-purple/25", "bg-accent-purple/40", "bg-accent-purple/60"].map(
                  (color, i) => (
                    <div
                      key={i}
                      className={cn("h-3 w-3 rounded-sm", color)}
                    />
                  ),
                )}
                <span className="text-xs text-white/30">More</span>
              </div>
            </div>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
