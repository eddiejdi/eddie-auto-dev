#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${REPO_ROOT}/patches"
TARGET_DIR="${TARGET_DIR:-/apps/crypto-trader/trading/btc_trading_agent}"
RUNTIME_ROOT="${RUNTIME_ROOT:-/apps/crypto-trader/trading}"
TRADING_VENV="${TRADING_VENV:-/apps/crypto-trader/.venv}"
ENVFILES_DIR="${ENVFILES_DIR:-/apps/crypto-trader/envfiles}"
SERVICE_USER="${SERVICE_USER:-btc-trading}"
SERVICE_GROUP="${SERVICE_GROUP:-btc-trading}"
SHARED_ENV="${ENVFILES_DIR}/shared-secrets.env"
TRADING_DB_ENV="${ENVFILES_DIR}/trading-database.env"
EXPORTERS_DIR="${RUNTIME_ROOT}/grafana/exporters"
SCRIPTS_DIR="${RUNTIME_ROOT}/scripts"
TOOLS_DIR="/apps/crypto-trader/tools"
SYSTEMD_HELPERS_DIR="${RUNTIME_ROOT}/systemd"
GRAFANA_PROVISIONING_DIR="${GRAFANA_PROVISIONING_DIR:-/home/homelab/monitoring/grafana/provisioning/dashboards}"
GRAFANA_DASHBOARD_BACKUP_DIR="${GRAFANA_DASHBOARD_BACKUP_DIR:-/home/homelab/monitoring/grafana/provisioning/dashboard_backups}"

CONSERVATIVE_SRC="${SOURCE_DIR}/config_BTC_USDT_conservative_optimized.json"
AGGRESSIVE_SRC="${SOURCE_DIR}/config_BTC_USDT_aggressive_optimized.json"
CONSERVATIVE_DST="${TARGET_DIR}/config_BTC_USDT_conservative.json"
AGGRESSIVE_DST="${TARGET_DIR}/config_BTC_USDT_aggressive.json"
BTC_DASHBOARD_SRC="${REPO_ROOT}/grafana/dashboards/btc_trading_monitor.json"
BTC_DASHBOARD_DST="${GRAFANA_PROVISIONING_DIR}/btc-trading-monitor.json"
BTC_DASHBOARD_DUPLICATE_PATHS=(
  "${GRAFANA_PROVISIONING_DIR}/btc_trading_monitor.json"
  "${GRAFANA_PROVISIONING_DIR}/btc_trading_dashboard_prometheus.json"
)

AGENT_SERVICES=(
  "crypto-agent@BTC_USDT_conservative.service"
  "crypto-agent@BTC_USDT_aggressive.service"
)

EXPORTER_SERVICES=(
  "crypto-exporter@BTC_USDT_conservative.service"
  "crypto-exporter@BTC_USDT_aggressive.service"
)

LEGACY_EXPORTER_SERVICES=(
  "autocoinbot-exporter.service"
  "autocoinbot-exporter@BTC_USDT_conservative.service"
  "autocoinbot-exporter@BTC_USDT_aggressive.service"
)

MANAGED_SYSTEMD_UNITS=(
  "crypto-agent@.service"
  "rss-sentiment-exporter.service"
  "candle-collector.service"
  "ollama-finetune.service"
  "ollama-gpu-coordinator.service"
)

require_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    echo "❌ Arquivo obrigatório ausente: ${path}" >&2
    exit 1
  fi
}

require_service_user() {
  if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
    echo "❌ Usuário ${SERVICE_USER} não existe neste host" >&2
    exit 1
  fi
}

require_secret_key() {
  local env_file="$1"
  local conservative_service="crypto-agent@BTC_USDT_conservative.service"
  local runtime_env=""
  local dot_env="${TARGET_DIR}/.env"

  if [[ -f "${env_file}" ]] && grep -Eq '^SECRETS_AGENT_API_KEY=.+' "${env_file}"; then
    return 0
  fi

  runtime_env="$(sudo systemctl show "${conservative_service}" -p Environment --value 2>/dev/null || true)"
  if [[ "${runtime_env}" == *"SECRETS_AGENT_API_KEY="* ]]; then
    echo "ℹ️ SECRETS_AGENT_API_KEY validada via systemd drop-in (${conservative_service})"
    return 0
  fi

  if [[ -f "${dot_env}" ]] \
    && grep -Eq '^KUCOIN_API_KEY=.+' "${dot_env}" \
    && grep -Eq '^KUCOIN_API_SECRET=.+' "${dot_env}" \
    && grep -Eq '^KUCOIN_API_PASSPHRASE=.+' "${dot_env}"; then
    echo "ℹ️ Credenciais KuCoin validadas via fallback controlado em ${dot_env}"
    return 0
  fi

  echo "❌ Secrets não encontrados em ${env_file}, no runtime do systemd ou em ${dot_env}" >&2
  exit 1
}

resolve_database_url() {
  local db_url=""
  local service_env=""

  service_env="$(sudo systemctl show "crypto-agent@BTC_USDT_aggressive.service" -p Environment --value 2>/dev/null || true)"
  db_url="$(printf '%s\n' "${service_env}" | tr ' ' '\n' | sed -n 's/^DATABASE_URL=//p' | tail -n1)"

  if [[ -z "${db_url}" && -f "${TRADING_DB_ENV}" ]]; then
    db_url="$(sed -n 's/^DATABASE_URL=//p' "${TRADING_DB_ENV}" | tail -n1)"
  fi

  if [[ -z "${db_url}" && -f "${SHARED_ENV}" ]]; then
    db_url="$(sed -n 's/^DATABASE_URL=//p' "${SHARED_ENV}" | tail -n1)"
  fi

  if [[ -z "${db_url}" ]]; then
    echo "❌ DATABASE_URL não encontrado no runtime do crypto-agent nem em ${TRADING_DB_ENV}/${SHARED_ENV}" >&2
    exit 1
  fi

  printf '%s\n' "${db_url}"
}

backup_if_present() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    sudo cp "${path}" "${path}.bak.$(date +%Y%m%d_%H%M%S)"
  fi
}

validate_ollama_models() {
  local models_env="${1:-/etc/crypto-agent/models.env}"
  local ollama_host="${OLLAMA_PLAN_HOST:-http://192.168.15.2:11434}"

  if [[ ! -f "${models_env}" ]]; then
    echo "⚠️  ${models_env} não encontrado — pulando validação de modelos Ollama" >&2
    return 0
  fi

  local model
  model="$(grep '^OLLAMA_PLAN_MODEL=' "${models_env}" 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1)"

  if [[ -z "${model}" ]]; then
    echo "⚠️  OLLAMA_PLAN_MODEL não definido em ${models_env} — pulando validação" >&2
    return 0
  fi

  echo "🔍 Verificando modelo Ollama '${model}' em ${ollama_host}..."

  local model_base
  model_base="${model%%:*}"
  if curl -sf --max-time 5 "${ollama_host}/api/tags" 2>/dev/null | \
      python3 -c "
import sys, json
data = json.load(sys.stdin)
names = [m['name'].split(':')[0] for m in data.get('models', [])]
sys.exit(0 if '${model_base}' in names else 1)" 2>/dev/null; then
    echo "  ✅ Modelo '${model}' confirmado no Ollama"
  else
    echo "❌ ERRO: Modelo '${model}' NÃO encontrado em ${ollama_host}" >&2
    echo "   Solução: ollama create ${model_base} -f models/Modelfile.${model_base}" >&2
    echo "   Ou:      OLLAMA_HOST=${ollama_host} ollama pull ${model}" >&2
    echo "   Depois:  Execute este script novamente" >&2
    exit 1
  fi
}

sync_runtime_file() {
  local src="$1"
  local dst="$2"

  require_file "${src}"
  sudo install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0755 "$(dirname "${dst}")"
  sudo install -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0644 "${src}" "${dst}"
}

sync_grafana_dashboard_file() {
  local src="$1"
  local dst="$2"

  require_file "${src}"
  sudo install -d -m 0755 "$(dirname "${dst}")"
  sudo install -m 0644 "${src}" "${dst}"
}

cleanup_btc_dashboard_duplicates() {
  local timestamp
  local duplicate=""

  timestamp="$(date +%Y%m%d_%H%M%S)"
  sudo install -d -m 0755 "${GRAFANA_DASHBOARD_BACKUP_DIR}"

  for duplicate in "${BTC_DASHBOARD_DUPLICATE_PATHS[@]}"; do
    if [[ -f "${duplicate}" ]]; then
      sudo mv "${duplicate}" \
        "${GRAFANA_DASHBOARD_BACKUP_DIR}/$(basename "${duplicate}").disabled.${timestamp}"
    fi
  done
}

sync_btc_grafana_dashboard() {
  backup_if_present "${BTC_DASHBOARD_DST}"
  sync_grafana_dashboard_file "${BTC_DASHBOARD_SRC}" "${BTC_DASHBOARD_DST}"
  cleanup_btc_dashboard_duplicates
}

restart_grafana_if_present() {
  if sudo docker ps --format '{{.Names}}' | grep -qx 'grafana'; then
    sudo docker restart grafana >/dev/null
    sleep 5
  fi
}

install_managed_units() {
  local unit=""
  for unit in "${MANAGED_SYSTEMD_UNITS[@]}"; do
    require_file "${REPO_ROOT}/systemd/${unit}"
    sudo install -m 0644 "${REPO_ROOT}/systemd/${unit}" "/etc/systemd/system/${unit}"
  done

  if [[ ! -d /etc/sudoers.d ]]; then
    sudo mkdir -p /etc/sudoers.d
  fi
  # Remove arquivo legado que define o mesmo alias TRADING_OLLAMA_CMDS
  sudo rm -f /etc/sudoers.d/trading-svc-ollama
  sudo install -m 0440 "${REPO_ROOT}/systemd/btc-trading-ollama.sudoers" \
    /etc/sudoers.d/btc-trading-ollama
  sudo visudo -cf /etc/sudoers.d/btc-trading-ollama >/dev/null
}

sync_trading_runtime() {
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/trading_agent.py" \
    "${TARGET_DIR}/trading_agent.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/sell_target_mixin.py" \
    "${TARGET_DIR}/sell_target_mixin.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/risk_guardian_mixin.py" \
    "${TARGET_DIR}/risk_guardian_mixin.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/position_manager_mixin.py" \
    "${TARGET_DIR}/position_manager_mixin.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/slot_exit_policy.py" \
    "${TARGET_DIR}/slot_exit_policy.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/fast_model.py" \
    "${TARGET_DIR}/fast_model.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/kucoin_api.py" \
    "${TARGET_DIR}/kucoin_api.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/profile_rules.py" \
    "${TARGET_DIR}/profile_rules.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/secrets_helper.py" \
    "${TARGET_DIR}/secrets_helper.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/prometheus_exporter.py" \
    "${TARGET_DIR}/prometheus_exporter.py"
  sync_runtime_file \
    "${REPO_ROOT}/grafana/exporters/rss_sentiment_exporter.py" \
    "${EXPORTERS_DIR}/rss_sentiment_exporter.py"
  sync_runtime_file \
    "${REPO_ROOT}/grafana/exporters/requirements.txt" \
    "${EXPORTERS_DIR}/requirements.txt"
  sync_runtime_file \
    "${REPO_ROOT}/scripts/candle_collector.py" \
    "${SCRIPTS_DIR}/candle_collector.py"
  sync_runtime_file \
    "${REPO_ROOT}/scripts/ollama_finetune_batch.py" \
    "${SCRIPTS_DIR}/ollama_finetune_batch.py"
  sync_runtime_file \
    "${REPO_ROOT}/systemd/validate_btc_config.py" \
    "${SYSTEMD_HELPERS_DIR}/validate_btc_config.py"
  # Coordenador de GPUs (ferramenta homelab, pertence ao user homelab)
  sudo install -d -o homelab -g homelab -m 0755 "${TOOLS_DIR}"
  sudo install -o homelab -g homelab -m 0755 \
    "${REPO_ROOT}/tools/ollama_gpu_coordinator.py" \
    "${TOOLS_DIR}/ollama_gpu_coordinator.py"
}

write_trading_database_env() {
  local db_url="$1"
  local tmp_env=""

  tmp_env="$(mktemp)"
  printf 'DATABASE_URL=%s\n' "${db_url}" > "${tmp_env}"
  sudo install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0750 "${ENVFILES_DIR}"
  sudo install -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0640 "${tmp_env}" "${TRADING_DB_ENV}"
  rm -f "${tmp_env}"
}

ensure_trading_venv() {
  # Garantir dependências de sistema necessárias para o venv
  sudo apt-get install -y --no-install-recommends python3-feedparser python3-venv 2>/dev/null || true

  if [[ ! -x "${TRADING_VENV}/bin/python" ]]; then
    echo "ℹ️ Criando venv dedicado do trading em ${TRADING_VENV}"
    sudo install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0755 "$(dirname "${TRADING_VENV}")"
    sudo python3 -m venv "${TRADING_VENV}"
    sudo chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${TRADING_VENV}"
  fi

  sudo -u "${SERVICE_USER}" "${TRADING_VENV}/bin/python" -m pip \
    install --disable-pip-version-check --quiet --break-system-packages --upgrade pip
  sudo -u "${SERVICE_USER}" "${TRADING_VENV}/bin/python" -m pip \
    install --disable-pip-version-check --quiet --break-system-packages \
    -r "${EXPORTERS_DIR}/requirements.txt"
}

echo "=== BTC trading profile deploy ==="
echo "Repo: ${REPO_ROOT}"
echo "Target: ${TARGET_DIR}"

require_file "${CONSERVATIVE_SRC}"
require_file "${AGGRESSIVE_SRC}"
require_service_user
require_secret_key "${SHARED_ENV}"
DATABASE_URL_VALUE="$(resolve_database_url)"
write_trading_database_env "${DATABASE_URL_VALUE}"
sync_trading_runtime
sync_btc_grafana_dashboard
ensure_trading_venv
install_managed_units

python3 - <<'PY' "${CONSERVATIVE_SRC}" "${AGGRESSIVE_SRC}"
import json
import sys

expected = {
    sys.argv[1]: "conservative",
    sys.argv[2]: "aggressive",
}

for path, profile in expected.items():
    with open(path) as fh:
        cfg = json.load(fh)
    if cfg.get("profile") != profile:
        raise SystemExit(f"Config {path} tem profile={cfg.get('profile')!r}, esperado {profile!r}")
    if cfg.get("dry_run") is not False or cfg.get("live_mode") is not True:
        raise SystemExit(f"Config {path} não está pronta para live trading seguro")
    print(
        f"{profile}: ok "
        f"cooldown={cfg.get('min_trade_interval')} "
        f"confidence={cfg.get('min_confidence')} "
        f"max_position_pct={cfg.get('max_position_pct')}"
    )
PY

backup_if_present "${CONSERVATIVE_DST}"
backup_if_present "${AGGRESSIVE_DST}"

sudo install -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0644 "${CONSERVATIVE_SRC}" "${CONSERVATIVE_DST}"
sudo install -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0644 "${AGGRESSIVE_SRC}" "${AGGRESSIVE_DST}"

# Remove pycache to avoid permission conflicts with files created by the running service
sudo rm -rf "${TARGET_DIR}/__pycache__"
sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile "${TARGET_DIR}/trading_agent.py"
sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile "${TARGET_DIR}/sell_target_mixin.py"
sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile "${TARGET_DIR}/risk_guardian_mixin.py"
sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile "${TARGET_DIR}/position_manager_mixin.py"
sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile "${TARGET_DIR}/slot_exit_policy.py"
sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile "${TARGET_DIR}/fast_model.py"
sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile "${TARGET_DIR}/kucoin_api.py"
sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile "${TARGET_DIR}/profile_rules.py"
sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile "${TARGET_DIR}/prometheus_exporter.py"

validate_ollama_models "/etc/crypto-agent/models.env"

sudo systemctl daemon-reload

# Habilita e inicia o coordenador de GPUs (deve iniciar antes dos agents)
sudo systemctl enable ollama-gpu-coordinator.service 2>/dev/null || true
sudo systemctl restart ollama-gpu-coordinator.service
sleep 2

# Atualiza common.conf para rotear cada classe de chamada para a GPU correta.
# Isso evita colocar modelos leves na GPU0 e reduz 503/fallback quando o
# coordenador estiver degradado.
sudo sed -i \
  -e 's|^Environment=OLLAMA_PLAN_HOST=.*|Environment=OLLAMA_PLAN_HOST=http://192.168.15.2:11434|' \
  -e 's|^Environment=OLLAMA_TRADE_PARAMS_HOST=.*|Environment=OLLAMA_TRADE_PARAMS_HOST=http://192.168.15.2:11435|' \
  -e 's|^Environment=OLLAMA_TRADE_PARAMS_FALLBACK_HOST=.*|Environment=OLLAMA_TRADE_PARAMS_FALLBACK_HOST=http://192.168.15.2:11434|' \
  -e 's|^Environment=OLLAMA_TRADE_WINDOW_HOST=.*|Environment=OLLAMA_TRADE_WINDOW_HOST=http://192.168.15.2:11435|' \
  -e 's|^Environment=OLLAMA_TRADE_WINDOW_FALLBACK_HOST=.*|Environment=OLLAMA_TRADE_WINDOW_FALLBACK_HOST=http://192.168.15.2:11434|' \
  /etc/systemd/system/crypto-agent@.service.d/common.conf 2>/dev/null || true
echo "🔀 Routing: agents → GPU0(:11434)=plan/fallback, GPU1(:11435)=params/window"

# Habilita e reinicia RSS sentiment
sudo systemctl enable rss-sentiment-exporter.service 2>/dev/null || true
sudo systemctl try-restart rss-sentiment-exporter.service 2>/dev/null || true

sudo systemctl daemon-reload
sudo systemctl restart "${AGENT_SERVICES[@]}"

if systemctl is-active --quiet "${LEGACY_EXPORTER_SERVICES[@]}"; then
  echo "ℹ️ Legacy BTC exporter detectado; desativando autocoinbot-exporter para evitar drift de métricas"
fi
sudo systemctl stop "${LEGACY_EXPORTER_SERVICES[@]}" 2>/dev/null || true
sudo systemctl disable "${LEGACY_EXPORTER_SERVICES[@]}" 2>/dev/null || true
sudo systemctl reset-failed "${LEGACY_EXPORTER_SERVICES[@]}" 2>/dev/null || true

sudo systemctl restart "${EXPORTER_SERVICES[@]}"
EXPORTER_STATUS_SERVICES=("${EXPORTER_SERVICES[@]}")

sleep 5

for svc in "${AGENT_SERVICES[@]}"; do
  echo "--- ${svc} ---"
  sudo systemctl --no-pager --full status "${svc}" | sed -n '1,12p'
done

for svc in "${EXPORTER_STATUS_SERVICES[@]}"; do
  echo "--- ${svc} ---"
  sudo systemctl --no-pager --full status "${svc}" | sed -n '1,12p'
done

restart_grafana_if_present

echo "=== Deploy concluido ==="
