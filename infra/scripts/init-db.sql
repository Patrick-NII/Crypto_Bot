-- =============================================================================
-- Okamoey Trading Platform - Database Initialization
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ─── Users & Auth ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    telegram_chat_id VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    risk_profile VARCHAR(20) DEFAULT 'moderate',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(500) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Portfolio ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    asset_type VARCHAR(20) NOT NULL, -- crypto, stock, etf, bond
    exchange VARCHAR(50),
    quantity DECIMAL(20, 8) NOT NULL DEFAULT 0,
    average_entry_price DECIMAL(20, 8) NOT NULL DEFAULT 0,
    current_price DECIMAL(20, 8) DEFAULT 0,
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    stop_loss_price DECIMAL(20, 8),
    take_profit_price DECIMAL(20, 8),
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    position_id UUID REFERENCES positions(id),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL, -- buy, sell
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    fee DECIMAL(20, 8) DEFAULT 0,
    exchange VARCHAR(50),
    order_id VARCHAR(100),
    strategy VARCHAR(50),
    notes TEXT,
    executed_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Market Data (TimescaleDB hypertable) ───────────────────────
CREATE TABLE IF NOT EXISTS price_history (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open DECIMAL(20, 8),
    high DECIMAL(20, 8),
    low DECIMAL(20, 8),
    close DECIMAL(20, 8),
    volume DECIMAL(20, 8)
);

SELECT create_hypertable('price_history', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_price_history_symbol_time
    ON price_history (symbol, time DESC);

-- ─── Trading Orders ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    portfolio_id UUID REFERENCES portfolios(id),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL, -- buy, sell
    order_type VARCHAR(20) NOT NULL, -- market, limit, stop_loss, take_profit, trailing_stop
    status VARCHAR(20) DEFAULT 'pending', -- pending, open, filled, partially_filled, cancelled, failed
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8),
    stop_price DECIMAL(20, 8),
    filled_quantity DECIMAL(20, 8) DEFAULT 0,
    filled_price DECIMAL(20, 8),
    fee DECIMAL(20, 8) DEFAULT 0,
    exchange VARCHAR(50),
    exchange_order_id VARCHAR(100),
    strategy VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Alerts ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    symbol VARCHAR(20),
    alert_type VARCHAR(30) NOT NULL, -- price_above, price_below, pct_change, volume_spike, rsi, drawdown
    condition_value DECIMAL(20, 8),
    message TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_triggered BOOLEAN DEFAULT FALSE,
    channel VARCHAR(20) DEFAULT 'telegram', -- telegram, email, push
    triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Risk Management ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    max_position_size_pct DECIMAL(5, 2) DEFAULT 10.0,
    max_portfolio_drawdown_pct DECIMAL(5, 2) DEFAULT 15.0,
    default_stop_loss_pct DECIMAL(5, 2) DEFAULT 5.0,
    default_take_profit_pct DECIMAL(5, 2) DEFAULT 15.0,
    max_daily_trades INT DEFAULT 20,
    max_leverage DECIMAL(5, 2) DEFAULT 1.0,
    risk_per_trade_pct DECIMAL(5, 2) DEFAULT 2.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── ML / Strategy Performance ──────────────────────────────────
CREATE TABLE IF NOT EXISTS strategy_performance (
    time TIMESTAMPTZ NOT NULL,
    strategy_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    total_pnl DECIMAL(20, 8) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    win_rate DECIMAL(5, 2),
    avg_trade_duration_hours DECIMAL(10, 2),
    parameters JSONB
);

SELECT create_hypertable('strategy_performance', 'time', if_not_exists => TRUE);

-- ─── Indexes ────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_positions_portfolio ON positions(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_transactions_portfolio ON transactions(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_alerts_user_active ON alerts(user_id, is_active);
