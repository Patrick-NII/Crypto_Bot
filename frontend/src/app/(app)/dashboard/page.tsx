"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Wallet,
  TrendingUp,
  ShoppingCart,
  ShieldAlert,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { pricesApi, portfolioApi, tradingApi } from "@/lib/api";
import type {
  CryptoMarketData,
  Order,
  Portfolio,
} from "@/lib/types";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/glass-card";
import { StatCard } from "@/components/ui/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PriceChart } from "@/components/charts/price-chart";

// ---- Skeleton helpers ----

function SkeletonBlock({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-lg bg-white/5", className)}
    />
  );
}

function StatCardSkeleton() {
  return (
    <GlassCard className="flex flex-col gap-2">
      <SkeletonBlock className="h-3 w-20" />
      <SkeletonBlock className="h-7 w-28" />
      <SkeletonBlock className="h-4 w-16" />
    </GlassCard>
  );
}

// ---- Color palette for pie chart (turquoise/lime theme) ----
const PIE_COLORS = ["#06d6a0", "#c6f135", "#06b6d4", "#3b82f6", "#8b5cf6"];

// ---- Order status badge variant ----
function orderStatusVariant(status: string) {
  switch (status) {
    case "filled":
      return "success";
    case "open":
      return "info";
    case "cancelled":
      return "default";
    case "failed":
      return "danger";
    default:
      return "default";
  }
}

// ---- Fear & Greed gauge color ----
function fearGreedColor(value: number) {
  if (value <= 25) return "text-[#ef4444]";
  if (value <= 45) return "text-[#c6f135]";
  if (value <= 55) return "text-[#8888a0]";
  if (value <= 75) return "text-[#06d6a0]";
  return "text-[#06d6a0]";
}

function fearGreedLabel(value: number) {
  if (value <= 25) return "Extreme Fear";
  if (value <= 45) return "Fear";
  if (value <= 55) return "Neutral";
  if (value <= 75) return "Greed";
  return "Extreme Greed";
}

// ============================================================
// Dashboard Page
// ============================================================

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [cryptos, setCryptos] = useState<CryptoMarketData[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [fearGreed, setFearGreed] = useState<number>(50);
  const [openOrderCount, setOpenOrderCount] = useState(0);

  // Quick trade state - symbols from API
  const [availableSymbols, setAvailableSymbols] = useState<string[]>([]);
  const [tradeSymbol, setTradeSymbol] = useState("");
  const [tradeSide, setTradeSide] = useState<"buy" | "sell">("buy");
  const [tradeAmount, setTradeAmount] = useState("");
  const [tradeSubmitting, setTradeSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [allCryptosResult, portfolios, orderData, fgData] = await Promise.allSettled([
        pricesApi.getAllCryptos(20),
        portfolioApi.list(),
        tradingApi.getOrders(),
        pricesApi.getFearGreed(),
      ]);

      if (allCryptosResult.status === "fulfilled") {
        setCryptos(allCryptosResult.value.data);
        const symbols = allCryptosResult.value.data.map((c) => c.symbol);
        setAvailableSymbols(symbols);
        if (symbols.length > 0 && !tradeSymbol) {
          setTradeSymbol(symbols[0]);
        }
      }
      if (portfolios.status === "fulfilled" && portfolios.value.length > 0) {
        setPortfolio(portfolios.value[0]);
      }
      if (orderData.status === "fulfilled") {
        setOrders(orderData.value.slice(0, 5));
        setOpenOrderCount(
          orderData.value.filter((o) => o.status === "open").length,
        );
      }
      if (fgData.status === "fulfilled") setFearGreed(fgData.value.value);
    } catch {
      // Errors handled per-request above
    } finally {
      setLoading(false);
    }
  }, [tradeSymbol]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      pricesApi.getAllCryptos(20).then((res) => setCryptos(res.data)).catch(() => {});
    }, 30_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Quick trade handler
  const handleQuickTrade = async () => {
    if (!tradeAmount || isNaN(Number(tradeAmount)) || !tradeSymbol) return;
    setTradeSubmitting(true);
    try {
      await tradingApi.placeOrder({
        symbol: tradeSymbol,
        side: tradeSide,
        order_type: "market",
        quantity: Number(tradeAmount),
      });
      setTradeAmount("");
      fetchData();
    } catch {
      // toast or error handling
    } finally {
      setTradeSubmitting(false);
    }
  };

  // Allocation data for pie chart
  const allocationData = portfolio?.positions
    ? Object.entries(
        portfolio.positions.reduce<Record<string, number>>((acc, p) => {
          const type = p.asset_type || "other";
          acc[type] = (acc[type] || 0) + p.current_price * p.quantity;
          return acc;
        }, {}),
      ).map(([name, value]) => ({ name, value }))
    : [];

  // Top 10 crypto for market overview
  const top10 = cryptos.slice(0, 10);

  // ---- Loading state ----
  if (loading) {
    return (
      <div className="relative z-10 min-h-screen p-4 md:p-8">
        <h1 className="mb-8 text-3xl font-bold glow-text">Dashboard</h1>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <StatCardSkeleton key={i} />
          ))}
        </div>
        <div className="mt-6">
          <SkeletonBlock className="h-12 w-full" />
        </div>
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <SkeletonBlock className="h-80" />
            <SkeletonBlock className="h-48" />
          </div>
          <div className="space-y-6">
            <SkeletonBlock className="h-48" />
            <SkeletonBlock className="h-64" />
            <SkeletonBlock className="h-56" />
          </div>
        </div>
      </div>
    );
  }

  const portfolioValue = portfolio?.total_value ?? 0;
  const pnl24h = portfolio?.total_pnl ?? 0;
  const pnlPct = portfolio?.total_pnl_pct ?? 0;
  const riskScore = 42; // fetched from API in future

  return (
    <div className="relative z-10 min-h-screen p-4 md:p-8">
      {/* Page Title */}
      <h1 className="mb-8 text-3xl font-bold glow-text">Dashboard</h1>

      {/* ---- Top Row: StatCards ---- */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Portfolio Value"
          value={formatCurrency(portfolioValue)}
          icon={Wallet}
        />
        <StatCard
          title="24h Change"
          value={formatCurrency(pnl24h)}
          subtitle={formatPercent(pnlPct)}
          trend={pnl24h >= 0 ? "up" : "down"}
          icon={TrendingUp}
        />
        <StatCard
          title="Open Orders"
          value={String(openOrderCount)}
          icon={ShoppingCart}
        />
        <StatCard
          title="Risk Score"
          value={`${riskScore}/100`}
          subtitle={riskScore < 50 ? "Low Risk" : "Moderate"}
          trend={riskScore < 50 ? "up" : "neutral"}
          icon={ShieldAlert}
        />
      </div>

      {/* ---- Price Ticker Strip ---- */}
      <div className="mt-6 overflow-x-auto">
        <div className="flex gap-4 pb-2">
          {cryptos.slice(0, 20).map((coin) => (
            <div
              key={coin.symbol}
              className="flex shrink-0 items-center gap-3 rounded-xl border border-white/[0.06] bg-[#14141b]/60 px-4 py-2.5"
            >
              <span className="text-sm font-semibold text-[#e8e8ed]">
                {coin.symbol}
              </span>
              <span className="text-sm text-[#e8e8ed]/80">
                {formatCurrency(coin.price)}
              </span>
              <span
                className={cn(
                  "flex items-center text-xs font-semibold",
                  coin.change_pct_24h >= 0 ? "text-[#06d6a0]" : "text-[#ef4444]",
                )}
              >
                {coin.change_pct_24h >= 0 ? (
                  <ArrowUpRight className="mr-0.5 h-3 w-3" />
                ) : (
                  <ArrowDownRight className="mr-0.5 h-3 w-3" />
                )}
                {formatPercent(coin.change_pct_24h)}
              </span>
              {/* Mini sparkline */}
              {coin.sparkline && coin.sparkline.length > 1 && (
                <svg className="h-6 w-12" viewBox="0 0 48 24">
                  <polyline
                    fill="none"
                    stroke={coin.change_pct_24h >= 0 ? "#06d6a0" : "#ef4444"}
                    strokeWidth="1.5"
                    points={coin.sparkline
                      .map((v, i) => {
                        const min = Math.min(...coin.sparkline!);
                        const max = Math.max(...coin.sparkline!);
                        const range = max - min || 1;
                        const x = (i / (coin.sparkline!.length - 1)) * 48;
                        const y = 24 - ((v - min) / range) * 24;
                        return `${x},${y}`;
                      })
                      .join(" ")}
                  />
                </svg>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ---- Main Content: 2-column layout ---- */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Column (2/3) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Market Overview */}
          <GlassCard>
            <h2 className="mb-4 text-lg font-semibold text-[#e8e8ed]">
              Market Overview
            </h2>
            {top10.length === 0 ? (
              <p className="text-sm text-[#55556a]">
                No market data available
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06] text-left text-xs uppercase tracking-wider text-[#55556a]">
                      <th className="pb-3 pr-4">#</th>
                      <th className="pb-3 pr-4">Asset</th>
                      <th className="pb-3 pr-4 text-right">Price</th>
                      <th className="pb-3 pr-4 text-right">24h</th>
                      <th className="hidden pb-3 pr-4 text-right sm:table-cell">
                        Volume
                      </th>
                      <th className="pb-3 text-right">Chart</th>
                    </tr>
                  </thead>
                  <tbody>
                    {top10.map((coin, idx) => (
                      <tr
                        key={coin.symbol}
                        className="border-b border-white/[0.06] transition-colors hover:bg-white/[0.02]"
                      >
                        <td className="py-3 pr-4 text-[#55556a]">
                          {idx + 1}
                        </td>
                        <td className="py-3 pr-4">
                          <div>
                            <span className="font-semibold text-[#e8e8ed]">
                              {coin.symbol}
                            </span>
                            <span className="ml-2 text-[#55556a]">
                              {coin.name}
                            </span>
                          </div>
                        </td>
                        <td className="py-3 pr-4 text-right font-mono text-[#e8e8ed]">
                          {formatCurrency(coin.price)}
                        </td>
                        <td
                          className={cn(
                            "py-3 pr-4 text-right font-mono font-semibold",
                            coin.change_pct_24h >= 0
                              ? "text-[#06d6a0]"
                              : "text-[#ef4444]",
                          )}
                        >
                          {formatPercent(coin.change_pct_24h)}
                        </td>
                        <td className="hidden py-3 pr-4 text-right font-mono text-[#8888a0] sm:table-cell">
                          {coin.volume_24h
                            ? `$${(coin.volume_24h / 1e9).toFixed(1)}B`
                            : "-"}
                        </td>
                        <td className="py-3 text-right">
                          <div className="inline-block w-[80px]">
                            <PriceChart
                              symbol={coin.symbol}
                              height={40}
                              type="line"
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </GlassCard>

          {/* Recent Trades */}
          <GlassCard>
            <h2 className="mb-4 text-lg font-semibold text-[#e8e8ed]">
              Recent Trades
            </h2>
            {orders.length === 0 ? (
              <p className="text-sm text-[#55556a]">No recent trades</p>
            ) : (
              <div className="space-y-3">
                {orders.map((order) => (
                  <div
                    key={order.id}
                    className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-3"
                  >
                    <div className="flex items-center gap-3">
                      <Badge
                        variant={order.side === "buy" ? "success" : "danger"}
                      >
                        {order.side.toUpperCase()}
                      </Badge>
                      <div>
                        <span className="font-semibold text-[#e8e8ed]">
                          {order.symbol}
                        </span>
                        <span className="ml-2 text-xs text-[#55556a]">
                          {order.order_type}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="font-mono text-sm text-[#8888a0]">
                        {order.quantity} @{" "}
                        {formatCurrency(order.filled_price ?? order.price ?? 0)}
                      </span>
                      <Badge variant={orderStatusVariant(order.status)}>
                        {order.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        </div>

        {/* Right Column (1/3) */}
        <div className="space-y-6">
          {/* Fear & Greed Index */}
          <GlassCard className="flex flex-col items-center">
            <h2 className="mb-4 self-start text-lg font-semibold text-[#e8e8ed]">
              Fear & Greed Index
            </h2>
            <div className="relative flex h-32 w-32 items-center justify-center">
              {/* Background circle */}
              <svg className="absolute inset-0" viewBox="0 0 128 128">
                <circle
                  cx="64"
                  cy="64"
                  r="56"
                  fill="none"
                  stroke="rgba(255,255,255,0.05)"
                  strokeWidth="8"
                />
                <circle
                  cx="64"
                  cy="64"
                  r="56"
                  fill="none"
                  stroke="url(#fgGrad)"
                  strokeWidth="8"
                  strokeDasharray={`${(fearGreed / 100) * 352} 352`}
                  strokeLinecap="round"
                  transform="rotate(-90 64 64)"
                />
                <defs>
                  <linearGradient id="fgGrad" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#ef4444" />
                    <stop offset="50%" stopColor="#c6f135" />
                    <stop offset="100%" stopColor="#06d6a0" />
                  </linearGradient>
                </defs>
              </svg>
              <span
                className={cn(
                  "text-3xl font-bold",
                  fearGreedColor(fearGreed),
                )}
              >
                {fearGreed}
              </span>
            </div>
            <span className="mt-2 text-sm font-medium text-[#8888a0]">
              {fearGreedLabel(fearGreed)}
            </span>
          </GlassCard>

          {/* Quick Trade Form */}
          <GlassCard>
            <h2 className="mb-4 text-lg font-semibold text-[#e8e8ed]">
              Quick Trade
            </h2>
            <div className="space-y-4">
              {/* Symbol selector - fetched from API */}
              <div>
                <label className="mb-1 block text-xs text-[#55556a]">
                  Symbol
                </label>
                <select
                  value={tradeSymbol}
                  onChange={(e) => setTradeSymbol(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.06] bg-[#1a1a24] px-3 py-2 text-sm text-[#e8e8ed] outline-none focus:border-[#06d6a0]/50"
                >
                  {availableSymbols.map((s) => (
                    <option key={s} value={s} className="bg-[#0d0d12]">
                      {s}
                    </option>
                  ))}
                </select>
              </div>

              {/* Buy / Sell toggle */}
              <div className="flex overflow-hidden rounded-lg border border-white/[0.06]">
                <button
                  className={cn(
                    "flex-1 py-2 text-sm font-semibold transition-colors",
                    tradeSide === "buy"
                      ? "bg-[#06d6a0]/20 text-[#06d6a0]"
                      : "text-[#55556a] hover:bg-white/5",
                  )}
                  onClick={() => setTradeSide("buy")}
                >
                  Buy
                </button>
                <button
                  className={cn(
                    "flex-1 py-2 text-sm font-semibold transition-colors",
                    tradeSide === "sell"
                      ? "bg-[#ef4444]/20 text-[#ef4444]"
                      : "text-[#55556a] hover:bg-white/5",
                  )}
                  onClick={() => setTradeSide("sell")}
                >
                  Sell
                </button>
              </div>

              {/* Amount input */}
              <div>
                <label className="mb-1 block text-xs text-[#55556a]">
                  Amount
                </label>
                <input
                  type="number"
                  value={tradeAmount}
                  onChange={(e) => setTradeAmount(e.target.value)}
                  placeholder="0.00"
                  className="w-full rounded-lg border border-white/[0.06] bg-[#1a1a24] px-3 py-2 text-sm text-[#e8e8ed] outline-none focus:border-[#06d6a0]/50"
                />
              </div>

              <Button
                className="w-full"
                variant={tradeSide === "buy" ? "success" : "danger"}
                onClick={handleQuickTrade}
                loading={tradeSubmitting}
                disabled={!tradeAmount || !tradeSymbol}
              >
                {tradeSide === "buy" ? "Buy" : "Sell"} {tradeSymbol}
              </Button>
            </div>
          </GlassCard>

          {/* Portfolio Allocation Donut */}
          <GlassCard>
            <h2 className="mb-4 text-lg font-semibold text-[#e8e8ed]">
              Allocation
            </h2>
            {allocationData.length === 0 ? (
              <p className="text-center text-sm text-[#55556a]">
                No positions yet
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={allocationData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={4}
                    stroke="none"
                  >
                    {allocationData.map((_, i) => (
                      <Cell
                        key={i}
                        fill={PIE_COLORS[i % PIE_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "rgba(13,13,18,0.95)",
                      border: "1px solid rgba(255,255,255,0.06)",
                      borderRadius: "0.5rem",
                      color: "#e8e8ed",
                    }}
                    formatter={(value) => formatCurrency(Number(value))}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
            {/* Legend */}
            <div className="mt-2 flex flex-wrap justify-center gap-3">
              {allocationData.map((entry, i) => (
                <div key={entry.name} className="flex items-center gap-1.5">
                  <div
                    className="h-2.5 w-2.5 rounded-full"
                    style={{
                      background: PIE_COLORS[i % PIE_COLORS.length],
                    }}
                  />
                  <span className="text-xs capitalize text-[#8888a0]">
                    {entry.name}
                  </span>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
