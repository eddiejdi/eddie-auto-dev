-- Migration: Criar tabela btc.news_sentiment para armazenar sentimento de notícias crypto
-- Executar com: psql -h 192.168.15.2 -p 5433 -U postgres -d btc_trading -f create_news_sentiment.sql

SET search_path TO btc;

CREATE TABLE IF NOT EXISTS btc.news_sentiment (
    id              SERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source          VARCHAR(50) NOT NULL,       -- coindesk, cointelegraph, decrypt, etc.
    title           TEXT NOT NULL,
    url             TEXT NOT NULL,
    coin            VARCHAR(10) NOT NULL,        -- BTC, ETH, XRP, SOL, DOGE, ADA, GENERAL
    sentiment       FLOAT NOT NULL DEFAULT 0.0,  -- -1.0 (bearish) a 1.0 (bullish)
    confidence      FLOAT NOT NULL DEFAULT 0.0,  -- 0.0 a 1.0
    category        VARCHAR(50),                 -- regulation, adoption, hack, price, macro, defi
    summary         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_news_url UNIQUE (url)
);

-- Índices para consultas rápidas pelo exporter
CREATE INDEX IF NOT EXISTS idx_news_sentiment_coin_ts
    ON btc.news_sentiment (coin, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_news_sentiment_ts
    ON btc.news_sentiment (timestamp DESC);

-- Comentários
COMMENT ON TABLE btc.news_sentiment IS 'Sentimento de notícias crypto extraído via RSS + Ollama';
COMMENT ON COLUMN btc.news_sentiment.sentiment IS 'Score de sentimento: -1.0 bearish a 1.0 bullish';
COMMENT ON COLUMN btc.news_sentiment.confidence IS 'Confiança do Ollama na classificação: 0.0 a 1.0';
COMMENT ON COLUMN btc.news_sentiment.category IS 'Categoria: regulation, adoption, hack, price, macro, defi';
