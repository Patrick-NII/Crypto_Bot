"use client";

import { useEffect, useState } from "react";
import { usePageAccent, PAGE_ACCENTS } from "@/components/providers/theme-provider";
import { useCurrency } from "@/components/providers/currency-provider";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Star, TrendingUp, TrendingDown, BarChart3, DollarSign, Activity } from "lucide-react";
import { pricesApi, signalsApi } from "@/lib/api";
import { priceWs } from "@/lib/websocket";
import { PriceChart } from "@/components/charts/price-chart";
import { QuickTradeModal } from "@/components/trading/quick-trade-modal";
import { SignalBadge, IndicatorBar, type SignalAction } from "@/components/trading/signal-badge";
import { cn } from "@/lib/utils";

// ---- Types ----

interface CoinData {
  symbol: string;
  name: string;
  image: string;
  current_price: number;
  market_cap: number;
  market_cap_rank: number;
  price_change_percentage_24h: number;
  total_volume: number;
  high_24h: number;
  low_24h: number;
  circulating_supply: number;
  total_supply: number;
  ath: number;
  ath_change_percentage: number;
}

// ---- Helpers ----

function getWatchlist(): string[] {
  try { return JSON.parse(localStorage.getItem("watchlist") || "[]"); } catch { return []; }
}

function toggleWL(symbol: string): string[] {
  const list = getWatchlist();
  const upper = symbol.toUpperCase();
  const next = list.includes(upper) ? list.filter((s) => s !== upper) : [...list, upper];
  try { localStorage.setItem("watchlist", JSON.stringify(next)); } catch { /* full */ }
  return next;
}

function fmt(n: number | undefined | null, dec = 2): string {
  if (n == null) return "\u2014";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(dec)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(dec)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(dec)}M`;
  if (n >= 1) return `$${n.toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec })}`;
  if (n >= 0.001) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(8)}`;
}

// ============================================================
// Crypto Detail Page
// ============================================================

export default function CryptoDetailClient() {
  usePageAccent(PAGE_ACCENTS.crypto.accent, PAGE_ACCENTS.crypto.glow);
  useCurrency();
  const params = useParams();
  const symbol = (params.symbol as string || "BTC").toUpperCase();

  const [coin, setCoin] = useState<CoinData | null>(null);
  const [livePrice, setLivePrice] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [tradeModal, setTradeModal] = useState<"buy" | "sell" | null>(null);
  const [watchlistVersion, setWatchlistVersion] = useState(0);
  const [signal, setSignal] = useState<{
    action: string; confidence: number; score: number; reasoning: string;
    indicators: Array<{ name: string; value: number; signal: number; description: string }>;
  } | null>(null);
  const isWatched = getWatchlist().includes(symbol);

  useEffect(() => {
    pricesApi.getAllCryptos(250).then((res) => {
      const data = res.data as unknown as CoinData[];
      const found = data.find((c) => (c.symbol ?? "").toUpperCase() === symbol);
      if (found) {
        setCoin(found);
        setLivePrice(found.current_price || (found as unknown as Record<string, number>).price || 0);
      }
    }).catch(() => {}).finally(() => setLoading(false));
    signalsApi.getSignal(symbol).then(setSignal).catch(() => {});
  }, [symbol, watchlistVersion]);

  useEffect(() => {
    const unsub = priceWs.subscribe(symbol, (data) => { if (data.price) setLivePrice(data.price); });
    return unsub;
  }, [symbol]);

  const price = livePrice || coin?.current_price || 0;
  const changePct = coin?.price_change_percentage_24h ?? 0;
  const positive = changePct >= 0;

  const STATS = [
    { label: "Market Cap", value: fmt(coin?.market_cap), icon: BarChart3 },
    { label: "24h Volume", value: fmt(coin?.total_volume), icon: Activity },
    { label: "24h High", value: fmt(coin?.high_24h), icon: TrendingUp },
    { label: "24h Low", value: fmt(coin?.low_24h), icon: TrendingDown },
    { label: "Circ. Supply", value: coin?.circulating_supply ? `${(coin.circulating_supply / 1e6).toFixed(1)}M` : "\u2014", icon: DollarSign },
    { label: "Total Supply", value: coin?.total_supply ? `${(coin.total_supply / 1e6).toFixed(1)}M` : "\u2014", icon: DollarSign },
    { label: "ATH", value: fmt(coin?.ath), icon: TrendingUp },
    { label: "ATH Change", value: coin?.ath_change_percentage ? `${coin.ath_change_percentage.toFixed(1)}%` : "\u2014", icon: TrendingDown },
  ];

  if (loading) {
    return (
      <div className="p-4 md:p-8">
        <div className="mb-6 h-8 w-32 animate-pulse rounded-lg bg-white/5" />
        <div className="mb-4 h-12 w-48 animate-pulse rounded-lg bg-white/5" />
        <div className="h-[500px] animate-pulse rounded-xl bg-white/5" />
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8">
      {/* Header — full width */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/crypto" className="rounded-lg p-2 text-[var(--text-muted)] hover:bg-[var(--glass-bg)] hover:text-[var(--foreground)] transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          {coin?.image && <img src={coin.image} alt={symbol} className="h-10 w-10 rounded-full" />}
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-[var(--foreground)]">{symbol}</h1>
              {coin?.market_cap_rank && (
                <span className="rounded-md px-2 py-0.5 text-[12px] font-medium text-[var(--text-muted)]" style={{ background: "var(--glass-bg)" }}>
                  #{coin.market_cap_rank}
                </span>
              )}
            </div>
            <p className="text-sm text-[var(--text-muted)]">{coin?.name}</p>
          </div>
        </div>
        <button
          onClick={() => { toggleWL(symbol); setWatchlistVersion((current) => current + 1); }}
          className={cn("rounded-lg p-2 transition-colors", isWatched ? "text-[#c6f135]" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]")}
        >
          <Star className="h-5 w-5" fill={isWatched ? "currentColor" : "none"} />
        </button>
      </div>

      {/* Price + Signal */}
      <div className="mb-5">
        <p className="text-4xl font-bold text-[var(--foreground)]">{fmt(price)}</p>
        <div className="flex items-center gap-3 mt-1.5">
          <p className={cn("text-sm font-medium", positive ? "text-[var(--success)]" : "text-[var(--danger)]")}>
            {positive ? "+" : ""}{changePct.toFixed(2)}% today
          </p>
          {signal && <SignalBadge action={signal.action as SignalAction} confidence={signal.confidence} size="md" />}
        </div>
      </div>

      {/* Main layout: Chart hero (left) + Sidebar (right) */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-4 mb-8">

        {/* Chart — 3/4 width, dominant */}
        <div className="lg:col-span-3">
          <PriceChart symbol={symbol} height={500} type="candlestick" showIntervals defaultInterval="1M" />
        </div>

        {/* Sidebar — 1/4 */}
        <div className="space-y-6">

          {/* Buy / Sell buttons */}
          <div className="flex gap-2">
            <button
              onClick={() => setTradeModal("buy")}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-xl py-3 text-[15px] font-bold transition-all bg-[var(--success)]/15 text-[var(--success)] hover:bg-[var(--success)]/25"
            >
              <TrendingUp className="h-4 w-4" /> Buy
            </button>
            <button
              onClick={() => setTradeModal("sell")}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-xl py-3 text-[15px] font-bold transition-all bg-[var(--danger)]/15 text-[var(--danger)] hover:bg-[var(--danger)]/25"
            >
              <TrendingDown className="h-4 w-4" /> Sell
            </button>
          </div>

          {/* Signal indicators */}
          {signal && signal.indicators.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-[var(--foreground)] mb-3">Indicators</h3>
              <div className="space-y-2">
                {signal.indicators.map((ind) => (
                  <IndicatorBar key={ind.name} name={ind.name} value={ind.value} signal={ind.signal} description={ind.description} />
                ))}
              </div>
              <p className="text-[12px] text-[var(--text-muted)] mt-3 leading-relaxed">{signal.reasoning}</p>
            </div>
          )}

          {/* Quick stats — vertical in sidebar */}
          <div>
            <h3 className="text-xs font-semibold text-[var(--foreground)] mb-3">Stats</h3>
            <div className="space-y-2">
              {STATS.map((s) => (
                <div key={s.label} className="flex items-center justify-between py-1.5">
                  <div className="flex items-center gap-1.5">
                    <s.icon className="h-3 w-3 text-[var(--text-muted)]" />
                    <span className="text-[12px] text-[var(--text-muted)]">{s.label}</span>
                  </div>
                  <span className="text-[13px] font-semibold font-mono text-[var(--foreground)]">{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {tradeModal && <QuickTradeModal symbol={symbol} price={price} onClose={() => setTradeModal(null)} />}
    </div>
  );
}
