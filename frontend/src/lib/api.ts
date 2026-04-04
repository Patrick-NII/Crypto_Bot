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

const BINANCE_PROXY = "http://localhost:3001";

async function fetchBinance<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BINANCE_PROXY}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) throw new Error(`Binance ${res.status}`);
  return res.json() as Promise<T>;
}

interface BinanceBalance {
  asset: string;
  free: number;
  locked: number;
}

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

export const tradingApi = {
  getBalances: () =>
    withFallback(
      () => fetchJson<PaperBalance[]>("/trades/balances"),
      async () => {
        const balances = await binanceApi.getBalances();
        return balances.map((b) => ({
          currency: b.asset,
          available: b.free,
          reserved: b.locked,
          total: b.free + b.locked,
        }));
      },
    ),
  placeOrder: (data: {
    symbol: string;
    side: OrderSide;
    order_type: OrderType;
    quantity: number;
    price?: number;
    stop_price?: number;
  }) =>
    withFallback(
      () => fetchJson<TradeResult>("/orders", {
        method: "POST",
        body: JSON.stringify(data),
      }),
      async () => {
        // Live Binance order via proxy
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
          message: `Order placed on Binance: ${result.status}`,
        } as TradeResult;
      },
    ),
  getOrders: (params?: { status?: string }) => {
    const qs = params?.status ? `?status=${params.status}` : "";
    return withFallback(
      () => fetchJson<Order[]>(`/orders${qs}`),
      async () => {
        const orders = await binanceApi.getOpenOrders();
        return orders as unknown as Order[];
      },
    );
  },
  cancelOrder: (orderId: string) =>
    fetchJson<{ success: boolean }>(`/orders/${orderId}/cancel`, { method: "POST" }),
};

// ---- Signals (ML Service) ----

interface SignalData {
  symbol: string;
  action: string;
  confidence: number;
  score: number;
  reasoning: string;
  indicators: Array<{ name: string; value: number; signal: number; description: string }>;
  timestamp: string;
}

// Client-side signal generation using CoinGecko OHLC data
async function cgGenerateSignal(symbol: string): Promise<SignalData> {
  const cgId = SYM_TO_CG[symbol.toUpperCase()];
  if (!cgId) return { symbol, action: "HOLD", confidence: 0, score: 0, reasoning: "Unknown", indicators: [], timestamp: new Date().toISOString() };

  const ohlc = await fetchCG<number[][]>(`/coins/${cgId}/ohlc`, { vs_currency: "usd", days: "30" });
  const closes = ohlc.map((c) => c[4]);
  if (closes.length < 15) return { symbol, action: "HOLD", confidence: 0, score: 0, reasoning: "Insufficient data", indicators: [], timestamp: new Date().toISOString() };

  // RSI
  const gains: number[] = []; const losses: number[] = [];
  for (let i = 1; i < closes.length; i++) { const d = closes[i] - closes[i-1]; gains.push(Math.max(d,0)); losses.push(Math.max(-d,0)); }
  const period = 14;
  const avgGain = gains.slice(-period).reduce((a,b)=>a+b,0)/period;
  const avgLoss = losses.slice(-period).reduce((a,b)=>a+b,0)/period;
  const rsi = avgLoss === 0 ? 100 : 100 - 100/(1 + avgGain/avgLoss);
  const rsiSignal = rsi < 30 ? 0.7 : rsi < 45 ? 0.3 : rsi > 70 ? -0.7 : rsi > 55 ? -0.3 : 0;

  // EMA cross
  const ema = (arr: number[], p: number) => { const k=2/(p+1); const r=[arr[0]]; for(let i=1;i<arr.length;i++) r.push(arr[i]*k+r[i-1]*(1-k)); return r; };
  const e9 = ema(closes, 9); const e21 = ema(closes, 21);
  const emaDiff = e9[e9.length-1] - e21[e21.length-1];
  const prevDiff = e9[e9.length-2] - e21[e21.length-2];
  const emaSignal = (emaDiff > 0 && prevDiff <= 0) ? 0.7 : (emaDiff < 0 && prevDiff >= 0) ? -0.7 : emaDiff > 0 ? 0.3 : emaDiff < 0 ? -0.3 : 0;

  // Bollinger
  const sma20 = closes.slice(-20).reduce((a,b)=>a+b,0)/20;
  const std20 = Math.sqrt(closes.slice(-20).reduce((a,b)=>a+(b-sma20)**2,0)/20);
  const upper = sma20+2*std20; const lower = sma20-2*std20;
  const pos = (upper-lower) === 0 ? 0.5 : (closes[closes.length-1]-lower)/(upper-lower);
  const bbSignal = pos < 0.2 ? 0.6 : pos < 0.4 ? 0.2 : pos > 0.8 ? -0.6 : pos > 0.6 ? -0.2 : 0;

  // Composite
  const score = (rsiSignal*1.2 + emaSignal*1.1 + bbSignal*1.0) / 3.3;
  const action = score > 0.5 ? "STRONG_BUY" : score > 0.25 ? "BUY" : score > 0.08 ? "ACCUMULATE" : score > -0.08 ? "HOLD" : score > -0.25 ? "REDUCE" : score > -0.5 ? "SELL" : "STRONG_SELL";

  return {
    symbol: symbol.toUpperCase(),
    action,
    confidence: Math.min(Math.abs(score), 1),
    score: Math.round(score * 1000) / 1000,
    reasoning: `RSI=${rsi.toFixed(0)}, EMA${emaDiff>0?"+":"-"}, BB${pos<0.3?"low":pos>0.7?"high":"mid"}`,
    indicators: [
      { name: "RSI", value: Math.round(rsi), signal: rsiSignal, description: `RSI ${rsi.toFixed(0)} — ${rsi<30?"Oversold":rsi>70?"Overbought":"Neutral"}` },
      { name: "EMA Cross", value: Math.round(emaDiff*100)/100, signal: emaSignal, description: `EMA 9/21 ${emaDiff>0?"bullish":"bearish"}` },
      { name: "Bollinger", value: Math.round(pos*100)/100, signal: bbSignal, description: `Price at ${(pos*100).toFixed(0)}% of bands` },
    ],
    timestamp: new Date().toISOString(),
  };
}

export const signalsApi = {
  getSignal: (symbol: string) =>
    withFallback(
      () => fetchJson<SignalData>(`/ml/signals/${symbol}`),
      () => cgGenerateSignal(symbol),
    ),
  getAllSignals: () =>
    withFallback(
      () => fetchJson<{ signals: SignalData[] }>("/ml/signals").then(r => r.signals),
      async () => {
        const syms = ["BTC","ETH","SOL","BNB","XRP","ADA","DOGE","AVAX","DOT","LINK"];
        const results = await Promise.allSettled(syms.map(s => cgGenerateSignal(s)));
        return results.filter((r): r is PromiseFulfilledResult<SignalData> => r.status === "fulfilled").map(r => r.value);
      },
    ),
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
