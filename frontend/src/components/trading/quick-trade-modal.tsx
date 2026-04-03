"use client";

import { useState } from "react";
import { X, ArrowUpRight, ArrowDownRight, Loader2 } from "lucide-react";
import { tradingApi } from "@/lib/api";
import { cn } from "@/lib/utils";

interface QuickTradeModalProps {
  symbol: string;
  price: number;
  onClose: () => void;
  onSuccess?: () => void;
}

export function QuickTradeModal({ symbol, price, onClose, onSuccess }: QuickTradeModalProps) {
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const usdAmount = parseFloat(amount) || 0;
  const cryptoAmount = price > 0 ? usdAmount / price : 0;
  const fee = usdAmount * 0.001;
  const presets = [10, 25, 50, 100, 500];

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
        className="relative w-full max-w-md liquid-glass-strong rounded-t-[32px] sm:rounded-[32px] p-6"
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

        {/* Buy/Sell toggle — pill segmented */}
        <div className="mb-5 flex liquid-glass-pill p-1">
          <button
            onClick={() => setSide("buy")}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-full py-2.5 text-sm font-semibold transition-all",
              side === "buy" ? "bg-[#22c55e] text-white shadow-lg" : "text-[var(--text-secondary)]",
            )}
          >
            <ArrowUpRight className="h-4 w-4" /> Buy
          </button>
          <button
            onClick={() => setSide("sell")}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-full py-2.5 text-sm font-semibold transition-all",
              side === "sell" ? "bg-[#ef4444] text-white shadow-lg" : "text-[var(--text-secondary)]",
            )}
          >
            <ArrowDownRight className="h-4 w-4" /> Sell
          </button>
        </div>

        {/* Amount input */}
        <div className="mb-4">
          <div className="flex items-center liquid-glass-pill px-5 py-4">
            <span className="mr-2 text-3xl font-bold text-[var(--text-muted)]">$</span>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className="flex-1 bg-transparent text-3xl font-bold text-[var(--foreground)] outline-none placeholder-[var(--elevated)]"
              autoFocus
            />
          </div>
          {usdAmount > 0 && (
            <p className="mt-1.5 text-right text-xs text-[var(--text-muted)]">
              ≈ {cryptoAmount.toFixed(6)} {symbol}
            </p>
          )}
        </div>

        {/* Presets */}
        <div className="mb-5 flex gap-2">
          {presets.map((p) => (
            <button
              key={p}
              onClick={() => setAmount(String(p))}
              className={cn(
                "flex-1 rounded-2xl py-2.5 text-xs font-medium transition-all",
                amount === String(p) ? "accent-bg accent-text" : "liquid-glass-pill text-[var(--text-muted)] hover:text-[var(--text-secondary)]",
              )}
            >
              ${p}
            </button>
          ))}
        </div>

        {/* Fee summary */}
        {usdAmount > 0 && (
          <div className="mb-5 space-y-2 liquid-glass-pill p-4">
            <div className="flex justify-between text-xs">
              <span className="text-[var(--text-muted)]">Amount</span>
              <span className="text-[var(--text-secondary)]">${usdAmount.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-[var(--text-muted)]">Fee (0.1%)</span>
              <span className="text-[var(--text-secondary)]">${fee.toFixed(2)}</span>
            </div>
            <div className="flex justify-between border-t border-[var(--glass-border)] pt-2 text-xs font-semibold">
              <span className="text-[var(--text-secondary)]">Total</span>
              <span className="text-[var(--foreground)]">${(usdAmount + fee).toFixed(2)}</span>
            </div>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className={cn("mb-4 rounded-2xl p-3 text-center text-sm", result.ok ? "bg-[#22c55e]/12 text-[#22c55e]" : "bg-[#ef4444]/12 text-[#ef4444]")}>
            {result.msg}
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleTrade}
          disabled={usdAmount <= 0 || loading}
          className={cn(
            "w-full rounded-2xl py-4 text-base font-bold transition-all disabled:opacity-40",
            side === "buy" ? "bg-[#22c55e] text-white hover:bg-[#16a34a]" : "bg-[#ef4444] text-white hover:bg-[#dc2626]",
          )}
        >
          {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : `${side === "buy" ? "Buy" : "Sell"} ${symbol}`}
        </button>
      </div>
    </div>
  );
}
