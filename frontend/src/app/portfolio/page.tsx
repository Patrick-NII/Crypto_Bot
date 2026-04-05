"use client";

import { useEffect, useState, useCallback } from "react";
import { usePageAccent, PAGE_ACCENTS } from "@/components/providers/theme-provider";
import { useCurrency } from "@/components/providers/currency-provider";
import { Wallet, RefreshCw } from "lucide-react";
import { WalletAccessPanel } from "@/components/account/wallet-access-panel";
import { ApiError, authApi, portfolioApi } from "@/lib/api";
import { cn, formatRelative } from "@/lib/utils";
import type { ExecutionFeedItem, UserProfile } from "@/lib/types";

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

  const [account, setAccount] = useState<UserProfile | null>(null);
  const [holdings, setHoldings] = useState<HoldingData[]>([]);
  const [totalValue, setTotalValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>("");
  const [activity, setActivity] = useState<ExecutionFeedItem[]>([]);

  const fetchPortfolio = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const me = await authApi.getMe();
      setAccount(me);

      if (!me.wallet_access_enabled) {
        setHoldings([]);
        setTotalValue(0);
        setActivity([]);
        setLastUpdate(new Date().toLocaleTimeString());
        return;
      }

      const snapshot = await portfolioApi.getSnapshot();
      const items: HoldingData[] = snapshot.holdings.map((holding) => ({
        asset: holding.symbol,
        free: holding.available,
        locked: holding.reserved,
        total: holding.total,
        price: holding.price,
        value: holding.value,
        change24h: holding.change_pct_24h,
        image: "",
      }));

      // Sort by value descending
      items.sort((a, b) => b.value - a.value);
      setHoldings(items);
      setTotalValue(snapshot.summary.equity);
      setActivity(snapshot.execution_feed);
      setLastUpdate(new Date().toLocaleTimeString());
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : "Could not load portfolio snapshot.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, [fetchPortfolio]);

  const walletUnlocked = account?.wallet_access_enabled ?? false;

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold glow-text">Portfolio</h1>
          <p className="text-[13px] text-[var(--text-muted)]">Canonical wallet snapshot &middot; Live balances</p>
        </div>
        <button onClick={fetchPortfolio} className="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-[13px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all">
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          {lastUpdate && <span>{lastUpdate}</span>}
        </button>
      </div>

      {/* Total value — no heavy frame */}
      <div className="mb-6">
        <p className="text-[13px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Total Value</p>
        <p className="text-4xl font-bold text-[var(--foreground)]">{walletUnlocked ? format(totalValue) : "Locked"}</p>
        <p className="text-xs text-[var(--text-muted)] mt-1">
          {walletUnlocked ? `${holdings.length} assets` : "Unlock wallet access in Settings"}
        </p>
      </div>

      {/* Allocation bar */}
      {walletUnlocked && holdings.length > 0 && totalValue > 0 && (
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
                <span key={h.asset} className="flex items-center gap-1 text-[12px] text-[var(--text-muted)]">
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
        <div className="mb-4 rounded-xl p-3 text-[14px] text-[#ef4444] bg-[#ef4444]/8">
          {error}
        </div>
      )}

      {!loading && !walletUnlocked && (
        <div className="mb-6">
          <WalletAccessPanel
            title="Your wallet stays private until you connect it"
            reason={account?.wallet_access_reason}
          />
        </div>
      )}

      {/* Holdings list — minimal, no cards per item */}
      {loading && holdings.length === 0 ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-14 animate-pulse rounded-xl" style={{ background: "var(--glass-bg)" }} />)}
        </div>
      ) : !walletUnlocked ? (
        <div className="py-12 text-center">
          <Wallet className="h-10 w-10 mx-auto mb-3 text-[var(--text-muted)] opacity-30" />
          <p className="text-sm text-[var(--text-muted)]">Wallet balances, valuation and execution history are locked.</p>
          <p className="text-[13px] text-[var(--text-muted)] mt-1 opacity-70">
            Configure your own exchange connection in Settings to unlock the portfolio view.
          </p>
        </div>
      ) : holdings.length === 0 ? (
        <div className="py-16 text-center">
          <Wallet className="h-10 w-10 mx-auto mb-3 text-[var(--text-muted)] opacity-30" />
          <p className="text-sm text-[var(--text-muted)]">No assets in your wallet</p>
          <p className="text-[13px] text-[var(--text-muted)] mt-1 opacity-60">Start by depositing on Binance</p>
        </div>
      ) : (
        <div className="space-y-0.5">
          {/* Header */}
          <div className="flex items-center gap-3 px-2 py-1 text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
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
                <div className="h-7 w-7 rounded-full flex-shrink-0 flex items-center justify-center text-[12px] font-bold" style={{ background: "var(--glass-bg)" }}>{h.asset.slice(0, 2)}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-[14px] font-semibold text-[var(--foreground)]">{h.asset}</p>
                  {h.locked > 0 && <p className="text-[11px] text-[var(--text-muted)]">{h.locked.toFixed(4)} locked</p>}
                </div>
                <div className="w-24 text-right">
                  <p className="text-[13px] font-mono text-[var(--foreground)]">{h.total < 1 ? h.total.toFixed(6) : h.total.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
                </div>
                <div className="w-24 text-right hidden sm:block">
                  <p className="text-[13px] text-[var(--text-secondary)]">{h.price > 0 ? format(h.price) : "—"}</p>
                </div>
                <div className="w-24 text-right">
                  <p className="text-[13px] font-semibold text-[var(--foreground)]">{format(h.value)}</p>
                </div>
                <div className="w-16 text-right hidden sm:block">
                  <p className={cn("text-[12px] font-medium", pos ? "text-[#22c55e]" : "text-[#ef4444]")}>
                    {h.change24h !== 0 ? `${pos ? "+" : ""}${h.change24h.toFixed(1)}%` : "—"}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Recent activity */}
      <div className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--foreground)]">Recent Activity</h2>
          <span className="text-[12px] text-[var(--text-muted)]">Unified execution flow</span>
        </div>
        {!walletUnlocked ? (
          <p className="text-[13px] text-[var(--text-muted)]">
            Execution activity appears here once a private exchange connection is unlocked.
          </p>
        ) : activity.length === 0 ? (
          <p className="text-[13px] text-[var(--text-muted)]">No execution activity yet.</p>
        ) : (
          <div className="space-y-1">
            {activity.slice(0, 8).map((entry) => (
              <div key={entry.id} className="flex items-center justify-between rounded-lg px-2 py-2 hover:bg-[var(--glass-bg)] transition-all">
                <div>
                  <p className="text-[13px] font-semibold text-[var(--foreground)]">
                    {entry.symbol} {entry.side.toUpperCase()}
                  </p>
                  <p className="text-[11px] text-[var(--text-muted)]">
                    {entry.execution_price != null
                      ? `Filled @ ${format(entry.execution_price)}`
                      : entry.requested_price != null
                        ? `Requested @ ${format(entry.requested_price)}`
                        : "Awaiting fill"}
                    {entry.fee > 0 ? ` · Fee ${format(entry.fee)}` : ""}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-[12px] font-semibold text-[var(--foreground)]">{entry.status}</p>
                  <p className="text-[11px] text-[var(--text-muted)]">{formatRelative(entry.timestamp)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
