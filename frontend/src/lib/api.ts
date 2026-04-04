// ============================================================
// Okamoey Trading Platform - API Client
// Gateway-first with CoinGecko direct fallback
// ============================================================

import type {
  MarketOverview,
  CryptoPrice,
  Portfolio,
  Position,
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
  RiskMetrics,
  SearchResponse,
  AllCryptosResponse,
  OHLCVPoint,
  AIAgent,
  ChatResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const CG_BASE = "https://api.coingecko.com/api/v3";

// ---- Helpers ----

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

async function fetchCG<T>(path: string, params: Record<string, string> = {}): Promise<T> {
  const qs = new URLSearchParams(params).toString();
  const url = `${CG_BASE}${path}${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`CoinGecko ${res.status}`);
  return res.json() as Promise<T>;
}

// Symbol → CoinGecko ID mapping
const SYM_TO_CG: Record<string, string> = {
  BTC: "bitcoin", ETH: "ethereum", SOL: "solana", BNB: "binancecoin", XRP: "ripple",
  ADA: "cardano", DOGE: "dogecoin", AVAX: "avalanche-2", DOT: "polkadot", MATIC: "matic-network",
  LINK: "chainlink", UNI: "uniswap", ATOM: "cosmos", LTC: "litecoin", NEAR: "near",
  APT: "aptos", ARB: "arbitrum", OP: "optimism", FIL: "filecoin", AAVE: "aave",
  SHIB: "shiba-inu", TRX: "tron", TON: "the-open-network", SUI: "sui", SEI: "sei-network",
  PEPE: "pepe", WLD: "worldcoin-wld", INJ: "injective-protocol", TIA: "celestia",
  JUP: "jupiter-exchange-solana", ONDO: "ondo-finance", RENDER: "render-token",
  FET: "fetch-ai", STX: "blockstack", IMX: "immutable-x", MKR: "maker", GRT: "the-graph",
  ALGO: "algorand", FTM: "fantom", SAND: "the-sandbox", MANA: "decentraland",
  AXS: "axie-infinity", THETA: "theta-token", EGLD: "elrond-erd-2", FLOW: "flow",
  XLM: "stellar", VET: "vechain", HBAR: "hedera-hashgraph", EOS: "eos", CRO: "crypto-com-chain",
};

// ---- Currency helper ----

function getActiveCurrency(): string {
  if (typeof window === "undefined") return "usd";
  return localStorage.getItem("okamoey-currency") || "usd";
}

// ---- CoinGecko Direct Fallbacks ----

async function cgGetAllCryptos(limit: number): Promise<AllCryptosResponse> {
  const data = await fetchCG<Array<Record<string, unknown>>>("/coins/markets", {
    vs_currency: getActiveCurrency(),
    order: "market_cap_desc",
    per_page: String(limit),
    page: "1",
    sparkline: "true",
    price_change_percentage: "24h",
  });

  return {
    data: data.map((coin) => {
      const sparkline = coin.sparkline_in_7d as { price?: number[] } | null;
      return {
        symbol: String(coin.symbol ?? "").toUpperCase(),
        name: String(coin.name ?? ""),
        price: Number(coin.current_price ?? 0),
        change_24h: Number(coin.price_change_24h ?? 0),
        change_pct_24h: Number(coin.price_change_percentage_24h ?? 0),
        volume_24h: Number(coin.total_volume ?? 0),
        market_cap: Number(coin.market_cap ?? 0),
        sparkline: sparkline?.price ?? [],
        rank: Number(coin.market_cap_rank ?? 0),
        // Extra fields for discover page
        id: String(coin.id ?? ""),
        image: String(coin.image ?? ""),
        current_price: Number(coin.current_price ?? 0),
        market_cap_rank: Number(coin.market_cap_rank ?? 0),
        price_change_percentage_24h: Number(coin.price_change_percentage_24h ?? 0),
        total_volume: Number(coin.total_volume ?? 0),
        sparkline_in_7d: sparkline?.price ?? null,
        high_24h: Number(coin.high_24h ?? 0),
        low_24h: Number(coin.low_24h ?? 0),
        circulating_supply: Number(coin.circulating_supply ?? 0),
        total_supply: Number(coin.total_supply ?? 0),
        ath: Number(coin.ath ?? 0),
        ath_change_percentage: Number(coin.ath_change_percentage ?? 0),
      };
    }),
    total: data.length,
    page: 1,
    limit,
  };
}

// CoinGecko OHLC endpoint (returns [timestamp, open, high, low, close])
async function cgGetOHLCV(symbol: string, interval: string, limit: number): Promise<OHLCVPoint[]> {
  const cgId = SYM_TO_CG[symbol.toUpperCase()];
  if (!cgId) return [];

  // Map interval to CoinGecko days parameter
  let days = "30";
  if (interval === "1m" || limit <= 60) days = "1";
  else if (interval === "5m" || limit <= 288) days = "1";
  else if (interval === "1h" || limit <= 168) days = "7";
  else if (interval === "4h" || limit <= 180) days = "30";
  else if (interval === "1d" && limit <= 90) days = "90";
  else if (interval === "1d" && limit <= 365) days = "365";
  else days = "max";

  const data = await fetchCG<number[][]>(`/coins/${cgId}/ohlc`, {
    vs_currency: getActiveCurrency(),
    days,
  });

  return data.map((d) => ({
    time: Math.floor(d[0] / 1000), // ms → seconds for lightweight-charts
    open: d[1],
    high: d[2],
    low: d[3],
    close: d[4],
    volume: 0, // OHLC endpoint doesn't include volume
  }));
}

async function cgGetFearGreed(): Promise<{ value: number; label: string }> {
  try {
    const data = await fetch("https://api.alternative.me/fng/?limit=1&format=json").then((r) => r.json());
    const entry = data?.data?.[0];
    return {
      value: Number(entry?.value ?? 50),
      label: String(entry?.value_classification ?? "Neutral"),
    };
  } catch {
    return { value: 50, label: "Neutral" };
  }
}

async function cgSearchAssets(query: string): Promise<SearchResponse> {
  const data = await fetchCG<{ coins: Array<Record<string, unknown>> }>("/search", { query });
  return {
    results: (data.coins ?? []).slice(0, 20).map((c) => ({
      symbol: String(c.symbol ?? "").toUpperCase(),
      name: String(c.name ?? ""),
      asset_type: "crypto" as const,
      market_cap: Number(c.market_cap_rank ?? 0),
    })),
    total: data.coins?.length ?? 0,
  };
}

// ---- API with fallback pattern ----

async function withFallback<T>(primary: () => Promise<T>, fallback: () => Promise<T>): Promise<T> {
  try {
    return await primary();
  } catch {
    return fallback();
  }
}

// ---- Prices / Market Data ----

export const pricesApi = {
  getOverview: () => fetchJson<MarketOverview>("/markets/overview"),
  getCrypto: () => fetchJson<CryptoPrice[]>("/prices/crypto"),
  getCryptoBySymbol: (symbol: string) =>
    fetchJson<CryptoPrice>(`/prices/crypto/${symbol}`),
  getStocks: () => fetchJson<CryptoPrice[]>("/prices/stocks"),

  getFearGreed: () =>
    withFallback(
      () => fetchJson<{ value: number; label: string }>("/markets/fear-greed"),
      () => cgGetFearGreed(),
    ),

  searchAssets: (query: string, limit = 20) =>
    withFallback(
      () => fetchJson<SearchResponse>(`/prices/search?q=${encodeURIComponent(query)}&limit=${limit}`),
      () => cgSearchAssets(query),
    ),

  getAllCryptos: (limit = 20, _page = 1) =>
    withFallback(
      () => fetchJson<AllCryptosResponse>(`/markets/all?limit=${limit}&page=${_page}`),
      () => cgGetAllCryptos(limit),
    ),

  getOHLCV: (symbol: string, interval = "1d", limit = 90) =>
    withFallback(
      () => fetchJson<OHLCVPoint[]>(`/prices/history/${encodeURIComponent(symbol)}?interval=${interval}&limit=${limit}`),
      () => cgGetOHLCV(symbol, interval, limit),
    ),
};

// ---- Portfolio ----

export const portfolioApi = {
  list: () => fetchJson<Portfolio[]>("/portfolios"),
  get: (id: string) => fetchJson<Portfolio>(`/portfolios/${id}`),
  create: (data: { name: string; description?: string }) =>
    fetchJson<Portfolio>("/portfolios", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getPositions: (portfolioId: string) =>
    fetchJson<Position[]>(`/portfolios/${portfolioId}/positions`),
  getTransactions: (portfolioId: string) =>
    fetchJson<Transaction[]>(`/portfolios/${portfolioId}/transactions`),
  closePosition: (positionId: string) =>
    fetchJson<TradeResult>(`/positions/${positionId}/close`, { method: "POST" }),
  updateStopLoss: (positionId: string, stopLoss: number) =>
    fetchJson<Position>(`/positions/${positionId}`, {
      method: "PATCH",
      body: JSON.stringify({ stop_loss: stopLoss }),
    }),
};

// ---- Trading ----

export const tradingApi = {
  getBalances: () => fetchJson<PaperBalance[]>("/trades/balances"),
  placeOrder: (data: {
    symbol: string;
    side: OrderSide;
    order_type: OrderType;
    quantity: number;
    price?: number;
    stop_price?: number;
  }) =>
    fetchJson<TradeResult>("/orders", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getOrders: (params?: { status?: string }) => {
    const qs = params?.status ? `?status=${params.status}` : "";
    return fetchJson<Order[]>(`/orders${qs}`);
  },
  cancelOrder: (orderId: string) =>
    fetchJson<{ success: boolean }>(`/orders/${orderId}/cancel`, {
      method: "POST",
    }),
};

// ---- Strategies ----

export const strategiesApi = {
  list: () => fetchJson<Strategy[]>("/ml/strategies"),
  get: (id: string) => fetchJson<Strategy>(`/ml/strategies/${id}`),
  generateSignal: (strategyId: string, symbol: string) =>
    fetchJson<Signal>(`/ml/strategies/${strategyId}/signal`, {
      method: "POST",
      body: JSON.stringify({ symbol }),
    }),
  updateParams: (strategyId: string, params: Record<string, unknown>) =>
    fetchJson<Strategy>(`/ml/strategies/${strategyId}`, {
      method: "PATCH",
      body: JSON.stringify({ parameters: params }),
    }),
};

// ---- Alerts ----

export const alertsApi = {
  list: () => fetchJson<Alert[]>("/alerts"),
  create: (data: CreateAlertPayload) =>
    fetchJson<Alert>("/alerts", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    fetchJson<{ success: boolean }>(`/alerts/${id}`, { method: "DELETE" }),
};

// ---- AI Agents ----

const AI_BASE = process.env.NEXT_PUBLIC_AI_URL ?? "http://localhost:8008/api/v1";

async function fetchAI<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${AI_BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`AI API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const aiApi = {
  getAgents: () => fetchAI<AIAgent[]>("/ai/agents"),
  chat: (message: string, agentType: string, userId = "default") =>
    fetchAI<ChatResponse>("/ai/chat", {
      method: "POST",
      body: JSON.stringify({ message, agent_type: agentType, user_id: userId }),
    }),
  clearChat: (agentType: string, userId = "default") =>
    fetchAI<{ status: string }>("/ai/chat/clear", {
      method: "POST",
      body: JSON.stringify({ agent_type: agentType, user_id: userId }),
    }),
  getAutoTradingStatus: () =>
    fetchAI<{ enabled: boolean; last_run: string | null; trades_today: number; total_pnl: number }>("/ai/auto-trading/status"),
  toggleAutoTrading: (enabled: boolean) =>
    fetchAI<{ enabled: boolean }>("/ai/auto-trading/toggle", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
  getAutoTradingHistory: () =>
    fetchAI<Array<{ timestamp: string; analysis: string; executed: number; trades: Array<{ symbol: string; action: string; amount_usd: number }> }>>("/ai/auto-trading/history"),
  analyzePerformance: (metrics: Record<string, unknown>) =>
    fetchAI<{ analysis: string; provider: string; model: string }>("/ai/analyze-performance", {
      method: "POST",
      body: JSON.stringify({ metrics }),
    }),
};

// ---- Analytics ----

export const analyticsApi = {
  getMetrics: () => fetchJson<AnalyticsMetrics>("/risk/analytics/metrics"),
  getEquityCurve: () => fetchJson<EquityPoint[]>("/risk/analytics/equity"),
  getStrategyComparison: () =>
    fetchJson<StrategyComparison[]>("/risk/analytics/strategies"),
  getTradingActivity: () =>
    fetchJson<TradingActivity[]>("/risk/analytics/activity"),
  getRiskMetrics: () => fetchJson<RiskMetrics>("/risk/metrics"),
};
