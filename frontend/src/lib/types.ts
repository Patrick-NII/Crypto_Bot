// ============================================================
// GlueTrade Trading Platform - Shared TypeScript Types
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
  is_default?: boolean;
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

export interface PortfolioBalanceSnapshot {
  currency: string;
  available: number;
  reserved: number;
  total: number;
}

export interface PortfolioHoldingSnapshot {
  symbol: string;
  available: number;
  reserved: number;
  total: number;
  price: number;
  value: number;
  change_pct_24h: number;
  stable: boolean;
}

export interface PortfolioSnapshotSummary {
  equity: number;
  cash: number;
  market_exposure: number;
  open_pnl: number;
  open_pnl_pct: number;
  day_change_value: number;
  day_change_pct: number;
  holdings_count: number;
  positions_count: number;
  open_orders_count: number;
}

export interface ExecutionFeedItem {
  id: string;
  source: "order" | "transaction" | "execution";
  order_id?: string | null;
  transaction_id?: string | null;
  portfolio_id?: string | null;
  symbol: string;
  side: "buy" | "sell";
  status: string;
  quantity: number;
  filled_quantity: number;
  requested_price?: number | null;
  execution_price?: number | null;
  notional: number;
  fee: number;
  exchange?: string | null;
  strategy?: string | null;
  notes?: string | null;
  timestamp: string;
  updated_at?: string | null;
}

export interface PortfolioSnapshot {
  updated_at: string;
  portfolio?: Portfolio | null;
  portfolios: Portfolio[];
  balances: PortfolioBalanceSnapshot[];
  holdings: PortfolioHoldingSnapshot[];
  positions: Position[];
  recent_transactions: Transaction[];
  execution_feed: ExecutionFeedItem[];
  summary: PortfolioSnapshotSummary;
  risk?: RiskMetrics | null;
}

// --- Trading ---

export type OrderSide = "buy" | "sell";
export type OrderType = "market" | "limit" | "stop_loss" | "take_profit" | "trailing_stop" | "oco";
export type OrderStatus = "pending" | "open" | "filled" | "partially_filled" | "cancelled" | "failed" | "expired";

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

export interface OrderPreflight {
  requested_symbol: string;
  resolved_symbol: string;
  side: "buy" | "sell";
  base_asset: string;
  quote_asset: string;
  input_quantity: string;
  adjusted_quantity: string;
  reference_price?: string | null;
  estimated_price?: string | null;
  estimated_notional?: string | null;
  estimated_fee?: string | null;
  fee_rate: string;
  min_notional?: string | null;
  available_quote?: string | null;
  available_base?: string | null;
  conversion_symbol?: string | null;
  conversion_side?: OrderSide | null;
  conversion_from_asset?: string | null;
  conversion_required_quantity?: string | null;
  conversion_estimated_spend?: string | null;
  can_execute: boolean;
  blocking_reason?: string | null;
  notes: string[];
}

export interface SymbolInfo {
  symbol: string;
  base_asset: string;
  quote_asset: string;
  step_size: string;
  tick_size: string;
  min_qty: string;
  max_qty: string;
  min_notional: string;
  base_precision: number;
  quote_precision: number;
  is_spot: boolean;
}

export type OrderWsEvent =
  | { event: "order_new"; order: Order }
  | { event: "order_update"; order: Order }
  | { event: "order_done"; order: Order }
  | { event: "warning"; message: string };

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

export type RiskProfileId = "conservative" | "moderate" | "aggressive" | "custom";
export type SubscriptionPlan = "discover" | "starter" | "pro" | "elite";
export type SubscriptionStatus = "trial" | "active" | "inactive" | "past_due" | "cancelled";
export type BillingCycle = "monthly" | "yearly";
export type AIBehaviorStyle = "gentle" | "balanced" | "assertive" | "aggressive";
export type AIAssistantTone = "concise" | "coach" | "analytical";
export type DeskChartType = "candlestick" | "line";
export type MarketMoversView = "gainers" | "losers" | "candidates";
export type MarketUniverseView = "all" | MarketMoversView;

export interface UserNotificationPreferences {
  email_enabled?: boolean;
  email_trades?: boolean;
  email_security?: boolean;
  email_deposits?: boolean;
  email_daily_recap?: boolean;
  email_weekly_recap?: boolean;
  email_strong_signals?: boolean;
  daily_recap_hour?: number;
}

export interface UserPreferences {
  crypto_desk?: {
    watchlist?: string[];
    selected_symbol?: string | null;
    chart_type?: DeskChartType;
    movers_view?: MarketMoversView;
    universe_view?: MarketUniverseView;
  };
  app?: {
    theme?: "dark" | "light";
    trading_mode?: "manual" | "auto";
  };
  notifications?: UserNotificationPreferences;
}

export interface RiskProfile {
  profile_id: RiskProfileId;
  max_position_size_pct: number;
  max_portfolio_drawdown_pct: number;
  default_stop_loss_pct: number;
  default_take_profit_pct: number;
  max_daily_trades: number;
  max_leverage: number;
  risk_per_trade_pct: number;
}

export interface RiskMetrics {
  total_value: number;
  risk_score: number;
  daily_var: number;
  var_pct: number;
  max_drawdown: number;
  max_drawdown_pct: number;
  sharpe_ratio?: number | null;
  volatility: number;
  correlation_risk: "low" | "medium" | "high";
  risk_level: "conservative" | "moderate" | "aggressive";
  concentration_pct: number;
  cash_ratio: number;
  warnings: string[];
  position_risk: PositionRisk[];
}

export interface PositionRisk {
  symbol: string;
  value: number;
  weight: number;
  var_contribution: number;
  volatility: number;
  risk_score: number;
}

export interface UserProfile {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  is_verified: boolean;
  risk_profile: RiskProfileId;
  subscription_plan: SubscriptionPlan;
  subscription_status: SubscriptionStatus;
  billing_cycle: BillingCycle;
  accepted_terms_at?: string | null;
  terms_version: string;
  ai_behavior_style: AIBehaviorStyle;
  ai_assistant_tone: AIAssistantTone;
  timezone?: string;
  language?: string;
  wallet_access_enabled: boolean;
  wallet_access_reason: string;
  connected_exchanges_count: number;
  live_trading_enabled: boolean;
  preferences: UserPreferences;
  created_at: string;
}

export interface ExchangeConnection {
  id: string;
  provider: string;
  label: string;
  api_key_hint: string;
  has_passphrase: boolean;
  sandbox_mode: boolean;
  can_trade: boolean;
  is_active: boolean;
  status: string;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExchangeProviderGuide {
  provider: string;
  label: string;
  supports_testnet: boolean;
  requires_passphrase: boolean;
  recommended_permissions: string[];
  setup_steps: string[];
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

// --- News & Market Intelligence ---

export interface NewsArticle {
  id: string;
  title: string;
  body: string;
  source: string;
  url: string;
  image: string;
  published_at: string;
  categories: string[];
  sentiment: number;
  impact: "high" | "medium" | "low";
}

export interface TrendingCoin {
  symbol: string;
  name: string;
  rank: number | null;
  thumb: string;
  score: number;
  price_btc: number;
}

export interface MarketSentiment {
  fear_greed: { value: number; label: string };
  news_sentiment: number;
  news_count: number;
  overall: "bullish" | "bearish" | "neutral";
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
