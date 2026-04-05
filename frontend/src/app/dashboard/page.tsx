"use client";

import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { WalletAccessPanel } from "@/components/account/wallet-access-panel";
import { usePageAccent, PAGE_ACCENTS } from "@/components/providers/theme-provider";
import { useCurrency } from "@/components/providers/currency-provider";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
  ColorType,
  LineSeries,
} from "lightweight-charts";
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  ArrowDownRight,
  ShieldCheck,
  Layers,
  RefreshCw,
  Activity,
  Sparkles,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { authApi, binanceApi, aiApi, analyticsApi, portfolioApi, pricesApi } from "@/lib/api";
import type { CryptoMarketData, RiskMetrics, UserProfile } from "@/lib/types";
import { cn, formatPercent } from "@/lib/utils";
import { PriceChart } from "@/components/charts/price-chart";

// ============================================================
// Constants (no magic numbers scattered in the code)
// ============================================================

const REFRESH_INTERVAL = 30_000;
const CHART_HEIGHT = 260;
const TOP_PERFORMERS_COUNT = 15;
const TOP_HOLDINGS_COUNT = 5;
const TOP_GAINERS_COUNT = 3;
const EQUITY_ASSETS_LIMIT = 6;
const EQUITY_DAYS = 90;
const EQUITY_MIN_WEIGHT = 0.02;
const TRADE_SYMBOLS_LIMIT = 5;
const TICKER_COUNT = 20;
const ALLOC_BAR_LIMIT = 8;
const ALLOC_LEGEND_LIMIT = 6;
const AI_CACHE_TTL = 600_000; // 10 min
const AI_MAX_CHARS = 1200;

const STABLES = new Set(["USDT", "BUSD", "USDC", "USD", "FDUSD", "DAI", "TUSD", "USD1"]);
const ALLOC_COLORS = ["#a855f7", "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#ec4899", "#06d6a0", "#6366f1"];

// ============================================================
// Types
// ============================================================

interface HoldingData {
  asset: string;
  total: number;
  price: number;
  value: number;
  change24h: number;
}

interface EquityPoint {
  time: number;
  value: number;
}

interface TradeMarker {
  time: number;
  side: "buy" | "sell";
  symbol: string;
  price: number;
  qty: number;
}

// ============================================================
// Helpers
// ============================================================

function computeRiskScore(holdings: HoldingData[], totalValue: number): number {
  if (holdings.length === 0 || totalValue <= 0) return 0;
  const weights = holdings.map((h) => h.value / totalValue);
  const hhi = weights.reduce((sum, w) => sum + w * w, 0);
  const weightedVol = holdings.reduce((sum, h, i) => sum + weights[i] * Math.abs(h.change24h), 0);
  const stableRatio = holdings.filter((h) => STABLES.has(h.asset)).reduce((sum, h) => sum + h.value, 0) / totalValue;
  const divPenalty = Math.max(0, 1 - holdings.length / 15);
  const raw = hhi * 35 + Math.min(weightedVol / 10, 1) * 30 + divPenalty * 15 + (1 - stableRatio) * 20;
  return Math.round(Math.max(0, Math.min(100, raw)));
}

function riskLabel(s: number) { return s <= 25 ? "Low Risk" : s <= 50 ? "Moderate" : s <= 75 ? "High Risk" : "Very High"; }
function riskColor(s: number) { return s <= 25 ? "text-[var(--success)]" : s <= 50 ? "text-[#c6f135]" : s <= 75 ? "text-[var(--warning)]" : "text-[var(--danger)]"; }
function riskLevelLabel(level?: RiskMetrics["risk_level"]) { return level ? `${level.charAt(0).toUpperCase()}${level.slice(1)}` : null; }
function fearGreedColor(v: number) { return v <= 25 ? "text-[var(--danger)]" : v <= 45 ? "text-[var(--warning)]" : v <= 55 ? "text-[var(--text-secondary)]" : "text-[var(--success)]"; }
function fearGreedLabel(v: number) { return v <= 25 ? "Extreme Fear" : v <= 45 ? "Fear" : v <= 55 ? "Neutral" : v <= 75 ? "Greed" : "Extreme Greed"; }

function safePnlPct(totalValue: number, pnl24h: number): number {
  const base = totalValue - pnl24h;
  if (base <= 0 || !Number.isFinite(base)) return 0;
  return (pnl24h / base) * 100;
}

function readCache(key: string, ttl: number): string | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (Date.now() - parsed.ts < ttl) return parsed.text;
  } catch { /* corrupted cache, ignore */ }
  return null;
}

function writeCache(key: string, text: string) {
  try { localStorage.setItem(key, JSON.stringify({ text, ts: Date.now() })); } catch { /* full or disabled */ }
}

// ============================================================
// Equity Chart Component
// ============================================================

function EquityChart({ data, trades }: { data: EquityPoint[]; trades: TradeMarker[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [period, setPeriod] = useState<"1W" | "1M" | "3M" | "ALL">("1M");

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      height: CHART_HEIGHT,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8888a0", fontSize: 12 },
      grid: { vertLines: { color: "rgba(255,255,255,0.03)" }, horzLines: { color: "rgba(255,255,255,0.03)" } },
      crosshair: { vertLine: { color: "rgba(6,214,160,0.3)", width: 1, labelBackgroundColor: "#14141b" }, horzLine: { color: "rgba(6,214,160,0.3)", width: 1, labelBackgroundColor: "#14141b" } },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.06)" },
      timeScale: { borderColor: "rgba(255,255,255,0.06)", timeVisible: false },
    });
    const series = chart.addSeries(LineSeries, { color: "#06d6a0", lineWidth: 2, crosshairMarkerBackgroundColor: "#06d6a0", priceLineVisible: false, lastValueVisible: true });
    chartRef.current = chart;
    seriesRef.current = series;
    const observer = new ResizeObserver(() => { if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth }); });
    observer.observe(containerRef.current);
    return () => { observer.disconnect(); chart.remove(); chartRef.current = null; seriesRef.current = null; };
  }, []);

  useEffect(() => {
    if (!chartRef.current || !seriesRef.current || data.length === 0) return;
    const now = Date.now() / 1000;
    const periodSec: Record<string, number> = { "1W": 7 * 86400, "1M": 30 * 86400, "3M": 90 * 86400, ALL: Infinity };
    const cutoff = now - (periodSec[period] ?? Infinity);
    const filtered = data.filter((p) => p.time >= cutoff);
    const points = (filtered.length > 2 ? filtered : data).map((p) => ({ time: p.time as Time, value: p.value }));
    seriesRef.current.setData(points);

    // Trade markers (setMarkers exists at runtime, wrapped in try-catch for safety)
    if (trades.length > 0) {
      try {
        const markers = trades.filter((t) => t.time >= cutoff).map((t) => ({
          time: t.time as Time,
          position: t.side === "buy" ? ("belowBar" as const) : ("aboveBar" as const),
          color: t.side === "buy" ? "#06d6a0" : "#ef4444",
          shape: t.side === "buy" ? ("arrowUp" as const) : ("arrowDown" as const),
          text: `${t.side.toUpperCase()} ${t.symbol}`,
        })).sort((a, b) => Number(a.time) - Number(b.time));
        if (markers.length > 0) {
          (seriesRef.current as unknown as { setMarkers: (m: typeof markers) => void }).setMarkers(markers);
        }
      } catch { /* setMarkers not available in this version */ }
    }
    chartRef.current.timeScale().fitContent();
  }, [data, trades, period]);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-[var(--foreground)] flex items-center gap-1.5">
          <Activity className="h-3.5 w-3.5 accent-text" /> Portfolio Performance
        </h2>
        <div className="flex gap-1">
          {(["1W", "1M", "3M", "ALL"] as const).map((p) => (
            <button key={p} onClick={() => setPeriod(p)} className={cn("rounded-md px-2.5 py-1 text-[12px] font-medium transition-all", period === p ? "bg-[var(--page-accent)]/15 text-[var(--page-accent)]" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]")}>{p}</button>
          ))}
        </div>
      </div>
      {data.length === 0 ? (
        <div className="flex h-[260px] items-center justify-center text-[14px] text-[var(--text-muted)]">Chargement des donn&eacute;es...</div>
      ) : (
        <div ref={containerRef} className="rounded-xl overflow-hidden" />
      )}
      {trades.length > 0 && (
        <div className="flex items-center gap-4 mt-2">
          <span className="flex items-center gap-1 text-[11px] text-[var(--text-muted)]"><span className="h-2 w-2 rounded-full bg-[var(--success)]" /> Buy</span>
          <span className="flex items-center gap-1 text-[11px] text-[var(--text-muted)]"><span className="h-2 w-2 rounded-full bg-[var(--danger)]" /> Sell</span>
        </div>
      )}
    </div>
  );
}

// ============================================================
// Dashboard Page
// ============================================================

export default function DashboardPage() {
  usePageAccent(PAGE_ACCENTS.dashboard.accent, PAGE_ACCENTS.dashboard.glow);
  const { format } = useCurrency();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [account, setAccount] = useState<UserProfile | null>(null);
  const [cryptos, setCryptos] = useState<CryptoMarketData[]>([]);
  const [holdings, setHoldings] = useState<HoldingData[]>([]);
  const [totalValue, setTotalValue] = useState(0);
  const [pnl24h, setPnl24h] = useState(0);
  const [fearGreed, setFearGreed] = useState<number>(50);
  const [openOrderCount, setOpenOrderCount] = useState(0);
  const [lastUpdate, setLastUpdate] = useState("");
  const [equityData, setEquityData] = useState<EquityPoint[]>([]);
  const [recentTrades, setRecentTrades] = useState<TradeMarker[]>([]);
  const [aiInsight, setAiInsight] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);

  const fetchData = useCallback(async () => {
    setError(null);
    try {
      const [allCryptosResult, fgData, profileResult] = await Promise.allSettled([
        pricesApi.getAllCryptos(250),
        pricesApi.getFearGreed(),
        authApi.getMe(),
      ]);

      let cryptoList: CryptoMarketData[] = [];
      if (allCryptosResult.status === "fulfilled") { cryptoList = allCryptosResult.value.data; setCryptos(cryptoList); }
      if (fgData.status === "fulfilled") setFearGreed(fgData.value.value);
      setAccount(profileResult.status === "fulfilled" ? profileResult.value : null);

      const walletUnlocked =
        profileResult.status === "fulfilled" ? profileResult.value.wallet_access_enabled : false;

      if (!walletUnlocked) {
        setHoldings([]);
        setTotalValue(0);
        setPnl24h(0);
        setOpenOrderCount(0);
        setEquityData([]);
        setRecentTrades([]);
        setRiskMetrics(null);
        setLastUpdate(new Date().toLocaleTimeString());
        return;
      }

      const [snapshotResult, riskResult] = await Promise.allSettled([
        portfolioApi.getSnapshot(),
        analyticsApi.getRiskMetrics(),
      ]);
      if (riskResult.status === "fulfilled") setRiskMetrics(riskResult.value);

      if (snapshotResult.status === "rejected") {
        setError("Impossible de charger le snapshot portefeuille canonique.");
      }
      const snapshot = snapshotResult.status === "fulfilled" ? snapshotResult.value : null;
      const items: HoldingData[] = (snapshot?.holdings ?? []).map((holding) => ({
        asset: holding.symbol,
        total: holding.total,
        price: holding.price,
        value: holding.value,
        change24h: holding.change_pct_24h,
      }));
      const total = snapshot?.summary.equity ?? 0;
      const pnlAcc = snapshot?.summary.day_change_value ?? 0;
      setOpenOrderCount(snapshot?.summary.open_orders_count ?? 0);

      items.sort((a, b) => b.value - a.value);
      setHoldings(items);
      setTotalValue(total);
      setPnl24h(pnlAcc);
      setLastUpdate(new Date().toLocaleTimeString());

      // --- Equity curve from klines ---
      const nonStable = items.filter((h) => !STABLES.has(h.asset) && h.value > total * EQUITY_MIN_WEIGHT);
      const stableValue = items.filter((h) => STABLES.has(h.asset)).reduce((s, h) => s + h.value, 0);
      const topForChart = nonStable.slice(0, EQUITY_ASSETS_LIMIT);

      if (topForChart.length > 0) {
        const klineResults = await Promise.allSettled(
          topForChart.map((h) => pricesApi.getOHLCV(h.asset, "1d", EQUITY_DAYS)),
        );
        const dayMap = new Map<number, number>();
        klineResults.forEach((res, idx) => {
          if (res.status !== "fulfilled" || !Array.isArray(res.value) || res.value.length === 0) return;
          const holding = topForChart[idx];
          for (const candle of res.value) {
            const existing = dayMap.get(candle.time) ?? stableValue;
            dayMap.set(candle.time, existing + holding.total * candle.close);
          }
        });
        const equity = Array.from(dayMap.entries()).sort((a, b) => a[0] - b[0]).map(([time, value]) => ({ time, value }));
        if (equity.length > 0) setEquityData(equity);
      }

      // --- Trades from top holdings ---
      const topSymbols = nonStable.slice(0, TRADE_SYMBOLS_LIMIT).map((h) => h.asset);
      const tradeResults = await Promise.allSettled(topSymbols.map((sym) => binanceApi.getMyTrades(sym)));
      const allTrades: TradeMarker[] = [];
      tradeResults.forEach((res, idx) => {
        if (res.status !== "fulfilled" || !Array.isArray(res.value)) return;
        for (const t of res.value) {
          const trade = t as Record<string, unknown>;
          const time = typeof trade.time === "number" ? trade.time : 0;
          const price = typeof trade.price === "string" ? parseFloat(trade.price) : 0;
          if (time > 0 && price > 0) {
            allTrades.push({
              time: Math.floor(time / 1000),
              side: trade.isBuyer ? "buy" : "sell",
              symbol: topSymbols[idx],
              price,
              qty: typeof trade.qty === "string" ? parseFloat(trade.qty) : 0,
            });
          }
        }
      });
      allTrades.sort((a, b) => a.time - b.time);
      setRecentTrades(allTrades);

    } catch { /* per-request errors handled above */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); const i = setInterval(fetchData, REFRESH_INTERVAL); return () => clearInterval(i); }, [fetchData]);

  // --- Computed ---
  const riskScore = useMemo(
    () => Math.round(riskMetrics?.risk_score ?? computeRiskScore(holdings, totalValue)),
    [holdings, riskMetrics?.risk_score, totalValue],
  );
  const walletUnlocked = account?.wallet_access_enabled ?? false;
  const riskSummary = riskLevelLabel(riskMetrics?.risk_level) ?? riskLabel(riskScore);
  const pnlPct = safePnlPct(totalValue, pnl24h);
  const topPerformers = useMemo(() => [...cryptos].sort((a, b) => b.change_pct_24h - a.change_pct_24h).slice(0, TOP_PERFORMERS_COUNT), [cryptos]);
  const nonStableHoldings = holdings.filter((h) => !STABLES.has(h.asset) && h.change24h !== 0);
  const topGainers = [...nonStableHoldings].sort((a, b) => b.change24h - a.change24h).slice(0, TOP_GAINERS_COUNT);
  const topLosers = [...nonStableHoldings].sort((a, b) => a.change24h - b.change24h).filter((h) => h.change24h < 0).slice(0, TOP_GAINERS_COUNT);

  // --- AI handler ---
  const handleAiAnalysis = useCallback(async () => {
    if (!walletUnlocked) return;
    setAiLoading(true);
    try {
      const cached = readCache("okamoey-dash-insight", AI_CACHE_TTL);
      if (cached) { setAiInsight(cached); setAiLoading(false); return; }

      const res = await aiApi.analyzePerformance({
        total_value: totalValue,
        pnl_24h: pnl24h,
        pnl_pct: pnlPct,
        risk_score: riskScore,
        holdings_count: holdings.length,
        top_holdings: holdings.slice(0, TOP_HOLDINGS_COUNT).map((h) => ({ asset: h.asset, value: h.value, change24h: h.change24h })),
        fear_greed: fearGreed,
        top_gainers: topGainers.map((h) => ({ asset: h.asset, change: h.change24h })),
        top_losers: topLosers.map((h) => ({ asset: h.asset, change: h.change24h })),
      });
      const text = res.analysis.slice(0, AI_MAX_CHARS);
      setAiInsight(text);
      writeCache("okamoey-dash-insight", text);
    } catch {
      setAiInsight("IA indisponible. V\u00e9rifiez la cl\u00e9 API OpenAI dans le fichier .env.");
    } finally { setAiLoading(false); }
  }, [fearGreed, holdings, pnl24h, pnlPct, riskScore, topGainers, topLosers, totalValue, walletUnlocked]);

  // ---- Loading ----
  if (loading) {
    return (
      <div className="mx-auto max-w-6xl p-4 md:p-8">
        <div className="h-6 w-40 animate-pulse rounded-lg bg-white/5 mb-6" />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 mb-6">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-20 animate-pulse rounded-xl bg-white/5" />)}</div>
        <div className="h-[260px] animate-pulse rounded-xl bg-white/5 mb-6" />
        <div className="h-80 animate-pulse rounded-xl bg-white/5" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl p-4 md:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl md:text-2xl font-bold glow-text">Dashboard</h1>
          <p className="text-[13px] text-[var(--text-muted)]">Binance live &middot; Auto-refresh 30s</p>
        </div>
        <button onClick={fetchData} className="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-[13px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all">
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          {lastUpdate && <span>{lastUpdate}</span>}
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 mb-4 rounded-xl px-3 py-2.5 text-[14px] text-[var(--danger)] bg-[var(--danger)]/8">
          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" /> {error}
        </div>
      )}

      {!walletUnlocked && (
        <div className="mb-6">
          <WalletAccessPanel
            compact
            title="Portfolio metrics are locked"
            reason={account?.wallet_access_reason}
          />
        </div>
      )}

      {/* Stat row */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-4 lg:grid-cols-4 mb-6">
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <Wallet className="h-3 w-3 accent-text opacity-50" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Portfolio</span>
          </div>
          <p className="text-2xl font-bold font-mono text-[var(--foreground)]">{walletUnlocked ? format(totalValue) : "Locked"}</p>
        </div>
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            {pnl24h >= 0 ? <TrendingUp className="h-3 w-3 text-[var(--success)] opacity-50" /> : <TrendingDown className="h-3 w-3 text-[var(--danger)] opacity-50" />}
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">24h Change</span>
          </div>
          <p className={cn("text-2xl font-bold font-mono", walletUnlocked ? (pnl24h >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]") : "text-[var(--foreground)]")}>
            {walletUnlocked ? `${pnl24h >= 0 ? "+" : ""}${format(pnl24h)}` : "Locked"}
          </p>
          <p className={cn("text-[12px] font-medium", walletUnlocked ? (pnl24h >= 0 ? "text-[var(--success)]/60" : "text-[var(--danger)]/60") : "text-[var(--text-muted)]")}>
            {walletUnlocked ? formatPercent(pnlPct) : "Connect an exchange in Settings"}
          </p>
        </div>
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <Layers className="h-3 w-3 accent-text opacity-50" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Assets</span>
          </div>
          <p className="text-2xl font-bold font-mono text-[var(--foreground)]">{walletUnlocked ? holdings.length : "Locked"}</p>
          <p className="text-[12px] text-[var(--text-muted)]">
            {walletUnlocked
              ? openOrderCount > 0
                ? `${openOrderCount} open order${openOrderCount > 1 ? "s" : ""}`
                : "No open orders"
              : "Private balances hidden"}
          </p>
        </div>
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <ShieldCheck className="h-3 w-3 accent-text opacity-50" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Risk Score</span>
          </div>
          <p className={cn("text-2xl font-bold font-mono", walletUnlocked ? riskColor(riskScore) : "text-[var(--foreground)]")}>
            {walletUnlocked ? <>{riskScore}<span className="text-sm font-normal text-[var(--text-muted)]">/100</span></> : "Locked"}
          </p>
          <p className={cn("text-[12px] font-medium", walletUnlocked ? riskColor(riskScore) : "text-[var(--text-muted)]")}>
            {walletUnlocked ? riskSummary : "Unlocked after connection"}
          </p>
        </div>
      </div>

      {/* Allocation bar */}
      {walletUnlocked && holdings.length > 0 && totalValue > 0 && (
        <div className="mb-6">
          <div className="flex h-2.5 rounded-full overflow-hidden gap-0.5">
            {holdings.slice(0, ALLOC_BAR_LIMIT).map((h, i) => { const pct = (h.value / totalValue) * 100; if (pct < 1) return null; return <div key={h.asset} className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: ALLOC_COLORS[i % ALLOC_COLORS.length] }} title={`${h.asset}: ${pct.toFixed(1)}%`} />; })}
          </div>
          <div className="flex flex-wrap gap-3 mt-2">
            {holdings.slice(0, ALLOC_LEGEND_LIMIT).map((h, i) => <span key={h.asset} className="flex items-center gap-1 text-[12px] text-[var(--text-muted)]"><span className="h-2 w-2 rounded-full" style={{ background: ALLOC_COLORS[i % ALLOC_COLORS.length] }} />{h.asset} {((h.value / totalValue) * 100).toFixed(1)}%</span>)}
          </div>
        </div>
      )}

      {/* Ticker strip */}
      {cryptos.length > 0 && (
        <div className="group relative overflow-hidden mb-6">
          <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-12 bg-gradient-to-r from-[var(--bg)] to-transparent" />
          <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-12 bg-gradient-to-l from-[var(--bg)] to-transparent" />
          <div className="flex w-max animate-ticker gap-3 pb-1 group-hover:[animation-play-state:paused]">
            {[...cryptos.slice(0, TICKER_COUNT), ...cryptos.slice(0, TICKER_COUNT)].map((coin, idx) => (
              <div key={`${coin.symbol}-${idx}`} className="flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-[13px] hover:bg-[var(--glass-bg)] transition-colors">
                <span className="font-semibold text-[var(--foreground)]">{coin.symbol}</span>
                <span className="text-[var(--text-secondary)]">{format(coin.price)}</span>
                <span className={cn("flex items-center font-semibold", coin.change_pct_24h >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>
                  {coin.change_pct_24h >= 0 ? <ArrowUpRight className="mr-0.5 h-2.5 w-2.5" /> : <ArrowDownRight className="mr-0.5 h-2.5 w-2.5" />}
                  {formatPercent(coin.change_pct_24h)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Equity Chart */}
      <div className="mb-6">
        {walletUnlocked ? (
          <EquityChart data={equityData} trades={recentTrades} />
        ) : (
          <WalletAccessPanel
            compact
            title="Portfolio performance stays hidden until wallet access is enabled"
            reason="You can explore market leaders and sentiment now. Equity curve, fills and portfolio attribution unlock after you connect your own exchange API."
          />
        )}
      </div>

      {/* 2-column layout */}
      <div className="grid grid-cols-1 gap-x-12 gap-y-8 lg:grid-cols-7">

        {/* Left — Top Performers */}
        <div className="lg:col-span-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-[var(--foreground)]">Top Performers</h2>
            <span className="text-[12px] text-[var(--text-muted)]">Best 24h change</span>
          </div>
          {topPerformers.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)] py-8 text-center">No market data</p>
          ) : (
            <div className="space-y-0.5">
              <div className="flex items-center gap-3 px-2 py-1 text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                <span className="w-5 text-center">#</span>
                <span className="flex-1">Asset</span>
                <span className="w-24 text-right">Price</span>
                <span className="w-14 text-right">24h</span>
                <span className="w-20 text-right hidden sm:block">Volume</span>
                <span className="w-16 text-right">Chart</span>
              </div>
              {topPerformers.map((coin, idx) => (
                <div key={coin.symbol} className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-[var(--glass-bg)] transition-all cursor-pointer">
                  <span className="w-5 text-center text-[12px] text-[var(--text-muted)]">{idx + 1}</span>
                  <div className="flex-1 min-w-0">
                    <span className="text-[14px] font-semibold text-[var(--foreground)]">{coin.symbol}</span>
                  </div>
                  <span className="w-24 text-right text-[13px] font-mono text-[var(--foreground)]">{format(coin.price)}</span>
                  <span className={cn("w-14 text-right text-[12px] font-semibold", coin.change_pct_24h >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>{formatPercent(coin.change_pct_24h)}</span>
                  <span className="w-20 text-right text-[12px] text-[var(--text-muted)] hidden sm:block">{coin.volume_24h ? `$${(coin.volume_24h / 1e9).toFixed(1)}B` : "\u2014"}</span>
                  <div className="w-16"><PriceChart symbol={coin.symbol} height={28} type="line" /></div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="lg:col-span-3 space-y-8">

          {/* AI Insight */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 accent-text" /> AI Insight
              </h2>
              <button onClick={handleAiAnalysis} disabled={aiLoading || !walletUnlocked}
                className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[13px] font-medium accent-text hover:bg-[var(--glass-bg)] transition-all disabled:opacity-40"
                >
                {aiLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                {aiLoading ? "Analyse..." : walletUnlocked ? "Analyser" : "Locked"}
              </button>
            </div>
            {!walletUnlocked ? (
              <p className="text-[14px] text-[var(--text-muted)] leading-relaxed">
                Connect your own exchange credentials to unlock AI portfolio analysis, allocation diagnostics and personalised risk commentary.
              </p>
            ) : aiInsight ? (
              <div className="relative">
                <div className="max-h-[320px] overflow-y-auto pr-2 custom-scrollbar">
                  <div className="text-[15px] leading-[1.75] text-[var(--text-secondary)]">
                    {aiInsight.split("\n").map((line, i) => {
                      const trimmed = line.trim();
                      if (!trimmed) return <div key={i} className="h-3" />;
                      const isLabel = /^(SITUATION|DYNAMIQUE|OPPORTUNIT|CONSEIL|RISQUE)/i.test(trimmed);
                      if (isLabel) {
                        const colonIdx = trimmed.indexOf(":");
                        const label = colonIdx > 0 ? trimmed.slice(0, colonIdx) : trimmed;
                        const body = colonIdx > 0 ? trimmed.slice(colonIdx + 1).trim() : "";
                        return (
                          <div key={i} className="mb-3">
                            <p className="text-[13px] font-bold uppercase tracking-[0.12em] accent-text mb-1">{label.trim()}</p>
                            {body && <p className="text-[15px] leading-[1.75] text-[var(--text-secondary)]">{body}</p>}
                          </div>
                        );
                      }
                      return <p key={i} className="mb-2 text-[15px] leading-[1.75]">{trimmed}</p>;
                    })}
                  </div>
                </div>
                {/* Scroll fade indicator */}
                <div className="pointer-events-none absolute bottom-0 left-0 right-2 h-6 bg-gradient-to-t from-[var(--bg)] to-transparent" />
              </div>
            ) : (
              <p className="text-[14px] text-[var(--text-muted)] leading-relaxed">
                Analyse IA de votre portfolio : situation, dynamique, opportunit&eacute;s et recommandations.
              </p>
            )}
          </div>

          {/* Fear & Greed */}
          <div>
            <h2 className="text-xs font-semibold text-[var(--foreground)] mb-3">Fear & Greed</h2>
            <div className="flex items-center gap-4">
              <div className="relative flex h-20 w-20 items-center justify-center flex-shrink-0">
                <svg className="absolute inset-0" viewBox="0 0 80 80">
                  <circle cx="40" cy="40" r="34" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="5" />
                  <circle cx="40" cy="40" r="34" fill="none" stroke="url(#fgGrad)" strokeWidth="5" strokeDasharray={`${(fearGreed / 100) * 213.6} 213.6`} strokeLinecap="round" transform="rotate(-90 40 40)" />
                  <defs><linearGradient id="fgGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#ef4444" /><stop offset="50%" stopColor="#c6f135" /><stop offset="100%" stopColor="#06d6a0" /></linearGradient></defs>
                </svg>
                <span className={cn("text-xl font-bold", fearGreedColor(fearGreed))}>{fearGreed}</span>
              </div>
              <div>
                <p className={cn("text-sm font-semibold", fearGreedColor(fearGreed))}>{fearGreedLabel(fearGreed)}</p>
                <p className="text-[12px] text-[var(--text-muted)] mt-0.5">Market sentiment</p>
              </div>
            </div>
          </div>

          {/* Today's Movers */}
          {nonStableHoldings.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold text-[var(--foreground)] mb-3">Today&apos;s Movers</h2>
              {topGainers.length > 0 && (
                <div className="mb-3">
                  <p className="text-[11px] uppercase tracking-wider text-[var(--success)]/60 mb-1.5">Gainers</p>
                  {topGainers.map((h) => <div key={h.asset} className="flex items-center justify-between py-1"><span className="text-[13px] font-semibold text-[var(--foreground)]">{h.asset}</span><span className="text-[12px] font-semibold text-[var(--success)]">+{h.change24h.toFixed(2)}%</span></div>)}
                </div>
              )}
              {topLosers.length > 0 && (
                <div>
                  <p className="text-[11px] uppercase tracking-wider text-[var(--danger)]/60 mb-1.5">Losers</p>
                  {topLosers.map((h) => <div key={h.asset} className="flex items-center justify-between py-1"><span className="text-[13px] font-semibold text-[var(--foreground)]">{h.asset}</span><span className="text-[12px] font-semibold text-[var(--danger)]">{h.change24h.toFixed(2)}%</span></div>)}
                </div>
              )}
            </div>
          )}

          {/* Top Holdings */}
          {holdings.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold text-[var(--foreground)] mb-3">Top Holdings</h2>
              <div className="space-y-2.5">
                {holdings.slice(0, TOP_HOLDINGS_COUNT).map((h) => {
                  const pct = totalValue > 0 ? (h.value / totalValue) * 100 : 0;
                  const pos = h.change24h >= 0;
                  return (
                    <div key={h.asset} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold" style={{ background: "var(--glass-bg-strong)" }}>{h.asset.slice(0, 2)}</div>
                        <div>
                          <p className="text-[13px] font-semibold text-[var(--foreground)]">{h.asset}</p>
                          <p className="text-[11px] text-[var(--text-muted)]">{pct.toFixed(1)}%</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-[13px] font-mono text-[var(--foreground)]">{format(h.value)}</p>
                        {h.change24h !== 0 && <p className={cn("text-[11px] font-medium", pos ? "text-[var(--success)]" : "text-[var(--danger)]")}>{pos ? "+" : ""}{h.change24h.toFixed(1)}%</p>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
