"use client";

import { useEffect, useState } from "react";
import { usePageAccent, PAGE_ACCENTS } from "@/components/providers/theme-provider";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Star, TrendingUp, TrendingDown, BarChart3, DollarSign, Activity } from "lucide-react";
import { pricesApi } from "@/lib/api";
import { priceWs } from "@/lib/websocket";
import { PriceChart } from "@/components/charts/price-chart";
import { QuickTradeModal } from "@/components/trading/quick-trade-modal";
import { cn } from "@/lib/utils";

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

function getWatchlist(): string[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem("watchlist") || "[]"); } catch { return []; }
}

function toggleWL(symbol: string): string[] {
  const list = getWatchlist();
  const upper = symbol.toUpperCase();
  const next = list.includes(upper) ? list.filter((s) => s !== upper) : [...list, upper];
  localStorage.setItem("watchlist", JSON.stringify(next));
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

export default function CryptoDetailClient() {
  usePageAccent(PAGE_ACCENTS.crypto.accent, PAGE_ACCENTS.crypto.glow);
  const params = useParams();
  const symbol = (params.symbol as string || "BTC").toUpperCase();

  const [coin, setCoin] = useState<CoinData | null>(null);
  const [livePrice, setLivePrice] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [tradeModal, setTradeModal] = useState(false);
  const [isWatched, setIsWatched] = useState(false);

  useEffect(() => {
    setIsWatched(getWatchlist().includes(symbol));
    pricesApi.getAllCryptos(250).then((res) => {
      const data = res.data as unknown as CoinData[];
      const found = data.find((c) => c.symbol?.toUpperCase() === symbol);
      if (found) { setCoin(found); setLivePrice(found.current_price); }
    }).catch(() => {}).finally(() => setLoading(false));
  }, [symbol]);

  useEffect(() => {
    const unsub = priceWs.subscribe(symbol, (data) => { if (data.price) setLivePrice(data.price); });
    return unsub;
  }, [symbol]);

  const price = livePrice || coin?.current_price || 0;
  const changePct = coin?.price_change_percentage_24h ?? 0;
  const positive = changePct >= 0;

  if (loading) {
    return <div className="mx-auto max-w-4xl animate-pulse"><div className="mb-6 h-8 w-32 rounded bg-[#1a1a24]" /><div className="mb-4 h-[400px] rounded-2xl bg-[#14141b]" /></div>;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/crypto" className="rounded-lg p-2 text-[#55556a] hover:bg-[rgba(255,255,255,0.05)] hover:text-white"><ArrowLeft className="h-5 w-5" /></Link>
          {coin?.image && <img src={coin.image} alt={symbol} className="h-10 w-10 rounded-full" />}
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-white">{symbol}</h1>
              {coin?.market_cap_rank && <span className="rounded-md bg-[#1a1a24] px-2 py-0.5 text-[10px] font-medium text-[#55556a]">#{coin.market_cap_rank}</span>}
            </div>
            <p className="text-sm text-[#55556a]">{coin?.name}</p>
          </div>
        </div>
        <button onClick={() => { setIsWatched((prev) => { toggleWL(symbol); return !prev; }); }} className={cn("rounded-lg p-2 transition-colors", isWatched ? "text-[#c6f135]" : "text-[#55556a] hover:text-[#8888a0]")}>
          <Star className="h-5 w-5" fill={isWatched ? "currentColor" : "none"} />
        </button>
      </div>

      <div className="mb-6">
        <p className="text-4xl font-bold text-white">{fmt(price)}</p>
        <p className={cn("mt-1 text-sm font-medium", positive ? "text-[#06d6a0]" : "text-red-400")}>{positive ? "+" : ""}{changePct.toFixed(2)}% today</p>
      </div>

      <div className="mb-6 rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] p-4">
        <PriceChart symbol={symbol} height={400} type="candlestick" showIntervals defaultInterval="1M" />
      </div>

      <div className="mb-8 flex gap-3">
        <button onClick={() => setTradeModal(true)} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] py-4 text-base font-bold text-[#0d0d12] transition-transform hover:scale-[1.01]">
          <TrendingUp className="h-5 w-5" /> Buy {symbol}
        </button>
        <button onClick={() => setTradeModal(true)} className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 py-4 text-base font-bold text-red-400 transition-all hover:bg-red-500/20">
          <TrendingDown className="h-5 w-5" /> Sell {symbol}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: "Market Cap", value: fmt(coin?.market_cap), icon: BarChart3 },
          { label: "24h Volume", value: fmt(coin?.total_volume), icon: Activity },
          { label: "24h High", value: fmt(coin?.high_24h), icon: TrendingUp },
          { label: "24h Low", value: fmt(coin?.low_24h), icon: TrendingDown },
          { label: "Circ. Supply", value: coin?.circulating_supply ? `${(coin.circulating_supply / 1e6).toFixed(1)}M` : "\u2014", icon: DollarSign },
          { label: "Total Supply", value: coin?.total_supply ? `${(coin.total_supply / 1e6).toFixed(1)}M` : "\u2014", icon: DollarSign },
          { label: "ATH", value: fmt(coin?.ath), icon: TrendingUp },
          { label: "ATH Change", value: coin?.ath_change_percentage ? `${coin.ath_change_percentage.toFixed(1)}%` : "\u2014", icon: TrendingDown },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] p-4">
            <div className="mb-2 flex items-center gap-1.5"><s.icon className="h-3.5 w-3.5 text-[#55556a]" /><span className="text-[10px] uppercase tracking-wider text-[#55556a]">{s.label}</span></div>
            <p className="text-sm font-semibold text-white">{s.value}</p>
          </div>
        ))}
      </div>

      {tradeModal && <QuickTradeModal symbol={symbol} price={price} onClose={() => setTradeModal(false)} />}
    </div>
  );
}
