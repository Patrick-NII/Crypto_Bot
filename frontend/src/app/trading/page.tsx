"use client";

import { useEffect, useState, useCallback } from "react";
import {
  DollarSign,
  ShoppingCart,
  XCircle,
  Clock,
  ArrowUpDown,
} from "lucide-react";
import { tradingApi } from "@/lib/api";
import type {
  Order,
  OrderSide,
  OrderType,
  PaperBalance,
} from "@/lib/types";
import { formatCurrency, formatTime, formatDate, cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

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

const POPULAR_SYMBOLS = [
  "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT",
  "AVAX", "MATIC", "LINK", "UNI",
];

export default function TradingPage() {
  const [loading, setLoading] = useState(true);
  const [balances, setBalances] = useState<PaperBalance[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);

  // Order form state
  const [symbol, setSymbol] = useState("BTC");
  const [symbolInput, setSymbolInput] = useState("BTC");
  const [showAutocomplete, setShowAutocomplete] = useState(false);
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

  const filteredSymbols = POPULAR_SYMBOLS.filter((s) =>
    s.toLowerCase().includes(symbolInput.toLowerCase()),
  );

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
        <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-white">
          <DollarSign className="h-5 w-5 text-accent-purple" />
          Paper Trading Balances
        </h2>
        {balances.length === 0 ? (
          <p className="text-sm text-white/40">No balances available</p>
        ) : (
          <div className="flex flex-wrap gap-4">
            {balances.map((b) => (
              <div
                key={b.currency}
                className="rounded-lg border border-white/5 bg-white/[0.03] px-4 py-3"
              >
                <span className="text-xs font-medium uppercase text-white/40">
                  {b.currency}
                </span>
                <p className="text-lg font-bold text-white">
                  {formatCurrency(b.total)}
                </p>
                <div className="flex gap-3 text-xs text-white/40">
                  <span>Avail: {formatCurrency(b.available)}</span>
                  <span>Reserved: {formatCurrency(b.reserved)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Order Form */}
        <GlassCard>
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <ShoppingCart className="h-5 w-5 text-accent-purple" />
            Place Order
          </h2>
          <div className="space-y-4">
            {/* Symbol with autocomplete */}
            <div className="relative">
              <label className="mb-1 block text-xs text-white/40">Symbol</label>
              <input
                type="text"
                value={symbolInput}
                onChange={(e) => {
                  setSymbolInput(e.target.value.toUpperCase());
                  setShowAutocomplete(true);
                }}
                onFocus={() => setShowAutocomplete(true)}
                onBlur={() => setTimeout(() => setShowAutocomplete(false), 200)}
                placeholder="BTC"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent-purple"
              />
              {showAutocomplete && filteredSymbols.length > 0 && (
                <div className="absolute z-20 mt-1 w-full rounded-lg border border-white/10 bg-[#0a0a1a] shadow-xl">
                  {filteredSymbols.map((s) => (
                    <button
                      key={s}
                      className="w-full px-3 py-2 text-left text-sm text-white/70 hover:bg-white/5 hover:text-white"
                      onMouseDown={() => {
                        setSymbol(s);
                        setSymbolInput(s);
                        setShowAutocomplete(false);
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Side toggle */}
            <div>
              <label className="mb-1 block text-xs text-white/40">Side</label>
              <div className="flex overflow-hidden rounded-lg border border-white/10">
                <button
                  className={cn(
                    "flex-1 py-2.5 text-sm font-semibold transition-colors",
                    side === "buy"
                      ? "bg-success/20 text-success"
                      : "text-white/40 hover:bg-white/5",
                  )}
                  onClick={() => setSide("buy")}
                >
                  Buy
                </button>
                <button
                  className={cn(
                    "flex-1 py-2.5 text-sm font-semibold transition-colors",
                    side === "sell"
                      ? "bg-danger/20 text-danger"
                      : "text-white/40 hover:bg-white/5",
                  )}
                  onClick={() => setSide("sell")}
                >
                  Sell
                </button>
              </div>
            </div>

            {/* Order type */}
            <div>
              <label className="mb-1 block text-xs text-white/40">
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
                        ? "border-accent-purple/30 bg-accent-purple/20 text-accent-purple"
                        : "border-white/10 text-white/40 hover:bg-white/5 hover:text-white/60",
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
              <label className="mb-1 block text-xs text-white/40">
                Quantity
              </label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="0.00"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent-purple"
              />
            </div>

            {/* Limit price */}
            {orderType === "limit" && (
              <div>
                <label className="mb-1 block text-xs text-white/40">
                  Limit Price
                </label>
                <input
                  type="number"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="0.00"
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent-purple"
                />
              </div>
            )}

            {/* Stop price */}
            {orderType === "stop_loss" && (
              <div>
                <label className="mb-1 block text-xs text-white/40">
                  Stop Price
                </label>
                <input
                  type="number"
                  value={stopPrice}
                  onChange={(e) => setStopPrice(e.target.value)}
                  placeholder="0.00"
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent-purple"
                />
              </div>
            )}

            {/* Risk indicator */}
            <div className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-xs text-white/40">
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
                    ? "border-success/20 bg-success/10 text-success"
                    : "border-danger/20 bg-danger/10 text-danger",
                )}
              >
                {submitResult.msg}
              </div>
            )}
          </div>
        </GlassCard>

        {/* Order History */}
        <GlassCard className="lg:col-span-2">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <Clock className="h-5 w-5 text-accent-purple" />
            Order History
          </h2>
          {orders.length === 0 ? (
            <p className="text-sm text-white/40">No orders yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wider text-white/40">
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
                      className="border-b border-white/5 transition-colors hover:bg-white/[0.02]"
                    >
                      <td className="py-3 pr-3 text-white/50">
                        <div className="text-xs">
                          {formatDate(order.created_at)}
                        </div>
                        <div className="text-xs text-white/30">
                          {formatTime(order.created_at)}
                        </div>
                      </td>
                      <td className="py-3 pr-3 font-semibold text-white">
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
                      <td className="py-3 pr-3 text-white/50">
                        {order.order_type}
                      </td>
                      <td className="py-3 pr-3 text-right font-mono text-white/70">
                        {order.quantity}
                      </td>
                      <td className="py-3 pr-3 text-right font-mono text-white/70">
                        {formatCurrency(
                          order.filled_price ?? order.price ?? 0,
                        )}
                      </td>
                      <td className="py-3 pr-3">
                        <Badge variant={statusVariant(order.status)}>
                          {order.status}
                        </Badge>
                      </td>
                      <td className="hidden py-3 pr-3 text-right font-mono text-white/40 sm:table-cell">
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
