"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { Search, Star, TrendingUp, TrendingDown, BarChart3 } from "lucide-react";
import { pricesApi } from "@/lib/api";
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
      <polyline fill="none" stroke={positive ? "#06d6a0" : "#ef4444"} strokeWidth="1.5" points={points} />
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
  const [cryptos, setCryptos] = useState<CryptoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<Tab>("all");
  const [watchlist, setWatchlist] = useState<string[]>([]);

  useEffect(() => {
    setWatchlist(getWatchlist());
    pricesApi.getAllCryptos(250).then((res) => {
      setCryptos(res.data as unknown as CryptoItem[]);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

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

  const formatPrice = (p: number) => {
    if (!p) return "$0.00";
    if (p >= 1) return `$${p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (p >= 0.001) return `$${p.toFixed(4)}`;
    return `$${p.toFixed(8)}`;
  };

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-1 text-3xl font-bold glow-text">Crypto</h1>
      <p className="mb-6 text-sm text-[#55556a]">{cryptos.length} assets available</p>

      <div className="mb-5 flex items-center gap-2 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] px-4 py-3">
        <Search className="h-4 w-4 text-[#55556a]" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search crypto..." className="flex-1 bg-transparent text-sm text-white outline-none placeholder-[#55556a]" />
      </div>

      <div className="mb-5 flex gap-1 overflow-x-auto">
        {([
          { id: "all" as Tab, label: "All", icon: BarChart3 },
          { id: "gainers" as Tab, label: "Top Gainers", icon: TrendingUp },
          { id: "losers" as Tab, label: "Top Losers", icon: TrendingDown },
          { id: "watchlist" as Tab, label: "Watchlist", icon: Star },
        ]).map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className={cn("flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-2 text-xs font-medium transition-all", tab === t.id ? "bg-[#06d6a0]/15 text-[#06d6a0]" : "text-[#55556a] hover:text-[#8888a0]")}>
            <t.icon className="h-3.5 w-3.5" /> {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">{Array.from({ length: 10 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded-xl bg-[#14141b]" />)}</div>
      ) : (
        <div className="space-y-1">
          {filtered.map((c) => {
            const positive = (c.price_change_percentage_24h ?? 0) >= 0;
            const isWatched = watchlist.includes(c.symbol?.toUpperCase());
            return (
              <div key={c.id || c.symbol} className="group flex items-center gap-3 rounded-xl px-3 py-3 transition-all hover:bg-[rgba(255,255,255,0.02)]">
                <button onClick={() => setWatchlist(toggleWatchlist(c.symbol))} className={cn("flex-shrink-0 transition-colors", isWatched ? "text-[#c6f135]" : "text-[#2a2a3a] hover:text-[#55556a]")}>
                  <Star className="h-4 w-4" fill={isWatched ? "currentColor" : "none"} />
                </button>
                <Link href={`/crypto/${c.symbol?.toUpperCase()}`} className="flex flex-1 items-center gap-3 min-w-0">
                  <span className="w-6 text-right text-[10px] text-[#3a3a4a]">{c.market_cap_rank}</span>
                  {c.image && <img src={c.image} alt={c.symbol} className="h-8 w-8 rounded-full" />}
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-white">{c.symbol?.toUpperCase()}</p>
                    <p className="truncate text-xs text-[#55556a]">{c.name}</p>
                  </div>
                </Link>
                <div className="hidden sm:block"><MiniSparkline data={c.sparkline_in_7d ?? []} positive={positive} /></div>
                <Link href={`/crypto/${c.symbol?.toUpperCase()}`} className="flex flex-col items-end">
                  <p className="text-sm font-semibold text-white">{formatPrice(c.current_price)}</p>
                  <p className={cn("text-xs font-medium", positive ? "text-[#06d6a0]" : "text-red-400")}>{positive ? "+" : ""}{(c.price_change_percentage_24h ?? 0).toFixed(2)}%</p>
                </Link>
              </div>
            );
          })}
          {filtered.length === 0 && <div className="py-16 text-center text-sm text-[#55556a]">{tab === "watchlist" ? "No favorites yet. Tap the star to add." : "No results found."}</div>}
        </div>
      )}
    </div>
  );
}
