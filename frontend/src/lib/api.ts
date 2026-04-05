// ============================================================
// Okamoey Trading Platform - API Client
// Binance API via local proxy (primary) + Gateway fallback
// ============================================================

import type {
  MarketOverview,
  CryptoPrice,
  Portfolio,
  Position,
  PortfolioBalanceSnapshot,
  ExecutionFeedItem,
  PortfolioHoldingSnapshot,
  PortfolioSnapshot,
  Transaction,
  Order,
  PaperBalance,
  TradeResult,
  OrderSide,
  OrderType,
  Strategy,
  Signal,
  Alert,
  CreateAlertPayload,
  AnalyticsMetrics,
  EquityPoint,
  StrategyComparison,
  TradingActivity,
  RiskProfile,
  RiskMetrics,
  RiskProfileId,
  SearchResponse,
  AllCryptosResponse,
  OHLCVPoint,
  AIAgent,
  ChatResponse,
  ExchangeConnection,
  ExchangeProviderGuide,
  UserProfile,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";
const BINANCE_PROXY = process.env.NEXT_PUBLIC_BINANCE_PROXY_URL ?? "/binance";
const AI_BASE = process.env.NEXT_PUBLIC_AI_URL ?? "/ai-api/api/v1";

export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(status: number, message: string, detail?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function buildApiError(response: Response, fallbackPrefix: string): Promise<ApiError> {
  let detail = `${fallbackPrefix} ${response.status}`;

  try {
    const payload = (await response.json()) as { detail?: string; message?: string };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      detail = payload.detail;
    } else if (typeof payload.message === "string" && payload.message.trim()) {
      detail = payload.message;
    }
  } catch {
    // Ignore non-JSON error bodies.
  }

  return new ApiError(response.status, detail, detail);
}

// ---- Helpers ----

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function getDemoUser(): UserProfile | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("demo_user");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<UserProfile>;
    return {
      id: parsed.id ?? "demo-001",
      email: parsed.email ?? "demo@okamoey.com",
      username: parsed.username ?? "DemoTrader",
      is_active: true,
      is_verified: true,
      risk_profile: parsed.risk_profile ?? "moderate",
      subscription_plan: parsed.subscription_plan ?? "pro",
      subscription_status: parsed.subscription_status ?? "trial",
      billing_cycle: parsed.billing_cycle ?? "monthly",
      accepted_terms_at: parsed.accepted_terms_at ?? new Date().toISOString(),
      terms_version: parsed.terms_version ?? "2026-04",
      ai_behavior_style: parsed.ai_behavior_style ?? "balanced",
      ai_assistant_tone: parsed.ai_assistant_tone ?? "analytical",
      wallet_access_enabled: parsed.wallet_access_enabled ?? false,
      wallet_access_reason:
        parsed.wallet_access_reason ?? "Demo mode does not expose private wallet data.",
      connected_exchanges_count: parsed.connected_exchanges_count ?? 0,
      live_trading_enabled: parsed.live_trading_enabled ?? false,
      created_at: parsed.created_at ?? new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

function buildHeaders(initHeaders?: HeadersInit): Headers {
  const headers = new Headers(initHeaders);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

// ---- Token refresh logic ----

let _refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken || refreshToken === "demo-refresh") return false;

  // Deduplicate concurrent refresh calls
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) return false;
      const data = (await res.json()) as {
        access_token: string;
        refresh_token: string;
      };
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch(`${API_BASE}${url}`, {
      headers: buildHeaders(init?.headers),
      ...init,
      signal: controller.signal,
    });

    // Auto-refresh on 401 (expired access token)
    if (res.status === 401 && !url.includes("/auth/login") && !url.includes("/auth/register")) {
      const refreshed = await tryRefreshToken();
      if (refreshed) {
        // Retry the original request with the new token
        const retryRes = await fetch(`${API_BASE}${url}`, {
          headers: buildHeaders(init?.headers),
          ...init,
          signal: controller.signal,
        });
        if (!retryRes.ok) throw await buildApiError(retryRes, "API");
        return retryRes.json() as Promise<T>;
      }
      // Refresh failed — clear tokens and redirect to login
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      }
    }

    if (!res.ok) throw await buildApiError(res, "API");
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchBinance<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch(`${BINANCE_PROXY}${path}`, {
      headers: buildHeaders(init?.headers),
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) throw await buildApiError(res, "Binance");
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchAI<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  // AI calls (especially GPT-4o analysis) can take 15-30s
  const timeout = setTimeout(() => controller.abort(), 60000);
  try {
    const res = await fetch(`${AI_BASE}${url}`, {
      headers: buildHeaders(init?.headers),
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) throw await buildApiError(res, "AI API");
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

// ---- Binance data helpers ----

interface BinanceTicker {
  symbol: string;
  priceChange: string;
  priceChangePercent: string;
  lastPrice: string;
  highPrice: string;
  lowPrice: string;
  volume: string;
  quoteVolume: string;
}

interface BinanceBalance {
  asset: string;
  free: number;
  locked: number;
}

interface BackendOrderResponse {
  id: string;
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  status: Order["status"];
  quantity: string;
  filled_quantity: string;
  price?: string | null;
  filled_price?: string | null;
  stop_price?: string | null;
  fee: string;
  created_at: string;
  updated_at: string;
}

interface BackendOrderListResponse {
  orders: BackendOrderResponse[];
  total: number;
  limit: number;
  offset: number;
}

interface BackendMultiPriceResponse {
  success: boolean;
  data: Record<string, CryptoPrice>;
}

interface BackendSinglePriceResponse {
  success: boolean;
  data: CryptoPrice;
}

interface BackendHistoryPoint {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface BackendHistoryResponse {
  success: boolean;
  symbol: string;
  interval: string;
  data: BackendHistoryPoint[];
}

interface BackendFearGreedResponse {
  success: boolean;
  data: {
    value: number;
    classification: string;
  };
}

interface BackendMarketListingResponse {
  success: boolean;
  data: Array<{
    id: string;
    symbol: string;
    name: string;
    image?: string | null;
    current_price?: number | null;
    market_cap?: number | null;
    market_cap_rank?: number | null;
    price_change_percentage_24h?: number | null;
    total_volume?: number | null;
    sparkline_in_7d?: number[] | null;
    high_24h?: number | null;
    low_24h?: number | null;
  }>;
  page: number;
  limit: number;
  total: number;
}

interface BackendSearchResponse {
  success: boolean;
  query: string;
  results: Array<{
    symbol: string;
    name: string;
  }>;
  total: number;
}

interface BackendPortfolio {
  id: string;
  user_id: string;
  name: string;
  description?: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

interface BackendPosition {
  id: string;
  portfolio_id: string;
  symbol: string;
  asset_type: "crypto" | "stock" | "etf";
  exchange?: string | null;
  quantity: string | number;
  average_entry_price: string | number;
  current_price: string | number;
  unrealized_pnl: string | number;
  realized_pnl: string | number;
  stop_loss_price?: string | number | null;
  take_profit_price?: string | number | null;
  opened_at: string;
  updated_at: string;
}

interface BackendTransaction {
  id: string;
  portfolio_id: string;
  position_id?: string | null;
  symbol: string;
  side: "buy" | "sell";
  quantity: string | number;
  price: string | number;
  fee: string | number;
  exchange?: string | null;
  order_id?: string | null;
  strategy?: string | null;
  notes?: string | null;
  executed_at: string;
}

interface BackendPortfolioSnapshot {
  updated_at: string;
  portfolio?: BackendPortfolio | null;
  portfolios: BackendPortfolio[];
  balances: Array<{
    currency: string;
    available: string | number;
    reserved: string | number;
    total: string | number;
  }>;
  holdings: Array<{
    symbol: string;
    available: string | number;
    reserved: string | number;
    total: string | number;
    price: string | number;
    value: string | number;
    change_pct_24h: string | number;
    stable: boolean;
  }>;
  positions: BackendPosition[];
  recent_transactions: BackendTransaction[];
  execution_feed: Array<{
    id: string;
    source: "order" | "transaction" | "execution";
    order_id?: string | null;
    transaction_id?: string | null;
    portfolio_id?: string | null;
    symbol: string;
    side: "buy" | "sell";
    status: string;
    quantity: string | number;
    filled_quantity: string | number;
    requested_price?: string | number | null;
    execution_price?: string | number | null;
    notional: string | number;
    fee: string | number;
    exchange?: string | null;
    strategy?: string | null;
    notes?: string | null;
    timestamp: string;
    updated_at?: string | null;
  }>;
  summary: {
    equity: string | number;
    cash: string | number;
    market_exposure: string | number;
    open_pnl: string | number;
    open_pnl_pct: string | number;
    day_change_value: string | number;
    day_change_pct: string | number;
    holdings_count: number;
    positions_count: number;
    open_orders_count: number;
  };
  risk?: BackendRiskMetrics | null;
}

interface BackendPositionRisk {
  symbol: string;
  value: string | number;
  weight: string | number;
  var_contribution: string | number;
  volatility: string | number;
  risk_score: string | number;
}

interface BackendRiskMetrics {
  total_value: string | number;
  risk_score: string | number;
  daily_var: string | number;
  var_pct: string | number;
  max_drawdown: string | number;
  max_drawdown_pct: string | number;
  sharpe_ratio?: string | number | null;
  volatility: string | number;
  correlation_risk: RiskMetrics["correlation_risk"];
  risk_level: RiskMetrics["risk_level"];
  concentration_pct: string | number;
  cash_ratio: string | number;
  warnings?: string[];
  position_risk?: BackendPositionRisk[];
}

interface BackendRiskProfile {
  profile_id: RiskProfileId;
  max_position_size_pct: string | number;
  max_portfolio_drawdown_pct: string | number;
  default_stop_loss_pct: string | number;
  default_take_profit_pct: string | number;
  max_daily_trades: number;
  max_leverage: string | number;
  risk_per_trade_pct: string | number;
}

function toNumber(value: string | number | null | undefined): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") return Number.parseFloat(value);
  return 0;
}

function normalizeRiskMetrics(metrics: BackendRiskMetrics): RiskMetrics {
  return {
    total_value: toNumber(metrics.total_value),
    risk_score: toNumber(metrics.risk_score),
    daily_var: toNumber(metrics.daily_var),
    var_pct: toNumber(metrics.var_pct),
    max_drawdown: toNumber(metrics.max_drawdown),
    max_drawdown_pct: toNumber(metrics.max_drawdown_pct),
    sharpe_ratio: metrics.sharpe_ratio != null ? toNumber(metrics.sharpe_ratio) : null,
    volatility: toNumber(metrics.volatility),
    correlation_risk: metrics.correlation_risk,
    risk_level: metrics.risk_level,
    concentration_pct: toNumber(metrics.concentration_pct),
    cash_ratio: toNumber(metrics.cash_ratio),
    warnings: metrics.warnings ?? [],
    position_risk: (metrics.position_risk ?? []).map((item) => ({
      symbol: item.symbol.toUpperCase(),
      value: toNumber(item.value),
      weight: toNumber(item.weight),
      var_contribution: toNumber(item.var_contribution),
      volatility: toNumber(item.volatility),
      risk_score: toNumber(item.risk_score),
    })),
  };
}

function normalizeRiskProfile(profile: BackendRiskProfile): RiskProfile {
  return {
    profile_id: profile.profile_id,
    max_position_size_pct: toNumber(profile.max_position_size_pct),
    max_portfolio_drawdown_pct: toNumber(profile.max_portfolio_drawdown_pct),
    default_stop_loss_pct: toNumber(profile.default_stop_loss_pct),
    default_take_profit_pct: toNumber(profile.default_take_profit_pct),
    max_daily_trades: Number(profile.max_daily_trades ?? 0),
    max_leverage: toNumber(profile.max_leverage),
    risk_per_trade_pct: toNumber(profile.risk_per_trade_pct),
  };
}

// In-memory cache to avoid hammering Binance on every page nav
let _tickerCache: { data: BinanceTicker[]; ts: number } | null = null;
const TICKER_CACHE_MS = 10000; // 10s cache
const DEFAULT_PRICE_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"];

function normalizeHistoryPoint(point: BackendHistoryPoint): OHLCVPoint {
  return {
    time: Math.floor(Number(point.timestamp) / 1000),
    open: Number(point.open),
    high: Number(point.high),
    low: Number(point.low),
    close: Number(point.close),
    volume: Number(point.volume),
  };
}

function normalizeKlineRow(row: number[]): OHLCVPoint {
  return {
    time: Math.floor(Number(row[0]) / 1000),
    open: parseFloat(String(row[1])),
    high: parseFloat(String(row[2])),
    low: parseFloat(String(row[3])),
    close: parseFloat(String(row[4])),
    volume: parseFloat(String(row[5])),
  };
}

function normalizeBackendCrypto(coin: BackendMarketListingResponse["data"][number], index: number) {
  const symbol = coin.symbol.toUpperCase();
  const price = Number(coin.current_price ?? 0);
  const changePct = Number(coin.price_change_percentage_24h ?? 0);
  return {
    id: coin.id,
    symbol,
    name: coin.name || symbol,
    price,
    change_24h: 0,
    change_pct_24h: changePct,
    volume_24h: Number(coin.total_volume ?? 0),
    market_cap: Number(coin.market_cap ?? 0),
    rank: coin.market_cap_rank ?? index + 1,
    image: coin.image ?? "",
    current_price: price,
    market_cap_rank: coin.market_cap_rank ?? index + 1,
    price_change_percentage_24h: changePct,
    total_volume: Number(coin.total_volume ?? 0),
    sparkline_in_7d: coin.sparkline_in_7d ?? null,
    high_24h: Number(coin.high_24h ?? 0),
    low_24h: Number(coin.low_24h ?? 0),
  };
}

function mapPriceRecordToArray(data: Record<string, CryptoPrice>): CryptoPrice[] {
  return Object.values(data).map((item) => ({
    ...item,
    symbol: item.symbol.toUpperCase(),
  }));
}

function normalizeOrder(order: BackendOrderResponse): Order {
  return {
    id: order.id,
    symbol: order.symbol,
    side: order.side,
    order_type: order.order_type,
    quantity: Number(order.quantity),
    price: order.price != null ? Number(order.price) : undefined,
    stop_price: order.stop_price != null ? Number(order.stop_price) : undefined,
    filled_price: order.filled_price != null ? Number(order.filled_price) : undefined,
    status: order.status,
    fee: Number(order.fee),
    created_at: order.created_at,
    filled_at: order.updated_at,
  };
}

function normalizePortfolio(portfolio: BackendPortfolio): Portfolio {
  return {
    id: portfolio.id,
    name: portfolio.name,
    description: portfolio.description ?? undefined,
    total_value: 0,
    total_pnl: 0,
    total_pnl_pct: 0,
    positions: [],
    created_at: portfolio.created_at,
    updated_at: portfolio.updated_at,
  };
}

function normalizePosition(position: BackendPosition): Position {
  const qty = toNumber(position.quantity);
  const avgEntry = toNumber(position.average_entry_price);
  const currentPrice = toNumber(position.current_price);
  const pnl = toNumber(position.unrealized_pnl);
  const costBasis = qty * avgEntry;
  const pnlPct = costBasis > 0 ? (pnl / costBasis) * 100 : 0;
  return {
    id: position.id,
    portfolio_id: position.portfolio_id,
    symbol: position.symbol.toUpperCase(),
    asset_type: position.asset_type,
    quantity: qty,
    avg_entry_price: avgEntry,
    current_price: currentPrice,
    pnl,
    pnl_pct: pnlPct,
    stop_loss: position.stop_loss_price != null ? toNumber(position.stop_loss_price) : undefined,
    take_profit: position.take_profit_price != null ? toNumber(position.take_profit_price) : undefined,
    created_at: position.opened_at,
  };
}

function normalizeTransaction(transaction: BackendTransaction): Transaction {
  const quantity = toNumber(transaction.quantity);
  const price = toNumber(transaction.price);
  return {
    id: transaction.id,
    portfolio_id: transaction.portfolio_id,
    symbol: transaction.symbol.toUpperCase(),
    side: transaction.side,
    quantity,
    price,
    total: quantity * price,
    fee: toNumber(transaction.fee),
    timestamp: transaction.executed_at,
  };
}

function normalizePortfolioSnapshot(snapshot: BackendPortfolioSnapshot): PortfolioSnapshot {
  return {
    updated_at: snapshot.updated_at,
    portfolio: snapshot.portfolio ? normalizePortfolio(snapshot.portfolio) : null,
    portfolios: snapshot.portfolios.map(normalizePortfolio),
    balances: snapshot.balances.map((balance): PortfolioBalanceSnapshot => ({
      currency: balance.currency.toUpperCase(),
      available: toNumber(balance.available),
      reserved: toNumber(balance.reserved),
      total: toNumber(balance.total),
    })),
    holdings: snapshot.holdings.map((holding): PortfolioHoldingSnapshot => ({
      symbol: holding.symbol.toUpperCase(),
      available: toNumber(holding.available),
      reserved: toNumber(holding.reserved),
      total: toNumber(holding.total),
      price: toNumber(holding.price),
      value: toNumber(holding.value),
      change_pct_24h: toNumber(holding.change_pct_24h),
      stable: holding.stable,
    })),
    positions: snapshot.positions.map(normalizePosition),
    recent_transactions: snapshot.recent_transactions.map(normalizeTransaction),
    execution_feed: snapshot.execution_feed.map((item): ExecutionFeedItem => ({
      id: item.id,
      source: item.source,
      order_id: item.order_id ?? null,
      transaction_id: item.transaction_id ?? null,
      portfolio_id: item.portfolio_id ?? null,
      symbol: item.symbol.toUpperCase(),
      side: item.side,
      status: item.status,
      quantity: toNumber(item.quantity),
      filled_quantity: toNumber(item.filled_quantity),
      requested_price: item.requested_price != null ? toNumber(item.requested_price) : null,
      execution_price: item.execution_price != null ? toNumber(item.execution_price) : null,
      notional: toNumber(item.notional),
      fee: toNumber(item.fee),
      exchange: item.exchange ?? null,
      strategy: item.strategy ?? null,
      notes: item.notes ?? null,
      timestamp: item.timestamp,
      updated_at: item.updated_at ?? null,
    })),
    summary: {
      equity: toNumber(snapshot.summary.equity),
      cash: toNumber(snapshot.summary.cash),
      market_exposure: toNumber(snapshot.summary.market_exposure),
      open_pnl: toNumber(snapshot.summary.open_pnl),
      open_pnl_pct: toNumber(snapshot.summary.open_pnl_pct),
      day_change_value: toNumber(snapshot.summary.day_change_value),
      day_change_pct: toNumber(snapshot.summary.day_change_pct),
      holdings_count: Number(snapshot.summary.holdings_count ?? 0),
      positions_count: Number(snapshot.summary.positions_count ?? 0),
      open_orders_count: Number(snapshot.summary.open_orders_count ?? 0),
    },
    risk: snapshot.risk ? normalizeRiskMetrics(snapshot.risk) : null,
  };
}

async function getAllTickers(): Promise<BinanceTicker[]> {
  if (_tickerCache && Date.now() - _tickerCache.ts < TICKER_CACHE_MS) {
    return _tickerCache.data;
  }
  try {
    const data = await fetchBinance<BinanceTicker[]>("/ticker24h");
    // Filter to USDT pairs only
    const usdt = data.filter((t) => t.symbol.endsWith("USDT"));
    _tickerCache = { data: usdt, ts: Date.now() };
    return usdt;
  } catch {
    return _tickerCache?.data ?? [];
  }
}

// ---- Prices / Market Data (ALL from Binance) ----

export const pricesApi = {
  getAllCryptos: async (limit = 250): Promise<AllCryptosResponse> => {
    try {
      const tickers = await getAllTickers();
      if (tickers.length > 0) {
        const sorted = [...tickers]
          .sort((a, b) => parseFloat(b.quoteVolume) - parseFloat(a.quoteVolume))
          .slice(0, limit);

        return {
          data: sorted.map((t, i) => {
            const sym = t.symbol.replace("USDT", "");
            return {
              symbol: sym,
              name: sym,
              price: parseFloat(t.lastPrice),
              change_24h: parseFloat(t.priceChange),
              change_pct_24h: parseFloat(t.priceChangePercent),
              volume_24h: parseFloat(t.quoteVolume),
              market_cap: 0,
              rank: i + 1,
              id: sym.toLowerCase(),
              image: "",
              current_price: parseFloat(t.lastPrice),
              market_cap_rank: i + 1,
              price_change_percentage_24h: parseFloat(t.priceChangePercent),
              total_volume: parseFloat(t.quoteVolume),
              sparkline_in_7d: null,
              high_24h: parseFloat(t.highPrice),
              low_24h: parseFloat(t.lowPrice),
            };
          }),
          total: sorted.length,
          page: 1,
          limit,
        };
      }
    } catch {
      // Gateway fallback below
    }

    const backend = await fetchJson<BackendMarketListingResponse>(`/markets/all?limit=${limit}&page=1`);
    return {
      data: backend.data.map((coin, index) => normalizeBackendCrypto(coin, index)),
      total: backend.total,
      page: backend.page,
      limit: backend.limit,
    };
  },

  getOHLCV: async (symbol: string, interval = "1d", limit = 90): Promise<OHLCVPoint[]> => {
    try {
      const response = await fetchJson<BackendHistoryResponse>(
        `/prices/history/${symbol.toUpperCase()}?interval=${encodeURIComponent(interval)}&limit=${limit}`,
      );
      return response.data.map(normalizeHistoryPoint);
    } catch {
      try {
        const pair = `${symbol.toUpperCase()}USDT`;
        const data = await fetchBinance<number[][]>(`/klines?symbol=${pair}&interval=${interval}&limit=${limit}`);
        return data.map(normalizeKlineRow);
      } catch {
        return [];
      }
    }
  },

  getFearGreed: async (): Promise<{ value: number; label: string }> => {
    try {
      const response = await fetchJson<BackendFearGreedResponse>("/markets/fear-greed");
      return {
        value: Number(response.data.value ?? 50),
        label: String(response.data.classification ?? "Neutral"),
      };
    } catch {
      try {
        const r = await fetch("https://api.alternative.me/fng/?limit=1&format=json");
        const d = await r.json();
        const e = d?.data?.[0];
        return { value: Number(e?.value ?? 50), label: String(e?.value_classification ?? "Neutral") };
      } catch {
        return { value: 50, label: "Neutral" };
      }
    }
  },

  searchAssets: async (query: string): Promise<SearchResponse> => {
    const trimmed = query.trim();
    if (!trimmed) return { results: [], total: 0 };

    try {
      const response = await fetchJson<BackendSearchResponse>(
        `/prices/search?q=${encodeURIComponent(trimmed)}&limit=20`,
      );
      return {
        results: response.results.map((item) => ({
          symbol: item.symbol.toUpperCase(),
          name: item.name,
          asset_type: "crypto" as const,
        })),
        total: response.total,
      };
    } catch {
      const tickers = await getAllTickers();
      const q = trimmed.toUpperCase();
      const matches = tickers
        .filter((t) => t.symbol.replace("USDT", "").includes(q))
        .slice(0, 20)
        .map((t) => ({
          symbol: t.symbol.replace("USDT", ""),
          name: t.symbol.replace("USDT", ""),
          asset_type: "crypto" as const,
        }));
      return { results: matches, total: matches.length };
    }
  },

  getOverview: async (): Promise<MarketOverview> => {
    const [crypto, fearGreed] = await Promise.all([
      pricesApi.getAllCryptos(10),
      pricesApi.getFearGreed(),
    ]);
    const totalMarketCap = crypto.data.reduce(
      (sum, item) => sum + Number(item.market_cap ?? 0),
      0,
    );
    const btcMarketCap =
      crypto.data.find((item) => item.symbol.toUpperCase() === "BTC")?.market_cap ?? 0;
    return {
      crypto: crypto.data,
      stocks: [],
      fear_greed_index: fearGreed.value,
      fear_greed_label: fearGreed.label,
      total_market_cap: totalMarketCap,
      btc_dominance: totalMarketCap > 0 ? (btcMarketCap / totalMarketCap) * 100 : 0,
    };
  },
  getCrypto: async (): Promise<CryptoPrice[]> => {
    const response = await fetchJson<BackendMultiPriceResponse>(
      `/prices?symbols=${DEFAULT_PRICE_SYMBOLS.join(",")}`,
    );
    return mapPriceRecordToArray(response.data);
  },
  getCryptoBySymbol: async (symbol: string): Promise<CryptoPrice> => {
    const response = await fetchJson<BackendSinglePriceResponse>(
      `/prices/${symbol.toUpperCase()}`,
    );
    return {
      ...response.data,
      symbol: response.data.symbol.toUpperCase(),
    };
  },
  getStocks: async (): Promise<CryptoPrice[]> => [],
};

// ---- Binance Account ----

export const binanceApi = {
  getBalances: () => fetchBinance<BinanceBalance[]>("/balances"),
  getAccount: () => fetchBinance<Record<string, unknown>>("/account"),
  getTicker: (symbol: string) => fetchBinance<Record<string, string>>(`/ticker?symbol=${symbol}USDT`),
  placeOrder: (params: { symbol: string; side: string; type: string; quantity?: string; quoteOrderQty?: string }) =>
    fetchBinance<Record<string, unknown>>("/order", { method: "POST", body: JSON.stringify(params) }),
  getOpenOrders: (symbol?: string) => fetchBinance<unknown[]>(`/orders${symbol ? `?symbol=${symbol}` : ""}`),
  getMyTrades: (symbol: string) => fetchBinance<unknown[]>(`/trades?symbol=${symbol}USDT`),
  health: () => fetchBinance<{ status: string; connected: boolean }>("/health"),
};

// ---- Portfolio ----

export const portfolioApi = {
  list: async () => {
    const portfolios = await fetchJson<BackendPortfolio[]>("/portfolios");
    return portfolios.map(normalizePortfolio);
  },
  get: async (id: string) => {
    const portfolio = await fetchJson<BackendPortfolio>(`/portfolios/${id}`);
    return normalizePortfolio(portfolio);
  },
  create: (data: { name: string; description?: string }) =>
    fetchJson<BackendPortfolio>("/portfolios", { method: "POST", body: JSON.stringify(data) }).then(normalizePortfolio),
  getPositions: async (portfolioId: string) => {
    const positions = await fetchJson<BackendPosition[]>(`/positions?portfolio_id=${encodeURIComponent(portfolioId)}`);
    return positions.map(normalizePosition);
  },
  getTransactions: async () => [],
  getSnapshot: async () => {
    const snapshot = await fetchJson<BackendPortfolioSnapshot>("/portfolios/snapshot");
    return normalizePortfolioSnapshot(snapshot);
  },
  closePosition: (positionId: string) => fetchJson<TradeResult>(`/positions/${positionId}/close`, { method: "POST" }),
  updateStopLoss: (positionId: string, stopLoss: number) =>
    fetchJson<BackendPosition>(`/positions/${positionId}`, { method: "PATCH", body: JSON.stringify({ stop_loss: stopLoss }) }).then(normalizePosition),
};

// ---- Trading ----

export const tradingApi = {
  getBalances: async (): Promise<PaperBalance[]> => {
    try {
      const balances = await fetchJson<Record<string, string>>("/orders/balance");
      return Object.entries(balances).map(([currency, total]) => ({
        currency,
        available: Number(total),
        reserved: 0,
        total: Number(total),
      }));
    } catch {
      try {
        const balances = await binanceApi.getBalances();
        return balances.map((b) => ({
          currency: b.asset,
          available: b.free,
          reserved: b.locked,
          total: b.free + b.locked,
        }));
      } catch {
        return [];
      }
    }
  },

  placeOrder: async (data: {
    symbol: string; side: OrderSide; order_type: OrderType; quantity: number; price?: number;
  }): Promise<TradeResult> => {
    const result = await fetchJson<BackendOrderResponse>("/orders", {
      method: "POST",
      body: JSON.stringify({
        symbol: data.symbol,
        side: data.side,
        order_type: data.order_type,
        quantity: data.quantity,
        price: data.price,
      }),
    });
    return {
      order_id: result.id,
      status: result.status,
      filled_price: result.filled_price != null ? Number(result.filled_price) : undefined,
      filled_quantity: Number(result.filled_quantity),
      fee: Number(result.fee),
      message: `Order ${result.status}`,
    };
  },

  getOrders: async (): Promise<Order[]> => {
    try {
      const response = await fetchJson<BackendOrderListResponse>("/orders");
      return response.orders.map(normalizeOrder);
    } catch {
      return [];
    }
  },

  cancelOrder: (orderId: string) =>
    fetchJson<BackendOrderResponse>(`/orders/${orderId}`, { method: "DELETE" }),
};

// ---- Signals (computed from Binance klines) ----

interface SignalData {
  symbol: string;
  action: string;
  confidence: number;
  score: number;
  reasoning: string;
  indicators: Array<{ name: string; value: number; signal: number; description: string }>;
  timestamp: string;
}

async function computeSignal(symbol: string): Promise<SignalData> {
  const closes: number[] = [];
  try {
    const klines = await pricesApi.getOHLCV(symbol, "1h", 100);
    for (const k of klines) closes.push(k.close);
  } catch { /* empty */ }

  if (closes.length < 15) {
    return { symbol, action: "HOLD", confidence: 0, score: 0, reasoning: "Insufficient data", indicators: [], timestamp: new Date().toISOString() };
  }

  // RSI
  const gains: number[] = []; const losses: number[] = [];
  for (let i = 1; i < closes.length; i++) { const d = closes[i] - closes[i-1]; gains.push(Math.max(d,0)); losses.push(Math.max(-d,0)); }
  const p = 14;
  const avgG = gains.slice(-p).reduce((a,b)=>a+b,0)/p;
  const avgL = losses.slice(-p).reduce((a,b)=>a+b,0)/p;
  const rsi = avgL === 0 ? 100 : 100 - 100/(1 + avgG/avgL);
  const rsiSig = rsi < 30 ? 0.7 : rsi < 45 ? 0.3 : rsi > 70 ? -0.7 : rsi > 55 ? -0.3 : 0;

  // EMA cross
  const ema = (arr: number[], n: number) => { const k=2/(n+1); const r=[arr[0]]; for(let i=1;i<arr.length;i++) r.push(arr[i]*k+r[i-1]*(1-k)); return r; };
  const e9 = ema(closes, 9); const e21 = ema(closes, 21);
  const ed = e9[e9.length-1] - e21[e21.length-1];
  const pd = e9[e9.length-2] - e21[e21.length-2];
  const emaSig = (ed > 0 && pd <= 0) ? 0.7 : (ed < 0 && pd >= 0) ? -0.7 : ed > 0 ? 0.3 : ed < 0 ? -0.3 : 0;

  // Bollinger
  const s20 = closes.slice(-20); const mean = s20.reduce((a,b)=>a+b,0)/20;
  const std = Math.sqrt(s20.reduce((a,b)=>a+(b-mean)**2,0)/20);
  const upper = mean+2*std; const lower = mean-2*std;
  const pos = (upper-lower) === 0 ? 0.5 : (closes[closes.length-1]-lower)/(upper-lower);
  const bbSig = pos < 0.2 ? 0.6 : pos < 0.4 ? 0.2 : pos > 0.8 ? -0.6 : pos > 0.6 ? -0.2 : 0;

  const score = (rsiSig*1.2 + emaSig*1.1 + bbSig*1.0) / 3.3;
  const action = score > 0.5 ? "STRONG_BUY" : score > 0.25 ? "BUY" : score > 0.08 ? "ACCUMULATE" : score > -0.08 ? "HOLD" : score > -0.25 ? "REDUCE" : score > -0.5 ? "SELL" : "STRONG_SELL";

  return {
    symbol: symbol.toUpperCase(),
    action,
    confidence: Math.min(Math.abs(score), 1),
    score: Math.round(score * 1000) / 1000,
    reasoning: `RSI=${rsi.toFixed(0)}, EMA${ed>0?"+":"-"}, BB${pos<0.3?"low":pos>0.7?"high":"mid"}`,
    indicators: [
      { name: "RSI", value: Math.round(rsi), signal: rsiSig, description: `RSI ${rsi.toFixed(0)} — ${rsi<30?"Oversold":rsi>70?"Overbought":"Neutral"}` },
      { name: "EMA Cross", value: Math.round(ed*100)/100, signal: emaSig, description: `EMA 9/21 ${ed>0?"bullish":"bearish"}` },
      { name: "Bollinger", value: Math.round(pos*100)/100, signal: bbSig, description: `Price at ${(pos*100).toFixed(0)}% of bands` },
    ],
    timestamp: new Date().toISOString(),
  };
}

export const signalsApi = {
  getSignal: (symbol: string) => computeSignal(symbol),
  getAllSignals: async () => {
    const syms = ["BTC","ETH","SOL","BNB","XRP","ADA","DOGE","AVAX","DOT","LINK"];
    const results = await Promise.allSettled(syms.map(s => computeSignal(s)));
    return results.filter((r): r is PromiseFulfilledResult<SignalData> => r.status === "fulfilled").map(r => r.value);
  },
};

// ---- Strategies ----

export const strategiesApi = {
  list: () => fetchJson<Strategy[]>("/strategies"),
  get: (id: string) => fetchJson<Strategy>(`/strategies/${id}`),
  generateSignal: (strategyId: string, symbol: string) =>
    fetchJson<Signal>(`/strategies/${strategyId}/signal`, { method: "POST", body: JSON.stringify({ symbol }) }),
  updateParams: (strategyId: string, params: Record<string, unknown>) =>
    fetchJson<Strategy>(`/strategies/${strategyId}`, { method: "PATCH", body: JSON.stringify({ parameters: params }) }),
};

// ---- Alerts ----

export const alertsApi = {
  list: () => fetchJson<Alert[]>("/alerts"),
  create: (data: CreateAlertPayload) => fetchJson<Alert>("/alerts", { method: "POST", body: JSON.stringify(data) }),
  delete: (id: string) => fetchJson<{ success: boolean }>(`/alerts/${id}`, { method: "DELETE" }),
};

// ---- Auth / User ----

export const authApi = {
  getMe: async () => {
    const token = getAccessToken();
    if (token === "demo-token") {
      const demo = getDemoUser();
      if (demo) return demo;
    }
    return fetchJson<UserProfile>("/auth/me");
  },
  updateMe: (
    data: Partial<
      Pick<
        UserProfile,
        | "username"
        | "risk_profile"
        | "subscription_plan"
        | "billing_cycle"
        | "ai_behavior_style"
        | "ai_assistant_tone"
      >
    > & { telegram_chat_id?: string | null },
  ) => fetchJson<UserProfile>("/auth/me", { method: "PUT", body: JSON.stringify(data) }),
  acceptTerms: (termsVersion = "2026-04") =>
    fetchJson<UserProfile>("/auth/me/accept-terms", {
      method: "POST",
      body: JSON.stringify({ terms_version: termsVersion }),
    }),
  getExchangeProviders: () => fetchJson<ExchangeProviderGuide[]>("/auth/exchange-providers"),
  listExchangeConnections: () => fetchJson<ExchangeConnection[]>("/auth/me/exchange-connections"),
  createExchangeConnection: (data: {
    provider: string;
    label?: string;
    api_key: string;
    api_secret: string;
    passphrase?: string;
    sandbox_mode?: boolean;
    can_trade?: boolean;
  }) => fetchJson<ExchangeConnection>("/auth/me/exchange-connections", {
    method: "POST",
    body: JSON.stringify(data),
  }),
  deleteExchangeConnection: (id: string) =>
    fetchJson<{ message: string }>(`/auth/me/exchange-connections/${id}`, { method: "DELETE" }),
};

// ---- Risk ----

export const riskApi = {
  getProfile: async () => {
    const profile = await fetchJson<BackendRiskProfile>("/risk/profile");
    return normalizeRiskProfile(profile);
  },
  setProfilePreset: async (preset: Exclude<RiskProfileId, "custom">) => {
    const profile = await fetchJson<BackendRiskProfile>(`/risk/profile/preset/${preset}`, { method: "PUT" });
    return normalizeRiskProfile(profile);
  },
  updateProfile: async (profile: RiskProfile) => {
    const result = await fetchJson<BackendRiskProfile>("/risk/profile", {
      method: "PUT",
      body: JSON.stringify(profile),
    });
    return normalizeRiskProfile(result);
  },
  getMetrics: async () => {
    const metrics = await fetchJson<BackendRiskMetrics>("/risk/metrics");
    return normalizeRiskMetrics(metrics);
  },
};

// ---- AI Agents ----

export const aiApi = {
  getAgents: () => fetchAI<AIAgent[]>("/ai/agents"),
  chat: (message: string, agentType: string, userId = "default") =>
    fetchAI<ChatResponse>("/ai/chat", { method: "POST", body: JSON.stringify({ message, agent_type: agentType, user_id: userId }) }),
  clearChat: (agentType: string, userId = "default") =>
    fetchAI<{ status: string }>("/ai/chat/clear", { method: "POST", body: JSON.stringify({ agent_type: agentType, user_id: userId }) }),
  getAutoTradingStatus: () =>
    fetchAI<{ enabled: boolean; last_run: string | null; trades_today: number; total_pnl: number }>("/ai/auto-trading/status"),
  toggleAutoTrading: (enabled: boolean) =>
    fetchAI<{ enabled: boolean }>("/ai/auto-trading/toggle", { method: "POST", body: JSON.stringify({ enabled }) }),
  getAutoTradingHistory: () =>
    fetchAI<Array<{
      timestamp: string;
      analysis: string;
      executed: number;
      trades: Array<{
        symbol: string;
        action: string;
        amount_usd: number;
        confidence?: number;
        reason?: string;
        regime?: string;
        strategy?: string;
        price?: number;
      }>;
      recommendations?: number;
      provider?: string | null;
      model?: string | null;
      regime?: string;
      signals_scanned?: number;
      candidates?: Array<{
        symbol: string;
        action: string;
        confidence: number;
        regime?: string | null;
        price?: number | null;
      }>;
    }>>("/ai/auto-trading/history"),
  analyzePerformance: (metrics: Record<string, unknown>) =>
    fetchAI<{ analysis: string; provider: string; model: string }>("/ai/analyze-performance", { method: "POST", body: JSON.stringify({ metrics }) }),
};

// ---- Analytics ----

export const analyticsApi = {
  getMetrics: () => fetchJson<AnalyticsMetrics>("/risk/analytics/metrics"),
  getEquityCurve: () => fetchJson<EquityPoint[]>("/risk/analytics/equity"),
  getStrategyComparison: () => fetchJson<StrategyComparison[]>("/risk/analytics/strategies"),
  getTradingActivity: () => fetchJson<TradingActivity[]>("/risk/analytics/activity"),
  getRiskMetrics: () => riskApi.getMetrics(),
};

// ---- News & Market Intelligence ----

import type { NewsArticle, TrendingCoin, MarketSentiment } from "./types";

export const newsApi = {
  getFeed: (limit = 20, symbol?: string) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (symbol) params.set("symbol", symbol);
    return fetchJson<NewsArticle[]>(`/news/feed?${params}`);
  },
  getFeedBySymbol: (symbol: string, limit = 20) =>
    fetchJson<NewsArticle[]>(`/news/feed/${symbol}?limit=${limit}`),
  getTrending: () => fetchJson<TrendingCoin[]>("/news/trending"),
  getSentiment: () => fetchJson<MarketSentiment>("/news/sentiment"),
};
