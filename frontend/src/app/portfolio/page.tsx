"use client";

import { useEffect, useState, useCallback } from "react";
import { usePageAccent, PAGE_ACCENTS } from "@/components/providers/theme-provider";
import { useCurrency } from "@/components/providers/currency-provider";
import { Wallet, TrendingUp, TrendingDown, RefreshCw } from "lucide-react";
import { pricesApi, binanceApi } from "@/lib/api";
import { cn } from "@/lib/utils";

interface HoldingData {
  asset: string;
  free: number;
  locked: number;
  total: number;
  price: number;
  value: number;
  change24h: number;
  image: string;
}

export default function PortfolioPage() {
  usePageAccent(PAGE_ACCENTS.portfolio.accent, PAGE_ACCENTS.portfolio.glow);
  const { format } = useCurrency();

  const [holdings, setHoldings] = useState<HoldingData[]>([]);
  const [totalValue, setTotalValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>("");

  const fetchPortfolio = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch Binance balances and crypto prices in parallel
      const [balResult, cryptoResult] = await Promise.allSettled([
        binanceApi.getBalances(),
        pricesApi.getAllCryptos(250),
      ]);

      const balances = balResult.status === "fulfilled" ? balResult.value : [];
      const cryptoRes = cryptoResult.status === "fulfilled" ? cryptoResult.value : { data: [] };

      if (balances.length === 0) {
        setError("Could not load Binance balances. Make sure the proxy is running: node frontend/binance-proxy.mjs");
        setLoading(false);
        return;
      }

      const cryptos = cryptoRes.data as unknown as Array<{
        symbol: string; current_price: number; price_change_percentage_24h: number; image: string;
      }>;

      // Build holdings with prices
      let total = 0;
      const items: HoldingData[] = [];

      for (const b of balances) {
        const amt = b.free + b.locked;
        if (amt <= 0) continue;

        // Stablecoins
        if (["USDT", "BUSD", "USDC", "USD", "FDUSD"].includes(b.asset)) {
          total += amt;
          items.push({ asset: b.asset, free: b.free, locked: b.locked, total: amt, price: 1, value: amt, change24h: 0, image: "" });
          continue;
        }

        // Find price
        const crypto = cryptos.find((c) => c.symbol?.toUpperCase() === b.asset.toUpperCase());
        const price = crypto?.current_price ?? 0;
        const value = amt * price;
        total += value;

        items.push({
          asset: b.asset,
          free: b.free,
          locked: b.locked,
          total: amt,
          price,
          value,
          change24h: crypto?.price_change_percentage_24h ?? 0,
          image: crypto?.image ?? "",
        });
      }

      // Sort by value descending
      items.sort((a, b) => b.value - a.value);
      setHoldings(items);
      setTotalValue(total);
      setLastUpdate(new Date().toLocaleTimeString());
    } catch (err) {
      setError("Could not load portfolio. Make sure the Binance proxy is running (node frontend/binance-proxy.mjs)");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, [fetchPortfolio]);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold glow-text">Portfolio</h1>
          <p className="text-[11px] text-[var(--text-muted)]">Binance wallet &middot; Live balances</p>
        </div>
        <button onClick={fetchPortfolio} className="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-[11px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all">
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          {lastUpdate && <span>{lastUpdate}</span>}
        </button>
      </div>

      {/* Total value — no heavy frame */}
      <div className="mb-6">
        <p className="text-[11px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Total Value</p>
        <p className="text-4xl font-bold text-[var(--foreground)]">{format(totalValue)}</p>
        <p className="text-xs text-[var(--text-muted)] mt-1">{holdings.length} assets</p>
      </div>

      {/* Allocation bar */}
      {holdings.length > 0 && totalValue > 0 && (
        <div className="mb-6">
          <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
            {holdings.slice(0, 8).map((h, i) => {
              const pct = (h.value / totalValue) * 100;
              if (pct < 1) return null;
              const colors = ["#a855f7", "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#ec4899", "#06d6a0", "#6366f1"];
              return (
                <div
                  key={h.asset}
                  className="h-full rounded-full transition-all"
                  style={{ width: `${pct}%`, background: colors[i % colors.length] }}
                  title={`${h.asset}: ${pct.toFixed(1)}%`}
                />
              );
            })}
          </div>
          <div className="flex flex-wrap gap-3 mt-2">
            {holdings.slice(0, 6).map((h, i) => {
              const pct = (h.value / totalValue) * 100;
              const colors = ["#a855f7", "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#ec4899"];
              return (
                <span key={h.asset} className="flex items-center gap-1 text-[10px] text-[var(--text-muted)]">
                  <span className="h-2 w-2 rounded-full" style={{ background: colors[i % colors.length] }} />
                  {h.asset} {pct.toFixed(1)}%
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-xl p-3 text-[12px] text-[#ef4444] bg-[#ef4444]/8">
          {error}
        </div>
      )}

      {/* Holdings list — minimal, no cards per item */}
      {loading && holdings.length === 0 ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-14 animate-pulse rounded-xl" style={{ background: "var(--glass-bg)" }} />)}
        </div>
      ) : holdings.length === 0 ? (
        <div className="py-16 text-center">
          <Wallet className="h-10 w-10 mx-auto mb-3 text-[var(--text-muted)] opacity-30" />
          <p className="text-sm text-[var(--text-muted)]">No assets in your wallet</p>
          <p className="text-[11px] text-[var(--text-muted)] mt-1 opacity-60">Start by depositing on Binance</p>
        </div>
      ) : (
        <div className="space-y-0.5">
          {/* Header */}
          <div className="flex items-center gap-3 px-2 py-1 text-[9px] uppercase tracking-wider text-[var(--text-muted)]">
            <span className="w-8" />
            <span className="flex-1">Asset</span>
            <span className="w-24 text-right">Balance</span>
            <span className="w-24 text-right hidden sm:block">Price</span>
            <span className="w-24 text-right">Value</span>
            <span className="w-16 text-right hidden sm:block">24h</span>
          </div>

          {holdings.map((h) => {
            const pos = h.change24h >= 0;
            return (
              <div key={h.asset} className="flex items-center gap-3 px-2 py-2.5 rounded-lg hover:bg-[var(--glass-bg)] transition-all">
                {h.image ? <img src={h.image} alt="" className="h-7 w-7 rounded-full flex-shrink-0" /> : <div className="h-7 w-7 rounded-full flex-shrink-0 flex items-center justify-center text-[10px] font-bold" style={{ background: "var(--glass-bg)" }}>{h.asset.slice(0, 2)}</div>}
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] font-semibold text-[var(--foreground)]">{h.asset}</p>
                  {h.locked > 0 && <p className="text-[9px] text-[var(--text-muted)]">{h.locked.toFixed(4)} locked</p>}
                </div>
                <div className="w-24 text-right">
                  <p className="text-[11px] font-mono text-[var(--foreground)]">{h.total < 1 ? h.total.toFixed(6) : h.total.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
                </div>
                <div className="w-24 text-right hidden sm:block">
                  <p className="text-[11px] text-[var(--text-secondary)]">{h.price > 0 ? format(h.price) : "—"}</p>
                </div>
                <div className="w-24 text-right">
                  <p className="text-[11px] font-semibold text-[var(--foreground)]">{format(h.value)}</p>
                </div>
                <div className="w-16 text-right hidden sm:block">
                  <p className={cn("text-[10px] font-medium", pos ? "text-[#22c55e]" : "text-[#ef4444]")}>
                    {h.change24h !== 0 ? `${pos ? "+" : ""}${h.change24h.toFixed(1)}%` : "—"}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
