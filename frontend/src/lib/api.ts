// ============================================================
// Okamoey Trading Platform - API Client
// Binance API via local proxy (primary) + Gateway fallback
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
const BINANCE_PROXY = "http://localhost:3001";
const AI_BASE = process.env.NEXT_PUBLIC_AI_URL ?? "http://localhost:8008/api/v1";

// ---- Helpers ----

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);
  try {
    const res = await fetch(`${API_BASE}${url}`, {
      headers: { "Content-Type": "application/json", ...init?.headers },
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
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
      headers: { "Content-Type": "application/json", ...init?.headers },
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`Binance ${res.status}`);
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchAI<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const res = await fetch(`${AI_BASE}${url}`, {
      headers: { "Content-Type": "application/json", ...init?.headers },
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`AI API ${res.status}`);
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

function getActiveCurrency(): string {
  if (typeof window === "undefined") return "usd";
  return localStorage.getItem("okamoey-currency") || "usd";
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

// In-memory cache to avoid hammering Binance on every page nav
let _tickerCache: { data: BinanceTicker[]; ts: number } | null = null;
const TICKER_CACHE_MS = 10000; // 10s cache

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
    const tickers = await getAllTickers();

    // Sort by quote volume (proxy for market cap)
    const sorted = [...tickers].sort((a, b) => parseFloat(b.quoteVolume) - parseFloat(a.quoteVolume)).slice(0, limit);

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
          // Extra fields for pages
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
  },

  getOHLCV: async (symbol: string, interval = "1d", limit = 90): Promise<OHLCVPoint[]> => {
    // Map our interval labels to Binance kline intervals
    const intervalMap: Record<string, string> = {
      "1m": "1m", "5m": "5m", "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w",
    };
    const binanceInterval = intervalMap[interval] || "1h";
    const pair = `${symbol.toUpperCase()}USDT`;

    try {
      const data = await fetchBinance<number[][]>(`/klines?symbol=${pair}&interval=${binanceInterval}&limit=${limit}`);
      return data.map((k) => ({
        time: Math.floor(Number(k[0]) / 1000),
        open: parseFloat(String(k[1])),
        high: parseFloat(String(k[2])),
        low: parseFloat(String(k[3])),
        close: parseFloat(String(k[4])),
        volume: parseFloat(String(k[5])),
      }));
    } catch {
      return [];
    }
  },

  getFearGreed: async (): Promise<{ value: number; label: string }> => {
    try {
      const r = await fetch("https://api.alternative.me/fng/?limit=1&format=json");
      const d = await r.json();
      const e = d?.data?.[0];
      return { value: Number(e?.value ?? 50), label: String(e?.value_classification ?? "Neutral") };
    } catch {
      return { value: 50, label: "Neutral" };
    }
  },

  searchAssets: async (query: string): Promise<SearchResponse> => {
    const tickers = await getAllTickers();
    const q = query.toUpperCase();
    const matches = tickers
      .filter((t) => t.symbol.replace("USDT", "").includes(q))
      .slice(0, 20)
      .map((t) => ({
        symbol: t.symbol.replace("USDT", ""),
        name: t.symbol.replace("USDT", ""),
        asset_type: "crypto" as const,
      }));
    return { results: matches, total: matches.length };
  },

  getOverview: () => fetchJson<MarketOverview>("/markets/overview"),
  getCrypto: () => fetchJson<CryptoPrice[]>("/prices/crypto"),
  getCryptoBySymbol: (symbol: string) => fetchJson<CryptoPrice>(`/prices/crypto/${symbol}`),
  getStocks: () => fetchJson<CryptoPrice[]>("/prices/stocks"),
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
  list: () => fetchJson<Portfolio[]>("/portfolios"),
  get: (id: string) => fetchJson<Portfolio>(`/portfolios/${id}`),
  create: (data: { name: string; description?: string }) =>
    fetchJson<Portfolio>("/portfolios", { method: "POST", body: JSON.stringify(data) }),
  getPositions: (portfolioId: string) => fetchJson<Position[]>(`/portfolios/${portfolioId}/positions`),
  getTransactions: (portfolioId: string) => fetchJson<Transaction[]>(`/portfolios/${portfolioId}/transactions`),
  closePosition: (positionId: string) => fetchJson<TradeResult>(`/positions/${positionId}/close`, { method: "POST" }),
  updateStopLoss: (positionId: string, stopLoss: number) =>
    fetchJson<Position>(`/positions/${positionId}`, { method: "PATCH", body: JSON.stringify({ stop_loss: stopLoss }) }),
};

// ---- Trading ----

export const tradingApi = {
  getBalances: async (): Promise<PaperBalance[]> => {
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
  },

  placeOrder: async (data: {
    symbol: string; side: OrderSide; order_type: OrderType; quantity: number; price?: number;
  }): Promise<TradeResult> => {
    const params: Record<string, string> = {
      symbol: `${data.symbol}USDT`,
      side: data.side.toUpperCase(),
      type: data.order_type === "market" ? "MARKET" : "LIMIT",
    };
    if (data.order_type === "market") {
      params.quoteOrderQty = String(Math.round(data.quantity * 100) / 100);
    } else {
      params.quantity = String(data.quantity);
      if (data.price) params.price = String(data.price);
      params.timeInForce = "GTC";
    }
    const result = await binanceApi.placeOrder(params as { symbol: string; side: string; type: string; quantity?: string; quoteOrderQty?: string });
    return {
      order_id: String(result.orderId || ""),
      status: "open" as const,
      filled_price: Number(result.price || 0),
      filled_quantity: Number(result.executedQty || 0),
      message: `Order placed: ${result.status}`,
    } as TradeResult;
  },

  getOrders: async (): Promise<Order[]> => {
    try {
      const orders = await binanceApi.getOpenOrders();
      return orders as unknown as Order[];
    } catch {
      return [];
    }
  },

  cancelOrder: (orderId: string) =>
    fetchJson<{ success: boolean }>(`/orders/${orderId}/cancel`, { method: "POST" }),
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
  list: () => fetchJson<Strategy[]>("/ml/strategies"),
  get: (id: string) => fetchJson<Strategy>(`/ml/strategies/${id}`),
  generateSignal: (strategyId: string, symbol: string) =>
    fetchJson<Signal>(`/ml/strategies/${strategyId}/signal`, { method: "POST", body: JSON.stringify({ symbol }) }),
  updateParams: (strategyId: string, params: Record<string, unknown>) =>
    fetchJson<Strategy>(`/ml/strategies/${strategyId}`, { method: "PATCH", body: JSON.stringify({ parameters: params }) }),
};

// ---- Alerts ----

export const alertsApi = {
  list: () => fetchJson<Alert[]>("/alerts"),
  create: (data: CreateAlertPayload) => fetchJson<Alert>("/alerts", { method: "POST", body: JSON.stringify(data) }),
  delete: (id: string) => fetchJson<{ success: boolean }>(`/alerts/${id}`, { method: "DELETE" }),
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
    fetchAI<Array<{ timestamp: string; analysis: string; executed: number; trades: Array<{ symbol: string; action: string; amount_usd: number }> }>>("/ai/auto-trading/history"),
  analyzePerformance: (metrics: Record<string, unknown>) =>
    fetchAI<{ analysis: string; provider: string; model: string }>("/ai/analyze-performance", { method: "POST", body: JSON.stringify({ metrics }) }),
};

// ---- Analytics ----

export const analyticsApi = {
  getMetrics: () => fetchJson<AnalyticsMetrics>("/risk/analytics/metrics"),
  getEquityCurve: () => fetchJson<EquityPoint[]>("/risk/analytics/equity"),
  getStrategyComparison: () => fetchJson<StrategyComparison[]>("/risk/analytics/strategies"),
  getTradingActivity: () => fetchJson<TradingActivity[]>("/risk/analytics/activity"),
  getRiskMetrics: () => fetchJson<RiskMetrics>("/risk/metrics"),
};
