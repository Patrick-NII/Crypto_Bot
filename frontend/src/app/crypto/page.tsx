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
} from "lucide-react";
import { WalletAccessPanel } from "@/components/account/wallet-access-panel";
import { usePageAccent, PAGE_ACCENTS, useTheme } from "@/components/providers/theme-provider";
import { useCurrency } from "@/components/providers/currency-provider";
import { PriceChart } from "@/components/charts/price-chart";
import { LiveSparkline } from "@/components/charts/live-sparkline";
import { QuickTradeModal } from "@/components/trading/quick-trade-modal";
import { ScoreGauge, SignalReadout } from "@/components/trading/signal-score";
import {
  type AutoTradingHistorySnapshot,
  type AutoTradingStatusSnapshot,
} from "@/components/trading/auto-trading-monitor";
import { SignalBadge, type SignalAction } from "@/components/trading/signal-badge";
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
  Order,
  PortfolioSnapshot,
  Strategy,
  UserProfile,
} from "@/lib/types";

const REFRESH_INTERVAL = 30_000;
const SIGNAL_REFRESH_INTERVAL = 45_000;
const SIGNAL_SCAN_LIMIT = 14;
const WATCHLIST_KEY = "watchlist";
const DEFAULT_WATCHLIST = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"];
const TRADING_VIEW_CACHE_KEY = "okamoey-trading-view";
const TRADING_VIEW_CACHE_TTL = 300_000;

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
  contradictions: Array<{ description: string; severity: string }>;
  signal_trade_plan: { side: string; entry_zone: string; invalidation_zone: string; target_zone: string; risk_reward: string; validity: string; execution_style: string } | null;
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

interface TradingViewCache {
  selectedSymbol: string | null;
  chartType: "candlestick" | "line";
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


/** Live clock that ticks every second, using the browser's local timezone. */
function LocalClock() {
  const [time, setTime] = useState("--:--:--");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
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
    <span className="text-[11px] font-mono text-[var(--text-muted)] tabular-nums" suppressHydrationWarning>
      {mounted ? time : "--:--:--"}
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
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">{label}</span>
      </div>
      <div className={cn("text-xl font-bold font-mono text-[var(--foreground)]", tone)}>{value}</div>
      {sublabel ? <p className="text-[12px] text-[var(--text-muted)] mt-0.5">{sublabel}</p> : null}
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
  const [chartType, setChartType] = useState<"candlestick" | "line">("candlestick");

  // ---- Live Wallet (always fetched, independent of walletUnlocked) ----
  const [walletPreview, setWalletPreview] = useState<Array<{ currency: string; available: number; reserved: number; total: number }>>([]);
  const [walletPreviewLoading, setWalletPreviewLoading] = useState(true);
  const [walletPreviewError, setWalletPreviewError] = useState<string | null>(null);

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

  // Load watchlist from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(WATCHLIST_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as string[];
        if (Array.isArray(parsed) && parsed.length > 0) {
          setWatchlist(parsed);
          return;
        }
      }
    } catch { /* empty */ }
    // First time: seed with defaults
    setWatchlist(DEFAULT_WATCHLIST);
    try { localStorage.setItem(WATCHLIST_KEY, JSON.stringify(DEFAULT_WATCHLIST)); } catch { /* empty */ }
  }, []);

  const toggleWatch = useCallback((symbol: string) => {
    setWatchlist((prev) => {
      const upper = symbol.toUpperCase();
      const next = prev.includes(upper) ? prev.filter((s) => s !== upper) : [...prev, upper];
      try { localStorage.setItem(WATCHLIST_KEY, JSON.stringify(next)); } catch { /* empty */ }
      return next;
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
      setSignalMap(cachedView.signalMap);
      setChartType(cachedView.chartType);
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
    writeObjectCache<TradingViewCache>(TRADING_VIEW_CACHE_KEY, {
      selectedSymbol,
      chartType,
      orders,
      analytics,
      strategies,
      autoStatus,
      autoHistory: autoHistory.slice(0, 24),
      health,
      signalMap,
    });
  }, [analytics, autoHistory, autoStatus, chartType, health, orders, selectedSymbol, signalMap, strategies]);

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
      const changePct = stable ? 0 : Number(mktAsset?.price_change_percentage_24h ?? mktAsset?.change_pct_24h ?? 0);
      return { symbol, total, available: balance.available, reserved: balance.reserved, price, value, changePct, stable };
    }).filter((h) => h.total > 0).sort((a, b) => b.value - a.value);
  }, [livePrices, marketBySymbol, snapshot, walletPreview]);

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
    (symbol: string, asset?: CryptoMarketData | null) =>
      Number(
        liveTickers[symbol]?.changePct24h ??
          asset?.price_change_percentage_24h ??
          asset?.change_pct_24h ??
          0,
      ),
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
      ...market
        .slice(0, 24)
        .sort((left, right) => Number(right.volume_24h ?? 0) - Number(left.volume_24h ?? 0))
        .map((asset) => asset.symbol.toUpperCase()),
      ...holdings.filter((holding) => !holding.stable).map((holding) => holding.symbol.toUpperCase()),
      ...positions.map((position) => position.symbol.toUpperCase()),
      ...orders.slice(0, 8).map((order) => order.symbol.toUpperCase()),
    ]);

    return candidateSymbols.filter(Boolean).slice(0, SIGNAL_SCAN_LIMIT);
  }, [holdings, market, orders, positions, selectedSymbol]);
  const signalUniverseKey = useMemo(() => signalUniverse.join("|"), [signalUniverse]);

  useEffect(() => {
    const symbols = signalUniverseKey.split("|").filter(Boolean);
    if (symbols.length === 0) return;

    let cancelled = false;
    const cachedSignals: Record<string, SignalDetail> = {};
    for (const symbol of symbols) {
      const cached = signalsApi.peekSignal(symbol);
      if (!cached) continue;
      cachedSignals[symbol.toUpperCase()] = {
        symbol: cached.symbol.toUpperCase(),
        action: normalizeAction(cached.action),
        confidence: Number(cached.confidence ?? 0),
        score: Number(cached.score ?? 0),
        reasoning: cached.reasoning,
        indicators: cached.indicators ?? [],
        timestamp: cached.timestamp,
        score_100: cached.score_100 ?? 50,
        action_label: cached.action_label ?? "Neutre",
        confidence_level: cached.confidence_level ?? "moyen",
        status: cached.status ?? "ignore",
        sub_scores: cached.sub_scores ?? [],
        key_reasons: cached.key_reasons ?? [],
        direction: cached.direction ?? cached.score_100 ?? 50,
        direction_label: cached.direction_label ?? cached.action_label ?? "Neutre",
        confidence_score: cached.confidence_score ?? Math.round((cached.confidence ?? 0) * 100),
        risk: cached.risk ?? 50,
        setup_quality: cached.setup_quality ?? 50,
        actionability: cached.actionability ?? cached.status?.toUpperCase() ?? "IGNORE",
        market_regime: cached.market_regime ?? "UNKNOWN",
        signal_context: cached.signal_context ?? "mixed",
        contradictions: cached.contradictions ?? [],
        signal_trade_plan: cached.signal_trade_plan ?? null,
      };
    }

    if (Object.keys(cachedSignals).length > 0) {
      setSignalMap((current) => ({ ...current, ...cachedSignals }));
    }

    const fetchSignals = async () => {
      setSignalsLoading(true);

      try {
        const results = await Promise.allSettled(symbols.map((symbol) => signalsApi.getSignal(symbol)));
        if (cancelled) return;

        const nextSignalMap: Record<string, SignalDetail> = {};
        for (const result of results) {
          if (result.status !== "fulfilled") continue;
          const signal = result.value;
          nextSignalMap[signal.symbol.toUpperCase()] = {
            symbol: signal.symbol.toUpperCase(),
            action: normalizeAction(signal.action),
            confidence: Number(signal.confidence ?? 0),
            score: Number(signal.score ?? 0),
            reasoning: signal.reasoning,
            indicators: signal.indicators ?? [],
            timestamp: signal.timestamp,
            score_100: signal.score_100 ?? 50,
            action_label: signal.action_label ?? "Neutre",
            confidence_level: signal.confidence_level ?? "moyen",
            status: signal.status ?? "ignore",
            sub_scores: signal.sub_scores ?? [],
            key_reasons: signal.key_reasons ?? [],
            direction: signal.direction ?? signal.score_100 ?? 50,
            direction_label: signal.direction_label ?? signal.action_label ?? "Neutre",
            confidence_score: signal.confidence_score ?? Math.round((signal.confidence ?? 0) * 100),
            risk: signal.risk ?? 50,
            setup_quality: signal.setup_quality ?? 50,
            actionability: signal.actionability ?? signal.status?.toUpperCase() ?? "IGNORE",
            market_regime: signal.market_regime ?? "UNKNOWN",
            signal_context: signal.signal_context ?? "mixed",
            contradictions: signal.contradictions ?? [],
            signal_trade_plan: signal.signal_trade_plan ?? null,
          };
        }

        setSignalMap((current) => ({ ...current, ...nextSignalMap }));
      } finally {
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
      ...market.slice(0, 16).map((asset) => asset.symbol.toUpperCase()),
      ...holdings.slice(0, 8).map((holding) => holding.symbol.toUpperCase()),
    ]).filter((symbol) => !WALLET_STABLES.has(symbol));
  }, [holdings, market, selectedSymbol]);
  const liveSymbolsKey = useMemo(() => liveSymbols.join("|"), [liveSymbols]);

  useEffect(() => {
    const symbols = liveSymbolsKey.split("|").filter(Boolean);
    if (symbols.length === 0) return;

    const unsubs = symbols.map((symbol) =>
      priceWs.subscribe(symbol, (update) => {
        const upper = update.symbol.toUpperCase();
        const nextPrice = Number(update.price);
        const nextChangePct = Number(update.change_pct_24h ?? 0);
        const nextVolume = Number(update.volume_24h ?? 0);

        startTransition(() => {
          setLiveTickers((current) => {
            const previous = current[upper];
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
      }),
    );

    return () => {
      for (const unsub of unsubs) unsub();
    };
  }, [liveSymbolsKey]);

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
    if (watchlist.length === 0) return market.slice(0, 10);
    return market.filter((a) => watchlist.includes(a.symbol.toUpperCase()));
  }, [market, watchlist]);

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
    if (!walletUnlocked) return;
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
      if (!walletUnlocked) return;
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

  const handleAutoToggle = useCallback(async () => {
    if (!autoStatus || !walletUnlocked) return;
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
            <h1 className="text-xl md:text-2xl font-bold glow-text">Trading</h1>
            <div className="flex items-center gap-2 mt-1">
              <span className={cn("text-[12px] font-medium", health?.connected ? "text-[var(--success)]" : "text-[var(--text-muted)]")}>{feedLabel}</span>
              <span className="text-[12px] text-[var(--text-muted)]">&middot; {portfolioHeadline}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Mode toggle */}
            <div className="flex rounded-lg p-0.5" style={{ background: "var(--glass-bg)" }}>
              <button onClick={() => setTradingMode("manual")}
                className={cn("flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-semibold transition-all",
                  tradingMode === "manual" ? "bg-[var(--glass-bg-strong)] text-[var(--foreground)]" : "text-[var(--text-muted)]")}>
                <CandlestickChart className="h-3.5 w-3.5" /> Manual
              </button>
              <button onClick={() => setTradingMode("auto")}
                className={cn("flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-semibold transition-all",
                  tradingMode === "auto" ? "bg-[var(--glass-bg-strong)] text-[var(--foreground)]" : "text-[var(--text-muted)]")}>
                <Bot className="h-3.5 w-3.5" /> Auto
              </button>
            </div>
            <button onClick={() => void refreshDesk()} className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all">
              <RefreshCw className={cn("h-3.5 w-3.5", refreshing && "animate-spin")} /> Refresh
            </button>
            <button onClick={() => void handleAutoToggle()} disabled={!autoStatus || arming || !walletUnlocked}
              className={cn("flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-semibold transition-all disabled:opacity-40",
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
        <section className="rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-bg)] p-4 md:p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Wallet className="h-4 w-4 accent-text" />
              <h2 className="text-sm font-semibold text-[var(--foreground)]">My Wallet</h2>
              <span className="rounded-full border border-[var(--glass-border)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-muted)]">
                Binance
              </span>
            </div>
            {walletPreviewLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--text-muted)]" />}
          </div>

          {walletPreviewError ? (
            <div className="rounded-xl border border-[var(--danger)]/20 bg-[var(--danger)]/5 px-3 py-2.5">
              <p className="text-[12px] text-[var(--danger)]">{walletPreviewError}</p>
              <p className="text-[11px] text-[var(--text-muted)] mt-1">
                Check your API keys in Settings and ensure wallet access is unlocked.
              </p>
            </div>
          ) : walletPreview.length === 0 && !walletPreviewLoading ? (
            <p className="text-[12px] text-[var(--text-muted)]">No balances found. Add your Binance API keys in Settings.</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {walletPreview.map((balance) => {
                const stable = WALLET_STABLES.has(balance.currency.toUpperCase());
                const mktAsset = marketBySymbol.get(balance.currency.toUpperCase());
                const price = stable ? 1 : livePrices[balance.currency.toUpperCase()] ?? Number(mktAsset?.current_price ?? mktAsset?.price ?? 0);
                const value = balance.total * price;
                return (
                  <div key={balance.currency} className="flex items-center justify-between rounded-xl border border-[var(--glass-border)] bg-[var(--background)]/30 px-3 py-2.5">
                    <div>
                      <p className="text-[13px] font-semibold text-[var(--foreground)]">{balance.currency}</p>
                      <p className="text-[11px] text-[var(--text-muted)]">{balance.total.toFixed(price >= 1000 ? 4 : balance.total < 1 ? 8 : 2)}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-[13px] font-semibold text-[var(--foreground)]">{price > 0 ? format(value) : "--"}</p>
                      <p className="text-[10px] text-[var(--text-muted)]">{stable ? "Stablecoin" : price > 0 ? `@ ${format(price, 2)}` : "No price"}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* ============ MAIN LAYOUT: Scanner (left) + Chart (right) ============ */}
        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">

          {/* LEFT: Scanner with search + watchlist */}
          <aside className="lg:order-first order-last">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-[var(--foreground)]">Scanner <span className="text-[10px] text-[var(--text-muted)] font-normal ml-1">{scannerAssets.length}</span></h2>
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
                  className="flex-1 bg-transparent text-[12px] text-[var(--foreground)] placeholder-[var(--text-muted)] outline-none"
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery("")} className="text-[var(--text-muted)] hover:text-[var(--foreground)] text-[10px]">x</button>
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
                            <span className="text-[12px] font-bold text-[var(--foreground)]">{asset.symbol}</span>
                            <span className="text-[10px] font-mono text-[var(--text-muted)]">{format(lp, 2)}</span>
                            <span className={cn("text-[9px] font-semibold", cp >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>{cp >= 0 ? "+" : ""}{cp.toFixed(1)}%</span>
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
                <p className="text-[11px] text-[var(--text-muted)] text-center py-4">Recherchez et suivez des cryptos</p>
              )}
              {scannerAssets.map((asset) => {
                const signal = signalMap[asset.symbol.toUpperCase()];
                const livePrice = resolveAssetPrice(asset.symbol.toUpperCase(), asset);
                const liveChangePct = resolveAssetChangePct(asset.symbol.toUpperCase(), asset);
                return (
                  <div key={asset.symbol} role="button" tabIndex={0}
                    onClick={() => setSelectedSymbol(asset.symbol)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setSelectedSymbol(asset.symbol); }}
                    className={cn("flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer transition-all duration-150 group",
                      selectedSymbol === asset.symbol
                        ? "bg-[var(--glass-bg-strong)] shadow-sm"
                        : "hover:bg-[var(--glass-bg)]")}>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[12px] font-bold text-[var(--foreground)]">{asset.symbol}</span>
                        <span className={cn("text-[9px] font-semibold", liveChangePct >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>{liveChangePct >= 0 ? "+" : ""}{liveChangePct.toFixed(1)}%</span>
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="text-[10px] font-mono text-[var(--text-muted)] tabular-nums">{format(livePrice, 2)}</span>
                        {signal && <span className="text-[9px] font-medium truncate" style={{ color: signal.score_100 >= 60 ? "#4ade80" : signal.score_100 <= 40 ? "#ef4444" : "#8888a0" }}>{signal.action_label}</span>}
                      </div>
                    </div>
                    <LiveSparkline symbol={asset.symbol} price={livePrice} width={50} height={20} maxPoints={60} positive={liveChangePct >= 0} />
                    {signal ? <ScoreGauge score={signal.score_100} size="sm" /> : <span className="text-[8px] text-[var(--text-muted)]">...</span>}
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
              <h2 className="text-lg font-semibold text-[var(--foreground)]">{selectedAsset?.symbol ?? selectedSymbol ?? "Select an asset"}</h2>
              {selectedSignal && <SignalBadge action={selectedSignal.action} confidence={selectedSignal.confidence} size="md" blink={tradingMode === "auto" && Boolean(autoStatus?.enabled)} />}
              {selectedAsset && (
                <span className={cn("text-sm font-semibold", resolveAssetChangePct(selectedAsset.symbol, selectedAsset) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>
                  {resolveAssetChangePct(selectedAsset.symbol, selectedAsset) >= 0 ? "+" : ""}{resolveAssetChangePct(selectedAsset.symbol, selectedAsset).toFixed(2)}%
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold font-mono text-[var(--foreground)]">
                {selectedAsset ? format(resolveAssetPrice(selectedAsset.symbol, selectedAsset), 2) : "--"}
              </span>
              {/* Chart type toggle */}
              <div className="flex rounded-md p-0.5" style={{ background: "var(--glass-bg)" }}>
                <button onClick={() => setChartType("candlestick")} className={cn("px-2 py-1 rounded text-[11px] font-medium transition", chartType === "candlestick" ? "bg-[var(--glass-bg-strong)] text-[var(--foreground)]" : "text-[var(--text-muted)]")}>
                  <CandlestickChart className="h-3.5 w-3.5" />
                </button>
              <button onClick={() => setChartType("line")} className={cn("px-2 py-1 rounded text-[11px] font-medium transition", chartType === "line" ? "bg-[var(--glass-bg-strong)] text-[var(--foreground)]" : "text-[var(--text-muted)]")}>
                  <Activity className="h-3.5 w-3.5" />
                </button>
              </div>
              <button onClick={() => openTradeModal("buy")} disabled={!selectedSymbol || !walletUnlocked}
                className="rounded-lg px-3 py-1.5 text-[12px] font-semibold bg-[var(--success)]/12 text-[var(--success)] hover:bg-[var(--success)]/20 transition disabled:opacity-40">
                <ArrowUpRight className="inline h-3.5 w-3.5 mr-1" />Buy
              </button>
              <button onClick={() => openTradeModal("sell")} disabled={!selectedSymbol || !walletUnlocked}
                className="rounded-lg px-3 py-1.5 text-[12px] font-semibold bg-[var(--danger)]/12 text-[var(--danger)] hover:bg-[var(--danger)]/20 transition disabled:opacity-40">
                <ArrowDownRight className="inline h-3.5 w-3.5 mr-1" />Sell
              </button>
            </div>
          </div>

          {selectedSymbol ? (
            <PriceChart symbol={selectedSymbol} type={chartType} height={320} showIntervals defaultInterval="1H" />
          ) : (
            <div className="flex h-[420px] items-center justify-center text-sm text-[var(--text-muted)]">Select an asset from the scanner below</div>
          )}

          {/* Signal readout V2 — enriched sub-scores */}
          {selectedSignal && selectedSignal.sub_scores?.length > 0 && (
            <div className="mt-4">
              <SignalReadout
                direction={selectedSignal.direction}
                directionLabel={selectedSignal.direction_label}
                confidence={selectedSignal.confidence_score}
                risk={selectedSignal.risk}
                setupQuality={selectedSignal.setup_quality}
                actionability={selectedSignal.actionability}
                action={selectedSignal.action}
                marketRegime={selectedSignal.market_regime}
                signalContext={selectedSignal.signal_context}
                subScores={selectedSignal.sub_scores}
                keyReasons={selectedSignal.key_reasons}
                contradictions={selectedSignal.contradictions}
                tradePlan={selectedSignal.signal_trade_plan}
              />
            </div>
          )}
          </section>
        </div>


      </div>

      {tradeModalOpen && selectedSymbol ? (
        <QuickTradeModal
          symbol={selectedSymbol}
          price={resolveAssetPrice(selectedSymbol.toUpperCase(), selectedAsset) || Number(selectedPosition?.current_price ?? 0)}
          initialSide={tradeIntent.side}
          initialUsdAmount={tradeIntent.amount}
          availableQuote={cashValue}
          availableBase={selectedHolding?.available ?? selectedHolding?.total ?? 0}
          advisoryText={tradeIntent.advisory}
          onClose={() => setTradeModalOpen(false)}
          onSuccess={() => { setTradeModalOpen(false); void refreshDesk(); }}
        />
      ) : null}
    </>
  );
}
