"use client";

import { useEffect, useState } from "react";
import { usePageAccent } from "@/components/providers/theme-provider";
import { useCurrency } from "@/components/providers/currency-provider";
import { pricesApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Flame, BarChart3, AlertTriangle, Zap, ArrowUpRight, ArrowDownRight } from "lucide-react";

interface MarketSignal {
  id: string;
  type: "gainer" | "loser" | "volume" | "trending" | "alert";
  title: string;
  description: string;
  symbol: string;
  value: string;
  sentiment: number; // -1 to 1
  impact: "high" | "medium" | "low";
  time: string;
}

const CG_BASE = "https://api.coingecko.com/api/v3";

async function fetchFearGreed(): Promise<{ value: number; label: string }> {
  try {
    const r = await fetch("https://api.alternative.me/fng/?limit=1&format=json");
    const d = await r.json();
    const e = d?.data?.[0];
    return { value: Number(e?.value ?? 50), label: String(e?.value_classification ?? "Neutral") };
  } catch { return { value: 50, label: "Neutral" }; }
}

async function fetchTrending(): Promise<Array<{ symbol: string; name: string; thumb: string; rank: number | null }>> {
  try {
    const r = await fetch(`${CG_BASE}/search/trending`);
    const d = await r.json();
    return (d.coins || []).map((e: Record<string, Record<string, unknown>>) => ({
      symbol: String(e.item?.symbol || "").toUpperCase(),
      name: String(e.item?.name || ""),
      thumb: String(e.item?.thumb || ""),
      rank: Number(e.item?.market_cap_rank || 0) || null,
    }));
  } catch { return []; }
}

function generateSignals(cryptos: Record<string, unknown>[], trending: { symbol: string; name: string }[]): MarketSignal[] {
  const signals: MarketSignal[] = [];
  const now = new Date().toISOString();

  // Top gainers (>5%)
  const sorted = [...cryptos].sort((a, b) => Number(b.price_change_percentage_24h || 0) - Number(a.price_change_percentage_24h || 0));
  sorted.slice(0, 5).forEach((c, i) => {
    const pct = Number(c.price_change_percentage_24h || 0);
    if (pct > 3) {
      signals.push({
        id: `gain-${i}`,
        type: "gainer",
        title: `${String(c.symbol).toUpperCase()} surging +${pct.toFixed(1)}%`,
        description: `${c.name} is up ${pct.toFixed(1)}% in the last 24 hours with $${(Number(c.total_volume || 0) / 1e6).toFixed(0)}M volume.`,
        symbol: String(c.symbol).toUpperCase(),
        value: `+${pct.toFixed(1)}%`,
        sentiment: Math.min(pct / 10, 1),
        impact: pct > 10 ? "high" : pct > 5 ? "medium" : "low",
        time: now,
      });
    }
  });

  // Top losers (<-5%)
  sorted.reverse().slice(0, 5).forEach((c, i) => {
    const pct = Number(c.price_change_percentage_24h || 0);
    if (pct < -3) {
      signals.push({
        id: `loss-${i}`,
        type: "loser",
        title: `${String(c.symbol).toUpperCase()} dropping ${pct.toFixed(1)}%`,
        description: `${c.name} has fallen ${Math.abs(pct).toFixed(1)}% in 24h. Watch for support levels.`,
        symbol: String(c.symbol).toUpperCase(),
        value: `${pct.toFixed(1)}%`,
        sentiment: Math.max(pct / 10, -1),
        impact: pct < -10 ? "high" : pct < -5 ? "medium" : "low",
        time: now,
      });
    }
  });

  // Trending coins
  trending.slice(0, 4).forEach((t, i) => {
    signals.push({
      id: `trend-${i}`,
      type: "trending",
      title: `${t.symbol} is trending`,
      description: `${t.name} is trending on CoinGecko right now. High social activity detected.`,
      symbol: t.symbol,
      value: "Trending",
      sentiment: 0.3,
      impact: "medium",
      time: now,
    });
  });

  // Volume anomalies
  const byVolume = [...cryptos].sort((a, b) => Number(b.total_volume || 0) - Number(a.total_volume || 0));
  byVolume.slice(0, 3).forEach((c, i) => {
    const vol = Number(c.total_volume || 0);
    if (vol > 1e9) {
      signals.push({
        id: `vol-${i}`,
        type: "volume",
        title: `${String(c.symbol).toUpperCase()} massive volume`,
        description: `$${(vol / 1e9).toFixed(1)}B traded in 24h. Unusual activity detected.`,
        symbol: String(c.symbol).toUpperCase(),
        value: `$${(vol / 1e9).toFixed(1)}B`,
        sentiment: 0,
        impact: vol > 10e9 ? "high" : "medium",
        time: now,
      });
    }
  });

  return signals.sort((a, b) => {
    const impactOrder = { high: 0, medium: 1, low: 2 };
    return impactOrder[a.impact] - impactOrder[b.impact];
  });
}

const TYPE_ICONS = {
  gainer: TrendingUp,
  loser: TrendingDown,
  volume: BarChart3,
  trending: Flame,
  alert: AlertTriangle,
};

const TYPE_COLORS = {
  gainer: "text-[#22c55e] bg-[#22c55e]/12",
  loser: "text-[#ef4444] bg-[#ef4444]/12",
  volume: "text-[#3b82f6] bg-[#3b82f6]/12",
  trending: "text-[#f59e0b] bg-[#f59e0b]/12",
  alert: "text-[#ef4444] bg-[#ef4444]/12",
};

const IMPACT_COLORS = { high: "bg-[#ef4444]", medium: "bg-[#f59e0b]", low: "bg-[var(--text-muted)]" };

export default function NewsPage() {
  usePageAccent("#6366f1", "99,102,241");
  const { format } = useCurrency();

  const [signals, setSignals] = useState<MarketSignal[]>([]);
  const [trending, setTrending] = useState<{ symbol: string; name: string; thumb: string }[]>([]);
  const [fearGreed, setFearGreed] = useState<{ value: number; label: string }>({ value: 50, label: "Neutral" });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      pricesApi.getAllCryptos(100),
      fetchTrending(),
      fetchFearGreed(),
    ]).then(([cryptoRes, trendRes, fgRes]) => {
      setTrending(trendRes);
      setFearGreed(fgRes);
      const sigs = generateSignals(cryptoRes.data as unknown as Record<string, unknown>[], trendRes);
      setSignals(sigs);
    }).finally(() => setLoading(false));
  }, []);

  const overallSentiment = signals.length > 0
    ? signals.reduce((sum, s) => sum + s.sentiment, 0) / signals.length
    : 0;

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-bold glow-text mb-1">Market Intelligence</h1>
      <p className="text-xs text-[var(--text-muted)] mb-5">Real-time signals, sentiment, and market movements.</p>

      {/* Market Pulse */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
        <div className="liquid-glass-card p-4 flex items-center gap-4">
          <div className={cn("flex h-14 w-14 items-center justify-center rounded-2xl text-xl font-bold",
            fearGreed.value < 30 ? "bg-[#ef4444]/12 text-[#ef4444]" : fearGreed.value > 70 ? "bg-[#22c55e]/12 text-[#22c55e]" : "accent-bg accent-text"
          )}>
            {fearGreed.value}
          </div>
          <div>
            <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">Fear & Greed</p>
            <p className="text-sm font-semibold text-[var(--foreground)]">{fearGreed.label}</p>
          </div>
        </div>

        <div className="liquid-glass-card p-4 flex items-center gap-4">
          <div className={cn("flex h-14 w-14 items-center justify-center rounded-2xl",
            overallSentiment > 0.1 ? "bg-[#22c55e]/12" : overallSentiment < -0.1 ? "bg-[#ef4444]/12" : "accent-bg"
          )}>
            {overallSentiment > 0.1 ? <ArrowUpRight className="h-6 w-6 text-[#22c55e]" /> : overallSentiment < -0.1 ? <ArrowDownRight className="h-6 w-6 text-[#ef4444]" /> : <BarChart3 className="h-6 w-6 accent-text" />}
          </div>
          <div>
            <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider">Market Mood</p>
            <p className={cn("text-sm font-semibold", overallSentiment > 0.1 ? "text-[#22c55e]" : overallSentiment < -0.1 ? "text-[#ef4444]" : "text-[var(--foreground)]")}>
              {overallSentiment > 0.1 ? "Bullish" : overallSentiment < -0.1 ? "Bearish" : "Neutral"}
            </p>
          </div>
        </div>

        <div className="liquid-glass-card p-4">
          <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-2 flex items-center gap-1"><Flame className="h-3 w-3" /> Trending Now</p>
          <div className="flex flex-wrap gap-1.5">
            {trending.slice(0, 6).map((c) => (
              <span key={c.symbol} className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium accent-bg accent-text">
                {c.thumb && <img src={c.thumb} alt="" className="h-3.5 w-3.5 rounded-full" />}
                {c.symbol}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Signals */}
      <div className="flex items-center gap-2 mb-3">
        <Zap className="h-4 w-4 accent-text" />
        <h2 className="text-sm font-semibold text-[var(--foreground)]">{signals.length} Market Signals</h2>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => <div key={i} className="h-20 animate-pulse rounded-2xl" style={{ background: "var(--glass-bg)" }} />)}
        </div>
      ) : (
        <div className="space-y-2">
          {signals.map((sig) => {
            const Icon = TYPE_ICONS[sig.type];
            return (
              <div key={sig.id} className="liquid-glass-card p-4 flex items-start gap-3">
                <div className={cn("flex h-9 w-9 items-center justify-center rounded-xl flex-shrink-0", TYPE_COLORS[sig.type])}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[13px] font-semibold text-[var(--foreground)]">{sig.title}</span>
                    <div className={cn("h-2 w-2 rounded-full flex-shrink-0", IMPACT_COLORS[sig.impact])} title={`${sig.impact} impact`} />
                  </div>
                  <p className="text-[11px] text-[var(--text-muted)] line-clamp-2">{sig.description}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <span className={cn("text-sm font-bold", sig.sentiment > 0 ? "text-[#22c55e]" : sig.sentiment < 0 ? "text-[#ef4444]" : "text-[var(--foreground)]")}>
                    {sig.value}
                  </span>
                  <p className="text-[10px] text-[var(--text-muted)]">{sig.symbol}</p>
                </div>
              </div>
            );
          })}
          {signals.length === 0 && <div className="py-16 text-center text-sm text-[var(--text-muted)]">No signals available.</div>}
        </div>
      )}
    </div>
  );
}
