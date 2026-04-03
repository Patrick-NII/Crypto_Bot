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
  const fee = usdAmount * 0.001; // 0.1% fee

  const handleTrade = async () => {
    if (usdAmount <= 0) return;
    setLoading(true);
    setResult(null);

    try {
      await tradingApi.placeOrder({
        symbol,
        side,
        order_type: "market",
        quantity: cryptoAmount,
      });
      setResult({ ok: true, msg: `${side === "buy" ? "Bought" : "Sold"} ${cryptoAmount.toFixed(6)} ${symbol}` });
      onSuccess?.();
    } catch {
      setResult({ ok: false, msg: "Order failed. Try again." });
    } finally {
      setLoading(false);
    }
  };

  const presets = [10, 25, 50, 100, 500];

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center sm:items-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-md rounded-t-3xl sm:rounded-3xl border border-[rgba(255,255,255,0.08)] bg-[#14141b] p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">{symbol}</h2>
            <p className="text-sm text-[#8888a0]">${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-[#55556a] hover:bg-[rgba(255,255,255,0.05)]">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Buy/Sell toggle */}
        <div className="mb-5 flex rounded-xl bg-[#0d0d12] p-1">
          <button
            onClick={() => setSide("buy")}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-semibold transition-all",
              side === "buy" ? "bg-[#06d6a0] text-[#0d0d12]" : "text-[#8888a0]",
            )}
          >
            <ArrowUpRight className="h-4 w-4" /> Buy
          </button>
          <button
            onClick={() => setSide("sell")}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-semibold transition-all",
              side === "sell" ? "bg-red-500 text-white" : "text-[#8888a0]",
            )}
          >
            <ArrowDownRight className="h-4 w-4" /> Sell
          </button>
        </div>

        {/* Amount input */}
        <div className="mb-4">
          <div className="flex items-center rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3">
            <span className="mr-2 text-2xl font-bold text-[#55556a]">$</span>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className="flex-1 bg-transparent text-2xl font-bold text-white outline-none placeholder-[#2a2a3a]"
              autoFocus
            />
          </div>
          {usdAmount > 0 && (
            <p className="mt-1.5 text-right text-xs text-[#55556a]">
              ≈ {cryptoAmount.toFixed(6)} {symbol}
            </p>
          )}
        </div>

        {/* Quick amount presets */}
        <div className="mb-5 flex gap-2">
          {presets.map((p) => (
            <button
              key={p}
              onClick={() => setAmount(String(p))}
              className={cn(
                "flex-1 rounded-lg py-2 text-xs font-medium transition-all",
                amount === String(p)
                  ? "bg-[#06d6a0]/15 text-[#06d6a0]"
                  : "bg-[#0d0d12] text-[#55556a] hover:text-[#8888a0]",
              )}
            >
              ${p}
            </button>
          ))}
        </div>

        {/* Fee summary */}
        {usdAmount > 0 && (
          <div className="mb-5 space-y-2 rounded-xl bg-[#0d0d12] p-3">
            <div className="flex justify-between text-xs">
              <span className="text-[#55556a]">Amount</span>
              <span className="text-[#8888a0]">${usdAmount.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-[#55556a]">Fee (0.1%)</span>
              <span className="text-[#8888a0]">${fee.toFixed(2)}</span>
            </div>
            <div className="flex justify-between border-t border-[rgba(255,255,255,0.06)] pt-2 text-xs font-semibold">
              <span className="text-[#8888a0]">Total</span>
              <span className="text-white">${(usdAmount + fee).toFixed(2)}</span>
            </div>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className={cn("mb-4 rounded-xl p-3 text-center text-sm", result.ok ? "bg-[#06d6a0]/10 text-[#06d6a0]" : "bg-red-500/10 text-red-400")}>
            {result.msg}
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleTrade}
          disabled={usdAmount <= 0 || loading}
          className={cn(
            "w-full rounded-xl py-4 text-base font-bold transition-all disabled:opacity-40",
            side === "buy"
              ? "bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] text-[#0d0d12]"
              : "bg-red-500 text-white",
          )}
        >
          {loading ? (
            <Loader2 className="mx-auto h-5 w-5 animate-spin" />
          ) : (
            `${side === "buy" ? "Buy" : "Sell"} ${symbol}`
          )}
        </button>
      </div>
    </div>
  );
}
