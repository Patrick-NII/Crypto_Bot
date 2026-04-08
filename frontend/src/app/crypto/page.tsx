"use client";

import { startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Bot,
  CandlestickChart,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  Wallet,
  Zap,
  Search,
  Star,
  X,
} from "lucide-react";
import { WalletAccessPanel } from "@/components/account/wallet-access-panel";
import { CryptoIcon } from "@/components/ui/crypto-icon";
import { usePageAccent, PAGE_ACCENTS, useTheme } from "@/components/providers/theme-provider";
import { useCurrency } from "@/components/providers/currency-provider";
import { PriceChart } from "@/components/charts/price-chart";
import { LiveSparkline } from "@/components/charts/live-sparkline";
import { QuickTradeModal } from "@/components/trading/quick-trade-modal";
import { MarketUniverseModal, type MarketUniverseItem } from "@/components/trading/market-universe-modal";
import { ScoreGauge, SignalReadout } from "@/components/trading/signal-score";
import {
  type AutoTradingHistorySnapshot,
  type AutoTradingStatusSnapshot,
} from "@/components/trading/auto-trading-monitor";
import { type SignalAction } from "@/components/trading/signal-badge";
import { ApiError, aiApi, analyticsApi, authApi, binanceApi, portfolioApi, pricesApi, signalsApi, strategiesApi, tradingApi } from "@/lib/api";
import {
  buildWalletHoldings,
  computeWalletCashValue,
  computeWalletMarketExposure,
  computeWalletValue,
  estimateWalletRiskScore,
  formatWalletRiskLevel,
  hasUsableRiskMetrics,
  type WalletHoldingView,
  WALLET_STABLES,
} from "@/lib/portfolio-view";
import { priceWs } from "@/lib/websocket";
import { cn, formatRelative } from "@/lib/utils";
import type {
  AnalyticsMetrics,
  CryptoMarketData,
  DeskChartType,
  MarketMoversView,
  MarketUniverseView,
  Order,
  PortfolioSnapshot,
  Strategy,
  UserProfile,
} from "@/lib/types";

const REFRESH_INTERVAL = 30_000;
const SIGNAL_REFRESH_INTERVAL = 45_000;
const SIGNAL_SCAN_LIMIT = 8;
const WATCHLIST_KEY = "watchlist";
const DEFAULT_WATCHLIST = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"];
const TRADING_VIEW_CACHE_KEY = "gluetrade-trading-view:v5";
const TRADING_VIEW_CACHE_TTL = 300_000;
const SCANNER_BLOCKLIST = new Set(["USDC", "USDT", "USD1", "FDUSD", "TUSD", "USDE", "XAUT", "PAXG", "STO", "U"]);
const COMPACT_MOVER_ROWS = 4;
const VISIBLE_PUBLICATION_FILTERS = 2;
const TOP_WALLET_ITEMS = 3;

interface SignalDetail {
  symbol: string;
  action: SignalAction;
  confidence: number;
  score: number;
  reasoning: string;
  indicators: Array<{ name: string; value: number; signal: number; description: string }>;
  timestamp: string;
  // V2 compat
  score_100: number;
  action_label: string;
  confidence_level: string;
  status: string;
  sub_scores: Array<{ category: string; score: number; label: string }>;
  key_reasons: string[];
  // V3 multi-dimensional
  direction: number;
  direction_label: string;
  confidence_score: number;
  risk: number;
  setup_quality: number;
  actionability: string;
  market_regime: string;
  signal_context: string;
  trend_context_score: number;
  trend_reliability_score: number;
  contradictions: Array<{ description: string; severity: string }>;
  signal_trade_plan: { side: string; entry_zone: string; invalidation_zone: string; target_zone: string; risk_reward: string; validity: string; execution_style: string } | null;
  horizon: string;
  setup_type: string;
  regime: string;
  regime_fit: number;
  confirmation_score: number;
  execution_risk: number;
  liquidity_score: number;
  notrade_reasons: string[];
  expected_holding_window: string;
  freshness_ms: number;
  publication_score: number;
  composite_score: number;
  reliability_score: number;
  display_score: number;
  published: boolean;
  scenario?: string | null;
  scenario_probability?: number | null;
}

type HoldingSnapshot = WalletHoldingView;

interface LiveTickerSnapshot {
  price: number;
  changePct24h?: number;
  volume24h?: number;
}

interface TradeOpportunity {
  symbol: string;
  side: "buy" | "sell";
  action: SignalAction;
  confidence: number;
  score: number;
  price: number;
  changePct: number;
  volume: number;
  volatility: number;
  recommendedUsd: number;
  currentValue: number;
  weight: number;
  reasoning: string;
  methods: string[];
  riskNote: string;
  edgeScore: number;
}

interface TradeIntent {
  side: "buy" | "sell";
  amount?: number;
  advisory?: string;
}

interface WalletPreviewItem {
  sym: string;
  fiat: boolean;
  stable: boolean;
  total: number;
  price: number;
  value: number;
  changePct: number;
  fiatSym: string;
  image?: string;
}

interface TradingViewCache {
  selectedSymbol: string | null;
  chartType: DeskChartType;
  moversView: MarketMoversView;
  universeView: MarketUniverseView;
  orders: Order[];
  analytics: AnalyticsMetrics | null;
  strategies: Strategy[];
  autoStatus: AutoTradingStatusSnapshot | null;
  autoHistory: AutoTradingHistorySnapshot[];
  health: { status: string; connected: boolean } | null;
  signalMap: Record<string, SignalDetail>;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function readObjectCache<T>(key: string, ttl: number): T | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { data?: T; ts?: number };
    if (parsed.ts == null || parsed.data == null) return null;
    if (Date.now() - parsed.ts > ttl) return null;
    return parsed.data;
  } catch {
    return null;
  }
}

function writeObjectCache<T>(key: string, data: T) {
  if (typeof window === "undefined") return;

  try {
    localStorage.setItem(key, JSON.stringify({ data, ts: Date.now() }));
  } catch {
    // Ignore storage issues.
  }
}

function unique<T>(items: T[]) {
  return Array.from(new Set(items));
}

function isScannerEligibleSymbol(symbol: string) {
  const upper = symbol.toUpperCase();
  if (!upper) return false;
  if (WALLET_STABLES.has(upper) || SCANNER_BLOCKLIST.has(upper)) return false;
  return /^[A-Z0-9]{2,12}$/.test(upper);
}

function normalizeAction(action: string): SignalAction {
  const upper = action.toUpperCase();
  if (
    upper === "STRONG_BUY" ||
    upper === "BUY" ||
    upper === "ACCUMULATE" ||
    upper === "HOLD" ||
    upper === "REDUCE" ||
    upper === "SELL" ||
    upper === "STRONG_SELL"
  ) {
    return upper;
  }
  return "HOLD";
}

function actionToSide(action: SignalAction): "buy" | "sell" | "hold" {
  if (action === "BUY" || action === "STRONG_BUY" || action === "ACCUMULATE") return "buy";
  if (action === "SELL" || action === "STRONG_SELL" || action === "REDUCE") return "sell";
  return "hold";
}

function uniqueStrings(items: string[]) {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const item of items) {
    const normalized = item.trim();
    if (!normalized) continue;
    const key = normalized.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(normalized);
  }
  return result;
}

function isDeskChartType(value: string | null | undefined): value is DeskChartType {
  return value === "candlestick" || value === "line";
}

function normalizeDeskChartType(value: string | null | undefined): DeskChartType {
  return isDeskChartType(value) ? value : "candlestick";
}

function normalizeMoversView(value: string | null | undefined): MarketMoversView {
  if (value === "gainers" || value === "losers" || value === "candidates") return value;
  return "candidates";
}

function normalizeUniverseView(value: string | null | undefined): MarketUniverseView {
  if (value === "all") return "all";
  return normalizeMoversView(value);
}

function sanitizeWatchlistSymbols(symbols: string[] | null | undefined) {
  if (!Array.isArray(symbols)) return [];
  return unique(
    symbols
      .map((symbol) => String(symbol ?? "").trim().toUpperCase())
      .filter((symbol) => /^[A-Z0-9]{2,12}$/.test(symbol) && !SCANNER_BLOCKLIST.has(symbol)),
  );
}

function normalizeSignalStatus(status?: string, actionability?: string) {
  const raw = String(status ?? actionability ?? "ignore").toLowerCase();
  if (raw === "high_conviction") return "high_conviction";
  if (raw === "actionable") return "actionable";
  if (raw === "watch") return "watch";
  return "ignore";
}

function isPublishedSignal(signal: Pick<SignalDetail, "published"> | { status?: string; actionability?: string }) {
  if ("published" in signal) return signal.published;
  const status = normalizeSignalStatus(signal.status, signal.actionability);
  return status === "actionable" || status === "high_conviction";
}

function computePublicationScore(signal: {
  publication_score?: number;
  composite_score?: number;
  reliability_score?: number;
  regime_fit?: number;
  confirmation_score?: number;
  setup_quality?: number;
  execution_risk?: number;
  status?: string;
  actionability?: string;
  contradictions?: Array<{ severity?: string }>;
}) {
  const provided = Number(signal.composite_score ?? signal.publication_score);
  if (Number.isFinite(provided) && provided >= 0) {
    return clamp(Math.round(provided), 0, 100);
  }
  const regimeFit = clamp(Number(signal.regime_fit ?? 0), 0, 100);
  const confirmationScore = clamp(Number(signal.confirmation_score ?? 0), 0, 100);
  const setupQuality = clamp(Number(signal.setup_quality ?? 0), 0, 100);
  const executionRisk = clamp(Number(signal.execution_risk ?? 50), 0, 100);
  const reliabilityScore = clamp(Number(signal.reliability_score ?? 50), 0, 100);
  const status = normalizeSignalStatus(signal.status, signal.actionability);
  const strongContradictions = (signal.contradictions ?? []).filter((item) => item?.severity === "strong").length;

  const weightedBase =
    regimeFit * 0.22 +
    confirmationScore * 0.22 +
    setupQuality * 0.22 +
    reliabilityScore * 0.18 +
    (100 - executionRisk) * 0.16;

  const blockerPenalty =
    Math.max(0, 70 - regimeFit) * 0.35 +
    Math.max(0, 60 - confirmationScore) * 0.8 +
    Math.max(0, 65 - setupQuality) * 0.6 +
    Math.max(0, 58 - reliabilityScore) * 0.55 +
    Math.max(0, executionRisk - 55) * 0.45 +
    strongContradictions * 8;

  const statusAdjustment =
    status === "high_conviction" ? 8 :
    status === "actionable" ? 4 :
    status === "watch" ? -3 :
    -7;

  return clamp(Math.round(weightedBase - blockerPenalty + statusAdjustment), 0, 100);
}

function nonPublishedActionLabel(score: number, status: string) {
  if (score >= 75) return status === "watch" ? "Observation forte" : "Sous conditions";
  if (score >= 60) return status === "watch" ? "A confirmer" : "Mitige";
  if (score >= 50) return status === "watch" ? "Mitige" : "Neutre fragile";
  return "Faible conviction";
}

function signalReadoutLabel(signal: SignalDetail) {
  const bias = signal.direction_label?.trim();
  if (!bias || bias === "Neutre / attente") return signal.action_label;
  return `${signal.action_label} · ${bias}`;
}

function scannerPriority(signal?: SignalDetail) {
  if (!signal) return -1;
  const statusBoost =
    signal.status === "high_conviction" ? 18 :
    signal.status === "actionable" ? 10 :
    signal.status === "watch" ? 4 :
    0;
  const directionalBonus = signal.published ? Math.abs((signal.direction ?? 50) - 50) * 0.12 : 0;
  return signal.composite_score * 0.85 + signal.reliability_score * 0.15 + statusBoost + directionalBonus;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toSignalDetail(signal: any): SignalDetail {
  const status = normalizeSignalStatus(signal.status, signal.actionability);
  const published = status === "actionable" || status === "high_conviction";
  const publicationScore = computePublicationScore(signal);
  const confidence = published
    ? Number(signal.confidence ?? 0)
    : clamp(publicationScore / 100, 0, 1);
  const keyReasons = uniqueStrings(signal.key_reasons ?? []);
  const notradeReasons = uniqueStrings(signal.notrade_reasons ?? []);
  const actionLabel = published
    ? (signal.action_label ?? signal.direction_label ?? "Neutre")
    : nonPublishedActionLabel(publicationScore, status);
  const reliabilityScore = clamp(Math.round(Number(signal.reliability_score ?? signal.trend_reliability_score ?? 50)), 0, 100);
  return {
    symbol: signal.symbol.toUpperCase(),
    action: normalizeAction(signal.action),
    confidence,
    score: Number(signal.score ?? 0),
    reasoning: signal.reasoning ?? "",
    indicators: signal.indicators ?? [],
    timestamp: signal.timestamp ?? new Date().toISOString(),
    score_100: signal.score_100 ?? signal.direction ?? 50,
    action_label: actionLabel,
    confidence_level: signal.confidence_level ?? "moyen",
    status,
    sub_scores: signal.sub_scores ?? [],
    key_reasons: keyReasons,
    direction: signal.direction ?? signal.score_100 ?? 50,
    direction_label: signal.direction_label ?? signal.action_label ?? "Neutre",
    confidence_score: published ? (signal.confidence_score ?? Math.round(confidence * 100)) : publicationScore,
    risk: signal.risk ?? signal.execution_risk ?? 50,
    setup_quality: signal.setup_quality ?? 50,
    actionability: signal.actionability ?? signal.status?.toUpperCase() ?? "IGNORE",
    market_regime: signal.market_regime ?? "UNKNOWN",
    signal_context: signal.signal_context ?? "mixed",
    trend_context_score: signal.trend_context_score ?? 50,
    trend_reliability_score: signal.trend_reliability_score ?? 50,
    contradictions: signal.contradictions ?? [],
    signal_trade_plan: signal.signal_trade_plan ?? null,
    horizon: signal.horizon ?? "Scalp 1m/5m/15m/1h",
    setup_type: signal.setup_type ?? "contextual_setup",
    regime: signal.regime ?? "UNKNOWN",
    regime_fit: signal.regime_fit ?? 0,
    confirmation_score: signal.confirmation_score ?? Math.round(confidence * 100),
    execution_risk: signal.execution_risk ?? signal.risk ?? 50,
    liquidity_score: signal.liquidity_score ?? 50,
    notrade_reasons: notradeReasons,
    expected_holding_window: signal.expected_holding_window ?? "",
    freshness_ms: signal.freshness_ms ?? 0,
    publication_score: publicationScore,
    composite_score: publicationScore,
    reliability_score: reliabilityScore,
    display_score: publicationScore,
    published,
    scenario: signal.scenario ?? null,
    scenario_probability: signal.scenario_probability ?? null,
  };
}


/** Live clock that ticks every second, using the browser's local timezone. */
function LocalClock() {
  const [time, setTime] = useState("--:--:--");

  useEffect(() => {
    const tick = () => {
      setTime(
        new Date().toLocaleTimeString(undefined, {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }),
      );
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <span className="text-[13px] font-mono text-[var(--text-muted)] tabular-nums" suppressHydrationWarning>
      {time}
    </span>
  );
}

function riskLabel(score: number) {
  if (score < 25) return "Low";
  if (score < 50) return "Moderate";
  if (score < 75) return "Elevated";
  return "High";
}

function riskTone(score: number) {
  if (score < 25) return "text-[var(--success)]";
  if (score < 50) return "text-[var(--warning)]";
  if (score < 75) return "text-[var(--warning)]";
  return "text-[var(--danger)]";
}

function marketRegime(market: CryptoMarketData[]) {
  if (market.length === 0) return { label: "No market feed", tone: "text-[var(--text-muted)]", breadth: 0 };
  const sample = market.slice(0, 25);
  const positive = sample.filter((asset) => Number(asset.change_pct_24h ?? 0) > 0).length;
  const breadth = positive / sample.length;
  const avgMove = sample.reduce((sum, asset) => sum + Number(asset.change_pct_24h ?? 0), 0) / sample.length;
  if (breadth > 0.68 && avgMove > 1) return { label: "Momentum risk-on", tone: "text-[var(--success)]", breadth };
  if (breadth < 0.35 && avgMove < -1) return { label: "Risk-off rotation", tone: "text-[var(--danger)]", breadth };
  return { label: "Mixed tape", tone: "text-[var(--warning)]", breadth };
}

function signalTone(score: number) {
  if (score >= 90) return "#16a34a";
  if (score >= 75) return "#22c55e";
  if (score >= 65) return "#eab308";
  if (score >= 50) return "#f59e0b";
  if (score >= 35) return "#ef4444";
  if (score >= 20) return "#dc2626";
  return "#991b1b";
}

function executionRiskTone(score: number) {
  if (score <= 35) return "text-[var(--success)]";
  if (score <= 55) return "text-[var(--warning)]";
  return "text-[var(--danger)]";
}

function formatSetupType(setupType: string) {
  return setupType
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function compactMetricNumber(value: number) {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return `${Math.round(value)}`;
}

function computeDiscoveryScore({
  changePct24h,
  volume24h,
  rank,
  signal,
}: {
  changePct24h: number;
  volume24h: number;
  rank: number | null;
  signal?: SignalDetail;
}) {
  const liquidityScore = clamp((Math.log10(Math.max(volume24h, 1)) - 4.5) * 24, 0, 100);
  const moveMagnitude = Math.abs(changePct24h);
  const moveQuality = clamp(100 - Math.abs(moveMagnitude - 6) * 10, 12, 100);
  const stabilityPenalty = clamp(Math.max(0, moveMagnitude - 18) * 2.8, 0, 28);
  const rankScore = rank ? clamp(100 - Math.max(rank - 1, 0) * 0.35, 32, 100) : 44;
  const signalScore = signal ? signal.composite_score * 0.55 + signal.reliability_score * 0.45 : 50;
  const directionalFit = changePct24h >= 0 ? 56 : 48;

  return clamp(
    Math.round(
      liquidityScore * 0.34 +
      moveQuality * 0.24 +
      rankScore * 0.16 +
      signalScore * 0.18 +
      directionalFit * 0.08 -
      stabilityPenalty,
    ),
    0,
    100,
  );
}

function formatFreshness(ms: number) {
  if (!ms || ms < 1_000) return "live";
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  return `${minutes}m`;
}

function formatMaybe(value: string | null | undefined) {
  if (!value) return "Waiting";
  return formatRelative(value);
}

function getStrategyName(analysis: string, strategies: Strategy[]) {
  const lowered = analysis.toLowerCase();
  const exact = strategies.find((strategy) => lowered.includes(strategy.name.toLowerCase()));
  if (exact) return exact.name;
  return strategies.find((strategy) => strategy.status === "active")?.name ?? "AI cycle";
}

function roundUsd(value: number) {
  return Math.round(value * 100) / 100;
}

function DeskMetric({
  label,
  value,
  sublabel,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string;
  sublabel?: string;
  icon: typeof Wallet;
  tone?: string;
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className="h-3 w-3 accent-text opacity-50" />
        <span className="text-[13px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">{label}</span>
      </div>
      <div className={cn("text-xl font-bold font-mono text-[var(--foreground)]", tone)}>{value}</div>
      {sublabel ? <p className="text-[14px] text-[var(--text-muted)] mt-0.5">{sublabel}</p> : null}
    </div>
  );
}

export default function CryptoTradingPage() {
  usePageAccent(PAGE_ACCENTS.trading.accent, PAGE_ACCENTS.trading.glow);

  const { tradingMode, setTradingMode } = useTheme();
  const { format } = useCurrency();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [signalsLoading, setSignalsLoading] = useState(false);
  const [arming, setArming] = useState(false);
  const [account, setAccount] = useState<UserProfile | null>(null);

  const [market, setMarket] = useState<CryptoMarketData[]>([]);
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsMetrics | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [autoStatus, setAutoStatus] = useState<AutoTradingStatusSnapshot | null>(null);
  const [autoHistory, setAutoHistory] = useState<AutoTradingHistorySnapshot[]>([]);
  const [health, setHealth] = useState<{ status: string; connected: boolean } | null>(null);
  const [signalMap, setSignalMap] = useState<Record<string, SignalDetail>>({});
  const [liveTickers, setLiveTickers] = useState<Record<string, LiveTickerSnapshot>>({});
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [tradeIntent, setTradeIntent] = useState<TradeIntent>({ side: "buy" });
  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  const [chartType, setChartType] = useState<DeskChartType>("candlestick");
  const [moversView, setMoversView] = useState<MarketMoversView>("candidates");
  const [moversSortBy, setMoversSortBy] = useState<"default" | "price" | "change" | "volume">("default");
  const [moversSortAsc, setMoversSortAsc] = useState(false);
  const [universeView, setUniverseView] = useState<MarketUniverseView>("all");
  const [universeModalOpen, setUniverseModalOpen] = useState(false);
  const [walletModalOpen, setWalletModalOpen] = useState(false);

  // ---- Live Wallet (always fetched, independent of walletUnlocked) ----
  const [walletPreview, setWalletPreview] = useState<Array<{ currency: string; available: number; reserved: number; total: number }>>([]);
  const [walletPreviewLoading, setWalletPreviewLoading] = useState(true);
  const [walletPreviewError, setWalletPreviewError] = useState<string | null>(null);

  const applyLiveTickerUpdate = useCallback((update: { symbol: string; price?: number; change_pct_24h?: number; volume_24h?: number }) => {
    const upper = update.symbol.toUpperCase();

    // Keep the previous value for any field that arrives invalid/missing.
    // This is what prevents the 24h change indicator from flickering back to
    // 0 when a tick doesn't carry every field.
    const parseKeep = (incoming: unknown, fallback: number | undefined): number | undefined => {
      const parsed = incoming === undefined || incoming === null ? NaN : Number(incoming);
      if (Number.isFinite(parsed)) return parsed;
      return fallback;
    };

    startTransition(() => {
      setLiveTickers((current) => {
        const previous = current[upper];
        const nextPrice = parseKeep(update.price, previous?.price) ?? 0;
        const nextChangePct = parseKeep(update.change_pct_24h, previous?.changePct24h);
        const nextVolume = parseKeep(update.volume_24h, previous?.volume24h) ?? 0;

        if (
          previous &&
          previous.price === nextPrice &&
          previous.changePct24h === nextChangePct &&
          previous.volume24h === nextVolume
        ) {
          return current;
        }

        return {
          ...current,
          [upper]: {
            price: nextPrice,
            changePct24h: nextChangePct,
            volume24h: nextVolume,
          },
        };
      });
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    const fetchWallet = async () => {
      setWalletPreviewLoading(true);
      setWalletPreviewError(null);
      try {
        const result = await tradingApi.getBalances();
        if (!cancelled) {
          setWalletPreview(result.filter((b) => b.total > 0));
          setWalletPreviewError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setWalletPreviewError(err instanceof Error ? err.message : "Failed to fetch wallet");
          setWalletPreview([]);
        }
      } finally {
        if (!cancelled) setWalletPreviewLoading(false);
      }
    };
    void fetchWallet();
    const interval = window.setInterval(() => void fetchWallet(), 30_000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, []);

  // Watchlist + search
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const accountPreferencesHydratedRef = useRef<string | null>(null);
  const accountPrefsSaveTimerRef = useRef<number | null>(null);
  const lastSavedPreferencesRef = useRef<string>("");

  // Load watchlist from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(WATCHLIST_KEY);
      if (stored) {
        const parsed = sanitizeWatchlistSymbols(JSON.parse(stored) as string[]);
        if (parsed.length > 0) {
          setWatchlist(parsed);
          return;
        }
      }
    } catch { /* empty */ }
    // First time: seed with defaults
    const seeded = sanitizeWatchlistSymbols(DEFAULT_WATCHLIST);
    setWatchlist(seeded);
    try { localStorage.setItem(WATCHLIST_KEY, JSON.stringify(seeded)); } catch { /* empty */ }
  }, []);

  useEffect(() => {
    try { localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist)); } catch { /* empty */ }
  }, [watchlist]);

  const toggleWatch = useCallback((symbol: string) => {
    setWatchlist((prev) => {
      const upper = symbol.toUpperCase();
      return prev.includes(upper) ? prev.filter((s) => s !== upper) : [...prev, upper];
    });
  }, []);
  const loadRequestRef = useRef(0);

  const hydrateFromCache = useCallback(() => {
    let hydrated = false;
    const cachedAccount = authApi.peekCachedMe();
    const cachedMarket = pricesApi.peekAllCryptos(80);
    const cachedSnapshot = portfolioApi.peekSnapshot();
    const cachedView = readObjectCache<TradingViewCache>(TRADING_VIEW_CACHE_KEY, TRADING_VIEW_CACHE_TTL);

    if (cachedAccount) {
      setAccount(cachedAccount);
      hydrated = true;
    }

    if (cachedMarket?.data.length) {
      setMarket(cachedMarket.data);
      setSelectedSymbol((current) => current ?? cachedView?.selectedSymbol ?? cachedMarket.data[0]?.symbol ?? null);
      hydrated = true;
    }

    if (cachedView) {
      setOrders(cachedView.orders);
      setAnalytics(cachedView.analytics);
      setStrategies(cachedView.strategies);
      setAutoStatus(cachedView.autoStatus);
      setAutoHistory(cachedView.autoHistory);
      setHealth(cachedView.health);
      const normalizedSignalMap = Object.fromEntries(
        Object.entries(cachedView.signalMap ?? {}).map(([symbol, signal]) => [symbol.toUpperCase(), toSignalDetail(signal)]),
      );
      setSignalMap(normalizedSignalMap);
      setChartType(normalizeDeskChartType(cachedView.chartType));
      setMoversView(normalizeMoversView(cachedView.moversView));
      setUniverseView(normalizeUniverseView(cachedView.universeView));
      if (cachedView.selectedSymbol) {
        setSelectedSymbol(cachedView.selectedSymbol);
      }
      hydrated = true;
    }

    if (cachedAccount?.wallet_access_enabled && cachedSnapshot) {
      setSnapshot(cachedSnapshot);
      hydrated = true;
    }

    if (cachedAccount && !cachedAccount.wallet_access_enabled) {
      setSnapshot(null);
      hydrated = true;
    }

    if (hydrated) setLoading(false);
  }, []);

  const loadSecondaryData = useCallback(async (requestId: number, walletUnlocked: boolean) => {
    const [strategiesResult, autoStatusResult, autoHistoryResult, healthResult] = await Promise.allSettled([
      strategiesApi.list(),
      aiApi.getAutoTradingStatus(),
      aiApi.getAutoTradingHistory(),
      binanceApi.health(),
    ]);

    if (loadRequestRef.current !== requestId) return;

    if (strategiesResult.status === "fulfilled") setStrategies(strategiesResult.value);
    if (autoStatusResult.status === "fulfilled") setAutoStatus(autoStatusResult.value);
    if (autoHistoryResult.status === "fulfilled") setAutoHistory(autoHistoryResult.value);
    if (healthResult.status === "fulfilled") setHealth(healthResult.value);

    const [ordersResult, analyticsResult] = await Promise.allSettled([
      tradingApi.getOrders(),
      analyticsApi.getMetrics(),
    ]);

    if (loadRequestRef.current !== requestId) return;

    if (ordersResult.status === "fulfilled") setOrders(ordersResult.value);
    if (analyticsResult.status === "fulfilled") setAnalytics(analyticsResult.value);
  }, []);

  const refreshDesk = useCallback(async () => {
    setRefreshing(true);
    const requestId = Date.now();
    loadRequestRef.current = requestId;
    const snapshotPromise = portfolioApi
      .getSnapshot()
      .then((value) => ({ status: "fulfilled" as const, value }))
      .catch((reason: unknown) => ({ status: "rejected" as const, reason }));

    try {
      const [meResult, marketResult] = await Promise.allSettled([
        authApi.getMe(),
        pricesApi.getAllCryptos(250),
      ]);

      if (loadRequestRef.current !== requestId) return;

      if (marketResult.status === "fulfilled" && marketResult.value.data.length > 0) {
        setMarket(marketResult.value.data);
        setSelectedSymbol((current) => current ?? marketResult.value.data[0]?.symbol ?? null);
      }

      const nextAccount = meResult.status === "fulfilled" ? meResult.value : null;
      setAccount(nextAccount);

      const walletUnlocked = nextAccount?.wallet_access_enabled ?? false;
      // Always try to load the snapshot (backend now serves real data via per-user credentials)
      const snapshotResult = await snapshotPromise;
      if (loadRequestRef.current !== requestId) return;

      if (snapshotResult.status === "fulfilled") {
        setSnapshot(snapshotResult.value);
      } else if (!walletUnlocked) {
        setSnapshot(null);
      }

      setLoading(false);
      void loadSecondaryData(requestId, walletUnlocked);
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 403)) {
        // Ignore wallet lock, surface everything else through the desk state.
      }
    } finally {
      if (loadRequestRef.current === requestId) {
        setRefreshing(false);
        setLoading(false);
      }
    }
  }, [loadSecondaryData]);

  useEffect(() => {
    hydrateFromCache();
    void refreshDesk();
    const interval = window.setInterval(() => {
      void refreshDesk();
    }, REFRESH_INTERVAL);
    return () => window.clearInterval(interval);
  }, [hydrateFromCache, refreshDesk]);

  useEffect(() => {
    if (!account?.id || accountPreferencesHydratedRef.current === account.id) return;

    const deskPreferences = account.preferences?.crypto_desk;
    const appPreferences = account.preferences?.app;

    if (deskPreferences && Object.prototype.hasOwnProperty.call(deskPreferences, "watchlist")) {
      setWatchlist(sanitizeWatchlistSymbols(deskPreferences.watchlist) ?? []);
    }
    if (deskPreferences && Object.prototype.hasOwnProperty.call(deskPreferences, "selected_symbol")) {
      setSelectedSymbol(deskPreferences.selected_symbol?.toUpperCase() ?? null);
    }
    if (deskPreferences?.chart_type) {
      setChartType(normalizeDeskChartType(deskPreferences.chart_type));
    }
    if (deskPreferences?.movers_view) {
      setMoversView(normalizeMoversView(deskPreferences.movers_view));
    }
    if (deskPreferences?.universe_view) {
      setUniverseView(normalizeUniverseView(deskPreferences.universe_view));
    }
    if (appPreferences?.trading_mode) {
      setTradingMode(appPreferences.trading_mode);
    }

    lastSavedPreferencesRef.current = JSON.stringify(account.preferences ?? {});
    accountPreferencesHydratedRef.current = account.id;
  }, [account, setTradingMode]);

  useEffect(() => {
    if (!account?.id || accountPreferencesHydratedRef.current !== account.id) return;

    const nextPreferences = {
      ...(account.preferences ?? {}),
      crypto_desk: {
        ...(account.preferences?.crypto_desk ?? {}),
        watchlist,
        selected_symbol: selectedSymbol ?? null,
        chart_type: chartType,
        movers_view: moversView,
        universe_view: universeView,
      },
      app: {
        ...(account.preferences?.app ?? {}),
        trading_mode: tradingMode,
      },
    };

    const serialized = JSON.stringify(nextPreferences);
    if (serialized === lastSavedPreferencesRef.current) return;

    if (accountPrefsSaveTimerRef.current) {
      window.clearTimeout(accountPrefsSaveTimerRef.current);
    }

    accountPrefsSaveTimerRef.current = window.setTimeout(() => {
      void authApi.updateMe({ preferences: nextPreferences })
        .then((profile) => {
          lastSavedPreferencesRef.current = serialized;
          setAccount(profile);
        })
        .catch(() => {
          // Keep local state even if persistence fails; next user change will retry.
        });
    }, 700);

    return () => {
      if (accountPrefsSaveTimerRef.current) {
        window.clearTimeout(accountPrefsSaveTimerRef.current);
        accountPrefsSaveTimerRef.current = null;
      }
    };
  }, [account, chartType, moversView, selectedSymbol, tradingMode, universeView, watchlist]);

  useEffect(() => {
    writeObjectCache<TradingViewCache>(TRADING_VIEW_CACHE_KEY, {
      selectedSymbol,
      chartType,
      moversView,
      universeView,
      orders,
      analytics,
      strategies,
      autoStatus,
      autoHistory: autoHistory.slice(0, 24),
      health,
      signalMap,
    });
  }, [analytics, autoHistory, autoStatus, chartType, health, moversView, orders, selectedSymbol, signalMap, strategies, universeView]);

  const marketBySymbol = useMemo(
    () => new Map(market.map((asset) => [asset.symbol.toUpperCase(), asset])),
    [market],
  );

  const livePrices = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(liveTickers).map(([symbol, snapshot]) => [symbol, snapshot.price]),
      ),
    [liveTickers],
  );

  const holdings = useMemo<HoldingSnapshot[]>(() => {
    if (snapshot) return buildWalletHoldings(snapshot, marketBySymbol, livePrices);
    // Fallback: build holdings from walletPreview (direct Binance balances)
    if (walletPreview.length === 0) return [];
    return walletPreview.map((balance) => {
      const symbol = balance.currency.toUpperCase();
      const stable = WALLET_STABLES.has(symbol);
      const mktAsset = marketBySymbol.get(symbol);
      const price = stable ? 1 : livePrices[symbol] ?? Number(mktAsset?.current_price ?? mktAsset?.price ?? 0);
      const total = balance.total;
      const value = total * price;
      let changePct = 0;
      if (!stable) {
        const live = liveTickers[symbol]?.changePct24h;
        if (typeof live === "number" && Number.isFinite(live)) {
          changePct = live;
        } else {
          const restPct = mktAsset?.price_change_percentage_24h ?? mktAsset?.change_pct_24h;
          const restNum = typeof restPct === "number" ? restPct : Number(restPct);
          changePct = Number.isFinite(restNum) ? restNum : 0;
        }
      }
      return { symbol, total, available: balance.available, reserved: balance.reserved, price, value, changePct, stable };
    }).filter((h) => h.total > 0).sort((a, b) => b.value - a.value);
  }, [liveTickers, livePrices, marketBySymbol, snapshot, walletPreview]);

  const positions = useMemo(() => snapshot?.positions ?? [], [snapshot]);
  const executionFeed = useMemo(() => snapshot?.execution_feed ?? [], [snapshot]);
  const portfolioHeadline = useMemo(
    () => snapshot?.portfolio?.name ?? snapshot?.portfolios[0]?.name ?? "Primary portfolio",
    [snapshot],
  );

  const portfolioValue = useMemo(
    () => computeWalletValue(holdings, snapshot?.summary.equity ?? 0),
    [holdings, snapshot],
  );

  const cashValue = useMemo(
    () => computeWalletCashValue(holdings, snapshot?.summary.cash ?? 0),
    [holdings, snapshot],
  );

  const marketExposure = useMemo(
    () => computeWalletMarketExposure(portfolioValue, cashValue, snapshot?.summary.market_exposure ?? 0),
    [cashValue, portfolioValue, snapshot],
  );

  const riskMetrics = useMemo(
    () => (hasUsableRiskMetrics(snapshot?.risk ?? null, portfolioValue) ? snapshot?.risk ?? null : null),
    [portfolioValue, snapshot],
  );

  const openPnl = useMemo(() => {
    if (snapshot) {
      return snapshot.summary.open_pnl;
    }

    if (positions.length > 0) {
      return positions.reduce((sum, position) => sum + Number(position.pnl ?? 0), 0);
    }

    return holdings
      .filter((holding) => !holding.stable)
      .reduce((sum, holding) => {
        if (holding.changePct === 0) return sum;
        return sum + (holding.value - holding.value / (1 + holding.changePct / 100));
      }, 0);
  }, [holdings, positions, snapshot]);

  const openPnlPct = useMemo(() => {
    if (snapshot) {
      return snapshot.summary.open_pnl_pct;
    }
    return portfolioValue > 0 ? (openPnl / Math.max(portfolioValue - openPnl, 1)) * 100 : 0;
  }, [openPnl, portfolioValue, snapshot]);

  const estimatedRisk = useMemo(
    () => estimateWalletRiskScore(holdings, portfolioValue, riskMetrics),
    [holdings, portfolioValue, riskMetrics],
  );
  const riskSummary = (riskMetrics ? formatWalletRiskLevel(riskMetrics.risk_level) : null) ?? riskLabel(estimatedRisk);
  const regime = useMemo(() => marketRegime(market), [market]);

  const resolveAssetPrice = useCallback(
    (symbol: string, asset?: CryptoMarketData | null) =>
      Number(liveTickers[symbol]?.price ?? asset?.current_price ?? asset?.price ?? 0),
    [liveTickers],
  );

  const resolveAssetChangePct = useCallback(
    (symbol: string, asset?: CryptoMarketData | null) => {
      // Prefer live value only when it is a finite number. An undefined live
      // value means we haven't received a valid tick yet — fall back to the
      // REST snapshot so the indicator stays stable on the 24h baseline.
      const live = liveTickers[symbol]?.changePct24h;
      if (typeof live === "number" && Number.isFinite(live)) return live;
      const restPct = asset?.price_change_percentage_24h ?? asset?.change_pct_24h;
      const restNum = typeof restPct === "number" ? restPct : Number(restPct);
      return Number.isFinite(restNum) ? restNum : 0;
    },
    [liveTickers],
  );

  const resolveAssetVolume = useCallback(
    (symbol: string, asset?: CryptoMarketData | null) =>
      Number(liveTickers[symbol]?.volume24h ?? asset?.total_volume ?? asset?.volume_24h ?? 0),
    [liveTickers],
  );

  const signalUniverse = useMemo(() => {
    const candidateSymbols = unique([
      ...(selectedSymbol ? [selectedSymbol] : []),
      ...watchlist,
      ...market
        .slice(0, 24)
        .sort((left, right) => Number(right.volume_24h ?? 0) - Number(left.volume_24h ?? 0))
        .map((asset) => asset.symbol.toUpperCase()),
      ...holdings.filter((holding) => !holding.stable).map((holding) => holding.symbol.toUpperCase()),
      ...positions.map((position) => position.symbol.toUpperCase()),
      ...orders.slice(0, 8).map((order) => order.symbol.toUpperCase()),
    ]);

    return candidateSymbols.filter(isScannerEligibleSymbol).slice(0, SIGNAL_SCAN_LIMIT);
  }, [holdings, market, orders, positions, selectedSymbol, watchlist]);
  const signalUniverseKey = useMemo(() => signalUniverse.join("|"), [signalUniverse]);
  const signalFetchInFlightRef = useRef(false);

  useEffect(() => {
    const symbols = signalUniverseKey.split("|").filter(Boolean);
    if (symbols.length === 0) return;

    let cancelled = false;
    const cachedSignals: Record<string, SignalDetail> = {};
    for (const symbol of symbols) {
      const cached = signalsApi.peekSignal(symbol);
      if (!cached) continue;
      cachedSignals[symbol.toUpperCase()] = toSignalDetail(cached);
    }

    if (Object.keys(cachedSignals).length > 0) {
      setSignalMap((current) => ({ ...current, ...cachedSignals }));
    }

    const fetchSignals = async () => {
      if (signalFetchInFlightRef.current) return;
      signalFetchInFlightRef.current = true;
      setSignalsLoading(true);

      try {
        const results = await signalsApi.getSignals(symbols);
        if (cancelled) return;

        const nextSignalMap: Record<string, SignalDetail> = {};
        for (const signal of results) {
          nextSignalMap[signal.symbol.toUpperCase()] = toSignalDetail(signal);
        }

        setSignalMap((current) => ({ ...current, ...nextSignalMap }));
      } finally {
        signalFetchInFlightRef.current = false;
        if (!cancelled) setSignalsLoading(false);
      }
    };

    void fetchSignals();
    const interval = window.setInterval(() => {
      void fetchSignals();
    }, SIGNAL_REFRESH_INTERVAL);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [signalUniverseKey]);

  const liveSymbols = useMemo(() => {
    return unique([
      ...(selectedSymbol ? [selectedSymbol] : []),
      ...watchlist.slice(0, 24).map((symbol) => symbol.toUpperCase()),
      ...market.slice(0, 40).map((asset) => asset.symbol.toUpperCase()),
      ...holdings.slice(0, 12).map((holding) => holding.symbol.toUpperCase()),
      ...positions.slice(0, 8).map((position) => position.symbol.toUpperCase()),
      ...orders.slice(0, 8).map((order) => order.symbol.toUpperCase()),
    ]).filter((symbol) => !WALLET_STABLES.has(symbol));
  }, [holdings, market, orders, positions, selectedSymbol, watchlist]);
  const liveSymbolsKey = useMemo(() => liveSymbols.join("|"), [liveSymbols]);

  useEffect(() => {
    const symbols = liveSymbolsKey.split("|").filter(Boolean);
    if (symbols.length === 0) return;

    const unsubs = symbols.map((symbol) =>
      priceWs.subscribe(symbol, applyLiveTickerUpdate),
    );

    return () => {
      for (const unsub of unsubs) unsub();
    };
  }, [applyLiveTickerUpdate, liveSymbolsKey]);

  useEffect(() => {
    if (selectedSymbol) return;
    if (market.length > 0) {
      setSelectedSymbol(market[0].symbol);
      return;
    }
    const firstHolding = holdings.find((holding) => !holding.stable);
    if (firstHolding) setSelectedSymbol(firstHolding.symbol);
  }, [holdings, market, selectedSymbol]);

  const scannerAssets = useMemo(() => {
    const base = watchlist.length === 0
      ? market.slice(0, 10)
      : market.filter((asset) => watchlist.includes(asset.symbol.toUpperCase()));

    return [...base].sort((left, right) => {
      const leftSignal = signalMap[left.symbol.toUpperCase()];
      const rightSignal = signalMap[right.symbol.toUpperCase()];
      const leftScore = scannerPriority(leftSignal);
      const rightScore = scannerPriority(rightSignal);
      return rightScore - leftScore;
    });
  }, [market, signalMap, watchlist]);

  const marketUniverseItems = useMemo<MarketUniverseItem[]>(() => {
    return market
      .filter((asset) => isScannerEligibleSymbol(asset.symbol))
      .map((asset) => {
        const symbol = asset.symbol.toUpperCase();
        const signal = signalMap[symbol];
        const price = resolveAssetPrice(symbol, asset);
        const changePct24h = resolveAssetChangePct(symbol, asset);
        const volume24h = resolveAssetVolume(symbol, asset);
        const rank = Number(asset.market_cap_rank ?? asset.rank ?? 0) || null;

        return {
          symbol,
          name: asset.name ?? symbol,
          price,
          changePct24h,
          volume24h,
          rank,
          discoveryScore: computeDiscoveryScore({ changePct24h, volume24h, rank, signal }),
          image: asset.image ?? undefined,
        };
      });
  }, [market, resolveAssetChangePct, resolveAssetPrice, resolveAssetVolume, signalMap]);

  const marketUniverseCollections = useMemo(() => {
    const all = [...marketUniverseItems].sort((left, right) => {
      const leftRank = left.rank ?? Number.POSITIVE_INFINITY;
      const rightRank = right.rank ?? Number.POSITIVE_INFINITY;
      if (leftRank !== rightRank) return leftRank - rightRank;
      return right.volume24h - left.volume24h;
    });

    const gainers = [...marketUniverseItems].sort((left, right) => {
      if (right.changePct24h !== left.changePct24h) return right.changePct24h - left.changePct24h;
      return right.volume24h - left.volume24h;
    });

    const losers = [...marketUniverseItems].sort((left, right) => {
      if (left.changePct24h !== right.changePct24h) return left.changePct24h - right.changePct24h;
      return right.volume24h - left.volume24h;
    });

    const candidates = [...marketUniverseItems].sort((left, right) => {
      if (right.discoveryScore !== left.discoveryScore) return right.discoveryScore - left.discoveryScore;
      return right.volume24h - left.volume24h;
    });

    return { all, gainers, losers, candidates };
  }, [marketUniverseItems]);

  const compactMoversItems = useMemo(() => {
    const base = [...marketUniverseCollections[moversView]];
    if (moversSortBy !== "default") {
      base.sort((a, b) => {
        let diff = 0;
        if (moversSortBy === "price") diff = a.price - b.price;
        else if (moversSortBy === "change") diff = a.changePct24h - b.changePct24h;
        else if (moversSortBy === "volume") diff = a.volume24h - b.volume24h;
        return moversSortAsc ? diff : -diff;
      });
    }
    return base.slice(0, COMPACT_MOVER_ROWS);
  }, [marketUniverseCollections, moversView, moversSortBy, moversSortAsc]);

  const modalUniverseItems = useMemo(
    () => marketUniverseCollections[universeView],
    [marketUniverseCollections, universeView],
  );
  const modalLiveSymbolsKey = useMemo(
    () =>
      universeModalOpen
        ? modalUniverseItems.slice(0, 48).map((item) => item.symbol.toUpperCase()).join("|")
        : "",
    [modalUniverseItems, universeModalOpen],
  );

  useEffect(() => {
    const symbols = modalLiveSymbolsKey.split("|").filter(Boolean);
    if (symbols.length === 0) return;

    const unsubs = symbols.map((symbol) => priceWs.subscribe(symbol, applyLiveTickerUpdate));
    return () => {
      for (const unsub of unsubs) unsub();
    };
  }, [applyLiveTickerUpdate, modalLiveSymbolsKey]);

  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toUpperCase().trim();
    return market.filter((a) => a.symbol.toUpperCase().includes(q)).slice(0, 12);
  }, [market, searchQuery]);
  const selectedAsset = selectedSymbol ? marketBySymbol.get(selectedSymbol.toUpperCase()) ?? null : null;
  const selectedSignal = selectedSymbol ? signalMap[selectedSymbol.toUpperCase()] ?? null : null;

  const selectedHolding = selectedSymbol
    ? holdings.find((holding) => holding.symbol.toUpperCase() === selectedSymbol.toUpperCase()) ?? null
    : null;
  const selectedPosition = selectedSymbol
    ? positions.find((position) => position.symbol.toUpperCase() === selectedSymbol.toUpperCase()) ?? null
    : null;

  const opportunities = useMemo<TradeOpportunity[]>(() => {
    return Object.values(signalMap)
      .map((signal) => {
        const asset = marketBySymbol.get(signal.symbol.toUpperCase());
        const side = actionToSide(signal.action);
        if (!asset || side === "hold") return null;

        const currentHolding = holdings.find((holding) => holding.symbol === signal.symbol);
        const currentValue = currentHolding?.value ?? 0;
        const riskItem = riskMetrics?.position_risk.find((item) => item.symbol.toUpperCase() === signal.symbol);
        const weight = riskItem?.weight ?? (portfolioValue > 0 ? currentValue / portfolioValue : 0);
        const changePct = resolveAssetChangePct(signal.symbol, asset);
        const volatility = riskItem?.volatility ?? Math.abs(changePct) * 1.4;
        const confidence = clamp(Number(signal.confidence ?? 0), 0, 1);
        const buyBase = cashValue * (0.015 + confidence * 0.055);
        const sellBase = currentValue * (0.2 + confidence * 0.55);
        const volatilityGuard = clamp(1 - volatility / 180, 0.4, 1);
        const concentrationGuard = clamp(1 - weight * 1.7, 0.35, 1);
        const directionalGuard = side === "buy" ? concentrationGuard : clamp(0.6 + weight * 1.4, 0.4, 1.25);
        const recommendedUsd = roundUsd(
          Math.max(
            0,
            side === "buy"
              ? Math.min(buyBase * volatilityGuard * directionalGuard, cashValue * 0.25)
              : Math.min(sellBase * volatilityGuard * directionalGuard, currentValue),
          ),
        );

        if (side === "sell" && currentValue <= 0) return null;
        if (side === "buy" && cashValue <= 0) return null;

        const riskNote =
          volatility > 12
            ? "Volatility elevated, size reduced."
            : weight > 0.18
              ? "Existing exposure already material."
              : "Risk budget available for execution.";

        return {
          symbol: signal.symbol,
          side,
          action: signal.action,
          confidence,
          score: signal.score,
          price: resolveAssetPrice(signal.symbol, asset),
          changePct,
          volume: resolveAssetVolume(signal.symbol, asset),
          volatility,
          recommendedUsd,
          currentValue,
          weight,
          reasoning: signal.reasoning,
          methods: signal.indicators.map((indicator) => indicator.name),
          riskNote,
          edgeScore:
            confidence * 70 +
            Math.abs(signal.score) * 20 +
            Math.min(Math.abs(changePct), 10),
        };
      })
      .filter((opportunity): opportunity is TradeOpportunity => Boolean(opportunity))
      .sort((left, right) => right.edgeScore - left.edgeScore);
  }, [cashValue, holdings, marketBySymbol, portfolioValue, resolveAssetChangePct, resolveAssetPrice, resolveAssetVolume, riskMetrics, signalMap]);

  const featuredOpportunity = useMemo(() => {
    if (selectedSymbol) {
      const exact = opportunities.find((opportunity) => opportunity.symbol === selectedSymbol);
      if (exact) return exact;
    }
    return opportunities[0] ?? null;
  }, [opportunities, selectedSymbol]);

  const decisionLedger = useMemo(() => {
    return autoHistory
      .flatMap((entry) =>
        entry.trades.map((trade, index) => ({
          id: `${entry.timestamp}-${trade.symbol}-${trade.action}-${index}`,
          timestamp: entry.timestamp,
          symbol: trade.symbol.toUpperCase(),
          action: trade.action.toUpperCase(),
          amountUsd: Number(trade.amount_usd ?? 0),
          analysis: entry.analysis,
          executed: entry.executed,
          strategy: getStrategyName(entry.analysis, strategies),
        })),
      )
      .sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime());
  }, [autoHistory, strategies]);
  const walletUnlocked = account?.wallet_access_enabled ?? false;


  const primeOpportunity = useCallback((opportunity: TradeOpportunity) => {
    setSelectedSymbol(opportunity.symbol);
    setTradeIntent({
      side: opportunity.side,
      amount: opportunity.recommendedUsd,
      advisory: `AI sizing ${opportunity.side === "buy" ? "buy" : "sell"}: ${format(opportunity.recommendedUsd)} based on ${Math.round(
        opportunity.confidence * 100,
      )}% confidence, ${opportunity.methods.join(" / ")}, and ${opportunity.riskNote.toLowerCase()}`,
    });
    setTradeModalOpen(true);
  }, [format, walletUnlocked]);

  const openTradeModal = useCallback(
    (side: "buy" | "sell") => {
      const activeOpportunity =
        featuredOpportunity && featuredOpportunity.symbol === selectedSymbol && featuredOpportunity.side === side
          ? featuredOpportunity
          : null;

      setTradeIntent({
        side,
        amount: activeOpportunity?.recommendedUsd,
        advisory: activeOpportunity
          ? `Suggested ${side} size ${format(activeOpportunity.recommendedUsd)}. ${activeOpportunity.reasoning}.`
          : selectedSignal
            ? `${selectedSignal.reasoning}. Signal confidence ${Math.round(selectedSignal.confidence * 100)}%.`
            : undefined,
      });
      setTradeModalOpen(true);
    },
    [featuredOpportunity, format, selectedSignal, selectedSymbol, walletUnlocked],
  );

  const selectUniverseSymbol = useCallback((symbol: string) => {
    setSelectedSymbol(symbol.toUpperCase());
    setUniverseModalOpen(false);
  }, []);

  const handleAutoToggle = useCallback(async () => {
    if (!autoStatus) return;
    setArming(true);
    try {
      const next = await aiApi.toggleAutoTrading(!autoStatus.enabled);
      setAutoStatus((current) =>
        current
          ? {
              ...current,
              enabled: next.enabled,
            }
          : {
              enabled: next.enabled,
              last_run: null,
              trades_today: 0,
              total_pnl: 0,
            },
      );
    } finally {
      setArming(false);
    }
  }, [autoStatus, walletUnlocked]);

  const activeStrategies = useMemo(
    () => strategies.filter((strategy) => strategy.status === "active"),
    [strategies],
  );

  const feedLabel = !walletUnlocked
    ? "Read-only market"
    : health?.connected
      ? "Exchange live"
      : market.length > 0
        ? "Snapshot mode"
        : "Offline";
  const visiblePublicationReasons = selectedSignal?.notrade_reasons.slice(0, VISIBLE_PUBLICATION_FILTERS) ?? [];
  const hiddenPublicationReasonCount = Math.max((selectedSignal?.notrade_reasons.length ?? 0) - visiblePublicationReasons.length, 0);
  const walletView = useMemo(() => {
    const FIAT_SYMBOLS: Record<string, string> = { EUR: "\u20ac", USD: "$", GBP: "\u00a3", CHF: "CHF", JPY: "\u00a5" };
    const isFiat = (symbol: string) => symbol in FIAT_SYMBOLS;
    const fiatSymbol = (symbol: string) => FIAT_SYMBOLS[symbol] ?? "";

    const items: WalletPreviewItem[] = walletPreview
      .map((balance) => {
        const sym = balance.currency.toUpperCase();
        const fiat = isFiat(sym);
        const stable = fiat || WALLET_STABLES.has(sym);
        const marketAsset = marketBySymbol.get(sym);
        const price = stable ? 1 : resolveAssetPrice(sym, marketAsset);
        const value = fiat ? balance.total : stable ? balance.total : balance.total * price;
        const changePct = stable ? 0 : resolveAssetChangePct(sym, marketAsset);
        return {
          sym,
          fiat,
          stable,
          total: balance.total,
          price,
          value,
          changePct,
          fiatSym: fiatSymbol(sym),
          image: marketAsset?.image,
        };
      })
      .filter((item) => item.total > 0)
      .sort((left, right) => right.value - left.value);

    const totalValue = items.reduce((sum, item) => sum + (item.fiat ? 0 : item.value), 0);
    const totalPnl24h = items.reduce((sum, item) => {
      if (item.stable || item.changePct === 0 || item.value <= 0) return sum;
      return sum + (item.value - item.value / (1 + item.changePct / 100));
    }, 0);
    const pnlPct = totalValue > 0 ? (totalPnl24h / (totalValue - totalPnl24h)) * 100 : 0;
    const pnlPositive = totalPnl24h >= 0;
    const cryptoItems = items.filter((item) => !item.fiat);
    const displayItems = (cryptoItems.length > 0 ? cryptoItems : items).slice(0, TOP_WALLET_ITEMS);

    return {
      items,
      displayItems,
      totalValue,
      totalPnl24h,
      pnlPct,
      pnlPositive,
      hasOverflow: (cryptoItems.length > 0 ? cryptoItems.length : items.length) > TOP_WALLET_ITEMS,
    };
  }, [marketBySymbol, resolveAssetChangePct, resolveAssetPrice, walletPreview]);

  if (loading && market.length === 0) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-[var(--text-secondary)]">
          <Loader2 className="h-7 w-7 animate-spin accent-text" />
          <p className="text-sm">Loading trading desk...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="mx-auto max-w-[1440px] space-y-3 p-3 md:p-5">

        {/* ============ 1. HEADER — compact, centered ============ */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl md:text-2xl font-bold glow-text">Crypto</h1>
            <div className="flex items-center gap-2 mt-1">
              <span className={cn("text-[14px] font-medium", health?.connected ? "text-[var(--success)]" : "text-[var(--text-muted)]")}>{feedLabel}</span>
              <span className="text-[14px] text-[var(--text-muted)]">&middot; {portfolioHeadline}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Mode toggle */}
            <div className="flex rounded-lg p-0.5" style={{ background: "var(--glass-bg)" }}>
              <button onClick={() => setTradingMode("manual")}
                className={cn("flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[14px] font-semibold transition-all",
                  tradingMode === "manual" ? "bg-[var(--glass-bg-strong)] text-[var(--foreground)]" : "text-[var(--text-muted)]")}>
                <CandlestickChart className="h-3.5 w-3.5" /> Manual
              </button>
              <button onClick={() => setTradingMode("auto")}
                className={cn("flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[14px] font-semibold transition-all",
                  tradingMode === "auto" ? "bg-[var(--glass-bg-strong)] text-[var(--foreground)]" : "text-[var(--text-muted)]")}>
                <Bot className="h-3.5 w-3.5" /> Auto
              </button>
            </div>
            <button onClick={() => void refreshDesk()} className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[14px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all">
              <RefreshCw className={cn("h-3.5 w-3.5", refreshing && "animate-spin")} /> Refresh
            </button>
            <button onClick={() => void handleAutoToggle()} disabled={!autoStatus || arming}
              className={cn("flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[14px] font-semibold transition-all disabled:opacity-40",
                autoStatus?.enabled ? "bg-[var(--danger)]/12 text-[var(--danger)]" : "bg-[var(--success)]/12 text-[var(--success)]")}>
              {arming ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />}
              {walletUnlocked ? (autoStatus?.enabled ? "Disarm" : "Arm AI") : "Wallet locked"}
            </button>
          </div>
        </div>

        {!walletUnlocked && (
          <WalletAccessPanel
            compact
            title="Trading execution is locked"
            reason={account?.wallet_access_reason}
          />
        )}

        {/* ============ MY WALLET — always visible ============ */}
        <section className="mb-6 flex h-[260px] flex-col rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-bg)] p-4 md:p-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div className="flex items-center gap-2">
              <Wallet className="h-5 w-5 accent-text" />
              <h2 className="text-base font-bold text-[var(--foreground)]">My Wallet</h2>
              <span className="rounded-full border border-[var(--glass-border)] px-2 py-0.5 text-[12px] font-medium text-[var(--text-muted)]">Binance</span>
            </div>
            <div className="flex items-start gap-3">
              {walletView.hasOverflow ? (
                <button
                  type="button"
                  onClick={() => setWalletModalOpen(true)}
                  className="rounded-full border border-[var(--glass-border)] px-3 py-1 text-[12px] font-semibold text-[var(--foreground)] transition-colors hover:bg-[var(--glass-bg-strong)]"
                >
                  Voir tout
                </button>
              ) : null}
              <div className="flex items-center gap-3">
                {walletPreviewLoading ? <Loader2 className="mt-1 h-4 w-4 animate-spin text-[var(--text-muted)]" /> : null}
                {!walletPreviewLoading && walletView.items.length > 0 ? (
                  <div className="text-right">
                    <p className="text-[24px] font-bold font-mono leading-none text-[var(--foreground)]">{format(walletView.totalValue)}</p>
                    <div
                      className={cn(
                        "mt-1 flex items-center justify-end gap-1 text-[14px] font-semibold",
                        walletView.pnlPositive ? "text-[var(--success)]" : "text-[var(--danger)]",
                      )}
                    >
                      {walletView.pnlPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                      <span>{walletView.pnlPositive ? "+" : ""}{format(walletView.totalPnl24h)}</span>
                      <span className="font-normal text-[var(--text-muted)]">({walletView.pnlPositive ? "+" : ""}{walletView.pnlPct.toFixed(2)}%)</span>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="flex min-h-[156px] flex-1 flex-col overflow-hidden">
            {walletPreviewError ? (
              <div className="flex flex-1 flex-col justify-center px-1 py-1">
                <p className="text-[15px] text-[var(--danger)]">{walletPreviewError}</p>
                <p className="mt-0.5 text-[13px] text-[var(--text-muted)]">Verifiez vos cles API dans Settings.</p>
              </div>
            ) : walletPreview.length === 0 && !walletPreviewLoading ? (
              <div className="flex flex-1 items-center">
                <p className="text-[15px] text-[var(--text-muted)]">Aucun solde. Ajoutez vos cles Binance dans Settings.</p>
              </div>
            ) : (
              <div className="flex flex-1 items-center">
                <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
                  {walletView.displayItems.map((item, index) => (
                    <div key={item.sym} className="flex items-center gap-x-5 gap-y-3">
                      <button
                        type="button"
                        onClick={() => setSelectedSymbol(item.sym)}
                        className={cn(
                          "flex items-center gap-2 py-0.5 text-left transition-colors hover:text-[var(--page-accent)]",
                          selectedSymbol === item.sym ? "text-[var(--page-accent)]" : "text-[var(--foreground)]",
                        )}
                      >
                        <CryptoIcon symbol={item.sym} imageUrl={item.image} size="xs" />
                        <span className="text-[15px] font-bold">{item.sym}</span>
                        <span className="text-[13px] font-mono text-[var(--text-muted)]">
                          {item.total.toLocaleString(undefined, {
                            maximumFractionDigits: item.price >= 1000 ? 4 : item.total < 1 ? 6 : 2,
                          })}
                        </span>
                        <span className="text-[14px] font-semibold font-mono">{item.price > 0 ? format(item.value) : "--"}</span>
                        <span
                          className={cn(
                            "text-[12px] font-semibold",
                            item.stable ? "text-[var(--text-muted)]" : item.changePct >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
                          )}
                        >
                          {item.stable ? "Stable" : `${item.changePct >= 0 ? "+" : ""}${item.changePct.toFixed(1)}%`}
                        </span>
                      </button>
                      {index < walletView.displayItems.length - 1 ? <span className="text-[var(--glass-border)]">/</span> : null}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ============ MAIN LAYOUT: Scanner (left) + Chart (right) ============ */}
        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">

          {/* LEFT: Scanner with search + watchlist */}
          <aside className="lg:order-first order-last">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-[var(--foreground)]">Watchlist <span className="text-[12px] text-[var(--text-muted)] font-normal ml-1">{scannerAssets.length}</span></h2>
              <LocalClock />
            </div>

            {/* Search bar */}
            <div className="relative mb-2">
              <div className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 bg-[var(--glass-bg)] border border-[var(--glass-border)]">
                <Search className="h-3.5 w-3.5 text-[var(--text-muted)] shrink-0" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Rechercher..."
                  className="flex-1 bg-transparent text-[14px] text-[var(--foreground)] placeholder-[var(--text-muted)] outline-none"
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery("")} className="text-[var(--text-muted)] hover:text-[var(--foreground)] text-[12px]">x</button>
                )}
              </div>

              {/* Search results dropdown */}
              {searchResults.length > 0 && (
                <div className="absolute z-20 top-full mt-1 left-0 right-0 rounded-lg border border-[var(--glass-border)] bg-[var(--surface)] shadow-xl max-h-[240px] overflow-y-auto custom-scrollbar">
                  {searchResults.map((asset) => {
                    const isWatched = watchlist.includes(asset.symbol.toUpperCase());
                    const lp = resolveAssetPrice(asset.symbol.toUpperCase(), asset);
                    const cp = resolveAssetChangePct(asset.symbol.toUpperCase(), asset);
                    return (
                      <div key={asset.symbol} className="flex items-center justify-between px-3 py-1.5 hover:bg-[var(--glass-bg)] transition-colors">
                        <button
                          onClick={() => { setSelectedSymbol(asset.symbol); setSearchQuery(""); }}
                          className="flex-1 text-left min-w-0">
                          <div className="flex items-center gap-2">
                            <CryptoIcon symbol={asset.symbol} imageUrl={asset.image} size="xs" /><span className="text-[15px] font-bold text-[var(--foreground)]">{asset.symbol}</span>
                            <span className="text-[12px] font-mono text-[var(--text-muted)]">{format(lp, lp < 1 ? 6 : 2)}</span>
                            <span className={cn("text-[12px] font-semibold", cp >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>{cp >= 0 ? "+" : ""}{cp.toFixed(1)}%</span>
                          </div>
                        </button>
                        <button
                          onClick={() => toggleWatch(asset.symbol)}
                          className={cn("p-1 rounded transition-colors", isWatched ? "text-[#c6f135]" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]")}>
                          <Star className="h-3.5 w-3.5" fill={isWatched ? "currentColor" : "none"} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Watchlist */}
            <div className="space-y-0.5 max-h-[calc(100vh-260px)] overflow-y-auto custom-scrollbar pr-1">
              {scannerAssets.length === 0 && (
                <p className="text-[13px] text-[var(--text-muted)] text-center py-4">Recherchez et suivez des cryptos</p>
              )}
	              {scannerAssets.map((asset) => {
	                const signal = signalMap[asset.symbol.toUpperCase()];
	                const livePrice = resolveAssetPrice(asset.symbol.toUpperCase(), asset);
	                const liveChangePct = resolveAssetChangePct(asset.symbol.toUpperCase(), asset);
	                const primaryReason = signal?.notrade_reasons?.[0] ?? signal?.key_reasons?.[0] ?? null;
	                return (
	                  <div key={asset.symbol} role="button" tabIndex={0}
	                    onClick={() => setSelectedSymbol(asset.symbol)}
	                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setSelectedSymbol(asset.symbol); }}
	                    className={cn("flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer transition-all duration-150 group",
	                      selectedSymbol === asset.symbol
	                        ? "bg-[var(--glass-bg-strong)] shadow-sm"
	                        : "hover:bg-[var(--glass-bg)]")}>
																				<div className="min-w-0 flex-1">
	                      <div className="flex items-center gap-1.5">
	                        <CryptoIcon symbol={asset.symbol} imageUrl={asset.image} size="xs" /><span className="text-[15px] font-bold text-[var(--foreground)]">{asset.symbol}</span>
	                        <span className={cn("text-[12px] font-semibold", liveChangePct >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>{liveChangePct >= 0 ? "+" : ""}{liveChangePct.toFixed(1)}%</span>
	                      </div>
	                      <div className="flex items-center gap-1.5 mt-0.5">
	                        <span className="text-[13px] font-mono text-[var(--text-muted)] tabular-nums">{format(livePrice, livePrice < 1 ? 6 : 2)}</span>
	                        {signal && <span className="text-[12px] font-medium whitespace-nowrap" style={{ color: signalTone(signal.display_score) }}>{signal.action_label}</span>}
	                      </div>
	                      {signal && (
	                        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
	                          <span className="text-[12px] uppercase tracking-wider text-[var(--text-muted)]">{signal.horizon}</span>
	                          <span className="text-[12px] text-[var(--text-secondary)]">{formatSetupType(signal.setup_type)}</span>
	                          <span className="text-[12px] text-[var(--text-muted)]">Indice {signal.composite_score}</span>
	                          <span className="text-[12px] text-[var(--text-muted)]">Fiab {signal.reliability_score}</span>
	                          <span className={cn("text-[12px]", executionRiskTone(signal.execution_risk))}>Exec {signal.execution_risk}</span>
	                          <span className="text-[12px] text-[var(--text-muted)]">Fresh {formatFreshness(signal.freshness_ms)}</span>
	                        </div>
	                      )}
	                      {primaryReason && (
	                        <p className="mt-1 text-[12px] leading-snug text-[var(--text-muted)]">{primaryReason}</p>
	                      )}
	                    </div>
	                    <LiveSparkline symbol={asset.symbol} price={livePrice} width={50} height={20} maxPoints={60} positive={liveChangePct >= 0} />
	                    {signal ? <ScoreGauge score={signal.display_score} size="sm" /> : <span className="text-[12px] text-[var(--text-muted)]">...</span>}
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleWatch(asset.symbol); }}
                      className="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--text-muted)] hover:text-[#ef4444] p-0.5">
                      <Star className="h-3 w-3" fill="currentColor" />
                    </button>
                  </div>
                );
              })}
            </div>
          </aside>

          {/* RIGHT: Chart + Readout */}
          <section className="min-w-0">
	          <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
	            <div className="flex items-center gap-3">
	              <div className="flex items-center gap-2">
								{selectedSymbol && <CryptoIcon symbol={selectedSymbol} imageUrl={selectedAsset?.image} size="lg" />}
	                <h2 className="text-lg font-semibold text-[var(--foreground)]">{selectedAsset?.symbol ?? selectedSymbol ?? "Select an asset"}</h2>
	                {selectedSignal && (
	                  <div className="mt-1 flex flex-wrap items-center gap-2">
	                    <span className="text-[12px] uppercase tracking-wider text-[var(--text-muted)]">{selectedSignal.horizon}</span>
	                    <span className="text-[12px] text-[var(--text-secondary)]">{formatSetupType(selectedSignal.setup_type)}</span>
	                    
	                  </div>
	                )}
	              </div>
	              {selectedAsset && (
	                <span className={cn("text-sm font-semibold", resolveAssetChangePct(selectedAsset.symbol, selectedAsset) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>
	                  {resolveAssetChangePct(selectedAsset.symbol, selectedAsset) >= 0 ? "+" : ""}{resolveAssetChangePct(selectedAsset.symbol, selectedAsset).toFixed(2)}%
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold font-mono text-[var(--foreground)]">
                {selectedAsset ? format(resolveAssetPrice(selectedAsset.symbol, selectedAsset), resolveAssetPrice(selectedAsset.symbol, selectedAsset) < 1 ? 6 : 2) : "--"}
              </span>
              {/* Chart type toggle */}
              <div className="flex rounded-md p-0.5" style={{ background: "var(--glass-bg)" }}>
                <button onClick={() => setChartType("candlestick")} className={cn("px-2 py-1 rounded text-[13px] font-medium transition", chartType === "candlestick" ? "bg-[var(--glass-bg-strong)] text-[var(--foreground)]" : "text-[var(--text-muted)]")}>
                  <CandlestickChart className="h-3.5 w-3.5" />
                </button>
              <button onClick={() => setChartType("line")} className={cn("px-2 py-1 rounded text-[13px] font-medium transition", chartType === "line" ? "bg-[var(--glass-bg-strong)] text-[var(--foreground)]" : "text-[var(--text-muted)]")}>
                  <Activity className="h-3.5 w-3.5" />
                </button>
              </div>
              <button onClick={() => openTradeModal("buy")} disabled={!selectedSymbol}
                className="rounded-lg px-3 py-1.5 text-[14px] font-semibold bg-[var(--success)]/12 text-[var(--success)] hover:bg-[var(--success)]/20 transition disabled:opacity-40">
                <ArrowUpRight className="inline h-3.5 w-3.5 mr-1" />Buy
              </button>
              <button onClick={() => openTradeModal("sell")} disabled={!selectedSymbol}
                className="rounded-lg px-3 py-1.5 text-[14px] font-semibold bg-[var(--danger)]/12 text-[var(--danger)] hover:bg-[var(--danger)]/20 transition disabled:opacity-40">
                <ArrowDownRight className="inline h-3.5 w-3.5 mr-1" />Sell
              </button>
            </div>
          </div>

          {selectedSymbol ? (
            <PriceChart symbol={selectedSymbol} type={chartType} height={292} showIntervals defaultInterval="1H" />
          ) : (
            <div className="flex h-[360px] items-center justify-center text-sm text-[var(--text-muted)]">Select an asset from the scanner below</div>
          )}

          {/* Signal readout V2 — enriched sub-scores */}
	          {selectedSignal && selectedSignal.sub_scores?.length > 0 && (
	            <div className="mt-4">
	              <SignalReadout
	                direction={selectedSignal.display_score}
	                directionLabel={signalReadoutLabel(selectedSignal)}
	                confidence={selectedSignal.composite_score}
	                reliability={selectedSignal.reliability_score}
	                risk={selectedSignal.risk}
	                setupQuality={selectedSignal.setup_quality}
	                regimeFit={selectedSignal.regime_fit}
	                confirmationScore={selectedSignal.confirmation_score}
	                executionRisk={selectedSignal.execution_risk}
	                published={selectedSignal.published}
	                actionability={selectedSignal.actionability}
	                action={selectedSignal.action}
	                marketRegime={selectedSignal.market_regime}
                signalContext={selectedSignal.signal_context}
                horizon={selectedSignal.horizon}
                setupType={formatSetupType(selectedSignal.setup_type)}
                expectedHoldingWindow={selectedSignal.expected_holding_window}
                subScores={selectedSignal.sub_scores}
                keyReasons={selectedSignal.key_reasons}
                notTradeReasons={selectedSignal.notrade_reasons}
                contradictions={selectedSignal.contradictions}
                tradePlan={selectedSignal.signal_trade_plan}
	              />
	            </div>
	          )}
	          {selectedSignal && selectedSignal.notrade_reasons.length > 0 && (
	            <div className="mt-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
	              <div className="flex items-center justify-between gap-3">
	                <p className="text-[12px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Publication filters</p>
	                {hiddenPublicationReasonCount > 0 ? (
	                  <span className="rounded-full border border-[var(--glass-border)] px-2 py-0.5 text-[12px] font-medium text-[var(--text-muted)]">
	                    +{hiddenPublicationReasonCount}
	                  </span>
	                ) : null}
	              </div>
	              {visiblePublicationReasons.map((reason, index) => (
	                <p key={`${reason}-${index}`} className="mt-1 text-[13px] text-[var(--text-secondary)]">
	                  - {reason}
	                </p>
	              ))}
	            </div>
	          )}
            <div className="mt-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[14px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Market Movers</p>
                  <p className="mt-0.5 text-[14px] text-[var(--text-muted)]">Discovery layer compacte pour alimenter la watchlist.</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setUniverseView(moversView);
                    setUniverseModalOpen(true);
                  }}
                  className="rounded-full border border-[var(--glass-border)] px-3 py-1 text-[12px] font-semibold text-[var(--foreground)] transition-colors hover:bg-[var(--glass-bg)]"
                >
                  Voir tout
                </button>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                {([
                  ["gainers", "Gains"],
                  ["losers", "Pertes"],
                  ["candidates", "Candidats"],
                ] as const).map(([view, label]) => (
                  <button
                    key={view}
                    type="button"
                    onClick={() => setMoversView(view)}
                    className={cn(
                      "rounded-full px-3 py-1 text-[13px] font-semibold transition-all",
                      moversView === view
                        ? "bg-[var(--glass-bg-strong)] text-[var(--foreground)]"
                        : "bg-[var(--glass-bg)] text-[var(--text-muted)] hover:text-[var(--foreground)]",
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {/* Sortable column headers */}
              <div className="mt-3 grid grid-cols-[minmax(0,1fr)_88px_74px_78px_34px] items-center gap-2 px-2 pb-1 border-b border-white/[0.04]">
                <button type="button" onClick={() => { setMoversSortBy("default"); setMoversSortAsc(false); }} className={cn("text-left text-[12px] uppercase tracking-wider transition-colors", moversSortBy === "default" ? "text-[var(--foreground)]" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]")}>
                  Asset
                </button>
                <button type="button" onClick={() => { if (moversSortBy === "price") { setMoversSortAsc(!moversSortAsc); } else { setMoversSortBy("price"); setMoversSortAsc(false); } }} className={cn("text-right text-[12px] uppercase tracking-wider transition-colors", moversSortBy === "price" ? "text-[var(--foreground)]" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]")}>
                  Prix {moversSortBy === "price" ? (moversSortAsc ? "\u2191" : "\u2193") : ""}
                </button>
                <button type="button" onClick={() => { if (moversSortBy === "change") { setMoversSortAsc(!moversSortAsc); } else { setMoversSortBy("change"); setMoversSortAsc(false); } }} className={cn("text-right text-[12px] uppercase tracking-wider transition-colors", moversSortBy === "change" ? "text-[var(--foreground)]" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]")}>
                  24h {moversSortBy === "change" ? (moversSortAsc ? "\u2191" : "\u2193") : ""}
                </button>
                <button type="button" onClick={() => { if (moversSortBy === "volume") { setMoversSortAsc(!moversSortAsc); } else { setMoversSortBy("volume"); setMoversSortAsc(false); } }} className={cn("text-right text-[12px] uppercase tracking-wider transition-colors", moversSortBy === "volume" ? "text-[var(--foreground)]" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]")}>
                  Vol {moversSortBy === "volume" ? (moversSortAsc ? "\u2191" : "\u2193") : ""}
                </button>
                <span />
              </div>
              <div className="mt-1 space-y-1">
                {compactMoversItems.length === 0 ? (
                  <p className="text-[14px] text-[var(--text-muted)] py-2">Le flux de marche est en cours de chargement.</p>
                ) : compactMoversItems.map((item) => {
                  const isWatched = watchlist.includes(item.symbol);
                  return (
                    <div
                      key={`${moversView}-${item.symbol}`}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedSymbol(item.symbol)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") setSelectedSymbol(item.symbol);
                      }}
                      className="grid grid-cols-[minmax(0,1fr)_88px_74px_78px_34px] items-center gap-2 rounded-xl px-2 py-2 transition-colors hover:bg-[var(--glass-bg)]"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <CryptoIcon symbol={item.symbol} imageUrl={item.image} size="sm" />
                          <span className="truncate text-[15px] font-bold text-[var(--foreground)]">{item.symbol}</span>
                        </div>
                        <p className="truncate text-[13px] text-[var(--text-muted)]">{item.name}</p>
                      </div>
                      <span className="text-right text-[14px] font-mono text-[var(--foreground)]">{format(item.price, item.price < 1 ? 6 : 2)}</span>
                      <span className={cn("text-right text-[14px] font-semibold", item.changePct24h >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>
                        {item.changePct24h >= 0 ? "+" : ""}
                        {item.changePct24h.toFixed(1)}%
                      </span>
                      <span className="text-right text-[13px] text-[var(--text-secondary)]">{compactMetricNumber(item.volume24h)}</span>
                      <div className="flex justify-end">
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            toggleWatch(item.symbol);
                          }}
                          className={cn(
                            "rounded-full p-1.5 transition-colors",
                            isWatched ? "text-[#c6f135]" : "text-[var(--text-muted)] hover:text-[var(--foreground)]",
                          )}
                        >
                          <Star className="h-3.5 w-3.5" fill={isWatched ? "currentColor" : "none"} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
	          </section>
        </div>


      </div>

      <MarketUniverseModal
        open={universeModalOpen}
        items={modalUniverseItems}
        activeView={universeView}
        watchlist={watchlist}
        onClose={() => setUniverseModalOpen(false)}
        onSelectSymbol={selectUniverseSymbol}
        onToggleWatch={toggleWatch}
        onViewChange={setUniverseView}
        formatPrice={format}
      />

      <WalletOverviewModal
        open={walletModalOpen}
        items={walletView.items}
        selectedSymbol={selectedSymbol}
        formatValue={format}
        onClose={() => setWalletModalOpen(false)}
        onSelectSymbol={(symbol) => {
          setSelectedSymbol(symbol);
          setWalletModalOpen(false);
        }}
      />

      {tradeModalOpen && selectedSymbol ? (
        <QuickTradeModal
          symbol={selectedSymbol}
          price={resolveAssetPrice(selectedSymbol.toUpperCase(), selectedAsset) || Number(selectedPosition?.current_price ?? 0)}
          initialSide={tradeIntent.side}
          initialUsdAmount={tradeIntent.amount}
          availableQuote={cashValue}
          availableBase={selectedHolding?.available ?? selectedHolding?.total ?? 0}
          advisoryText={tradeIntent.advisory}
          walletAccessEnabled={account?.wallet_access_enabled ?? false}
          walletAccessReason={account?.wallet_access_reason}
          liveTradingEnabled={account?.live_trading_enabled ?? false}
          onClose={() => setTradeModalOpen(false)}
          onSuccess={() => { setTradeModalOpen(false); void refreshDesk(); }}
        />
      ) : null}
    </>
  );
}

function WalletOverviewModal({
  open,
  items,
  selectedSymbol,
  formatValue,
  onClose,
  onSelectSymbol,
}: {
  open: boolean;
  items: WalletPreviewItem[];
  selectedSymbol: string | null;
  formatValue: (value: number, decimals?: number) => string;
  onClose: () => void;
  onSelectSymbol: (symbol: string) => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative flex h-[min(85vh,760px)] w-full max-w-2xl flex-col overflow-hidden rounded-[28px] border border-[var(--glass-border)] bg-[var(--surface)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-[var(--glass-border)] px-5 py-4">
          <div>
            <h3 className="text-lg font-bold text-[var(--foreground)]">Wallet complet</h3>
            <p className="mt-1 text-[13px] text-[var(--text-muted)]">{items.length} actifs detectes</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl p-2 text-[var(--text-muted)] transition-colors hover:bg-[var(--glass-bg)] hover:text-[var(--foreground)]"
            aria-label="Fermer le wallet"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-4">
          <div className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
            {items.map((item) => (
              <button
                key={item.sym}
                type="button"
                disabled={item.fiat}
                onClick={() => onSelectSymbol(item.sym)}
                className={cn(
                  "flex w-full items-center justify-between gap-4 py-1 text-left transition-colors",
                  item.fiat
                    ? "cursor-default opacity-80"
                    : "hover:text-[var(--page-accent)]",
                  !item.fiat && selectedSymbol === item.sym ? "text-[var(--page-accent)]" : "",
                )}
              >
                <div className="flex min-w-0 items-center gap-3">
                  <CryptoIcon symbol={item.sym} imageUrl={item.image} size="sm" />
                  <div className="min-w-0">
                    <p className="truncate text-[15px] font-bold text-[var(--foreground)]">{item.sym}</p>
                    <p className="truncate text-[12px] font-mono text-[var(--text-muted)]">
                      {item.fiat ? `${item.fiatSym}${item.total.toFixed(2)}` : item.total.toLocaleString(undefined, {
                        maximumFractionDigits: item.price >= 1000 ? 4 : item.total < 1 ? 6 : 2,
                      })}
                    </p>
                  </div>
                </div>
                <div className="ml-4 text-right">
                  <p className="text-[15px] font-semibold font-mono text-[var(--foreground)]">{item.price > 0 ? formatValue(item.value) : "--"}</p>
                  <p
                    className={cn(
                      "text-[12px] font-semibold",
                      item.fiat || item.stable ? "text-[var(--text-muted)]" : item.changePct >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
                    )}
                  >
                    {item.fiat || item.stable ? "Stable" : `${item.changePct >= 0 ? "+" : ""}${item.changePct.toFixed(1)}%`}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
