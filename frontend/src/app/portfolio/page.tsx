"use client";

import { useEffect, useState, useCallback } from "react";
import { usePageAccent, PAGE_ACCENTS } from "@/components/providers/theme-provider";
import {
  Wallet,
  TrendingUp,
  Percent,
  Plus,
  X,
  Edit3,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { portfolioApi } from "@/lib/api";
import type { Portfolio, Position, Transaction } from "@/lib/types";
import { formatCurrency, formatPercent, formatRelative, cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/glass-card";
import { StatCard } from "@/components/ui/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PriceChart } from "@/components/charts/price-chart";

const PIE_COLORS = ["#06d6a0", "#c6f135", "#06b6d4", "#3b82f6", "#8b5cf6", "#ef4444"];

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-white/5", className)} />;
}

export default function PortfolioPage() {
  usePageAccent(PAGE_ACCENTS.portfolio.accent, PAGE_ACCENTS.portfolio.glow);
  const [loading, setLoading] = useState(true);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [activePortfolio, setActivePortfolio] = useState<Portfolio | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  // Stop-loss editing
  const [editingStopLoss, setEditingStopLoss] = useState<string | null>(null);
  const [stopLossValue, setStopLossValue] = useState("");

  // Sort state
  const [sortField, setSortField] = useState<"symbol" | "pnl" | "pnl_pct">("pnl");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Expanded position for mini chart
  const [expandedPosition, setExpandedPosition] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const data = await portfolioApi.list();
      setPortfolios(data);
      if (data.length > 0) {
        const p = data[0];
        setActivePortfolio(p);
        const [posData, txData] = await Promise.allSettled([
          portfolioApi.getPositions(p.id),
          portfolioApi.getTransactions(p.id),
        ]);
        if (posData.status === "fulfilled") setPositions(posData.value);
        if (txData.status === "fulfilled") setTransactions(txData.value.slice(0, 10));
      }
    } catch {
      // handle error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await portfolioApi.create({ name: newName, description: newDesc });
      setNewName("");
      setNewDesc("");
      setShowCreateForm(false);
      fetchData();
    } catch {
      // handle error
    } finally {
      setCreating(false);
    }
  };

  const handleClosePosition = async (positionId: string) => {
    try {
      await portfolioApi.closePosition(positionId);
      fetchData();
    } catch {
      // handle error
    }
  };

  const handleUpdateStopLoss = async (positionId: string) => {
    if (!stopLossValue || isNaN(Number(stopLossValue))) return;
    try {
      await portfolioApi.updateStopLoss(positionId, Number(stopLossValue));
      setEditingStopLoss(null);
      setStopLossValue("");
      fetchData();
    } catch {
      // handle error
    }
  };

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const sortedPositions = [...positions].sort((a, b) => {
    const mult = sortDir === "asc" ? 1 : -1;
    if (sortField === "symbol") return mult * a.symbol.localeCompare(b.symbol);
    return mult * ((a[sortField] ?? 0) - (b[sortField] ?? 0));
  });

  // Allocation chart data
  const allocationData = positions.reduce<Record<string, number>>((acc, p) => {
    const type = p.asset_type || "other";
    acc[type] = (acc[type] || 0) + p.current_price * p.quantity;
    return acc;
  }, {});
  const pieData = Object.entries(allocationData).map(([name, value]) => ({
    name,
    value,
  }));

  const SortIcon = ({ field }: { field: typeof sortField }) => {
    if (sortField !== field) return null;
    return sortDir === "asc" ? (
      <ChevronUp className="inline h-3 w-3" />
    ) : (
      <ChevronDown className="inline h-3 w-3" />
    );
  };

  if (loading) {
    return (
      <div className="relative z-10 min-h-screen p-4 md:p-8">
        <h1 className="mb-8 text-3xl font-bold glow-text">Portfolio</h1>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonBlock key={i} className="h-24" />
          ))}
        </div>
        <SkeletonBlock className="mt-6 h-96" />
      </div>
    );
  }

  const totalValue = activePortfolio?.total_value ?? 0;
  const totalPnl = activePortfolio?.total_pnl ?? 0;
  const totalPnlPct = activePortfolio?.total_pnl_pct ?? 0;

  return (
    <div className="relative z-10 min-h-screen p-4 md:p-8">
      {/* Header */}
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-3xl font-bold glow-text">Portfolio</h1>
        <Button onClick={() => setShowCreateForm(!showCreateForm)}>
          <Plus className="h-4 w-4" />
          Create Portfolio
        </Button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <GlassCard className="mb-6">
          <h3 className="mb-4 text-base font-semibold text-[#e8e8ed]">
            New Portfolio
          </h3>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className="mb-1 block text-xs text-[#55556a]">Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="My Portfolio"
                className="w-full rounded-lg border border-white/[0.06] bg-[#1a1a24] px-3 py-2 text-sm text-[#e8e8ed] outline-none focus:border-[#06d6a0]/50"
              />
            </div>
            <div className="flex-1">
              <label className="mb-1 block text-xs text-[#55556a]">
                Description
              </label>
              <input
                type="text"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Optional description"
                className="w-full rounded-lg border border-white/[0.06] bg-[#1a1a24] px-3 py-2 text-sm text-[#e8e8ed] outline-none focus:border-[#06d6a0]/50"
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleCreate} loading={creating}>
                Create
              </Button>
              <Button
                variant="ghost"
                onClick={() => setShowCreateForm(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        </GlassCard>
      )}

      {/* Portfolio tabs (if multiple) */}
      {portfolios.length > 1 && (
        <div className="mb-6 flex gap-2 overflow-x-auto">
          {portfolios.map((p) => (
            <button
              key={p.id}
              onClick={async () => {
                setActivePortfolio(p);
                const [posData, txData] = await Promise.allSettled([
                  portfolioApi.getPositions(p.id),
                  portfolioApi.getTransactions(p.id),
                ]);
                if (posData.status === "fulfilled") setPositions(posData.value);
                if (txData.status === "fulfilled")
                  setTransactions(txData.value.slice(0, 10));
              }}
              className={cn(
                "shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
                activePortfolio?.id === p.id
                  ? "bg-[#06d6a0]/20 text-[#06d6a0] border border-[#06d6a0]/30"
                  : "border border-white/[0.06] text-[#8888a0] hover:text-[#e8e8ed] hover:bg-white/5",
              )}
            >
              {p.name}
            </button>
          ))}
        </div>
      )}

      {/* Summary Cards */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          title="Total Value"
          value={formatCurrency(totalValue)}
          icon={Wallet}
        />
        <StatCard
          title="Total P&L"
          value={formatCurrency(totalPnl)}
          trend={totalPnl >= 0 ? "up" : "down"}
          icon={TrendingUp}
        />
        <StatCard
          title="P&L %"
          value={formatPercent(totalPnlPct)}
          trend={totalPnlPct >= 0 ? "up" : "down"}
          icon={Percent}
        />
      </div>

      {/* Main content: positions table + allocation chart */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Positions Table (2/3) */}
        <GlassCard className="lg:col-span-2">
          <h2 className="mb-4 text-lg font-semibold text-[#e8e8ed]">Positions</h2>
          {sortedPositions.length === 0 ? (
            <p className="text-sm text-[#55556a]">No open positions</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06] text-left text-xs uppercase tracking-wider text-[#55556a]">
                    <th
                      className="cursor-pointer pb-3 pr-3"
                      onClick={() => toggleSort("symbol")}
                    >
                      Asset <SortIcon field="symbol" />
                    </th>
                    <th className="pb-3 pr-3">Type</th>
                    <th className="pb-3 pr-3 text-right">Qty</th>
                    <th className="hidden pb-3 pr-3 text-right sm:table-cell">
                      Avg Entry
                    </th>
                    <th className="pb-3 pr-3 text-right">Current</th>
                    <th
                      className="cursor-pointer pb-3 pr-3 text-right"
                      onClick={() => toggleSort("pnl")}
                    >
                      P&L <SortIcon field="pnl" />
                    </th>
                    <th
                      className="cursor-pointer pb-3 pr-3 text-right"
                      onClick={() => toggleSort("pnl_pct")}
                    >
                      P&L% <SortIcon field="pnl_pct" />
                    </th>
                    <th className="pb-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedPositions.map((pos) => (
                    <>
                      <tr
                        key={pos.id}
                        className="border-b border-white/[0.06] transition-colors hover:bg-white/[0.02] cursor-pointer"
                        onClick={() =>
                          setExpandedPosition(
                            expandedPosition === pos.id ? null : pos.id,
                          )
                        }
                      >
                        <td className="py-3 pr-3 font-semibold text-[#e8e8ed]">
                          {pos.symbol}
                        </td>
                        <td className="py-3 pr-3">
                          <Badge variant="info">{pos.asset_type}</Badge>
                        </td>
                        <td className="py-3 pr-3 text-right font-mono text-[#8888a0]">
                          {pos.quantity}
                        </td>
                        <td className="hidden py-3 pr-3 text-right font-mono text-[#8888a0] sm:table-cell">
                          {formatCurrency(pos.avg_entry_price)}
                        </td>
                        <td className="py-3 pr-3 text-right font-mono text-[#e8e8ed]">
                          {formatCurrency(pos.current_price)}
                        </td>
                        <td
                          className={cn(
                            "py-3 pr-3 text-right font-mono font-semibold",
                            pos.pnl >= 0 ? "text-[#06d6a0]" : "text-[#ef4444]",
                          )}
                        >
                          {formatCurrency(pos.pnl)}
                        </td>
                        <td
                          className={cn(
                            "py-3 pr-3 text-right font-mono font-semibold",
                            pos.pnl_pct >= 0 ? "text-[#06d6a0]" : "text-[#ef4444]",
                          )}
                        >
                          {formatPercent(pos.pnl_pct)}
                        </td>
                        <td
                          className="py-3 text-right"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <div className="flex items-center justify-end gap-1">
                            {editingStopLoss === pos.id ? (
                              <div className="flex items-center gap-1">
                                <input
                                  type="number"
                                  value={stopLossValue}
                                  onChange={(e) =>
                                    setStopLossValue(e.target.value)
                                  }
                                  placeholder="Stop price"
                                  className="w-20 rounded border border-white/[0.06] bg-[#1a1a24] px-2 py-1 text-xs text-[#e8e8ed] outline-none"
                                />
                                <Button
                                  size="sm"
                                  onClick={() => handleUpdateStopLoss(pos.id)}
                                >
                                  Set
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => setEditingStopLoss(null)}
                                >
                                  <X className="h-3 w-3" />
                                </Button>
                              </div>
                            ) : (
                              <>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => {
                                    setEditingStopLoss(pos.id);
                                    setStopLossValue(
                                      pos.stop_loss?.toString() ?? "",
                                    );
                                  }}
                                  title="Edit stop-loss"
                                >
                                  <Edit3 className="h-3 w-3" />
                                </Button>
                                <Button
                                  size="sm"
                                  variant="danger"
                                  onClick={() => handleClosePosition(pos.id)}
                                >
                                  Close
                                </Button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                      {/* Expanded mini chart row */}
                      {expandedPosition === pos.id && (
                        <tr key={`${pos.id}-chart`}>
                          <td colSpan={8} className="p-3">
                            <div className="rounded-lg border border-white/[0.06] bg-[#14141b] p-3">
                              <PriceChart
                                symbol={pos.symbol}
                                height={120}
                                type="line"
                              />
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCard>

        {/* Allocation Chart (1/3) */}
        <GlassCard>
          <h2 className="mb-4 text-lg font-semibold text-[#e8e8ed]">Allocation</h2>
          {pieData.length === 0 ? (
            <p className="text-center text-sm text-[#55556a]">
              No positions to display
            </p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={4}
                    stroke="none"
                  >
                    {pieData.map((_, i) => (
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
              <div className="mt-3 flex flex-wrap justify-center gap-3">
                {pieData.map((entry, i) => (
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
            </>
          )}
        </GlassCard>
      </div>

      {/* Recent Transactions */}
      <GlassCard className="mt-6">
        <h2 className="mb-4 text-lg font-semibold text-[#e8e8ed]">
          Recent Transactions
        </h2>
        {transactions.length === 0 ? (
          <p className="text-sm text-[#55556a]">No transactions yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06] text-left text-xs uppercase tracking-wider text-[#55556a]">
                  <th className="pb-3 pr-3">Time</th>
                  <th className="pb-3 pr-3">Symbol</th>
                  <th className="pb-3 pr-3">Side</th>
                  <th className="pb-3 pr-3 text-right">Qty</th>
                  <th className="pb-3 pr-3 text-right">Price</th>
                  <th className="pb-3 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr
                    key={tx.id}
                    className="border-b border-white/[0.06] transition-colors hover:bg-white/[0.02]"
                  >
                    <td className="py-3 pr-3 text-[#8888a0]">
                      {formatRelative(tx.timestamp)}
                    </td>
                    <td className="py-3 pr-3 font-semibold text-[#e8e8ed]">
                      {tx.symbol}
                    </td>
                    <td className="py-3 pr-3">
                      <Badge variant={tx.side === "buy" ? "success" : "danger"}>
                        {tx.side.toUpperCase()}
                      </Badge>
                    </td>
                    <td className="py-3 pr-3 text-right font-mono text-[#8888a0]">
                      {tx.quantity}
                    </td>
                    <td className="py-3 pr-3 text-right font-mono text-[#8888a0]">
                      {formatCurrency(tx.price)}
                    </td>
                    <td className="py-3 text-right font-mono text-[#e8e8ed]">
                      {formatCurrency(tx.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
