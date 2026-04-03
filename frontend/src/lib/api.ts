// ============================================================
// Okamoey Trading Platform - API Client
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

// ---- Prices / Market Data ----

export const pricesApi = {
  getOverview: () => fetchJson<MarketOverview>("/markets/overview"),
  getCrypto: () => fetchJson<CryptoPrice[]>("/prices/crypto"),
  getCryptoBySymbol: (symbol: string) =>
    fetchJson<CryptoPrice>(`/prices/crypto/${symbol}`),
  getStocks: () => fetchJson<CryptoPrice[]>("/prices/stocks"),
  getFearGreed: () =>
    fetchJson<{ value: number; label: string }>("/markets/fear-greed"),
  searchAssets: (query: string, limit = 20) =>
    fetchJson<SearchResponse>(`/prices/search?q=${encodeURIComponent(query)}&limit=${limit}`),
  getAllCryptos: (limit = 20, page = 1) =>
    fetchJson<AllCryptosResponse>(`/markets/all?limit=${limit}&page=${page}`),
  getOHLCV: (symbol: string, interval = "1d", limit = 90) =>
    fetchJson<OHLCVPoint[]>(
      `/prices/history/${encodeURIComponent(symbol)}?interval=${interval}&limit=${limit}`,
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

// ---- Analytics ----

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
  // Auto-trading
  getAutoTradingStatus: () =>
    fetchAI<{ enabled: boolean; last_run: string | null; trades_today: number; total_pnl: number }>("/ai/auto-trading/status"),
  toggleAutoTrading: (enabled: boolean) =>
    fetchAI<{ enabled: boolean }>("/ai/auto-trading/toggle", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
  getAutoTradingHistory: () =>
    fetchAI<Array<{ timestamp: string; analysis: string; executed: number; trades: Array<{ symbol: string; action: string; amount_usd: number }> }>>("/ai/auto-trading/history"),
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
