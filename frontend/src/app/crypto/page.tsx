"use client";

import { useEffect, useState, useMemo } from "react";
import { usePageAccent, PAGE_ACCENTS } from "@/components/providers/theme-provider";
import { useCurrency } from "@/components/providers/currency-provider";
import { Search, Star, TrendingUp, TrendingDown, BarChart3, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { pricesApi, signalsApi } from "@/lib/api";
import { PriceChart } from "@/components/charts/price-chart";
import { SignalBadge, IndicatorBar, type SignalAction } from "@/components/trading/signal-badge";
import { QuickTradeModal } from "@/components/trading/quick-trade-modal";
import { AutoTradingMonitor } from "@/components/trading/auto-trading-monitor";
import { cn } from "@/lib/utils";

interface CryptoItem {
  id: string;
  symbol: string;
  name: string;
  image: string;
  current_price: number;
  market_cap: number;
  market_cap_rank: number;
  price_change_percentage_24h: number;
  total_volume: number;
  sparkline_in_7d: number[] | null;
  high_24h?: number;
  low_24h?: number;
}

type Tab = "all" | "gainers" | "losers" | "watchlist";

function MiniSparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 64; const h = 24;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`).join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="flex-shrink-0">
      <polyline fill="none" stroke={positive ? "#22c55e" : "#ef4444"} strokeWidth="1.5" points={points} />
    </svg>
  );
}

function getWatchlist(): string[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem("watchlist") || "[]"); } catch { return []; }
}

function toggleWatchlist(symbol: string): string[] {
  const list = getWatchlist();
  const upper = symbol.toUpperCase();
  const next = list.includes(upper) ? list.filter((s) => s !== upper) : [...list, upper];
  localStorage.setItem("watchlist", JSON.stringify(next));
  return next;
}

export default function CryptoTradingPage() {
  usePageAccent(PAGE_ACCENTS.crypto.accent, PAGE_ACCENTS.crypto.glow);
  const { format } = useCurrency();

  const [cryptos, setCryptos] = useState<CryptoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<Tab>("all");
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [selected, setSelected] = useState<CryptoItem | null>(null);
  const [signal, setSignal] = useState<{ action: string; confidence: number; indicators: Array<{ name: string; value: number; signal: number; description: string }> } | null>(null);
  const [tradeModal, setTradeModal] = useState(false);

  useEffect(() => {
    setWatchlist(getWatchlist());
    pricesApi.getAllCryptos(250).then((res) => {
      const data = res.data as unknown as CryptoItem[];
      setCryptos(data);
      if (data.length > 0) setSelected(data[0]);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setSignal(null);
    signalsApi.getSignal(selected.symbol?.toUpperCase()).then((s) => {
      setSignal({ action: s.action, confidence: s.confidence, indicators: s.indicators });
    }).catch(() => {});
  }, [selected]);

  const filtered = useMemo(() => {
    let list = [...cryptos];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((c) => c.name?.toLowerCase().includes(q) || c.symbol?.toLowerCase().includes(q));
    }
    if (tab === "gainers") list = list.filter((c) => (c.price_change_percentage_24h ?? 0) > 0).sort((a, b) => (b.price_change_percentage_24h ?? 0) - (a.price_change_percentage_24h ?? 0));
    else if (tab === "losers") list = list.filter((c) => (c.price_change_percentage_24h ?? 0) < 0).sort((a, b) => (a.price_change_percentage_24h ?? 0) - (b.price_change_percentage_24h ?? 0));
    else if (tab === "watchlist") list = list.filter((c) => watchlist.includes(c.symbol?.toUpperCase()));
    return list;
  }, [cryptos, search, tab, watchlist]);

  const pct = selected?.price_change_percentage_24h ?? 0;
  const positive = pct >= 0;

  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold glow-text">Trading</h1>
          <p className="text-[11px] text-[var(--text-muted)]">{cryptos.length} assets &middot; Real-time signals</p>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-4">
        {/* ─── Left: Chart + Trading Tools ─── */}
        <div className="lg:w-[58%] space-y-3 flex-shrink-0">
          {selected && (
            <>
              {/* Crypto header — no frame */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {selected.image && <img src={selected.image} alt={selected.symbol} className="h-9 w-9 rounded-full" />}
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-lg font-bold text-[var(--foreground)]">{selected.symbol?.toUpperCase()}</h2>
                      <span className="text-[9px] text-[var(--text-muted)] opacity-60">#{selected.market_cap_rank}</span>
                    </div>
                    <p className="text-[11px] text-[var(--text-muted)]">{selected.name}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {signal && <SignalBadge action={signal.action as SignalAction} confidence={signal.confidence} size="sm" />}
                  <button
                    onClick={() => setWatchlist(toggleWatchlist(selected.symbol))}
                    className={cn("p-1", watchlist.includes(selected.symbol?.toUpperCase()) ? "text-[#c6f135]" : "text-[var(--text-muted)]")}
                  >
                    <Star className="h-4 w-4" fill={watchlist.includes(selected.symbol?.toUpperCase()) ? "currentColor" : "none"} />
                  </button>
                </div>
              </div>

              {/* Price — no frame */}
              <div className="flex items-baseline gap-3">
                <span className="text-3xl font-bold text-[var(--foreground)]">{format(selected.current_price)}</span>
                <span className={cn("text-sm font-medium flex items-center gap-0.5", positive ? "text-[#22c55e]" : "text-[#ef4444]")}>
                  {positive ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
                  {positive ? "+" : ""}{pct.toFixed(2)}%
                </span>
              </div>

              {/* Quick stats — minimal, no frames */}
              <div className="flex gap-4 text-[10px] text-[var(--text-muted)]">
                <span>H: <span className="text-[var(--foreground)] font-medium">{format(selected.high_24h ?? 0)}</span></span>
                <span>L: <span className="text-[var(--foreground)] font-medium">{format(selected.low_24h ?? 0)}</span></span>
                <span>Vol: <span className="text-[var(--foreground)] font-medium">${((selected.total_volume ?? 0) / 1e6).toFixed(0)}M</span></span>
              </div>

              {/* Chart — single frame */}
              <div className="rounded-2xl overflow-hidden" style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>
                <PriceChart
                  key={selected.symbol}
                  symbol={selected.symbol?.toUpperCase()}
                  height={300}
                  type="candlestick"
                  showIntervals
                  defaultInterval="1D"
                />
              </div>

              {/* Indicators — inline, no frames */}
              {signal && signal.indicators.length > 0 && (
                <div className="grid grid-cols-3 gap-3">
                  {signal.indicators.map((ind) => (
                    <IndicatorBar key={ind.name} name={ind.name} value={ind.value} signal={ind.signal} description={ind.description} />
                  ))}
                </div>
              )}

              {/* Buy/Sell — clean buttons */}
              <div className="flex gap-2">
                <button onClick={() => setTradeModal(true)} className="flex-1 flex items-center justify-center gap-1.5 rounded-2xl py-3 text-sm font-bold bg-[#22c55e] text-white hover:bg-[#16a34a] transition-all">
                  <TrendingUp className="h-4 w-4" /> Buy
                </button>
                <button onClick={() => setTradeModal(true)} className="flex-1 flex items-center justify-center gap-1.5 rounded-2xl py-3 text-sm font-bold border border-[#ef4444]/30 text-[#ef4444] hover:bg-[#ef4444]/10 transition-all">
                  <TrendingDown className="h-4 w-4" /> Sell
                </button>
              </div>

              {/* Signal Monitor */}
              <AutoTradingMonitor />
            </>
          )}
        </div>

        {/* ─── Right: Crypto List ─── */}
        <div className="lg:w-[42%] flex flex-col min-h-0">
          <div className="mb-2 flex items-center gap-2 rounded-xl px-3 py-2" style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>
            <Search className="h-3.5 w-3.5 text-[var(--text-muted)]" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search..." className="flex-1 bg-transparent text-xs text-[var(--foreground)] outline-none placeholder-[var(--text-muted)]" />
          </div>

          <div className="mb-2 flex gap-1 overflow-x-auto">
            {([
              { id: "all" as Tab, label: "All", icon: BarChart3 },
              { id: "gainers" as Tab, label: "Gainers", icon: TrendingUp },
              { id: "losers" as Tab, label: "Losers", icon: TrendingDown },
              { id: "watchlist" as Tab, label: "Stars", icon: Star },
            ]).map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)} className={cn("flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1.5 text-[10px] font-medium transition-all", tab === t.id ? "accent-bg accent-text" : "text-[var(--text-muted)]")}>
                <t.icon className="h-3 w-3" /> {t.label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto max-h-[60vh] lg:max-h-[80vh] space-y-px">
            {loading ? (
              Array.from({ length: 20 }).map((_, i) => <div key={i} className="h-12 animate-pulse rounded-lg" style={{ background: "var(--glass-bg)" }} />)
            ) : (
              filtered.map((c) => {
                const pos = (c.price_change_percentage_24h ?? 0) >= 0;
                const isSel = selected?.symbol === c.symbol;
                const isW = watchlist.includes(c.symbol?.toUpperCase());
                return (
                  <button
                    key={c.id || c.symbol}
                    onClick={() => setSelected(c)}
                    className={cn(
                      "w-full flex items-center gap-2 rounded-lg px-2 py-2 text-left transition-all",
                      isSel ? "accent-bg" : "hover:bg-[var(--glass-bg)]",
                    )}
                  >
                    <button onClick={(e) => { e.stopPropagation(); setWatchlist(toggleWatchlist(c.symbol)); }} className={cn("flex-shrink-0", isW ? "text-[#c6f135]" : "text-[var(--elevated)] hover:text-[var(--text-muted)]")}>
                      <Star className="h-3 w-3" fill={isW ? "currentColor" : "none"} />
                    </button>
                    {c.image && <img src={c.image} alt="" className="h-5 w-5 rounded-full flex-shrink-0" />}
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-semibold text-[var(--foreground)] truncate">{c.symbol?.toUpperCase()}</p>
                    </div>
                    <div className="hidden sm:block"><MiniSparkline data={c.sparkline_in_7d ?? []} positive={pos} /></div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-[11px] font-semibold text-[var(--foreground)]">{format(c.current_price)}</p>
                      <p className={cn("text-[9px] font-medium", pos ? "text-[#22c55e]" : "text-[#ef4444]")}>{pos ? "+" : ""}{(c.price_change_percentage_24h ?? 0).toFixed(1)}%</p>
                    </div>
                  </button>
                );
              })
            )}
            {!loading && filtered.length === 0 && (
              <div className="py-8 text-center text-[11px] text-[var(--text-muted)]">{tab === "watchlist" ? "No favorites." : "No results."}</div>
            )}
          </div>
        </div>
      </div>

      {tradeModal && selected && (
        <QuickTradeModal symbol={selected.symbol?.toUpperCase()} price={selected.current_price} onClose={() => setTradeModal(false)} />
      )}
    </div>
  );
}
