"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { usePageAccent, PAGE_ACCENTS } from "@/components/providers/theme-provider";
import {
  DollarSign,
  ShoppingCart,
  XCircle,
  Clock,
  ArrowUpDown,
  Search,
} from "lucide-react";
import { pricesApi, tradingApi } from "@/lib/api";
import type {
  Order,
  OrderSide,
  OrderType,
  PaperBalance,
  AssetSearchResult,
} from "@/lib/types";
import { formatCurrency, formatTime, formatDate, cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PriceChart } from "@/components/charts/price-chart";

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-white/5", className)} />;
}

// Status badge variant helper
function statusVariant(status: string) {
  switch (status) {
    case "filled":
      return "success" as const;
    case "open":
      return "info" as const;
    case "cancelled":
      return "default" as const;
    case "failed":
      return "danger" as const;
    case "partial":
      return "warning" as const;
    default:
      return "default" as const;
  }
}

export default function TradingPage() {
  usePageAccent(PAGE_ACCENTS.trading.accent, PAGE_ACCENTS.trading.glow);
  const [loading, setLoading] = useState(true);
  const [balances, setBalances] = useState<PaperBalance[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);

  // Symbol search state
  const [symbol, setSymbol] = useState("BTC");
  const [searchQuery, setSearchQuery] = useState("BTC");
  const [searchResults, setSearchResults] = useState<AssetSearchResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searching, setSearching] = useState(false);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Order form state
  const [side, setSide] = useState<OrderSide>("buy");
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [stopPrice, setStopPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{
    ok: boolean;
    msg: string;
  } | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [bal, ord] = await Promise.allSettled([
        tradingApi.getBalances(),
        tradingApi.getOrders(),
      ]);
      if (bal.status === "fulfilled") setBalances(bal.value);
      if (ord.status === "fulfilled") setOrders(ord.value);
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Debounced search
  const handleSearchChange = (query: string) => {
    setSearchQuery(query.toUpperCase());
    setShowDropdown(true);

    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    if (query.length < 1) {
      setSearchResults([]);
      return;
    }

    searchTimeoutRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await pricesApi.searchAssets(query, 10);
        setSearchResults(res.results);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
  };

  const selectSymbol = (s: AssetSearchResult) => {
    setSymbol(s.symbol);
    setSearchQuery(s.symbol);
    setShowDropdown(false);
  };

  const handleSubmit = async () => {
    if (!quantity || isNaN(Number(quantity))) return;
    setSubmitting(true);
    setSubmitResult(null);

    try {
      const payload: Parameters<typeof tradingApi.placeOrder>[0] = {
        symbol,
        side,
        order_type: orderType,
        quantity: Number(quantity),
      };
      if (orderType === "limit" && price) payload.price = Number(price);
      if (orderType === "stop_loss" && stopPrice)
        payload.stop_price = Number(stopPrice);

      const result = await tradingApi.placeOrder(payload);
      setSubmitResult({
        ok: true,
        msg: `Order ${result.status}: ${result.order_id}`,
      });
      setQuantity("");
      setPrice("");
      setStopPrice("");
      fetchData();
    } catch (err) {
      setSubmitResult({
        ok: false,
        msg: err instanceof Error ? err.message : "Order failed",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async (orderId: string) => {
    try {
      await tradingApi.cancelOrder(orderId);
      fetchData();
    } catch {
      // handle error
    }
  };

  if (loading) {
    return (
      <div className="relative z-10 min-h-screen p-4 md:p-8">
        <h1 className="mb-8 text-3xl font-bold glow-text">Trading</h1>
        <SkeletonBlock className="h-24" />
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <SkeletonBlock className="h-96" />
          <SkeletonBlock className="lg:col-span-2 h-96" />
        </div>
      </div>
    );
  }

  return (
    <div className="relative z-10 min-h-screen p-4 md:p-8">
      <h1 className="mb-8 text-3xl font-bold glow-text">Trading</h1>

      {/* Paper Trading Balances */}
      <GlassCard className="mb-6">
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-[#e8e8ed]">
          <DollarSign className="h-5 w-5 text-[#06d6a0]" />
          Paper Trading Balances
        </h2>
        {balances.length === 0 ? (
          <p className="text-sm text-[#55556a]">No balances available</p>
        ) : (
          <div className="flex flex-wrap gap-4">
            {balances.map((b) => (
              <div
                key={b.currency}
                className="rounded-lg border border-white/[0.06] bg-[#14141b] px-4 py-3"
              >
                <span className="text-xs font-medium uppercase text-[#55556a]">
                  {b.currency}
                </span>
                <p className="text-lg font-bold text-[#e8e8ed]">
                  {formatCurrency(b.total)}
                </p>
                <div className="flex gap-3 text-xs text-[#55556a]">
                  <span>Avail: <span className="text-[#06d6a0]">{formatCurrency(b.available)}</span></span>
                  <span>Reserved: {formatCurrency(b.reserved)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      {/* Price chart for selected symbol */}
      <GlassCard className="mb-6">
        <h2 className="mb-3 text-lg font-semibold text-[#e8e8ed]">
          {symbol} Chart
        </h2>
        <PriceChart symbol={symbol} height={300} type="candlestick" />
      </GlassCard>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Order Form */}
        <GlassCard>
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-[#e8e8ed]">
            <ShoppingCart className="h-5 w-5 text-[#06d6a0]" />
            Place Order
          </h2>
          <div className="space-y-4">
            {/* Symbol search input */}
            <div className="relative">
              <label className="mb-1 block text-xs text-[#55556a]">Symbol</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#55556a]" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  onFocus={() => setShowDropdown(true)}
                  onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
                  placeholder="Search symbol..."
                  className="w-full rounded-lg border border-white/[0.06] bg-[#1a1a24] pl-9 pr-3 py-2 text-sm text-[#e8e8ed] outline-none focus:border-[#06d6a0]/50"
                />
              </div>
              {showDropdown && (searchResults.length > 0 || searching) && (
                <div className="absolute z-20 mt-1 w-full rounded-lg border border-white/[0.06] bg-[#0d0d12] shadow-xl max-h-60 overflow-y-auto">
                  {searching && (
                    <div className="px-3 py-2 text-xs text-[#55556a]">
                      Searching...
                    </div>
                  )}
                  {searchResults.map((s) => (
                    <button
                      key={s.symbol}
                      className="w-full px-3 py-2 text-left text-sm text-[#8888a0] hover:bg-white/5 hover:text-[#e8e8ed] flex items-center justify-between"
                      onMouseDown={() => selectSymbol(s)}
                    >
                      <div>
                        <span className="font-semibold text-[#e8e8ed]">{s.symbol}</span>
                        <span className="ml-2 text-xs text-[#55556a]">{s.name}</span>
                      </div>
                      {s.price !== undefined && (
                        <span className="text-xs font-mono text-[#8888a0]">
                          {formatCurrency(s.price)}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Side toggle */}
            <div>
              <label className="mb-1 block text-xs text-[#55556a]">Side</label>
              <div className="flex overflow-hidden rounded-lg border border-white/[0.06]">
                <button
                  className={cn(
                    "flex-1 py-2.5 text-sm font-semibold transition-colors",
                    side === "buy"
                      ? "bg-[#06d6a0]/20 text-[#06d6a0]"
                      : "text-[#55556a] hover:bg-white/5",
                  )}
                  onClick={() => setSide("buy")}
                >
                  Buy
                </button>
                <button
                  className={cn(
                    "flex-1 py-2.5 text-sm font-semibold transition-colors",
                    side === "sell"
                      ? "bg-[#ef4444]/20 text-[#ef4444]"
                      : "text-[#55556a] hover:bg-white/5",
                  )}
                  onClick={() => setSide("sell")}
                >
                  Sell
                </button>
              </div>
            </div>

            {/* Order type */}
            <div>
              <label className="mb-1 block text-xs text-[#55556a]">
                Order Type
              </label>
              <div className="flex gap-2">
                {(
                  [
                    ["market", "Market"],
                    ["limit", "Limit"],
                    ["stop_loss", "Stop-Loss"],
                  ] as const
                ).map(([type, label]) => (
                  <button
                    key={type}
                    className={cn(
                      "flex-1 rounded-lg border py-2 text-xs font-semibold transition-colors",
                      orderType === type
                        ? "border-[#06d6a0]/30 bg-[#06d6a0]/20 text-[#06d6a0]"
                        : "border-white/[0.06] text-[#55556a] hover:bg-white/5 hover:text-[#8888a0]",
                    )}
                    onClick={() => setOrderType(type)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Quantity */}
            <div>
              <label className="mb-1 block text-xs text-[#55556a]">
                Quantity
              </label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="0.00"
                className="w-full rounded-lg border border-white/[0.06] bg-[#1a1a24] px-3 py-2 text-sm text-[#e8e8ed] outline-none focus:border-[#06d6a0]/50"
              />
            </div>

            {/* Limit price */}
            {orderType === "limit" && (
              <div>
                <label className="mb-1 block text-xs text-[#55556a]">
                  Limit Price
                </label>
                <input
                  type="number"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="0.00"
                  className="w-full rounded-lg border border-white/[0.06] bg-[#1a1a24] px-3 py-2 text-sm text-[#e8e8ed] outline-none focus:border-[#06d6a0]/50"
                />
              </div>
            )}

            {/* Stop price */}
            {orderType === "stop_loss" && (
              <div>
                <label className="mb-1 block text-xs text-[#55556a]">
                  Stop Price
                </label>
                <input
                  type="number"
                  value={stopPrice}
                  onChange={(e) => setStopPrice(e.target.value)}
                  placeholder="0.00"
                  className="w-full rounded-lg border border-white/[0.06] bg-[#1a1a24] px-3 py-2 text-sm text-[#e8e8ed] outline-none focus:border-[#06d6a0]/50"
                />
              </div>
            )}

            {/* Risk indicator */}
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-xs text-[#55556a]">
              <ArrowUpDown className="mr-1 inline h-3 w-3" />
              Risk check: {orderType === "market" ? "Market order" : "Limit order"}{" "}
              {side === "buy" ? "buying" : "selling"} {quantity || "0"} {symbol}
            </div>

            {/* Submit */}
            <Button
              className="w-full"
              variant={side === "buy" ? "success" : "danger"}
              onClick={handleSubmit}
              loading={submitting}
              disabled={!quantity}
            >
              {side === "buy" ? "Buy" : "Sell"} {symbol}
            </Button>

            {/* Result feedback */}
            {submitResult && (
              <div
                className={cn(
                  "rounded-lg border px-3 py-2 text-xs",
                  submitResult.ok
                    ? "border-[#06d6a0]/20 bg-[#06d6a0]/10 text-[#06d6a0]"
                    : "border-[#ef4444]/20 bg-[#ef4444]/10 text-[#ef4444]",
                )}
              >
                {submitResult.msg}
              </div>
            )}
          </div>
        </GlassCard>

        {/* Order History */}
        <GlassCard className="lg:col-span-2">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-[#e8e8ed]">
            <Clock className="h-5 w-5 text-[#06d6a0]" />
            Order History
          </h2>
          {orders.length === 0 ? (
            <p className="text-sm text-[#55556a]">No orders yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06] text-left text-xs uppercase tracking-wider text-[#55556a]">
                    <th className="pb-3 pr-3">Time</th>
                    <th className="pb-3 pr-3">Symbol</th>
                    <th className="pb-3 pr-3">Side</th>
                    <th className="pb-3 pr-3">Type</th>
                    <th className="pb-3 pr-3 text-right">Qty</th>
                    <th className="pb-3 pr-3 text-right">Price</th>
                    <th className="pb-3 pr-3">Status</th>
                    <th className="hidden pb-3 pr-3 text-right sm:table-cell">
                      Fee
                    </th>
                    <th className="pb-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr
                      key={order.id}
                      className="border-b border-white/[0.06] transition-colors hover:bg-white/[0.02]"
                    >
                      <td className="py-3 pr-3 text-[#8888a0]">
                        <div className="text-xs">
                          {formatDate(order.created_at)}
                        </div>
                        <div className="text-xs text-[#55556a]">
                          {formatTime(order.created_at)}
                        </div>
                      </td>
                      <td className="py-3 pr-3 font-semibold text-[#e8e8ed]">
                        {order.symbol}
                      </td>
                      <td className="py-3 pr-3">
                        <Badge
                          variant={
                            order.side === "buy" ? "success" : "danger"
                          }
                        >
                          {order.side.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="py-3 pr-3 text-[#8888a0]">
                        {order.order_type}
                      </td>
                      <td className="py-3 pr-3 text-right font-mono text-[#8888a0]">
                        {order.quantity}
                      </td>
                      <td className="py-3 pr-3 text-right font-mono text-[#8888a0]">
                        {formatCurrency(
                          order.filled_price ?? order.price ?? 0,
                        )}
                      </td>
                      <td className="py-3 pr-3">
                        <Badge variant={statusVariant(order.status)}>
                          {order.status}
                        </Badge>
                      </td>
                      <td className="hidden py-3 pr-3 text-right font-mono text-[#55556a] sm:table-cell">
                        {order.fee ? formatCurrency(order.fee) : "-"}
                      </td>
                      <td className="py-3 text-right">
                        {order.status === "open" && (
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => handleCancel(order.id)}
                          >
                            <XCircle className="h-3 w-3" />
                            Cancel
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
