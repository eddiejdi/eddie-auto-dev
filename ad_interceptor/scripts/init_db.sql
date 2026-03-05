CREATE SCHEMA IF NOT EXISTS ads;

CREATE TABLE IF NOT EXISTS ads.ad_requests (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64),
    timestamp TIMESTAMPTZ DEFAULT now(),
    domain VARCHAR(128),
    method VARCHAR(8),
    url TEXT,
    headers JSONB,
    body_raw BYTEA,
    body_json JSONB
);

CREATE TABLE IF NOT EXISTS ads.ad_responses (
    id SERIAL PRIMARY KEY,
    request_id INTEGER REFERENCES ads.ad_requests(id),
    status_code INTEGER,
    headers JSONB,
    body_raw BYTEA,
    body_json JSONB,
    has_nonce BOOLEAN,
    has_s2s_token BOOLEAN,
    has_signature BOOLEAN
);

CREATE TABLE IF NOT EXISTS ads.ad_test_results (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64),
    timestamp TIMESTAMPTZ DEFAULT now(),
    ad_loaded BOOLEAN,
    reward_granted BOOLEAN,
    ad_network VARCHAR(64),
    response_type VARCHAR(32)
);

CREATE TABLE IF NOT EXISTS ads.ad_templates (
    id SERIAL PRIMARY KEY,
    ad_network VARCHAR(64),
    response_template JSONB,
    static_fields JSONB,
    dynamic_fields JSONB,
    accuracy_score FLOAT
);
