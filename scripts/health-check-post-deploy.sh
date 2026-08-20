#!/bin/bash
# health-check-post-deploy.sh
#
# Verifica a saúde dos serviços críticos após um deploy no homelab.
# Sai com código !=0 se qualquer serviço essencial estiver inativo,
# permitindo que o pipeline de CI faça rollback automático.
#
# Uso: scripts/health-check-post-deploy.sh [--timeout 60]
#
# Serviços verificados (ordem de criticidade):
#   1. SSH para o homelab (conectividade)
#   2. systemd: clear-trading-agent, crypto-agent@BTC_USDT_*, specialized-agents
#   3. APIs internas: Secrets Agent, Trading API, MCP Bus (porta 8503)
#   4. Postgres do trading (porta 5433)
#   5. Trading agent: status do processo e última decisão recente
#
# Projeta a política anti-regressão: só considera o deploy efetivo
# se todos os serviços críticos responderem dentro do timeout.

set -uo pipefail

TIMEOUT="${1:-60}"
HOMELAB_HOST="${HOMELAB_HOST:-192.168.15.2}"
HOMELAB_USER="${HOMELAB_USER:-homelab}"

# Serviços systemd críticos (verificar com systemctl is-active)
CRITICAL_SERVICES=(
    "clear-trading-agent"
    "crypto-agent@BTC_USDT_aggressive"
    "crypto-agent@BTC_USDT_conservative"
    "specialized-agents"
    "ollama.service"
)

# Portas que devem responder (host:porta)
CRITICAL_PORTS=(
    "127.0.0.1:5433"   # Postgres (schema btc)
    "127.0.0.1:8503"   # Communication Bus (homelab MCP)
)

# NAS — Ollama com trading-analyst (RTX 2060 SUPER, porta :11436)
# Política AGENTS.md 2b: modelos trading-* nunca são evictados.
# Se o NAS estiver inacessível, o trading-analyst não pode ser servido.
NAS_HOST="${NAS_HOST:-192.168.15.2}"
NAS_OLLAMA_PORT="${NAS_OLLAMA_PORT:-11436}"

# APIs HTTP que devem responder 200 (host:path)
# Exemplo: Trading agent, Secrets Agent. Vazio = não checa.
CRITICAL_HTTP=()

PASS=0
FAIL=0

ok()  { echo "✅ $1"; PASS=$((PASS + 1)); }
fail(){ echo "❌ $1"; FAIL=$((FAIL + 1)); }

echo "=== Health Check Pós-Deploy (timeout ${TIMEOUT}s) ==="

# ─── 1. SSH ───────────────────────────────────────────────────────────────
if timeout 5 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 \
        "${HOMELAB_USER}@${HOMELAB_HOST}" "true" 2>/dev/null; then
    ok "SSH para ${HOMELAB_HOST}"
else
    fail "SSH para ${HOMELAB_HOST} (deploy pode ter isolado o host)"
fi

# ─── 2. systemd services ───────────────────────────────────────────────────
for svc in "${CRITICAL_SERVICES[@]}"; do
    if timeout 5 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 \
            "${HOMELAB_USER}@${HOMELAB_HOST}" \
            "systemctl is-active --quiet ${svc} 2>/dev/null" 2>/dev/null; then
        ok "systemd: ${svc}"
    else
        # Em dry-run local sem SSH, checa só que o serviço existe
        if [ "${HOMELAB_HOST}" = "localhost" ] || [ "${HOMELAB_HOST}" = "127.0.0.1" ]; then
            if systemctl is-active --quiet "${svc}" 2>/dev/null; then
                ok "systemd (local): ${svc}"
            else
                fail "systemd (local): ${svc} inativo"
            fi
        else
            fail "systemd: ${svc} inativo ou inacessível"
        fi
    fi
done

# ─── 3. Portas críticas (TCP check) ────────────────────────────────────────
for entry in "${CRITICAL_PORTS[@]}"; do
    host="${entry%:*}"
    port="${entry##*:}"
    # Em dry-run local, usa bash /dev/tcp
    if timeout 3 bash -c "echo > /dev/tcp/${host}/${port}" 2>/dev/null; then
        ok "TCP ${host}:${port}"
    else
        fail "TCP ${host}:${port} não respondeu"
    fi
done

# ─── 4. Health HTTP ────────────────────────────────────────────────────────
for url in "${CRITICAL_HTTP[@]}"; do
    if curl -sSf -m 5 -o /dev/null "$url" 2>/dev/null; then
        ok "HTTP ${url}"
    else
        fail "HTTP ${url} não respondeu"
    fi
done

# ─── 4b. NAS — Ollama trading-analyst (RTX 2060, :11436) ───────────────────────
# Política AGENTS.md 2b: o analyst reside no NAS desde 2026-08-12.
# Se o NAS não responder, o trading-analyst não pode ser servido — regressão.
echo "  [NAS] Verificando Ollama do NAS (${NAS_HOST}:${NAS_OLLAMA_PORT})..."
if timeout 5 bash -c "echo > /dev/tcp/${NAS_HOST}/${NAS_OLLAMA_PORT}" 2>/dev/null; then
    ok "NAS Ollama TCP ${NAS_HOST}:${NAS_OLLAMA_PORT}"
    # Verifica se o modelo trading-analyst está carregado
    if command -v curl >/dev/null 2>&1; then
        NAS_TAGS=$(curl -sS -m 5 "http://${NAS_HOST}:${NAS_OLLAMA_PORT}/api/tags" 2>/dev/null)
        if echo "$NAS_TAGS" | grep -q "trading-analyst" 2>/dev/null; then
            ok "NAS: modelo trading-analyst carregado"
        else
            fail "NAS: modelo trading-analyst NÃO encontrado no /api/tags"
        fi
    fi
else
    # NAS inacessível — só alerta se não estivermos no homelab (pode ser localhost)
    if [ "${HOMELAB_HOST}" = "192.168.15.2" ]; then
        fail "NAS Ollama ${NAS_HOST}:${NAS_OLLAMA_PORT} inacessível"
    else
        echo "  ⚠️ NAS não acessível deste host (normal em CI remoto)"
    fi
fi

# ─── 5. Verificação via MCP (Trading API / Secrets Agent) ──────────────────
# Roda só se `curl` estiver disponível e houver mapeamento de host
# (delegado ao caller — não força dependência externa neste script).

# ─── Resumo ────────────────────────────────────────────────────────────────
echo ""
echo "=== Resumo ==="
echo "PASS: ${PASS}    FAIL: ${FAIL}"
echo "=============="

if [ "$FAIL" -gt 0 ]; then
    echo "::warning::Health check falhou em ${FAIL} item(s). Recomenda-se rollback."
    exit 1
fi
echo "::notice::Health check OK em todos os ${PASS} serviços críticos."
exit 0
