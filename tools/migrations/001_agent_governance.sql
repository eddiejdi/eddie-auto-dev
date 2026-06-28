-- Migration: 001_agent_governance
-- Descrição: Cria infraestrutura do Agent Governance Layer (Fase 0)
-- Tabelas: agent_actions, schema_migrations
-- Views: agent_audit_log

-- ── Tabela de controle de migrations ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Tabela principal de intenções e ações dos agentes ────────────────────
CREATE TABLE IF NOT EXISTS agent_actions (
    id                   SERIAL PRIMARY KEY,
    intent_id            TEXT UNIQUE NOT NULL,
    agent_id             TEXT NOT NULL,
    action_type          TEXT NOT NULL,
    -- restart | deploy | modify | delete | create | query | config | other
    description          TEXT NOT NULL,
    target               TEXT,
    -- serviço, arquivo, host, URL do recurso afetado
    risk_level           TEXT NOT NULL DEFAULT 'medium',
    -- none | low | medium | high | critical
    status               TEXT NOT NULL DEFAULT 'pending',
    -- pending | approved | rejected | in_progress | done | failed | expired
    approved_by          TEXT,
    telegram_msg_id      BIGINT,
    context_snapshot     JSONB,
    -- snapshot do ambiente/memória no momento da declaração
    outcome              TEXT,
    error_detail         TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at          TIMESTAMPTZ,
    -- quando aprovado/rejeitado/expirado
    executed_at          TIMESTAMPTZ,
    -- quando a execução começou
    completed_at         TIMESTAMPTZ
    -- quando a execução terminou (done/failed)
);

-- ── Índices ───────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_agent_actions_agent_id
    ON agent_actions (agent_id);

CREATE INDEX IF NOT EXISTS idx_agent_actions_status
    ON agent_actions (status);

CREATE INDEX IF NOT EXISTS idx_agent_actions_created_at
    ON agent_actions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_actions_risk_status
    ON agent_actions (risk_level, status);

CREATE INDEX IF NOT EXISTS idx_agent_actions_target
    ON agent_actions (target)
    WHERE target IS NOT NULL;

-- ── View de auditoria (leitura fácil para agentes e dashboards) ──────────
CREATE OR REPLACE VIEW agent_audit_log AS
SELECT
    intent_id,
    agent_id,
    action_type,
    description,
    target,
    risk_level,
    status,
    approved_by,
    EXTRACT(EPOCH FROM (resolved_at - created_at))::INT   AS approval_wait_seconds,
    EXTRACT(EPOCH FROM (completed_at - executed_at))::INT AS execution_seconds,
    outcome,
    error_detail,
    context_snapshot,
    created_at,
    completed_at
FROM agent_actions
ORDER BY created_at DESC;

-- ── Registrar esta migration ──────────────────────────────────────────────
INSERT INTO schema_migrations (version, description)
VALUES ('001', 'Agent Governance Layer: tabela agent_actions + view agent_audit_log')
ON CONFLICT (version) DO NOTHING;
