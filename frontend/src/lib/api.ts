// ============================================================
// GlueTrade Trading Platform - API Client
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
  OrderPreflight,
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
      email: parsed.email ?? "demo@gluetrade.com",
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
      preferences: parsed.preferences ?? {},
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
const OHLCV_CACHE_MS = 15_000;
const PERSISTED_OHLCV_CACHE_MS = 300_000;
const SIGNAL_CACHE_MS = 20_000;
const PERSISTED_SIGNAL_CACHE_MS = 180_000;
const MARKET_CACHE_MS = 10_000;
const SNAPSHOT_CACHE_MS = 5_000;
const ME_CACHE_MS = 10_000;
const FEAR_GREED_CACHE_MS = 60_000;
const DEFAULT_PRICE_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"];
const _ohlcvCache = new Map<string, { ts: number; data: OHLCVPoint[]; promise?: Promise<OHLCVPoint[]> }>();
const _signalCache = new Map<string, { ts: number; data?: SignalData; promise?: Promise<SignalData> }>();
let _marketCache: { data: AllCryptosResponse; ts: number } | null = null;
let _meCache: { data: UserProfile; ts: number } | null = null;
let _fearGreedCache: { data: { value: number; label: string }; ts: number } | null = null;
let _snapshotCache: { scope: string; data: PortfolioSnapshot; ts: number } | null = null;
const CLIENT_CACHE_PREFIX = "gluetrade-cache:v4:";

function currentCacheScope() {
  const token = getAccessToken();
  return token ? token.slice(-16) : "anon";
}

function clientCacheKey(key: string, scoped = false) {
  return `${CLIENT_CACHE_PREFIX}${scoped ? `${currentCacheScope()}:` : ""}${key}`;
}

function readClientCache<T>(key: string, maxAge = Number.POSITIVE_INFINITY): { data: T; ts: number } | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { data?: T; ts?: number };
    if (parsed.ts == null || parsed.data == null) return null;
    if (Date.now() - parsed.ts > maxAge) return null;
    return { data: parsed.data, ts: parsed.ts };
  } catch {
    return null;
  }
}

function writeClientCache<T>(key: string, data: T) {
  if (typeof window === "undefined") return;

  try {
    localStorage.setItem(key, JSON.stringify({ data, ts: Date.now() }));
  } catch {
    // Ignore storage quota issues.
  }
}

function trimAllCryptosResponse(response: AllCryptosResponse, limit: number): AllCryptosResponse {
  const data = response.data.slice(0, limit);
  return {
    data,
    total: Math.max(response.total ?? data.length, data.length),
    page: 1,
    limit,
  };
}

function rememberAllCryptos(response: AllCryptosResponse) {
  const payload = trimAllCryptosResponse(response, response.data.length);
  _marketCache = { data: payload, ts: Date.now() };
  writeClientCache(clientCacheKey("markets:all"), payload);
  return payload;
}

function readPersistedAllCryptos() {
  const cached = readClientCache<AllCryptosResponse>(clientCacheKey("markets:all"), MARKET_CACHE_MS);
  if (!cached) return null;
  _marketCache = cached;
  return cached.data;
}

function rememberMe(profile: UserProfile) {
  _meCache = { data: profile, ts: Date.now() };
  writeClientCache(clientCacheKey("auth:me", true), profile);
  return profile;
}

function readPersistedMe(maxAge = ME_CACHE_MS) {
  const cached = readClientCache<UserProfile>(clientCacheKey("auth:me", true), maxAge);
  if (!cached) return null;
  _meCache = cached;
  return cached.data;
}

function rememberFearGreed(data: { value: number; label: string }) {
  _fearGreedCache = { data, ts: Date.now() };
  writeClientCache(clientCacheKey("markets:fear-greed"), data);
  return data;
}

function readPersistedFearGreed(maxAge = FEAR_GREED_CACHE_MS) {
  const cached = readClientCache<{ value: number; label: string }>(
    clientCacheKey("markets:fear-greed"),
    maxAge,
  );
  if (!cached) return null;
  _fearGreedCache = cached;
  return cached.data;
}

function rememberSnapshot(snapshot: PortfolioSnapshot) {
  const scope = currentCacheScope();
  _snapshotCache = { scope, data: snapshot, ts: Date.now() };
  writeClientCache(clientCacheKey("portfolio:snapshot", true), snapshot);
  return snapshot;
}

function readPersistedSnapshot(maxAge = SNAPSHOT_CACHE_MS) {
  const cached = readClientCache<PortfolioSnapshot>(clientCacheKey("portfolio:snapshot", true), maxAge);
  if (!cached) return null;
  _snapshotCache = { scope: currentCacheScope(), data: cached.data, ts: cached.ts };
  return cached.data;
}

function readPersistedOHLCV(key: string, maxAge = PERSISTED_OHLCV_CACHE_MS) {
  return readClientCache<OHLCVPoint[]>(clientCacheKey(`ohlcv:${key}`), maxAge);
}

function rememberOHLCV(key: string, data: OHLCVPoint[]) {
  _ohlcvCache.set(key, { ts: Date.now(), data });
  writeClientCache(clientCacheKey(`ohlcv:${key}`), data);
  return data;
}

function readPersistedSignal(key: string, maxAge = PERSISTED_SIGNAL_CACHE_MS) {
  return readClientCache<SignalData>(clientCacheKey(`signal:${key}`), maxAge);
}

function rememberSignal(key: string, data: SignalData) {
  const normalized = {
    ...data,
    symbol: data.symbol.toUpperCase(),
  };
  _signalCache.set(key, { ts: Date.now(), data: normalized });
  writeClientCache(clientCacheKey(`signal:${key}`), normalized);
  return normalized;
}

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
  peekAllCryptos: (limit = 250): AllCryptosResponse | null => {
    if (_marketCache?.data) return trimAllCryptosResponse(_marketCache.data, limit);
    const persisted = readPersistedAllCryptos();
    return persisted ? trimAllCryptosResponse(persisted, limit) : null;
  },

  getAllCryptos: async (limit = 250): Promise<AllCryptosResponse> => {
    if (_marketCache && Date.now() - _marketCache.ts < MARKET_CACHE_MS) {
      return trimAllCryptosResponse(_marketCache.data, limit);
    }

    try {
      const tickers = await getAllTickers();
      if (tickers.length > 0) {
        const sorted = [...tickers]
          .sort((a, b) => parseFloat(b.quoteVolume) - parseFloat(a.quoteVolume))
          .slice(0, limit);

        return rememberAllCryptos({
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
        });
      }
    } catch {
      // Gateway fallback below
    }

    const backend = await fetchJson<BackendMarketListingResponse>(`/markets/all?limit=${limit}&page=1`);
    return rememberAllCryptos({
      data: backend.data.map((coin, index) => normalizeBackendCrypto(coin, index)),
      total: backend.total,
      page: backend.page,
      limit: backend.limit,
    });
  },

  peekOHLCV: (symbol: string, interval = "1d", limit = 90): OHLCVPoint[] => {
    const key = `${symbol.toUpperCase()}|${interval}|${limit}`;
    const memory = _ohlcvCache.get(key);
    if (memory?.data?.length) return memory.data;

    const persisted = readPersistedOHLCV(key, Number.POSITIVE_INFINITY);
    if (!persisted?.data?.length) return [];
    _ohlcvCache.set(key, { ts: persisted.ts, data: persisted.data });
    return persisted.data;
  },

  getOHLCV: async (symbol: string, interval = "1d", limit = 90): Promise<OHLCVPoint[]> => {
    const key = `${symbol.toUpperCase()}|${interval}|${limit}`;
    const persisted = readPersistedOHLCV(key);
    if (persisted?.data?.length && !_ohlcvCache.has(key)) {
      _ohlcvCache.set(key, { ts: persisted.ts, data: persisted.data });
    }

    const cached = _ohlcvCache.get(key);

    if (cached?.data && Date.now() - cached.ts < OHLCV_CACHE_MS) {
      return cached.data;
    }

    if (cached?.promise) {
      return cached.promise;
    }

    const request = (async () => {
      try {
        const response = await fetchJson<BackendHistoryResponse>(
          `/prices/history/${symbol.toUpperCase()}?interval=${encodeURIComponent(interval)}&limit=${limit}`,
        );
        const data = response.data.map(normalizeHistoryPoint);
        return rememberOHLCV(key, data);
      } catch {
        try {
          const pair = `${symbol.toUpperCase()}USDT`;
          const data = await fetchBinance<number[][]>(`/klines?symbol=${pair}&interval=${interval}&limit=${limit}`);
          const normalized = data.map(normalizeKlineRow);
          return rememberOHLCV(key, normalized);
        } catch {
          const stale = _ohlcvCache.get(key)?.data ?? persisted?.data ?? [];
          if (stale.length > 0) {
            rememberOHLCV(key, stale);
          } else {
            _ohlcvCache.set(key, { ts: Date.now(), data: stale });
          }
          return stale;
        }
      }
    })();

    _ohlcvCache.set(key, {
      ts: cached?.ts ?? 0,
      data: cached?.data ?? [],
      promise: request,
    });

    try {
      return await request;
    } finally {
      const latest = _ohlcvCache.get(key);
      if (latest?.promise === request) {
        _ohlcvCache.set(key, {
          ts: latest.ts,
          data: latest.data,
        });
      }
    }
  },

  peekFearGreed: (): { value: number; label: string } | null => {
    if (_fearGreedCache?.data) return _fearGreedCache.data;
    return readPersistedFearGreed(Number.POSITIVE_INFINITY);
  },

  getFearGreed: async (): Promise<{ value: number; label: string }> => {
    if (_fearGreedCache && Date.now() - _fearGreedCache.ts < FEAR_GREED_CACHE_MS) {
      return _fearGreedCache.data;
    }

    try {
      const response = await fetchJson<BackendFearGreedResponse>("/markets/fear-greed");
      return rememberFearGreed({
        value: Number(response.data.value ?? 50),
        label: String(response.data.classification ?? "Neutral"),
      });
    } catch {
      try {
        const r = await fetch("https://api.alternative.me/fng/?limit=1&format=json");
        const d = await r.json();
        const e = d?.data?.[0];
        return rememberFearGreed({
          value: Number(e?.value ?? 50),
          label: String(e?.value_classification ?? "Neutral"),
        });
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
  peekSnapshot: () => {
    if (_snapshotCache && _snapshotCache.scope === currentCacheScope()) {
      return _snapshotCache.data;
    }
    return readPersistedSnapshot(Number.POSITIVE_INFINITY);
  },
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
    if (
      _snapshotCache &&
      _snapshotCache.scope === currentCacheScope() &&
      Date.now() - _snapshotCache.ts < SNAPSHOT_CACHE_MS
    ) {
      return _snapshotCache.data;
    }

    try {
      const snapshot = await fetchJson<BackendPortfolioSnapshot>("/portfolios/snapshot");
      return rememberSnapshot(normalizePortfolioSnapshot(snapshot));
    } catch (error) {
      const stale = portfolioApi.peekSnapshot();
      if (stale) return stale;
      throw error;
    }
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
    const result = await fetchJson<BackendOrderResponse>("/orders/", {
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

  getErrorCatalog: async (): Promise<{ version: string; entries: Array<Record<string, unknown>> }> => {
    return fetchJson("/orders/error-catalog");
  },

  executeWithConversion: async (data: {
    symbol: string;
    side: OrderSide;
    quantity: number;
    max_retries?: number;
  }): Promise<{ status: string; steps: Array<Record<string, unknown>>; error: Record<string, unknown> | null }> => {
    return fetchJson("/orders/execute-with-conversion", {
      method: "POST",
      body: JSON.stringify({
        symbol: data.symbol,
        side: data.side,
        quantity: data.quantity,
        max_retries: data.max_retries ?? 3,
      }),
    });
  },

  preflightOrder: (params: {
    symbol: string;
    side: OrderSide;
    quantity: number;
    reference_price?: number;
  }) => {
    const search = new URLSearchParams({
      symbol: params.symbol,
      side: params.side,
      quantity: String(params.quantity),
    });
    if (params.reference_price != null && Number.isFinite(params.reference_price) && params.reference_price > 0) {
      search.set("reference_price", String(params.reference_price));
    }
    return fetchJson<OrderPreflight>(`/orders/preflight?${search.toString()}`);
  },

  getOrders: async (): Promise<Order[]> => {
    try {
      const response = await fetchJson<BackendOrderListResponse>("/orders/");
      return response.orders.map(normalizeOrder);
    } catch {
      return [];
    }
  },

  cancelOrder: (orderId: string) =>
    fetchJson<BackendOrderResponse>(`/orders/${orderId}`, { method: "DELETE" }),
};

// ---- Signals (computed from Binance klines) ----

interface SubScoreData {
  category: string;
  score: number;
  label: string;
}

interface SignalData {
  symbol: string;
  action: string;
  confidence: number;
  score: number;
  publication_score?: number;
  composite_score?: number;
  reliability_score?: number;
  reasoning: string;
  indicators: Array<{ name: string; value: number; signal: number; description: string }>;
  timestamp: string;
  // Enhanced scoring (V2)
  score_100: number;
  action_label: string;
  confidence_level: string;
  status: string;
  sub_scores: SubScoreData[];
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
  trend_context_score?: number;
  trend_reliability_score?: number;
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
  scenario?: string | null;
  scenario_probability?: number | null;
}

interface ScannerIndicatorData {
  name: string;
  value: number;
  signal: number;
  description: string;
}

interface ScannerSignalPayload {
  rank: number;
  symbol: string;
  horizon: string;
  setup_type: string;
  regime: string;
  reasoning: string;
  indicators: ScannerIndicatorData[];
  direction: number;
  direction_label: string;
  confidence: number;
  confidence_score: number;
  regime_fit: number;
  confirmation_score: number;
  composite_score?: number;
  reliability_score?: number;
  trend_context_score?: number;
  trend_reliability_score?: number;
  execution_risk: number;
  liquidity_score: number;
  risk: number;
  setup_quality: number;
  actionability: string;
  action: string;
  market_regime: string;
  signal_context: string;
  sub_scores: SubScoreData[];
  key_reasons: string[];
  contradictions: Array<{ description: string; severity: string }>;
  notrade_reasons: string[];
  expected_holding_window: string;
  freshness_ms: number;
  signal_trade_plan: SignalData["signal_trade_plan"];
  scenario?: string | null;
  scenario_probability?: number | null;
  global_score: number;
  publication_score?: number;
  score_100: number;
  status: string;
  action_label: string;
  confidence_level: string;
  best_strategy?: {
    strategy_name?: string;
    timeframe?: string;
    reasoning?: string;
    indicators?: ScannerIndicatorData[];
  } | null;
  timestamp: string;
}

interface ScannerSnapshotPayload {
  signals: ScannerSignalPayload[];
  mode: string;
  scanned: number;
  timestamp: string;
}

function uniqueTextList(items: string[] | undefined): string[] {
  if (!items?.length) return [];
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

function normalizedPublicationStatus(status?: string, actionability?: string): "high_conviction" | "actionable" | "watch" | "ignore" {
  const raw = (status ?? actionability ?? "ignore").toString().toLowerCase();
  if (raw === "high_conviction") return "high_conviction";
  if (raw === "actionable") return "actionable";
  if (raw === "watch") return "watch";
  return "ignore";
}

function actionabilityFromStatus(status: string): SignalData["actionability"] {
  if (status === "high_conviction") return "HIGH_CONVICTION";
  if (status === "actionable") return "ACTIONABLE";
  if (status === "watch") return "WATCH";
  return "IGNORE";
}

function normalizeScannerSignal(payload: ScannerSignalPayload): SignalData {
  const confidenceScore = toNumber(payload.confidence_score ?? payload.confidence);
  const confidence =
    payload.confidence <= 1
      ? toNumber(payload.confidence)
      : Math.max(0, Math.min(1, confidenceScore / 100));
  const status = normalizedPublicationStatus(payload.status, payload.actionability);
  const published = status === "actionable" || status === "high_conviction";
  const actionLabel = published
    ? (payload.action_label ?? payload.direction_label)
    : (status === "watch" ? "A surveiller" : "Neutre / attente");
  const score100 = toNumber(payload.score_100 ?? payload.direction);
  const direction = toNumber(payload.direction ?? payload.score_100);
  const directionLabel = payload.direction_label ?? "Neutre / attente";
  const action = published ? payload.action : "HOLD";

  const indicators =
    payload.indicators?.length
      ? payload.indicators
      : payload.best_strategy?.indicators ?? [];
  const keyReasons = uniqueTextList(payload.key_reasons);
  const notradeReasons = uniqueTextList(payload.notrade_reasons);

  return {
    symbol: payload.symbol.toUpperCase(),
    action,
    confidence,
    score: toNumber(payload.global_score),
    publication_score: toNumber(payload.publication_score ?? payload.composite_score),
    composite_score: toNumber(payload.composite_score ?? payload.publication_score),
    reliability_score: toNumber(payload.reliability_score ?? payload.trend_reliability_score),
    reasoning:
      payload.reasoning ||
      payload.best_strategy?.reasoning ||
      keyReasons.join(". ") ||
      actionLabel,
    indicators: indicators.map((indicator) => ({
      name: indicator.name,
      value: toNumber(indicator.value),
      signal: toNumber(indicator.signal),
      description: indicator.description,
    })),
    timestamp: payload.timestamp,
    score_100: score100,
    action_label: actionLabel,
    confidence_level: payload.confidence_level ?? "moyen",
    status,
    sub_scores: payload.sub_scores ?? [],
    key_reasons: keyReasons,
    direction,
    direction_label: directionLabel,
    confidence_score: confidenceScore,
    risk: payload.risk ?? payload.execution_risk,
    setup_quality: payload.setup_quality,
    actionability: actionabilityFromStatus(status),
    market_regime: payload.market_regime,
    signal_context: payload.signal_context,
    trend_context_score: toNumber(payload.trend_context_score),
    trend_reliability_score: toNumber(payload.trend_reliability_score),
    contradictions: payload.contradictions ?? [],
    signal_trade_plan: published ? (payload.signal_trade_plan ?? null) : null,
    horizon: payload.horizon ?? "Scalp 1m/5m/15m/1h",
    setup_type: payload.setup_type || payload.scenario || payload.best_strategy?.strategy_name || "contextual_setup",
    regime: payload.regime ?? "RANGE",
    regime_fit: payload.regime_fit ?? 0,
    confirmation_score: payload.confirmation_score ?? 0,
    execution_risk: payload.execution_risk ?? payload.risk ?? 50,
    liquidity_score: payload.liquidity_score ?? 50,
    notrade_reasons: notradeReasons,
    expected_holding_window: payload.expected_holding_window ?? "",
    freshness_ms: payload.freshness_ms ?? 0,
    scenario: payload.scenario ?? null,
    scenario_probability: payload.scenario_probability ?? null,
  };
}

function scannerFallbackReason(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return "Scanner backend indisponible pour ce symbole";
    }
    if (error.status === 504) {
      return "Scanner backend trop lent, resultat degrade";
    }
    if (error.detail) {
      return `Scanner backend indisponible (${error.detail})`;
    }
  }

  return "Scanner backend indisponible — contexte multi-timeframe manquant";
}

function buildUnavailableSignal(symbol: string, reason: string): SignalData {
  const timestamp = new Date().toISOString();
  return {
    symbol: symbol.toUpperCase(),
    action: "HOLD",
    confidence: 0,
    score: 0,
    publication_score: 0,
    composite_score: 0,
    reliability_score: 0,
    reasoning: reason,
    indicators: [],
    timestamp,
    score_100: 50,
    action_label: "Neutre / attente",
    confidence_level: "faible",
    status: "ignore",
    sub_scores: [],
    key_reasons: [reason],
    direction: 50,
    direction_label: "Neutre / attente",
    confidence_score: 0,
    risk: 50,
    setup_quality: 0,
    actionability: "IGNORE",
    market_regime: "UNKNOWN",
    signal_context: "scanner_unavailable",
    contradictions: [],
    signal_trade_plan: null,
    horizon: "Scalp 1m/5m/15m/1h",
    setup_type: "scanner_unavailable",
    regime: "UNKNOWN",
    regime_fit: 0,
    confirmation_score: 0,
    execution_risk: 50,
    liquidity_score: 0,
    notrade_reasons: [reason],
    expected_holding_window: "",
    freshness_ms: 0,
    scenario: null,
    scenario_probability: null,
  };
}

async function computeSignal(symbol: string): Promise<SignalData> {
  const closes: number[] = [];
  try {
    const klines = await pricesApi.getOHLCV(symbol, "1h", 100);
    for (const k of klines) closes.push(k.close);
  } catch { /* empty */ }

  if (closes.length < 15) {
    return {
      symbol,
      action: "HOLD",
      confidence: 0,
      score: 0,
      publication_score: 0,
      composite_score: 0,
      reliability_score: 0,
      reasoning: "Insufficient data",
      indicators: [],
      timestamp: new Date().toISOString(),
      score_100: 50,
      action_label: "Neutre / attente",
      confidence_level: "faible",
      status: "ignore",
      sub_scores: [],
      key_reasons: ["Donnees insuffisantes"],
      direction: 50,
      direction_label: "Neutre / attente",
      confidence_score: 0,
      risk: 50,
      setup_quality: 0,
      actionability: "IGNORE",
      market_regime: "UNKNOWN",
      signal_context: "mixed",
      contradictions: [],
      signal_trade_plan: null,
      horizon: "Scalp 1h",
      setup_type: "degraded_fallback",
      regime: "UNKNOWN",
      regime_fit: 0,
      confirmation_score: 0,
      execution_risk: 50,
      liquidity_score: 0,
      notrade_reasons: ["Donnees insuffisantes"],
      expected_holding_window: "",
      freshness_ms: 0,
      scenario: null,
      scenario_probability: null,
    };
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

  // Enhanced scoring: convert -1..+1 to 0..100
  const score_100 = Math.max(0, Math.min(100, Math.round((score + 1) / 2 * 100)));
  const momentumScore = Math.max(0, Math.min(100, Math.round((rsiSig + 1) / 2 * 100)));
  const trendScore = Math.max(0, Math.min(100, Math.round((emaSig + 1) / 2 * 100)));
  const volatilityScore = Math.max(0, Math.min(100, Math.round(((bbSig * -1) + 1) / 2 * 100))); // invert: low BB = high vol opportunity

  const labelMap = (s: number) => s >= 80 ? "Achat fort" : s >= 70 ? "Achat" : s >= 60 ? "Achat prudent" : s >= 45 ? "Neutre / attente" : s >= 30 ? "Biais vendeur" : "Vente forte";
  const momLabel = (s: number) => s >= 80 ? "Impulsion forte" : s >= 60 ? "En acceleration" : s >= 40 ? "Neutre" : s >= 20 ? "Pression baissiere" : "Epuisement vendeur";
  const trendLabel = (s: number) => s >= 80 ? "Tendance tres forte" : s >= 60 ? "Tendance haussiere" : s >= 40 ? "Consolidation" : s >= 20 ? "Tendance fragile" : "Tendance baissiere forte";
  const volLabel = (s: number) => s >= 80 ? "Volatilite extreme" : s >= 60 ? "En expansion" : s >= 40 ? "Expansion moderee" : s >= 20 ? "Faible expansion" : "Calme / compresse";

  // Confidence from indicator agreement
  const sigs = [rsiSig, emaSig, bbSig];
  const posCount = sigs.filter(s => s > 0.15).length;
  const negCount = sigs.filter(s => s < -0.15).length;
  const agreement = Math.max(posCount, negCount) / sigs.length;
  const confLevel = agreement >= 0.85 ? "tres eleve" : agreement >= 0.65 ? "eleve" : agreement >= 0.45 ? "moyen" : "faible";

  // Status
  const isExtreme = score_100 >= 75 || score_100 <= 25;
  const isDirectional = score_100 >= 60 || score_100 <= 40;
  const status = isExtreme && agreement >= 0.65 ? "high_conviction" : isDirectional ? "actionable" : agreement < 0.45 ? "watch" : "ignore";

  // Key reasons (top 2 by signal strength)
  const indicators = [
    { name: "RSI", value: Math.round(rsi), signal: rsiSig, description: rsi < 30 ? `RSI ${rsi.toFixed(0)} — Zone de survente` : rsi > 70 ? `RSI ${rsi.toFixed(0)} — Zone de surachat` : rsi < 45 ? `RSI ${rsi.toFixed(0)} — Momentum en reprise` : rsi > 55 ? `RSI ${rsi.toFixed(0)} — Pression vendeuse` : `RSI ${rsi.toFixed(0)} — Zone neutre` },
    { name: "EMA Cross", value: Math.round(ed*100)/100, signal: emaSig, description: (ed > 0 && pd <= 0) ? "Croisement haussier EMA 9/21" : (ed < 0 && pd >= 0) ? "Croisement baissier EMA 9/21" : ed > 0 ? "EMA haussiere alignee" : "EMA baissiere alignee" },
    { name: "Bollinger", value: Math.round(pos*100)/100, signal: bbSig, description: pos < 0.15 ? "Prix sous bande basse — rebond probable" : pos > 0.85 ? "Prix sur bande haute — risque de rejet" : pos < 0.4 ? "Prix en zone basse des bandes" : pos > 0.6 ? "Prix en zone haute des bandes" : "Prix au milieu des bandes" },
  ];
  const sortedByStrength = [...indicators].sort((a, b) => Math.abs(b.signal) - Math.abs(a.signal));
  const key_reasons = sortedByStrength.slice(0, 2).filter(i => Math.abs(i.signal) > 0.1).map(i => i.description);

  return {
    symbol: symbol.toUpperCase(),
    action,
    confidence: Math.min(Math.abs(score), 1),
    score: Math.round(score * 1000) / 1000,
    publication_score: Math.max(0, Math.min(100, Math.round(agreement * 100))),
    composite_score: Math.max(0, Math.min(100, Math.round(agreement * 100))),
    reliability_score: Math.max(0, Math.min(100, Math.round(agreement * 100))),
    reasoning: `RSI=${rsi.toFixed(0)}, EMA${ed>0?"+":"-"}, BB${pos<0.3?"low":pos>0.7?"high":"mid"}`,
    indicators,
    timestamp: new Date().toISOString(),
    score_100,
    action_label: labelMap(score_100),
    confidence_level: confLevel,
    status,
    sub_scores: [
      { category: "momentum", score: momentumScore, label: momLabel(momentumScore) },
      { category: "trend", score: trendScore, label: trendLabel(trendScore) },
      { category: "volatility", score: volatilityScore, label: volLabel(volatilityScore) },
    ],
    key_reasons: key_reasons.length > 0 ? key_reasons : ["Signaux mixtes — pas de direction claire"],
    // V3 multi-dimensional
    direction: score_100,
    direction_label: labelMap(score_100),
    confidence_score: Math.round(agreement * 100),
    risk: Math.max(0, Math.min(100, 30 + (score_100 >= 80 || score_100 <= 20 ? 20 : 0) + (agreement < 0.45 ? 15 : 0))),
    setup_quality: Math.max(0, Math.min(100, Math.round(agreement * 70) + (score_100 >= 60 || score_100 <= 40 ? 15 : 0))),
    actionability: (Math.abs(score_100 - 50) >= 25 && agreement >= 0.65) ? "HIGH_CONVICTION" : (Math.abs(score_100 - 50) >= 15 && agreement >= 0.45) ? "ACTIONABLE" : Math.abs(score_100 - 50) >= 10 ? "WATCH" : "IGNORE",
    market_regime: "UNKNOWN",
    signal_context: "mixed",
    contradictions: (rsiSig > 0.3 && emaSig < -0.3) || (rsiSig < -0.3 && emaSig > 0.3) ? [{ description: "RSI et EMA en desaccord", severity: "moderate" }] : [],
    signal_trade_plan: null,
    horizon: "Scalp 1h",
    setup_type: "degraded_fallback",
    regime: "UNKNOWN",
    regime_fit: Math.max(0, Math.min(100, Math.round(agreement * 60 + Math.abs(score_100 - 50) * 0.8))),
    confirmation_score: Math.max(0, Math.min(100, Math.round(agreement * 100))),
    execution_risk: Math.max(0, Math.min(100, 35 + (agreement < 0.45 ? 15 : 0) + (score_100 <= 20 || score_100 >= 80 ? 15 : 0))),
    liquidity_score: 50,
    notrade_reasons: [],
    expected_holding_window: "5-30 min",
    freshness_ms: 0,
    scenario: null,
    scenario_probability: null,
  };
}

async function fetchScannerSignal(symbol: string, mode = "scalping"): Promise<SignalData> {
  const payload = await fetchJson<ScannerSignalPayload>(`/scanner/signals/${encodeURIComponent(symbol.toUpperCase())}?mode=${encodeURIComponent(mode)}`);
  return normalizeScannerSignal(payload);
}

async function fetchScannerSignals(symbols: string[], mode = "scalping"): Promise<SignalData[]> {
  const normalizedSymbols = Array.from(new Set(symbols.map((symbol) => symbol.toUpperCase()).filter(Boolean)));
  if (normalizedSymbols.length === 0) return [];
  const params = new URLSearchParams({
    symbols: normalizedSymbols.join(","),
    mode,
  });
  const payload = await fetchJson<ScannerSnapshotPayload>(`/scanner/signals?${params.toString()}`);
  return payload.signals.map(normalizeScannerSignal);
}

export const signalsApi = {
  peekSignal: (symbol: string): SignalData | null => {
    const key = symbol.toUpperCase();
    const memory = _signalCache.get(key);
    if (memory?.data) return memory.data;

    const persisted = readPersistedSignal(key, Number.POSITIVE_INFINITY);
    if (!persisted?.data) return null;

    _signalCache.set(key, { ts: persisted.ts, data: persisted.data });
    return persisted.data;
  },
  getSignal: async (symbol: string, mode = "scalping") => {
    const key = symbol.toUpperCase();
    const persisted = readPersistedSignal(key);
    if (persisted?.data && !_signalCache.has(key)) {
      _signalCache.set(key, { ts: persisted.ts, data: persisted.data });
    }

    const cached = _signalCache.get(key);
    if (cached?.data && Date.now() - cached.ts < SIGNAL_CACHE_MS) {
      return cached.data;
    }

    if (cached?.promise) {
      return cached.promise;
    }

    const request = (async () => {
      try {
        return rememberSignal(key, await fetchScannerSignal(key, mode));
      } catch (error) {
        return rememberSignal(key, buildUnavailableSignal(key, scannerFallbackReason(error)));
      }
    })();

    _signalCache.set(key, {
      ts: cached?.ts ?? persisted?.ts ?? 0,
      data: cached?.data ?? persisted?.data,
      promise: request,
    });

    try {
      return await request;
    } finally {
      const latest = _signalCache.get(key);
      if (latest?.promise === request) {
        _signalCache.set(key, {
          ts: latest.ts,
          data: latest.data,
        });
      }
    }
  },
  getSignals: async (symbols: string[], mode = "scalping") => {
    const orderedSymbols = Array.from(new Set(symbols.map((symbol) => symbol.toUpperCase()).filter(Boolean)));
    const results = new Map<string, SignalData>();
    const missing: string[] = [];

    for (const symbol of orderedSymbols) {
      const cached = signalsApi.peekSignal(symbol);
      const fresh = _signalCache.get(symbol);
      if (cached && fresh?.ts != null && Date.now() - fresh.ts < SIGNAL_CACHE_MS) {
        results.set(symbol, cached);
      } else {
        missing.push(symbol);
      }
    }

    if (missing.length > 0) {
      try {
        const fetched = await fetchScannerSignals(missing, mode);
        const fetchedSymbols = new Set<string>();
        for (const signal of fetched) {
          const key = signal.symbol.toUpperCase();
          fetchedSymbols.add(key);
          results.set(key, rememberSignal(key, signal));
        }
        for (const symbol of missing) {
          const key = symbol.toUpperCase();
          if (fetchedSymbols.has(key)) continue;
          results.set(key, rememberSignal(key, buildUnavailableSignal(key, "Scanner backend indisponible pour ce symbole")));
        }
      } catch (error) {
        const reason = scannerFallbackReason(error);
        for (const symbol of missing) {
          const key = symbol.toUpperCase();
          results.set(key, rememberSignal(key, buildUnavailableSignal(key, reason)));
        }
      }
    }

    return orderedSymbols
      .map((symbol) => results.get(symbol))
      .filter((signal): signal is SignalData => Boolean(signal));
  },
  getAllSignals: async (mode = "scalping") => {
    const syms = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"];
    return signalsApi.getSignals(syms, mode);
  },
};

// ---- Strategies ----

export const strategiesApi = {
  list: () => fetchJson<Strategy[]>("/strategies/"),
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
  peekCachedMe: () => {
    if (_meCache) {
      return _meCache.data;
    }
    return readPersistedMe(Number.POSITIVE_INFINITY);
  },
  getMe: async () => {
    const token = getAccessToken();
    if (token === "demo-token") {
      const demo = getDemoUser();
      if (demo) return demo;
    }
    if (_meCache && Date.now() - _meCache.ts < ME_CACHE_MS) {
      return _meCache.data;
    }

    try {
      const me = await fetchJson<UserProfile>("/auth/me");
      return rememberMe(me);
    } catch (error) {
      const stale = authApi.peekCachedMe();
      if (stale) return stale;
      throw error;
    }
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
        | "preferences"
      >
    > & { telegram_chat_id?: string | null },
  ) => fetchJson<UserProfile>("/auth/me", { method: "PUT", body: JSON.stringify(data) }).then(rememberMe),
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
  deleteAccount: (password: string) =>
    fetchJson<{ message: string }>("/auth/me", { method: "DELETE", body: JSON.stringify({ password }) }),
  exportData: () => fetchJson<Record<string, unknown>>("/auth/me/data-export"),
  resendVerification: () =>
    fetchJson<{ message: string }>("/auth/resend-verification", { method: "POST" }),
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
  getMetrics: () => fetchJson<AnalyticsMetrics>("/risk/metrics"),
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
