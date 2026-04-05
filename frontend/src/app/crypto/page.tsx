"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
} from "lucide-react";
import { WalletAccessPanel } from "@/components/account/wallet-access-panel";
import { usePageAccent, PAGE_ACCENTS, useTheme } from "@/components/providers/theme-provider";
import { useCurrency } from "@/components/providers/currency-provider";
import { PriceChart } from "@/components/charts/price-chart";
import { QuickTradeModal } from "@/components/trading/quick-trade-modal";
import {
  type AutoTradingHistorySnapshot,
  type AutoTradingStatusSnapshot,
} from "@/components/trading/auto-trading-monitor";
import { IndicatorBar, SignalBadge, type SignalAction } from "@/components/trading/signal-badge";
import { AIReasoningMonitor, transformHistoryToMonitorEntries } from "@/components/trading/ai-reasoning-monitor";
import { ApiError, aiApi, analyticsApi, authApi, binanceApi, portfolioApi, pricesApi, signalsApi, strategiesApi, tradingApi } from "@/lib/api";
import { priceWs } from "@/lib/websocket";
import { cn, formatRelative } from "@/lib/utils";
import type {
  AnalyticsMetrics,
  CryptoMarketData,
  ExecutionFeedItem,
  Order,
  PaperBalance,
  Portfolio,
  Position,
  RiskMetrics,
  Strategy,
  UserProfile,
} from "@/lib/types";

const MARKET_CACHE_KEY = "okamoey-trading-market-cache";
const STABLES = new Set(["USDT", "USDC", "BUSD", "FDUSD", "USD", "DAI", "TUSD", "EUR"]);
const SIGNAL_SCAN_LIMIT = 14;

interface SignalDetail {
  symbol: string;
  action: SignalAction;
  confidence: number;
  score: number;
  reasoning: string;
  indicators: Array<{
    name: string;
    value: number;
    signal: number;
    description: string;
  }>;
  timestamp: string;
}

interface HoldingSnapshot {
  symbol: string;
  total: number;
  available: number;
  reserved: number;
  price: number;
  value: number;
  changePct: number;
  stable: boolean;
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

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
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

function estimateRiskScore(holdings: HoldingSnapshot[], riskMetrics: RiskMetrics | null): number {
  if (riskMetrics?.risk_score != null) {
    return Math.round(clamp(riskMetrics.risk_score, 0, 100));
  }

  const totalValue = holdings.reduce((sum, item) => sum + item.value, 0);
  if (totalValue <= 0) return 0;
  const weights = holdings.filter((item) => item.value > 0).map((item) => item.value / totalValue);
  const hhi = weights.reduce((sum, weight) => sum + weight * weight, 0);
  const weightedChange = holdings.reduce((sum, item) => sum + Math.abs(item.changePct) * (item.value / totalValue), 0);
  return Math.round(clamp(hhi * 65 + weightedChange * 1.5, 0, 100));
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
  const [balances, setBalances] = useState<PaperBalance[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [executionFeed, setExecutionFeed] = useState<ExecutionFeedItem[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsMetrics | null>(null);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [autoStatus, setAutoStatus] = useState<AutoTradingStatusSnapshot | null>(null);
  const [autoHistory, setAutoHistory] = useState<AutoTradingHistorySnapshot[]>([]);
  const [health, setHealth] = useState<{ status: string; connected: boolean } | null>(null);
  const [signalMap, setSignalMap] = useState<Record<string, SignalDetail>>({});
  const [livePrices, setLivePrices] = useState<Record<string, number>>({});
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [tradeIntent, setTradeIntent] = useState<TradeIntent>({ side: "buy" });
  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  const [chartType, setChartType] = useState<"candlestick" | "line">("candlestick");

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = localStorage.getItem(MARKET_CACHE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as { data?: CryptoMarketData[] };
      if (!Array.isArray(parsed.data) || parsed.data.length === 0) return;
      setMarket(parsed.data);
      setSelectedSymbol((current) => current ?? parsed.data?.[0]?.symbol ?? null);
    } catch {
      // Ignore cache parse failures
    }
  }, []);

  const refreshDesk = useCallback(async () => {
    setRefreshing(true);

    try {
      const [
        meResult,
        marketResult,
        strategiesResult,
        autoStatusResult,
        autoHistoryResult,
        healthResult,
      ] = await Promise.allSettled([
        authApi.getMe(),
        pricesApi.getAllCryptos(80),
        strategiesApi.list(),
        aiApi.getAutoTradingStatus(),
        aiApi.getAutoTradingHistory(),
        binanceApi.health(),
      ]);

      if (marketResult.status === "fulfilled" && marketResult.value.data.length > 0) {
        setMarket(marketResult.value.data);
        setSelectedSymbol((current) => current ?? marketResult.value.data[0]?.symbol ?? null);
        if (typeof window !== "undefined") {
          localStorage.setItem(MARKET_CACHE_KEY, JSON.stringify({ data: marketResult.value.data, ts: Date.now() }));
        }
      }

      setAccount(meResult.status === "fulfilled" ? meResult.value : null);

      const walletUnlocked = meResult.status === "fulfilled" ? meResult.value.wallet_access_enabled : false;
      if (walletUnlocked) {
        const [snapshotResult, ordersResult, analyticsResult] = await Promise.allSettled([
          portfolioApi.getSnapshot(),
          tradingApi.getOrders(),
          analyticsApi.getMetrics(),
        ]);

        if (snapshotResult.status === "fulfilled") {
          setBalances(
            snapshotResult.value.balances.map((balance) => ({
              currency: balance.currency,
              available: balance.available,
              reserved: balance.reserved,
              total: balance.total,
            })),
          );
          setPortfolios(snapshotResult.value.portfolios);
          setPositions(snapshotResult.value.positions);
          setExecutionFeed(snapshotResult.value.execution_feed);
          setRiskMetrics(snapshotResult.value.risk ?? null);
        }
        if (ordersResult.status === "fulfilled") setOrders(ordersResult.value);
        if (analyticsResult.status === "fulfilled") setAnalytics(analyticsResult.value);
      } else {
        setBalances([]);
        setOrders([]);
        setPortfolios([]);
        setPositions([]);
        setExecutionFeed([]);
        setAnalytics(null);
        setRiskMetrics(null);
      }
      if (strategiesResult.status === "fulfilled") setStrategies(strategiesResult.value);
      if (autoStatusResult.status === "fulfilled") setAutoStatus(autoStatusResult.value);
      if (autoHistoryResult.status === "fulfilled") setAutoHistory(autoHistoryResult.value);
      if (healthResult.status === "fulfilled") setHealth(healthResult.value);
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 403)) {
        // Ignore wallet lock, surface everything else through the desk state.
      }
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshDesk();
    const interval = window.setInterval(() => {
      void refreshDesk();
    }, 30_000);
    return () => window.clearInterval(interval);
  }, [refreshDesk]);

  const marketBySymbol = useMemo(
    () => new Map(market.map((asset) => [asset.symbol.toUpperCase(), asset])),
    [market],
  );

  const holdings = useMemo<HoldingSnapshot[]>(() => {
    return balances
      .map((balance) => {
        const symbol = balance.currency.toUpperCase();
        const stable = STABLES.has(symbol);
        const marketAsset = marketBySymbol.get(symbol);
        const livePrice = livePrices[symbol];
        const price = stable ? 1 : livePrice ?? Number(marketAsset?.current_price ?? marketAsset?.price ?? 0);
        const total = Number(balance.total ?? balance.available + balance.reserved);
        const value = stable ? total : total * price;
        const changePct = stable
          ? 0
          : Number(marketAsset?.price_change_percentage_24h ?? marketAsset?.change_pct_24h ?? 0);

        return {
          symbol,
          total,
          available: Number(balance.available ?? total),
          reserved: Number(balance.reserved ?? 0),
          price,
          value,
          changePct,
          stable,
        };
      })
      .filter((holding) => holding.total > 0)
      .sort((left, right) => right.value - left.value);
  }, [balances, livePrices, marketBySymbol]);

  const portfolioValue = useMemo(() => {
    const fromHoldings = holdings.reduce((sum, holding) => sum + holding.value, 0);
    if (fromHoldings > 0) return fromHoldings;
    return portfolios[0]?.total_value ?? 0;
  }, [holdings, portfolios]);

  const cashValue = useMemo(
    () => holdings.filter((holding) => holding.stable).reduce((sum, holding) => sum + holding.value, 0),
    [holdings],
  );

  const marketExposure = Math.max(portfolioValue - cashValue, 0);

  const openPnl = useMemo(() => {
    if (positions.length > 0) {
      return positions.reduce((sum, position) => sum + Number(position.pnl ?? 0), 0);
    }

    return holdings
      .filter((holding) => !holding.stable)
      .reduce((sum, holding) => {
        if (holding.changePct === 0) return sum;
        return sum + (holding.value - holding.value / (1 + holding.changePct / 100));
      }, 0);
  }, [holdings, positions]);

  const openPnlPct = portfolioValue > 0 ? (openPnl / Math.max(portfolioValue - openPnl, 1)) * 100 : 0;
  const estimatedRisk = useMemo(() => estimateRiskScore(holdings, riskMetrics), [holdings, riskMetrics]);
  const riskSummary = riskMetrics?.risk_level
    ? `${riskMetrics.risk_level.charAt(0).toUpperCase()}${riskMetrics.risk_level.slice(1)}`
    : riskLabel(estimatedRisk);
  const regime = useMemo(() => marketRegime(market), [market]);

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

  useEffect(() => {
    if (signalUniverse.length === 0) return;

    let cancelled = false;
    const fetchSignals = async () => {
      setSignalsLoading(true);

      try {
        const results = await Promise.allSettled(signalUniverse.map((symbol) => signalsApi.getSignal(symbol)));
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
    }, 45_000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [signalUniverse]);

  const liveSymbols = useMemo(() => {
    return unique([
      ...(selectedSymbol ? [selectedSymbol] : []),
      ...market.slice(0, 16).map((asset) => asset.symbol.toUpperCase()),
      ...holdings.slice(0, 8).map((holding) => holding.symbol.toUpperCase()),
    ]).filter((symbol) => !STABLES.has(symbol));
  }, [holdings, market, selectedSymbol]);

  useEffect(() => {
    if (liveSymbols.length === 0) return;

    const unsubs = liveSymbols.map((symbol) =>
      priceWs.subscribe(symbol, (update) => {
        const upper = update.symbol.toUpperCase();
        setLivePrices((current) => ({ ...current, [upper]: Number(update.price) }));
        setMarket((current) =>
          current.map((asset) =>
            asset.symbol.toUpperCase() === upper
              ? {
                  ...asset,
                  price: Number(update.price),
                  current_price: Number(update.price),
                  change_pct_24h: Number(update.change_pct_24h ?? asset.change_pct_24h ?? 0),
                  price_change_percentage_24h: Number(
                    update.change_pct_24h ?? asset.price_change_percentage_24h ?? asset.change_pct_24h ?? 0,
                  ),
                  volume_24h: Number(update.volume_24h ?? asset.volume_24h ?? 0),
                  total_volume: Number(update.volume_24h ?? asset.total_volume ?? asset.volume_24h ?? 0),
                }
              : asset,
          ),
        );
      }),
    );

    return () => {
      for (const unsub of unsubs) unsub();
    };
  }, [liveSymbols]);

  useEffect(() => {
    if (selectedSymbol) return;
    if (market.length > 0) {
      setSelectedSymbol(market[0].symbol);
      return;
    }
    const firstHolding = holdings.find((holding) => !holding.stable);
    if (firstHolding) setSelectedSymbol(firstHolding.symbol);
  }, [holdings, market, selectedSymbol]);

  const scannerAssets = useMemo(() => market.slice(0, 18), [market]);
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
        const volatility = riskItem?.volatility ?? Math.abs(Number(asset.change_pct_24h ?? 0)) * 1.4;
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
          price: Number(livePrices[signal.symbol] ?? asset.current_price ?? asset.price ?? 0),
          changePct: Number(asset.price_change_percentage_24h ?? asset.change_pct_24h ?? 0),
          volume: Number(asset.total_volume ?? asset.volume_24h ?? 0),
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
            Math.min(Math.abs(Number(asset.change_pct_24h ?? 0)), 10),
        };
      })
      .filter((opportunity): opportunity is TradeOpportunity => Boolean(opportunity))
      .sort((left, right) => right.edgeScore - left.edgeScore);
  }, [cashValue, holdings, livePrices, marketBySymbol, portfolioValue, riskMetrics, signalMap]);

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

  const monitorEntries = useMemo(
    () => transformHistoryToMonitorEntries(autoHistory),
    [autoHistory],
  );

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

  const portfolioHeadline = portfolios[0]?.name ?? "Primary portfolio";
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
      <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-8">

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

        {/* ============ 2. STATS ROW — flat, no frames ============ */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 md:grid-cols-3 xl:grid-cols-5">
          <DeskMetric label="Equity" value={walletUnlocked ? format(portfolioValue) : "Locked"} sublabel={walletUnlocked ? `${holdings.length} assets` : "Unlock in Settings"} icon={Wallet} />
          <DeskMetric label="Cash" value={walletUnlocked ? format(cashValue) : "Locked"} sublabel={walletUnlocked ? `${portfolioValue > 0 ? ((cashValue / portfolioValue) * 100).toFixed(0) : 0}% deployable` : "Private balances hidden"} icon={ShieldCheck} />
          <DeskMetric label="Open PnL" value={walletUnlocked ? format(openPnl) : "Locked"} sublabel={walletUnlocked ? `${openPnlPct >= 0 ? "+" : ""}${openPnlPct.toFixed(2)}%` : "Execution access required"} icon={openPnl >= 0 ? TrendingUp : TrendingDown} tone={walletUnlocked ? (openPnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]") : undefined} />
          <DeskMetric label="Exposure" value={walletUnlocked ? format(marketExposure) : "Locked"} sublabel={walletUnlocked ? `${positions.length || holdings.filter((h) => !h.stable).length} lines` : "Portfolio data locked"} icon={Target} />
          <DeskMetric label="Risk" value={walletUnlocked ? `${estimatedRisk}/100` : "Locked"} sublabel={walletUnlocked ? riskSummary : "Needs wallet context"} icon={Activity} tone={walletUnlocked ? riskTone(estimatedRisk) : undefined} />
        </div>

        {/* ============ 3. CHART + ASSET DETAIL + TOOLS ============ */}
        <section>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-[var(--foreground)]">{selectedAsset?.symbol ?? selectedSymbol ?? "Select an asset"}</h2>
              {selectedSignal && <SignalBadge action={selectedSignal.action} confidence={selectedSignal.confidence} size="md" blink={tradingMode === "auto" && Boolean(autoStatus?.enabled)} />}
              {selectedAsset && (
                <span className={cn("text-sm font-semibold", Number(selectedAsset.change_pct_24h ?? 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>
                  {Number(selectedAsset.change_pct_24h ?? 0) >= 0 ? "+" : ""}{Number(selectedAsset.change_pct_24h ?? 0).toFixed(2)}%
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold font-mono text-[var(--foreground)]">
                {selectedAsset ? format(livePrices[selectedAsset.symbol] ?? Number(selectedAsset.current_price ?? selectedAsset.price ?? 0), 2) : "--"}
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

          {selectedSignal?.reasoning && (
            <p className="text-[13px] text-[var(--text-secondary)] mb-3 leading-relaxed">{selectedSignal.reasoning}</p>
          )}

          {selectedSymbol ? (
            <PriceChart symbol={selectedSymbol} type={chartType} height={420} showIntervals defaultInterval="1W" />
          ) : (
            <div className="flex h-[420px] items-center justify-center text-sm text-[var(--text-muted)]">Select an asset from the scanner below</div>
          )}

          {/* Indicators + AI context in a row */}
          {(selectedSignal?.indicators?.length || (featuredOpportunity && featuredOpportunity.symbol === selectedSymbol)) && (
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              {/* Indicators */}
              {selectedSignal?.indicators?.length ? (
                <div>
                  <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-2">Indicators</p>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {selectedSignal.indicators.map((indicator) => (
                      <IndicatorBar key={indicator.name} name={indicator.name} value={indicator.value} signal={indicator.signal} description={indicator.description} />
                    ))}
                  </div>
                </div>
              ) : null}
              {/* AI context */}
              {featuredOpportunity && featuredOpportunity.symbol === selectedSymbol && (
                <div>
                  <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-2">AI Sizing</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div><p className="text-[11px] text-[var(--text-muted)]">Size</p><p className="text-sm font-semibold text-[var(--foreground)]">{format(featuredOpportunity.recommendedUsd)}</p></div>
                    <div><p className="text-[11px] text-[var(--text-muted)]">Confidence</p><p className="text-sm font-semibold text-[var(--foreground)]">{Math.round(featuredOpportunity.confidence * 100)}%</p></div>
                    <div><p className="text-[11px] text-[var(--text-muted)]">Risk</p><p className="text-sm font-semibold text-[var(--foreground)]">{featuredOpportunity.riskNote}</p></div>
                    <div><p className="text-[11px] text-[var(--text-muted)]">Edge</p><p className="text-sm font-semibold text-[var(--foreground)]">{featuredOpportunity.edgeScore.toFixed(0)}</p></div>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {/* ============ 4. THREE COLUMNS: Scanner | Opportunities/Auto | Holdings ============ */}
        <div className="grid grid-cols-1 gap-x-8 gap-y-8 lg:grid-cols-12">

          {/* Col 1 (3/12) — Market Scanner */}
          <div className="lg:col-span-3">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-[var(--foreground)]">Scanner</h2>
              <span className="text-[11px] text-[var(--text-muted)]">{signalsLoading ? "..." : `${scannerAssets.length}`}</span>
            </div>
            <div className="space-y-0.5 max-h-[700px] overflow-y-auto custom-scrollbar pr-1">
              {scannerAssets.map((asset) => {
                const signal = signalMap[asset.symbol.toUpperCase()];
                const livePrice = livePrices[asset.symbol.toUpperCase()];
                const assetHolding = holdings.find((h) => h.symbol === asset.symbol);
                return (
                  <div key={asset.symbol} role="button" tabIndex={0}
                    onClick={() => setSelectedSymbol(asset.symbol)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setSelectedSymbol(asset.symbol); }}
                    className={cn("flex items-center justify-between px-2 py-2 rounded-lg cursor-pointer transition-all",
                      selectedSymbol === asset.symbol ? "bg-[var(--glass-bg-strong)]" : "hover:bg-[var(--glass-bg)]")}>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1">
                        <span className="text-[13px] font-semibold text-[var(--foreground)]">{asset.symbol}</span>
                        {assetHolding && <span className="text-[9px] text-[var(--text-muted)]">H</span>}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[11px] font-mono text-[var(--text-secondary)]">{format(livePrice ?? Number(asset.current_price ?? asset.price ?? 0), 2)}</span>
                        <span className={cn("text-[10px] font-semibold", Number(asset.change_pct_24h ?? 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>
                          {Number(asset.change_pct_24h ?? 0) >= 0 ? "+" : ""}{Number(asset.change_pct_24h ?? 0).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                    {signal ? <SignalBadge action={signal.action} confidence={signal.confidence} size="sm" blink={false} />
                      : <span className="text-[9px] text-[var(--text-muted)]">...</span>}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Col 2 (5/12) — Opportunities / Auto Pilot */}
          <div className="lg:col-span-5 space-y-6">
            {tradingMode === "manual" ? (
              <>
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-sm font-semibold text-[var(--foreground)]">Opportunities</h2>
                    <span className="text-[11px] text-[var(--text-muted)]">{opportunities.length} setups</span>
                  </div>
                  {opportunities.length > 0 ? opportunities.slice(0, 6).map((opp) => (
                    <div key={`${opp.symbol}-${opp.action}`} className="py-3 border-b border-white/[0.04] last:border-0">
                      <div className="flex items-start justify-between gap-3 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[14px] font-semibold text-[var(--foreground)]">{opp.symbol}</span>
                          <SignalBadge action={opp.action} confidence={opp.confidence} size="sm" blink={false} />
                        </div>
                        <div className="text-right">
                          <span className="text-[13px] font-semibold text-[var(--foreground)]">{format(opp.recommendedUsd)}</span>
                          <p className="text-[11px] text-[var(--text-muted)]">{Math.round(opp.confidence * 100)}%</p>
                        </div>
                      </div>
                      <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed mb-2">{opp.reasoning}</p>
                      <div className="flex items-center gap-4 text-[12px]">
                        <span className={cn("font-semibold", opp.side === "buy" ? "text-[var(--success)]" : "text-[var(--danger)]")}>{opp.side.toUpperCase()}</span>
                        <span className="text-[var(--text-muted)]">{opp.riskNote}</span>
                        <span className="text-[var(--text-muted)]">{opp.methods.join(" / ")}</span>
                        <button onClick={() => primeOpportunity(opp)}
                          disabled={!walletUnlocked}
                          className={cn("ml-auto font-semibold disabled:opacity-40", opp.side === "buy" ? "text-[var(--success)]" : "text-[var(--danger)]")}>
                          {walletUnlocked ? "Execute" : "Locked"}
                        </button>
                      </div>
                    </div>
                  )) : (
                    <div className="py-6 text-center">
                      <Sparkles className="h-5 w-5 mx-auto mb-2 text-[var(--text-muted)] opacity-30" />
                      <p className="text-[13px] text-[var(--text-muted)]">Le scanner AI analyse les signaux...</p>
                      <p className="text-[11px] text-[var(--text-muted)] mt-1">Les opportunit&eacute;s apparaitront d&egrave;s qu&apos;un setup sera qualifi&eacute;.</p>
                    </div>
                  )}
                </div>
                {/* Execution feed */}
                <div>
                  <h3 className="text-xs font-semibold text-[var(--foreground)] mb-3">Execution Feed</h3>
                  <div className="space-y-1">
                    {executionFeed.slice(0, 6).map((entry) => (
                      <div key={entry.id} className="flex items-center justify-between py-2">
                        <div>
                          <span className="text-[13px] font-semibold text-[var(--foreground)]">
                            {entry.symbol} {entry.side.toUpperCase()}
                          </span>
                          <span className="text-[11px] text-[var(--text-muted)] ml-2">
                            {formatRelative(entry.timestamp)}
                          </span>
                          <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                            {entry.execution_price != null
                              ? `Filled @ ${format(entry.execution_price, 2)}`
                              : entry.requested_price != null
                                ? `Target @ ${format(entry.requested_price, 2)}`
                                : "Awaiting fill"}
                            {entry.fee > 0 ? ` · Fee ${format(entry.fee, 2)}` : ""}
                          </p>
                        </div>
                        <div className="text-right">
                          <span className="text-[12px] font-semibold text-[var(--foreground)]">{entry.status}</span>
                          <span className="text-[11px] text-[var(--text-muted)] ml-2">{entry.quantity.toFixed(6)}</span>
                        </div>
                      </div>
                    ))}
                    {executionFeed.length === 0 && <p className="text-[12px] text-[var(--text-muted)]">No execution activity yet.</p>}
                  </div>
                </div>
              </>
            ) : (
              <>
                {/* ===== AUTO PILOT PANEL ===== */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-sm font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                      <Bot className="h-3.5 w-3.5 accent-text" /> Auto Pilot
                    </h2>
                    <span className={cn("text-[11px] font-semibold", autoStatus?.enabled ? "text-[var(--success)]" : "text-[var(--text-muted)]")}>
                      {autoStatus?.enabled ? "ARMED" : "MONITORING"}
                    </span>
                  </div>

                  {/* AI Status row */}
                  <div className="grid grid-cols-4 gap-3 mb-4">
                    <div><p className="text-[11px] text-[var(--text-muted)]">Last run</p><p className="text-[13px] font-semibold text-[var(--foreground)]">{formatMaybe(autoStatus?.last_run)}</p></div>
                    <div><p className="text-[11px] text-[var(--text-muted)]">Trades</p><p className="text-[13px] font-semibold text-[var(--foreground)]">{autoStatus?.trades_today ?? 0}</p></div>
                    <div><p className="text-[11px] text-[var(--text-muted)]">AI PnL</p><p className={cn("text-[13px] font-semibold", (autoStatus?.total_pnl ?? 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>{format(autoStatus?.total_pnl ?? 0)}</p></div>
                    <div><p className="text-[11px] text-[var(--text-muted)]">Regime</p><p className={cn("text-[13px] font-semibold", regime.tone)}>{regime.label}</p></div>
                  </div>

                  {/* Active Strategies */}
                  <h3 className="text-xs font-semibold text-[var(--foreground)] mb-2">Active Strategies</h3>
                  {activeStrategies.length > 0 ? activeStrategies.map((strat) => (
                    <div key={strat.id} className="py-2.5 border-b border-white/[0.04] last:border-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[13px] font-semibold text-[var(--foreground)]">{strat.name}</span>
                        <span className="text-[11px] font-semibold text-[var(--success)]">active</span>
                      </div>
                      <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed">{strat.description}</p>
                      {strat.performance && (
                        <div className="flex gap-4 mt-1.5 text-[11px] text-[var(--text-muted)]">
                          <span>Win {(strat.performance.win_rate * 100).toFixed(0)}%</span>
                          <span>Sharpe {strat.performance.sharpe_ratio.toFixed(2)}</span>
                        </div>
                      )}
                    </div>
                  )) : <p className="text-[12px] text-[var(--text-muted)] mb-3">No active strategies.</p>}
                </div>

                {/* Decision Ledger — AI thinking/actions log */}
                <div>
                  <h3 className="text-xs font-semibold text-[var(--foreground)] mb-3 flex items-center gap-1.5">
                    <Zap className="h-3 w-3 accent-text" /> Decision Ledger
                  </h3>
                  {decisionLedger.length > 0 ? (
                    <div className="space-y-1 max-h-[400px] overflow-y-auto custom-scrollbar pr-1">
                      {decisionLedger.slice(0, 10).map((entry) => (
                        <div key={entry.id} className="py-2.5 border-b border-white/[0.04] last:border-0">
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                              <span className="text-[13px] font-semibold text-[var(--foreground)]">{entry.symbol}</span>
                              <span className={cn("text-[11px] font-semibold", entry.action.includes("BUY") ? "text-[var(--success)]" : "text-[var(--danger)]")}>{entry.action}</span>
                              <span className="text-[10px] text-[var(--text-muted)]">{entry.strategy}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[12px] font-semibold font-mono text-[var(--foreground)]">{format(entry.amountUsd)}</span>
                              <span className="text-[10px] text-[var(--text-muted)]">{formatRelative(entry.timestamp)}</span>
                            </div>
                          </div>
                          <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed">{entry.analysis}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-6 text-center">
                      <Bot className="h-5 w-5 mx-auto mb-2 text-[var(--text-muted)] opacity-30" />
                      <p className="text-[12px] text-[var(--text-muted)]">Les d&eacute;cisions AI apparaitront ici d&egrave;s que l&apos;autopilote ex&eacute;cutera un cycle.</p>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          {/* Col 3 (4/12) — Holdings + Performance */}
          <div className="lg:col-span-4 space-y-6">
            {/* Holdings */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-semibold text-[var(--foreground)]">Holdings</h2>
                <span className="text-[11px] text-[var(--text-muted)]">{holdings.length} lines</span>
              </div>
              {!walletUnlocked ? (
                <WalletAccessPanel
                  compact
                  title="Holdings stay hidden until you connect your own account"
                  reason="You can still use the scanner, price chart, signals and market regime view in read-only mode."
                />
              ) : (
                <div className="space-y-1.5">
                {holdings.slice(0, 8).map((holding) => (
                  <div key={holding.symbol} className="flex items-center justify-between py-1.5">
                    <div>
                      <p className="text-[13px] font-semibold text-[var(--foreground)]">{holding.symbol}</p>
                      <p className="text-[10px] text-[var(--text-muted)]">{holding.total.toFixed(holding.price >= 1000 ? 4 : 6)}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-[13px] font-semibold text-[var(--foreground)]">{format(holding.value)}</p>
                      <p className={cn("text-[10px]", holding.changePct >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>{holding.changePct >= 0 ? "+" : ""}{holding.changePct.toFixed(2)}%</p>
                    </div>
                  </div>
                ))}
                {holdings.length === 0 && <p className="text-[12px] text-[var(--text-muted)]">No funded balances.</p>}
                </div>
              )}
            </div>

            {/* Performance */}
            <div>
              <h2 className="text-xs font-semibold text-[var(--foreground)] mb-3">Performance</h2>
              {!walletUnlocked ? (
                <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                  <div><p className="text-[11px] text-[var(--text-muted)]">Sharpe</p><p className="text-sm font-semibold text-[var(--foreground)]">Locked</p></div>
                  <div><p className="text-[11px] text-[var(--text-muted)]">Win rate</p><p className="text-sm font-semibold text-[var(--foreground)]">Locked</p></div>
                  <div><p className="text-[11px] text-[var(--text-muted)]">Trades</p><p className="text-sm font-semibold text-[var(--foreground)]">Locked</p></div>
                  <div><p className="text-[11px] text-[var(--text-muted)]">AI PnL</p><p className="text-sm font-semibold text-[var(--foreground)]">Locked</p></div>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                  <div><p className="text-[11px] text-[var(--text-muted)]">Sharpe</p><p className="text-sm font-semibold text-[var(--foreground)]">{analytics ? analytics.sharpe_ratio.toFixed(2) : "--"}</p></div>
                  <div><p className="text-[11px] text-[var(--text-muted)]">Win rate</p><p className="text-sm font-semibold text-[var(--foreground)]">{analytics ? `${(analytics.win_rate * 100).toFixed(0)}%` : "--"}</p></div>
                  <div><p className="text-[11px] text-[var(--text-muted)]">Trades</p><p className="text-sm font-semibold text-[var(--foreground)]">{autoStatus?.trades_today ?? analytics?.total_trades ?? 0}</p></div>
                  <div><p className="text-[11px] text-[var(--text-muted)]">AI PnL</p><p className={cn("text-sm font-semibold", (autoStatus?.total_pnl ?? 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>{format(autoStatus?.total_pnl ?? 0)}</p></div>
                </div>
              )}
            </div>

            {/* Positions */}
            {positions.length > 0 && (
              <div>
                <h2 className="text-xs font-semibold text-[var(--foreground)] mb-3">Open Positions</h2>
                <div className="space-y-1.5">
                  {positions.slice(0, 5).map((pos) => (
                    <div key={pos.id} className="flex items-center justify-between py-1.5">
                      <div>
                        <p className="text-[13px] font-semibold text-[var(--foreground)]">{pos.symbol}</p>
                        <p className="text-[10px] text-[var(--text-muted)]">Entry {format(Number(pos.avg_entry_price ?? 0), 2)}</p>
                      </div>
                      <div className="text-right">
                        <p className={cn("text-[13px] font-semibold", Number(pos.pnl ?? 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>{format(Number(pos.pnl ?? 0))}</p>
                        <p className="text-[10px] text-[var(--text-muted)]">{Number(pos.pnl_pct ?? 0) >= 0 ? "+" : ""}{Number(pos.pnl_pct ?? 0).toFixed(2)}%</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

        </div>

        {/* ============ 5. AI REASONING MONITOR — always visible bottom panel ============ */}
        <AIReasoningMonitor
          entries={monitorEntries}
          loading={loading}
          tradingMode={tradingMode}
          armed={Boolean(autoStatus?.enabled)}
        />
      </div>

      {tradeModalOpen && selectedSymbol ? (
        <QuickTradeModal
          symbol={selectedSymbol}
          price={Number(livePrices[selectedSymbol.toUpperCase()] ?? selectedAsset?.current_price ?? selectedAsset?.price ?? selectedPosition?.current_price ?? 0)}
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
