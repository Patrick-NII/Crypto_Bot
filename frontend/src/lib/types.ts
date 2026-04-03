// ============================================================
// Okamoey Trading Platform - Shared TypeScript Types
// ============================================================

// --- Market Data ---

export interface CryptoPrice {
  symbol: string;
  name: string;
  price: number;
  change_24h: number;
  change_pct_24h: number;
  volume_24h: number;
  market_cap: number;
  sparkline?: number[];
}

export interface StockPrice {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  volume: number;
}

export interface MarketOverview {
  crypto: CryptoPrice[];
  stocks: StockPrice[];
  fear_greed_index: number;
  fear_greed_label: string;
  total_market_cap: number;
  btc_dominance: number;
}

// --- Portfolio ---

export interface Portfolio {
  id: string;
  name: string;
  description?: string;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  positions: Position[];
  created_at: string;
  updated_at: string;
}

export interface Position {
  id: string;
  portfolio_id: string;
  symbol: string;
  asset_type: "crypto" | "stock" | "etf";
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  pnl: number;
  pnl_pct: number;
  stop_loss?: number;
  take_profit?: number;
  created_at: string;
}

export interface PortfolioAllocation {
  asset_type: string;
  value: number;
  percentage: number;
  color: string;
}

export interface Transaction {
  id: string;
  portfolio_id: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  total: number;
  fee: number;
  timestamp: string;
}

// --- Trading ---

export type OrderSide = "buy" | "sell";
export type OrderType = "market" | "limit" | "stop_loss";
export type OrderStatus = "open" | "filled" | "cancelled" | "failed" | "partial";

export interface Order {
  id: string;
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  quantity: number;
  price?: number;
  stop_price?: number;
  filled_price?: number;
  status: OrderStatus;
  fee: number;
  created_at: string;
  filled_at?: string;
}

export interface PaperBalance {
  currency: string;
  available: number;
  reserved: number;
  total: number;
}

export interface TradeResult {
  order_id: string;
  status: OrderStatus;
  filled_price?: number;
  filled_quantity?: number;
  fee?: number;
  message?: string;
}

// --- Strategies ---

export interface Strategy {
  id: string;
  name: string;
  description: string;
  status: "active" | "inactive";
  parameters: Record<string, string | number | boolean>;
  performance?: StrategyPerformance;
  created_at: string;
}

export interface StrategyPerformance {
  total_trades: number;
  win_rate: number;
  avg_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
}

export interface Signal {
  strategy_id: string;
  symbol: string;
  action: "buy" | "sell" | "hold";
  confidence: number;
  reason: string;
  timestamp: string;
}

// --- Alerts ---

export type AlertType = "price_above" | "price_below" | "pct_change";
export type AlertChannel = "email" | "push" | "sms";
export type AlertStatus = "active" | "triggered" | "expired" | "disabled";

export interface Alert {
  id: string;
  symbol: string;
  alert_type: AlertType;
  value: number;
  channel: AlertChannel;
  status: AlertStatus;
  created_at: string;
  triggered_at?: string;
}

export interface CreateAlertPayload {
  symbol: string;
  alert_type: AlertType;
  value: number;
  channel: AlertChannel;
}

// --- Analytics ---

export interface AnalyticsMetrics {
  sharpe_ratio: number;
  win_rate: number;
  max_drawdown: number;
  total_pnl: number;
  total_trades: number;
  avg_trade_return: number;
  volatility: number;
  var_95: number;
  sortino_ratio: number;
  calmar_ratio: number;
}

export interface EquityPoint {
  date: string;
  value: number;
}

export interface StrategyComparison {
  name: string;
  trades: number;
  win_rate: number;
  pnl: number;
  sharpe: number;
}

export interface TradingActivity {
  day: string;
  hour: number;
  count: number;
}

// --- Risk ---

export interface RiskMetrics {
  portfolio_var: number;
  portfolio_volatility: number;
  beta: number;
  correlation_matrix: Record<string, Record<string, number>>;
  position_risk: PositionRisk[];
}

export interface PositionRisk {
  symbol: string;
  weight: number;
  var_contribution: number;
  volatility: number;
}

// --- Search & Market Discovery ---

export interface AssetSearchResult {
  symbol: string;
  name: string;
  asset_type: "crypto" | "stock" | "etf";
  price?: number;
  change_pct_24h?: number;
  market_cap?: number;
}

export interface SearchResponse {
  results: AssetSearchResult[];
  total: number;
}

export interface CryptoMarketData {
  symbol: string;
  name: string;
  price: number;
  change_24h: number;
  change_pct_24h: number;
  volume_24h: number;
  market_cap: number;
  sparkline?: number[];
  rank?: number;
  // Extra fields from CoinGecko fallback
  id?: string;
  image?: string;
  current_price?: number;
  market_cap_rank?: number;
  price_change_percentage_24h?: number;
  total_volume?: number;
  sparkline_in_7d?: number[] | null;
  high_24h?: number;
  low_24h?: number;
  circulating_supply?: number;
  total_supply?: number;
  ath?: number;
  ath_change_percentage?: number;
}

export interface AllCryptosResponse {
  data: CryptoMarketData[];
  total: number;
  page: number;
  limit: number;
}

export interface OHLCVPoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// --- AI Agents ---

export interface AIAgent {
  type: string;
  name: string;
  description: string;
  capabilities: string[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: number;
  provider?: string;
  model?: string;
}

export interface ChatResponse {
  reply: string;
  agent_type: string;
  agent_name: string;
  provider: string;
  model: string;
  complexity: string;
}
