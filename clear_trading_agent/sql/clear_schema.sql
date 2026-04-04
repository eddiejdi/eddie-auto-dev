-- =============================================================
-- Schema PostgreSQL para Clear Trading Agent (B3 / MT5)
-- Schema: clear (separado do schema btc para crypto)
-- Porta: 5433 (mesmo server, schema diferente)
-- =============================================================

CREATE SCHEMA IF NOT EXISTS clear;
SET search_path TO clear, public;

-- Tabela de trades
CREATE TABLE IF NOT EXISTS trades (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    side            VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),
    price           NUMERIC(18, 4) NOT NULL,
    volume          NUMERIC(18, 4) NOT NULL DEFAULT 0,
    order_type      VARCHAR(20) DEFAULT 'market',
    order_id        VARCHAR(100),
    pnl             NUMERIC(18, 4),
    pnl_pct         NUMERIC(10, 4),
    dry_run         BOOLEAN NOT NULL DEFAULT TRUE,
    asset_class     VARCHAR(20) DEFAULT 'equity',
    commission      NUMERIC(18, 6) DEFAULT 0,
    metadata        JSONB,
    profile         VARCHAR(50) DEFAULT 'default',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clear_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_clear_trades_created ON trades(created_at);
CREATE INDEX IF NOT EXISTS idx_clear_trades_side ON trades(side);
CREATE INDEX IF NOT EXISTS idx_clear_trades_dry ON trades(dry_run);

-- Tabela de decisões (sinais gerados pelo modelo)
CREATE TABLE IF NOT EXISTS decisions (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    action          VARCHAR(10) NOT NULL,
    confidence      NUMERIC(6, 4) NOT NULL,
    price           NUMERIC(18, 4) NOT NULL,
    reason          TEXT,
    features        JSONB,
    executed        BOOLEAN DEFAULT FALSE,
    trade_id        INTEGER REFERENCES trades(id),
    profile         VARCHAR(50) DEFAULT 'default',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clear_decisions_symbol ON decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_clear_decisions_action ON decisions(action);
CREATE INDEX IF NOT EXISTS idx_clear_decisions_created ON decisions(created_at);

-- Tabela de estados do mercado (snapshots)
CREATE TABLE IF NOT EXISTS market_states (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    price           NUMERIC(18, 4) NOT NULL,
    rsi             NUMERIC(8, 4),
    momentum        NUMERIC(10, 6),
    volatility      NUMERIC(10, 6),
    trend           NUMERIC(8, 6),
    spread_pct      NUMERIC(10, 6),
    trade_flow      NUMERIC(8, 6),
    regime          VARCHAR(20),
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clear_mktstate_symbol ON market_states(symbol);
CREATE INDEX IF NOT EXISTS idx_clear_mktstate_created ON market_states(created_at);

-- Tabela de learning rewards
CREATE TABLE IF NOT EXISTS learning_rewards (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    trade_id        INTEGER REFERENCES trades(id),
    reward          NUMERIC(12, 6) NOT NULL,
    context         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clear_rewards_symbol ON learning_rewards(symbol);

-- Tabela de performance stats (snapshots diários)
CREATE TABLE IF NOT EXISTS performance_stats (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    period          VARCHAR(20) DEFAULT 'daily',
    total_trades    INTEGER DEFAULT 0,
    winning_trades  INTEGER DEFAULT 0,
    total_pnl       NUMERIC(18, 4) DEFAULT 0,
    win_rate        NUMERIC(6, 4) DEFAULT 0,
    metadata        JSONB,
    profile         VARCHAR(50) DEFAULT 'default',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clear_perf_symbol ON performance_stats(symbol);

-- Tabela de candles cacheados
CREATE TABLE IF NOT EXISTS candles (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    open_time       TIMESTAMPTZ NOT NULL,
    open            NUMERIC(18, 4) NOT NULL,
    high            NUMERIC(18, 4) NOT NULL,
    low             NUMERIC(18, 4) NOT NULL,
    close           NUMERIC(18, 4) NOT NULL,
    volume          NUMERIC(18, 4) DEFAULT 0,
    UNIQUE(symbol, timeframe, open_time)
);

CREATE INDEX IF NOT EXISTS idx_clear_candles_sym_tf ON candles(symbol, timeframe);

-- Tabela de controles de trade da IA
CREATE TABLE IF NOT EXISTS ai_trade_controls (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    profile         VARCHAR(50) DEFAULT 'default',
    regime          VARCHAR(20),
    min_confidence  NUMERIC(6, 4),
    min_interval    INTEGER,
    max_position_pct NUMERIC(6, 4),
    max_positions   INTEGER,
    source          VARCHAR(50) DEFAULT 'rag',
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clear_aitc_symbol ON ai_trade_controls(symbol);

-- Tabela de janelas de trading da IA
CREATE TABLE IF NOT EXISTS ai_trade_windows (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    profile         VARCHAR(50) DEFAULT 'default',
    entry_low       NUMERIC(18, 4),
    entry_high      NUMERIC(18, 4),
    target_sell     NUMERIC(18, 4),
    valid_until     TIMESTAMPTZ,
    source          VARCHAR(50) DEFAULT 'rag',
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clear_aitw_symbol ON ai_trade_windows(symbol);

-- Tabela de eventos fiscais (cada venda registrada)
CREATE TABLE IF NOT EXISTS tax_events (
    id              SERIAL PRIMARY KEY,
    timestamp       DOUBLE PRECISION NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    asset_class     VARCHAR(20) NOT NULL DEFAULT 'equity',
    trade_type      VARCHAR(20) NOT NULL DEFAULT 'swing',
    side            VARCHAR(10) NOT NULL,
    volume          NUMERIC(18, 4) NOT NULL,
    price           NUMERIC(18, 4) NOT NULL,
    gross_value     NUMERIC(18, 4) NOT NULL,
    pnl             NUMERIC(18, 4) DEFAULT 0,
    commission      NUMERIC(18, 6) DEFAULT 0,
    irrf            NUMERIC(18, 6) DEFAULT 0,
    tax_exempt      BOOLEAN DEFAULT FALSE,
    year_month      VARCHAR(7) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clear_tax_events_symbol ON tax_events(symbol, year_month);
CREATE INDEX IF NOT EXISTS idx_clear_tax_events_ym ON tax_events(year_month);

-- Resumo fiscal mensal (upsert por year_month)
CREATE TABLE IF NOT EXISTS tax_monthly_summary (
    id                          SERIAL PRIMARY KEY,
    year_month                  VARCHAR(7) NOT NULL UNIQUE,
    equity_swing_sales_total    NUMERIC(18, 4) DEFAULT 0,
    equity_swing_pnl            NUMERIC(18, 4) DEFAULT 0,
    equity_daytrade_pnl         NUMERIC(18, 4) DEFAULT 0,
    futures_swing_pnl           NUMERIC(18, 4) DEFAULT 0,
    futures_daytrade_pnl        NUMERIC(18, 4) DEFAULT 0,
    irrf_total                  NUMERIC(18, 6) DEFAULT 0,
    commissions_total           NUMERIC(18, 6) DEFAULT 0,
    equity_swing_exempt         BOOLEAN DEFAULT TRUE,
    total_tax_due               NUMERIC(18, 4) DEFAULT 0,
    events_count                INTEGER DEFAULT 0,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clear_tax_monthly_ym ON tax_monthly_summary(year_month);

-- Prejuízo acumulado por categoria fiscal (sem expiração)
CREATE TABLE IF NOT EXISTS tax_accumulated_losses (
    id              SERIAL PRIMARY KEY,
    category        VARCHAR(30) NOT NULL UNIQUE,
    amount          NUMERIC(18, 4) NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Permissões (ajustar conforme user do sistema)
-- GRANT ALL ON SCHEMA clear TO trading_user;
-- GRANT ALL ON ALL TABLES IN SCHEMA clear TO trading_user;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA clear TO trading_user;
