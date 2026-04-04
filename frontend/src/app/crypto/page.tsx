"use client";

import { useEffect, useState, useMemo } from "react";
import { usePageAccent, PAGE_ACCENTS } from "@/components/providers/theme-provider";
import { useCurrency } from "@/components/providers/currency-provider";
import { Search, Star, TrendingUp, TrendingDown, BarChart3, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { pricesApi, signalsApi } from "@/lib/api";
import { PriceChart } from "@/components/charts/price-chart";
import { SignalBadge, IndicatorBar, type SignalAction } from "@/components/trading/signal-badge";
import { QuickTradeModal } from "@/components/trading/quick-trade-modal";
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
  ath?: number;
}

type Tab = "all" | "gainers" | "losers" | "watchlist";

function MiniSparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 80;
  const h = 28;
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

export default function CryptoDiscoverPage() {
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
      if (data.length > 0) setSelected(data[0]); // Select BTC by default
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  // Fetch signal when selected crypto changes
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
      <h1 className="mb-1 text-xl md:text-2xl font-bold glow-text">Crypto</h1>
      <p className="mb-4 text-xs text-[var(--text-muted)]">{cryptos.length} assets available</p>

      {/* ─── Main Layout: Chart left/top + List right/bottom ─── */}
      <div className="flex flex-col lg:flex-row gap-4">

        {/* ─── Left: Selected crypto chart + info ─── */}
        <div className="lg:w-[55%] xl:w-[60%] space-y-3 flex-shrink-0">
          {selected && (
            <>
              {/* Crypto header */}
              <div className="liquid-glass-card p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    {selected.image && <img src={selected.image} alt={selected.symbol} className="h-10 w-10 rounded-full" />}
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-lg font-bold text-[var(--foreground)]">{selected.symbol?.toUpperCase()}</h2>
                        <span className="text-[10px] rounded-md px-1.5 py-0.5 text-[var(--text-muted)]" style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>#{selected.market_cap_rank}</span>
                      </div>
                      <p className="text-xs text-[var(--text-muted)]">{selected.name}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {signal && <SignalBadge action={signal.action as SignalAction} confidence={signal.confidence} size="sm" />}
                    <button
                      onClick={() => setWatchlist(toggleWatchlist(selected.symbol))}
                      className={cn("p-1.5 rounded-lg", watchlist.includes(selected.symbol?.toUpperCase()) ? "text-[#c6f135]" : "text-[var(--text-muted)] hover:text-[var(--foreground)]")}
                    >
                      <Star className="h-4 w-4" fill={watchlist.includes(selected.symbol?.toUpperCase()) ? "currentColor" : "none"} />
                    </button>
                  </div>
                </div>

                {/* Price */}
                <div className="flex items-baseline gap-3 mb-3">
                  <span className="text-3xl font-bold text-[var(--foreground)]">{format(selected.current_price)}</span>
                  <span className={cn("text-sm font-medium flex items-center gap-0.5", positive ? "text-[#22c55e]" : "text-[#ef4444]")}>
                    {positive ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
                    {positive ? "+" : ""}{pct.toFixed(2)}%
                  </span>
                </div>

                {/* Quick stats row */}
                <div className="grid grid-cols-3 gap-2 text-[10px]">
                  <div className="rounded-lg p-2" style={{ background: "var(--glass-bg)" }}>
                    <span className="text-[var(--text-muted)]">24h High</span>
                    <p className="text-[var(--foreground)] font-semibold mt-0.5">{format(selected.high_24h ?? 0)}</p>
                  </div>
                  <div className="rounded-lg p-2" style={{ background: "var(--glass-bg)" }}>
                    <span className="text-[var(--text-muted)]">24h Low</span>
                    <p className="text-[var(--foreground)] font-semibold mt-0.5">{format(selected.low_24h ?? 0)}</p>
                  </div>
                  <div className="rounded-lg p-2" style={{ background: "var(--glass-bg)" }}>
                    <span className="text-[var(--text-muted)]">Volume</span>
                    <p className="text-[var(--foreground)] font-semibold mt-0.5">${((selected.total_volume ?? 0) / 1e6).toFixed(0)}M</p>
                  </div>
                </div>
              </div>

              {/* Chart */}
              <div className="liquid-glass-card p-3">
                <PriceChart
                  key={selected.symbol}
                  symbol={selected.symbol?.toUpperCase()}
                  height={320}
                  type="candlestick"
                  showIntervals
                  defaultInterval="1D"
                />
              </div>

              {/* Indicators */}
              {signal && signal.indicators.length > 0 && (
                <div className="liquid-glass-card p-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {signal.indicators.map((ind) => (
                    <IndicatorBar key={ind.name} name={ind.name} value={ind.value} signal={ind.signal} description={ind.description} />
                  ))}
                </div>
              )}

              {/* Buy/Sell buttons */}
              <div className="flex gap-2">
                <button
                  onClick={() => setTradeModal(true)}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl py-3 text-sm font-bold bg-[#22c55e] text-white hover:bg-[#16a34a] transition-all"
                >
                  <TrendingUp className="h-4 w-4" /> Buy {selected.symbol?.toUpperCase()}
                </button>
                <button
                  onClick={() => setTradeModal(true)}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl py-3 text-sm font-bold border border-[#ef4444]/30 bg-[#ef4444]/10 text-[#ef4444] hover:bg-[#ef4444]/20 transition-all"
                >
                  <TrendingDown className="h-4 w-4" /> Sell {selected.symbol?.toUpperCase()}
                </button>
              </div>
            </>
          )}
        </div>

        {/* ─── Right: Crypto List ─── */}
        <div className="lg:w-[45%] xl:w-[40%] flex flex-col min-h-0">
          {/* Search + Tabs */}
          <div className="mb-3 flex items-center gap-2 rounded-xl px-3 py-2" style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>
            <Search className="h-3.5 w-3.5 text-[var(--text-muted)]" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search..." className="flex-1 bg-transparent text-xs text-[var(--foreground)] outline-none placeholder-[var(--text-muted)]" />
          </div>

          <div className="mb-3 flex gap-1 overflow-x-auto">
            {([
              { id: "all" as Tab, label: "All", icon: BarChart3 },
              { id: "gainers" as Tab, label: "Gainers", icon: TrendingUp },
              { id: "losers" as Tab, label: "Losers", icon: TrendingDown },
              { id: "watchlist" as Tab, label: "Watchlist", icon: Star },
            ]).map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)} className={cn("flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1.5 text-[11px] font-medium transition-all", tab === t.id ? "accent-bg accent-text" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]")}>
                <t.icon className="h-3 w-3" /> {t.label}
              </button>
            ))}
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto max-h-[65vh] lg:max-h-[75vh] space-y-0.5 pr-1">
            {loading ? (
              Array.from({ length: 15 }).map((_, i) => <div key={i} className="h-14 animate-pulse rounded-xl" style={{ background: "var(--glass-bg)" }} />)
            ) : (
              filtered.map((c) => {
                const pos = (c.price_change_percentage_24h ?? 0) >= 0;
                const isSelected = selected?.symbol === c.symbol;
                const isWatched = watchlist.includes(c.symbol?.toUpperCase());
                return (
                  <button
                    key={c.id || c.symbol}
                    onClick={() => setSelected(c)}
                    className={cn(
                      "w-full flex items-center gap-2 rounded-xl px-2.5 py-2 text-left transition-all",
                      isSelected ? "accent-bg ring-1 ring-[var(--page-accent)]/30" : "hover:bg-[var(--glass-bg)]",
                    )}
                  >
                    <button
                      onClick={(e) => { e.stopPropagation(); setWatchlist(toggleWatchlist(c.symbol)); }}
                      className={cn("flex-shrink-0", isWatched ? "text-[#c6f135]" : "text-[var(--elevated)]")}
                    >
                      <Star className="h-3.5 w-3.5" fill={isWatched ? "currentColor" : "none"} />
                    </button>
                    <span className="w-5 text-right text-[9px] text-[var(--text-muted)]">{c.market_cap_rank}</span>
                    {c.image && <img src={c.image} alt="" className="h-6 w-6 rounded-full flex-shrink-0" />}
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] font-semibold text-[var(--foreground)] truncate">{c.symbol?.toUpperCase()}</p>
                      <p className="text-[10px] text-[var(--text-muted)] truncate">{c.name}</p>
                    </div>
                    <div className="hidden sm:block"><MiniSparkline data={c.sparkline_in_7d ?? []} positive={pos} /></div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-[12px] font-semibold text-[var(--foreground)]">{format(c.current_price)}</p>
                      <p className={cn("text-[10px] font-medium", pos ? "text-[#22c55e]" : "text-[#ef4444]")}>{pos ? "+" : ""}{(c.price_change_percentage_24h ?? 0).toFixed(2)}%</p>
                    </div>
                  </button>
                );
              })
            )}
            {!loading && filtered.length === 0 && (
              <div className="py-12 text-center text-xs text-[var(--text-muted)]">{tab === "watchlist" ? "No favorites yet." : "No results."}</div>
            )}
          </div>
        </div>
      </div>

      {/* Trade Modal */}
      {tradeModal && selected && (
        <QuickTradeModal
          symbol={selected.symbol?.toUpperCase()}
          price={selected.current_price}
          onClose={() => setTradeModal(false)}
        />
      )}
    </div>
  );
}
