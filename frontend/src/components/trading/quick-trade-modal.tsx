"use client";

import { useEffect, useState } from "react";
import { X, ArrowUpRight, ArrowDownRight, Loader2 } from "lucide-react";
import { tradingApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const FEE_RATE = 0.001;
const PRESETS = [10, 25, 50, 100, 500];

interface QuickTradeModalProps {
  symbol: string;
  price: number;
  onClose: () => void;
  onSuccess?: () => void;
  initialSide?: "buy" | "sell";
  initialUsdAmount?: number;
  availableQuote?: number;
  availableBase?: number;
  advisoryText?: string;
}

export function QuickTradeModal({
  symbol,
  price,
  onClose,
  onSuccess,
  initialSide = "buy",
  initialUsdAmount,
  availableQuote,
  availableBase,
  advisoryText,
}: QuickTradeModalProps) {
  const [side, setSide] = useState<"buy" | "sell">(initialSide);
  const [amount, setAmount] = useState(initialUsdAmount ? initialUsdAmount.toFixed(2) : "");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const usdAmount = parseFloat(amount) || 0;
  const cryptoAmount = price > 0 ? usdAmount / price : 0;
  const fee = usdAmount * FEE_RATE;
  const settlementTotal = side === "buy" ? usdAmount + fee : Math.max(usdAmount - fee, 0);

  useEffect(() => {
    setSide(initialSide);
    setAmount(initialUsdAmount ? initialUsdAmount.toFixed(2) : "");
    setResult(null);
  }, [initialSide, initialUsdAmount, symbol]);

  const handleTrade = async () => {
    if (usdAmount <= 0) return;
    setLoading(true);
    setResult(null);
    try {
      await tradingApi.placeOrder({ symbol, side, order_type: "market", quantity: cryptoAmount });
      setResult({ ok: true, msg: `${side === "buy" ? "Bought" : "Sold"} ${cryptoAmount.toFixed(6)} ${symbol}` });
      onSuccess?.();
    } catch {
      setResult({ ok: false, msg: "Order failed. Try again." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center sm:items-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-md rounded-t-[32px] sm:rounded-[32px] p-6 border border-[var(--glass-border)]"
        style={{ background: "var(--surface)", backdropFilter: "blur(28px) saturate(180%)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-[var(--foreground)]">{symbol}</h2>
            <p className="text-sm text-[var(--text-secondary)]">${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
          </div>
          <button onClick={onClose} className="rounded-xl p-2 text-[var(--text-muted)] hover:bg-[var(--glass-bg)]">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Buy/Sell toggle */}
        <div className="mb-5 flex rounded-xl p-1" style={{ background: "var(--glass-bg)" }}>
          <button
            onClick={() => setSide("buy")}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-semibold transition-all",
              side === "buy" ? "bg-[var(--success)] text-white shadow-lg" : "text-[var(--text-secondary)]",
            )}
          >
            <ArrowUpRight className="h-4 w-4" /> Buy
          </button>
          <button
            onClick={() => setSide("sell")}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-semibold transition-all",
              side === "sell" ? "bg-[var(--danger)] text-white shadow-lg" : "text-[var(--text-secondary)]",
            )}
          >
            <ArrowDownRight className="h-4 w-4" /> Sell
          </button>
        </div>

        {/* Advisory text */}
        {advisoryText && (
          <div className="mb-3 rounded-xl border border-[var(--glass-border)] px-4 py-3 text-xs leading-5 text-[var(--text-secondary)]" style={{ background: "var(--glass-bg)" }}>
            {advisoryText}
          </div>
        )}

        {/* Available balance */}
        {(availableQuote != null || availableBase != null) && (
          <div className="mb-3 flex items-center justify-between rounded-xl border border-[var(--glass-border)] px-4 py-2 text-xs" style={{ background: "var(--glass-bg)" }}>
            <span className="text-[var(--text-muted)]">Available</span>
            <span className="text-[var(--text-secondary)]">
              ${Number(availableQuote ?? 0).toFixed(2)} / {Number(availableBase ?? 0).toFixed(6)} {symbol}
            </span>
          </div>
        )}

        {/* Amount input */}
        <div className="mb-4">
          <div className="flex items-center rounded-xl px-5 py-4 border border-[var(--glass-border)]" style={{ background: "var(--glass-bg)" }}>
            <span className="mr-2 text-3xl font-bold text-[var(--text-muted)]">$</span>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className="flex-1 bg-transparent text-3xl font-bold text-[var(--foreground)] outline-none placeholder-[var(--text-muted)]/30"
              autoFocus
            />
          </div>
          {usdAmount > 0 && (
            <p className="mt-1.5 text-right text-xs text-[var(--text-muted)]">
              &asymp; {cryptoAmount.toFixed(6)} {symbol}
            </p>
          )}
        </div>

        {/* Presets */}
        <div className="mb-5 flex gap-2">
          {PRESETS.map((p) => (
            <button
              key={p}
              onClick={() => setAmount(String(p))}
              className={cn(
                "flex-1 rounded-xl py-2.5 text-xs font-medium transition-all border",
                amount === String(p)
                  ? "border-[var(--page-accent)]/30 bg-[var(--page-accent)]/12 text-[var(--page-accent)]"
                  : "border-[var(--glass-border)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]",
              )}
              style={amount !== String(p) ? { background: "var(--glass-bg)" } : undefined}
            >
              ${p}
            </button>
          ))}
        </div>

        {/* Fee summary */}
        {usdAmount > 0 && (
          <div className="mb-5 space-y-2 rounded-xl p-4 border border-[var(--glass-border)]" style={{ background: "var(--glass-bg)" }}>
            <div className="flex justify-between text-xs">
              <span className="text-[var(--text-muted)]">Amount</span>
              <span className="text-[var(--text-secondary)]">${usdAmount.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-[var(--text-muted)]">Fee ({(FEE_RATE * 100).toFixed(1)}%)</span>
              <span className="text-[var(--text-secondary)]">${fee.toFixed(2)}</span>
            </div>
            <div className="flex justify-between border-t border-[var(--glass-border)] pt-2 text-xs font-semibold">
              <span className="text-[var(--text-secondary)]">{side === "buy" ? "Estimated cost" : "Estimated proceeds"}</span>
              <span className="text-[var(--foreground)]">${settlementTotal.toFixed(2)}</span>
            </div>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className={cn("mb-4 rounded-xl p-3 text-center text-sm", result.ok ? "bg-[var(--success)]/12 text-[var(--success)]" : "bg-[var(--danger)]/12 text-[var(--danger)]")}>
            {result.msg}
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleTrade}
          disabled={usdAmount <= 0 || loading}
          className={cn(
            "w-full rounded-xl py-4 text-base font-bold transition-all disabled:opacity-40",
            side === "buy" ? "bg-[var(--success)] text-white hover:brightness-110" : "bg-[var(--danger)] text-white hover:brightness-110",
          )}
        >
          {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : `${side === "buy" ? "Buy" : "Sell"} ${symbol}`}
        </button>
      </div>
    </div>
  );
}
