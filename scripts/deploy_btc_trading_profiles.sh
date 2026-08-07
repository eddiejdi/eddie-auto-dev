#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${REPO_ROOT}/patches"
TARGET_DIR="${TARGET_DIR:-/apps/crypto-trader/trading/btc_trading_agent}"
RUNTIME_ROOT="${RUNTIME_ROOT:-/apps/crypto-trader/trading}"
TRADING_VENV="${TRADING_VENV:-/apps/crypto-trader/.venv}"
ENVFILES_DIR="${ENVFILES_DIR:-/apps/crypto-trader/envfiles}"
SHARED_ENV="${ENVFILES_DIR}/shared-secrets.env"
TRADING_DB_ENV="${ENVFILES_DIR}/trading-database.env"
SERVICE_USER="${SERVICE_USER:-btc-trading}"
SERVICE_GROUP="${SERVICE_GROUP:-btc-trading}"
EXPORTERS_DIR="${RUNTIME_ROOT}/grafana/exporters"
SCRIPTS_DIR="${RUNTIME_ROOT}/scripts"
TOOLS_DIR="/apps/crypto-trader/tools"
SYSTEMD_HELPERS_DIR="${RUNTIME_ROOT}/systemd"
GRAFANA_PROVISIONING_DIR="${GRAFANA_PROVISIONING_DIR:-/home/homelab/monitoring/grafana/provisioning/dashboards}"
GRAFANA_DASHBOARD_BACKUP_DIR="${GRAFANA_DASHBOARD_BACKUP_DIR:-/home/homelab/monitoring/grafana/provisioning/dashboard_backups}"
PROMETHEUS_CONFIG="${PROMETHEUS_CONFIG:-/home/homelab/monitoring/prometheus.yml}"
MYCLAUDE_SCRIPTS_DIR="${MYCLAUDE_SCRIPTS_DIR:-/home/homelab/myClaude/scripts}"

CONSERVATIVE_SRC="${SOURCE_DIR}/config_BTC_USDT_conservative_optimized.json"
AGGRESSIVE_SRC="${SOURCE_DIR}/config_BTC_USDT_aggressive_optimized.json"
CONSERVATIVE_DST="${TARGET_DIR}/config_BTC_USDT_conservative.json"
AGGRESSIVE_DST="${TARGET_DIR}/config_BTC_USDT_aggressive.json"
BTC_DASHBOARD_SRC="${REPO_ROOT}/grafana/dashboards/btc-trading-monitor.json"
BTC_DASHBOARD_DST="${GRAFANA_PROVISIONING_DIR}/btc-trading-monitor.json"
BTC_DASHBOARD_DUPLICATE_PATHS=(
  "${GRAFANA_PROVISIONING_DIR}/btc_trading_monitor.json"
  "${GRAFANA_PROVISIONING_DIR}/btc_trading_dashboard_v3_prometheus.json"
)

# TODOS os agents que rodam o runtime compartilhado (trading_agent.py, training_db.py,
# mixins, llm.py …). Como o código é sincronizado uma vez em ${TARGET_DIR} e usado por
# todas as instâncias, cada perfil PRECISA ser reiniciado no deploy — senão fica com
# código antigo em memória (foi o que deixou ETH sem log de llm_calls na Fase 1).
# Mantenha em paridade com EXPORTER_SERVICES abaixo.
AGENT_SERVICES=(
  "crypto-agent@BTC_USDT_conservative.service"
  "crypto-agent@BTC_USDT_aggressive.service"
  "crypto-agent@BTC_USDT_shadow.service"
  "crypto-agent@ETH_USDT_conservative.service"
  "crypto-agent@ETH_USDT_aggressive.service"
  "crypto-agent@ETH_USDT_shadow.service"
  "crypto-agent@SOL_USDT_conservative.service"
  "crypto-agent@SOL_USDT_aggressive.service"
  "crypto-agent@SOL_USDT_shadow.service"
  "crypto-agent@DOGE_USDT_conservative.service"
  "crypto-agent@DOGE_USDT_aggressive.service"
  "crypto-agent@DOGE_USDT_shadow.service"
  "crypto-agent@USDT_BRL_conservative.service"
  "crypto-agent@USDT_BRL_aggressive.service"
)

EXPORTER_SERVICES=(
  "crypto-exporter@BTC_USDT_conservative.service"
  "crypto-exporter@BTC_USDT_aggressive.service"
  "crypto-exporter@BTC_USDT_shadow.service"
  "crypto-exporter@ETH_USDT_conservative.service"
  "crypto-exporter@ETH_USDT_aggressive.service"
  "crypto-exporter@ETH_USDT_shadow.service"
  "crypto-exporter@SOL_USDT_conservative.service"
  "crypto-exporter@SOL_USDT_aggressive.service"
  "crypto-exporter@SOL_USDT_shadow.service"
  "crypto-exporter@DOGE_USDT_conservative.service"
  "crypto-exporter@DOGE_USDT_aggressive.service"
  "crypto-exporter@DOGE_USDT_shadow.service"
  "crypto-exporter@USDT_BRL_conservative.service"
  "crypto-exporter@USDT_BRL_aggressive.service"
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

# Ferramentas em ${TOOLS_DIR} chamadas por ExecStart=/ExecStartPost= das units e
# drop-ins gerenciados. Sem elas o drop-in instalado falha no boot (ex.: o
# warmup da GPU1 chama ollama_warmup.py).
MANAGED_TOOLS=(
  "ollama_gpu_coordinator.py"
  "ollama_warmup.py"
  "ollama_gpu_selfheal.py"
  "ollama_offloader.py"
)

# Allowlist opt-in POR ARQUIVO do que pode ir para o host (PR #248). Fonte
# única, compartilhada com scripts/check_systemd_dropin_drift.py — não duplicar.
SYSTEMD_SYSTEM_DIR="${SYSTEMD_SYSTEM_DIR:-/etc/systemd/system}"
DROPIN_ALLOWLIST="${REPO_ROOT}/deploy/systemd-dropins-sync.allowlist"
DROPIN_DRIFT_CHECKER="${REPO_ROOT}/scripts/check_systemd_dropin_drift.py"

# Units cujo restart já é feito em outro ponto do deploy — não reiniciar duas
# vezes quando o drop-in delas mudar.
DROPIN_RESTART_SKIP=(
  "ollama-gpu-coordinator.service"  # restart incondicional mais abaixo
)

# Preenchido por sync_systemd_dropins(); consumido por restart_dropin_changed_units().
DROPIN_CHANGED_UNITS=()

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
  if ! getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
    echo "❌ Grupo ${SERVICE_GROUP} não existe neste host" >&2
    exit 1
  fi
}

require_secret_key() {
  local env_file="$1"
  local conservative_service="crypto-agent@BTC_USDT_conservative.service"
  local runtime_env=""
  local dot_env="${TARGET_DIR}/.env"
  # Arquivo criado quando migramos SECRETS_AGENT_API_KEY de inline para EnvironmentFile=
  local dedicated_env="/etc/crypto-agent/secrets-api.env"
  local key_name="SECRETS_AGENT_API_KEY"

  if [[ -f "${env_file}" ]] && grep -Eq "^${key_name}=.+" "${env_file}"; then
    return 0
  fi

  # EnvironmentFile= dedicado (systemctl show -p Environment não expande arquivos)
  if [[ -f "${dedicated_env}" ]] && grep -Eq "^${key_name}=.+" "${dedicated_env}"; then
    echo "ℹ️ ${key_name} validada via ${dedicated_env}"
    return 0
  fi

  # Fallback: Environment= inline (configurações antigas)
  runtime_env="$(sudo systemctl show "${conservative_service}" -p Environment --value 2>/dev/null || true)"
  if [[ "${runtime_env}" == *"${key_name}="* ]]; then
    echo "ℹ️ ${key_name} validada via systemd drop-in (${conservative_service})"
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

sync_multi_coin_configs() {
  local cfg=""
  for cfg in "${REPO_ROOT}"/btc_trading_agent/config_{ETH,SOL}_USDT_*.json; do
    [[ -f "${cfg}" ]] || continue
    sync_runtime_file "${cfg}" "${TARGET_DIR}/$(basename "${cfg}")"
    echo "  ✅ $(basename "${cfg}")"
  done
}

sync_prometheus_config() {
  local src="${REPO_ROOT}/monitoring/prometheus.yml"
  require_file "${src}"
  backup_if_present "${PROMETHEUS_CONFIG}"
  sudo install -m 0644 "${src}" "${PROMETHEUS_CONFIG}"
  if sudo docker ps --format '{{.Names}}' | grep -qx 'prometheus'; then
    sudo docker exec prometheus promtool check config /etc/prometheus/prometheus.yml
    sudo docker kill --signal=SIGHUP prometheus >/dev/null 2>&1 || true
    echo "  ✅ Prometheus (docker) recarregado"
  elif systemctl is-active --quiet prometheus 2>/dev/null; then
    sudo systemctl reload prometheus 2>/dev/null || sudo kill -HUP "$(pgrep -xo prometheus)" 2>/dev/null || true
    echo "  ✅ Prometheus (systemd) recarregado"
  fi
}

# GNU install falha com "same file" quando src e dst são o mesmo path
# (ex.: REPO_ROOT=/home/homelab/myClaude e MYCLAUDE_SCRIPTS_DIR=$REPO_ROOT/scripts).
install_file_if_different() {
  local src="$1"
  local dst="$2"
  local src_real dst_real
  require_file "${src}"
  # -m: dest pode ainda não existir; só compara path canônico
  src_real="$(realpath -m "${src}")"
  dst_real="$(realpath -m "${dst}")"
  if [[ "${src_real}" == "${dst_real}" ]]; then
    echo "  ℹ️  trading_daily_report.py já está em ${dst_real} (src==dst; skip install)"
    return 0
  fi
  sudo install -d -m 0755 "$(dirname "${dst}")"
  sudo install -m 0644 "${src}" "${dst}"
  echo "  ✅ $(basename "${src}") → ${dst}"
}

sync_myClaude_trading_scripts() {
  if [[ -d "${MYCLAUDE_SCRIPTS_DIR}" ]]; then
    install_file_if_different "${REPO_ROOT}/scripts/trading_daily_report.py" \
      "${MYCLAUDE_SCRIPTS_DIR}/trading_daily_report.py"
  fi
}

ensure_sol_trading_profiles() {
  local activate="${REPO_ROOT}/scripts/activate_sol_trading_profiles.sh"
  if [[ -x "${activate}" ]] && compgen -G "${REPO_ROOT}/btc_trading_agent/config_SOL_USDT_*.json" >/dev/null; then
    echo "🔗 Ativando perfis SOL-USDT (envfiles + systemd)..."
    sudo bash "${activate}"
  fi
}

ensure_doge_trading_profiles() {
  local activate="${REPO_ROOT}/scripts/activate_doge_trading_profiles.sh"
  if [[ -x "${activate}" ]] && compgen -G "${REPO_ROOT}/btc_trading_agent/config_DOGE_USDT_*.json" >/dev/null; then
    echo "🔗 Ativando perfis DOGE-USDT (envfiles + systemd)..."
    sudo bash "${activate}"
  fi
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
  sudo rm -f /etc/sudoers.d/trading-svc-ollama
  sudo install -m 0440 "${REPO_ROOT}/systemd/btc-trading-ollama.sudoers" \
    /etc/sudoers.d/btc-trading-ollama
  sudo visudo -cf /etc/sudoers.d/btc-trading-ollama >/dev/null
}

read_dropin_allowlist() {
  # Caminhos sincronizáveis relativos à raiz do repo, um por linha
  # (`#` comenta, linha vazia ignorada). Ex.: systemd/<unit>.service.d/x.conf
  sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
    "${DROPIN_ALLOWLIST}" | grep -v '^$'
}

dropin_is_redacted() {
  # Templates com placeholder de segredo NUNCA vão para o host: instalar
  # common.conf com SECRETS_AGENT_API_KEY=<from_bitwarden> apagaria a
  # credencial viva do crypto-agent. Mantenha em paridade com
  # REDACTION_PATTERNS de scripts/check_systemd_dropin_drift.py.
  grep -Eq '<from_bitwarden>|<your_[a-z0-9_]+>|CHANGEME|REPLACE_ME|<REDACTED>|<PLACEHOLDER>' "$1"
}

dropin_unit_is_restarted_elsewhere() {
  local unit="$1" skip=""
  # Template não é reiniciável; instâncias crypto-agent@* já entram no restart
  # escalonado de AGENT_SERVICES.
  [[ "${unit}" == *"@.service" ]] && return 0
  [[ "${unit}" == crypto-agent@* ]] && return 0
  for skip in "${DROPIN_RESTART_SKIP[@]}"; do
    [[ "${unit}" == "${skip}" ]] && return 0
  done
  return 1
}

sync_systemd_dropins() {
  # Instala em /etc/systemd/system/ APENAS os arquivos da allowlist (opt-in por
  # arquivo, PR #248). Cópia ADITIVA, sem --delete de propósito: o host tem
  # drop-ins vivos e apagá-los derrubaria a contenção do Ollama.
  local rel="" src="" dst="" unit="" base="" rel_dir=""
  local -A seen_dirs=()
  local host_only=()

  if [[ ! -f "${DROPIN_ALLOWLIST}" ]]; then
    echo "❌ Allowlist de drop-ins ausente: ${DROPIN_ALLOWLIST}" >&2
    exit 1
  fi

  echo "🧩 Sincronizando drop-ins systemd (allowlist: $(basename "${DROPIN_ALLOWLIST}"))..."
  DROPIN_CHANGED_UNITS=()

  while IFS= read -r rel; do
    src="${REPO_ROOT}/${rel}"
    rel_dir="$(basename "$(dirname "${rel}")")"
    base="$(basename "${rel}")"
    unit="${rel_dir%.d}"
    seen_dirs["${rel_dir}"]=1

    if [[ ! -f "${src}" ]]; then
      echo "❌ Arquivo da allowlist não existe: ${src}" >&2
      exit 1
    fi

    # Defesa em profundidade: o guard test do #248 já barra placeholder na
    # allowlist, mas instalar um template apagaria segredo vivo do host.
    if dropin_is_redacted "${src}"; then
      echo "❌ ${rel} tem placeholder de segredo e está na allowlist — abortando" >&2
      exit 1
    fi

    sudo install -d -m 0755 "${SYSTEMD_SYSTEM_DIR}/${rel_dir}"
    dst="${SYSTEMD_SYSTEM_DIR}/${rel_dir}/${base}"

    if [[ -f "${dst}" ]] && cmp -s "${src}" "${dst}"; then
      echo "  ✅ ${rel_dir}/${base} (já em paridade)"
      continue
    fi

    backup_if_present "${dst}"
    sudo install -m 0644 "${src}" "${dst}"
    echo "  ⬆️  ${rel_dir}/${base} instalado → ${dst}"
    DROPIN_CHANGED_UNITS+=("${unit}")
  done < <(read_dropin_allowlist)

  # host → repo: o que existe só no host é configuração viva fora do git.
  for rel_dir in "${!seen_dirs[@]}"; do
    [[ -d "${SYSTEMD_SYSTEM_DIR}/${rel_dir}" ]] || continue
    for dst in "${SYSTEMD_SYSTEM_DIR}/${rel_dir}"/*.conf; do
      [[ -f "${dst}" ]] || continue
      base="$(basename "${dst}")"
      [[ -f "${REPO_ROOT}/systemd/${rel_dir}/${base}" ]] && continue
      host_only+=("${rel_dir}/${base}")
    done
  done

  if ((${#host_only[@]})); then
    echo "⚠️  Drop-ins presentes só no host (preservados, mas fora do git):"
    printf '     - %s\n' "${host_only[@]}"
    echo "     ↳ versione com: scripts/export_host_systemd_dropins.sh --apply"
  fi

  if ((${#DROPIN_CHANGED_UNITS[@]})); then
    mapfile -t DROPIN_CHANGED_UNITS < <(printf '%s\n' "${DROPIN_CHANGED_UNITS[@]}" | sort -u)
  fi
}

restart_dropin_changed_units() {
  # Restart escalonado APENAS das units cujo drop-in mudou agora e que não são
  # reiniciadas em outro ponto do deploy. Roda antes do coordenador e dos
  # agents, para que a pilha suba na ordem GPU → coordenador → agents.
  local unit="" restarted=0
  local stagger="${DROPIN_RESTART_STAGGER_SEC:-3}"

  ((${#DROPIN_CHANGED_UNITS[@]})) || {
    echo "ℹ️ Nenhum drop-in mudou — nenhum restart adicional necessário"
    return 0
  }

  for unit in "${DROPIN_CHANGED_UNITS[@]}"; do
    if dropin_unit_is_restarted_elsewhere "${unit}"; then
      echo "  ↪︎ ${unit}: drop-in atualizado (restart já coberto pelo deploy)"
      continue
    fi
    if ! systemctl list-unit-files "${unit}" --no-legend >/dev/null 2>&1 \
       || [[ "$(systemctl show "${unit}" -p LoadState --value 2>/dev/null)" == "not-found" ]]; then
      echo "  ⚠️  ${unit}: unit não encontrada no host — restart pulado" >&2
      continue
    fi
    echo "  ♻️ restart ${unit} (drop-in alterado)"
    sudo systemctl restart "${unit}" || {
      echo "  ⚠️  falha ao reiniciar ${unit} — seguindo" >&2
      continue
    }
    restarted=$((restarted + 1))
    sleep "${stagger}"
  done

  # Ollama precisa responder antes de coordenador/agents subirem, senão o
  # primeiro plano de cada agent bate em 503 (mesma classe do incidente #245).
  if ((restarted)); then
    wait_for_ollama_ready
  fi
}

wait_for_ollama_ready() {
  local host="" attempt=0
  for host in "http://127.0.0.1:11434" "http://127.0.0.1:11435"; do
    for attempt in 1 2 3 4 5 6 7 8 9 10; do
      if curl -sf --max-time 5 "${host}/api/tags" >/dev/null 2>&1; then
        echo "  ✅ Ollama respondendo em ${host}"
        break
      fi
      [[ "${attempt}" -eq 10 ]] && echo "  ⚠️  Ollama não respondeu em ${host} após 10 tentativas" >&2
      sleep 3
    done
  done
}

verify_systemd_dropin_parity() {
  # HOOK de completude (espelho de verify_agents_running_current_code): depois
  # do deploy, todo .conf gerenciado do repo tem que existir idêntico no host.
  # Divergir aqui significa que o deploy não aplicou o que está versionado.
  if [[ ! -f "${DROPIN_DRIFT_CHECKER}" ]]; then
    echo "❌ Verificador de drift ausente: ${DROPIN_DRIFT_CHECKER}" >&2
    exit 1
  fi
  python3 "${DROPIN_DRIFT_CHECKER}" \
    --repo-root "${REPO_ROOT}" --system-dir "${SYSTEMD_SYSTEM_DIR}" \
    --allowlist "${DROPIN_ALLOWLIST}" --strict
}

sync_trading_runtime() {
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/trading_agent.py" \
    "${TARGET_DIR}/trading_agent.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/training_db.py" \
    "${TARGET_DIR}/training_db.py"
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
    "${REPO_ROOT}/btc_trading_agent/llm.py" \
    "${TARGET_DIR}/llm.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/fast_model.py" \
    "${TARGET_DIR}/fast_model.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/market_rag.py" \
    "${TARGET_DIR}/market_rag.py"
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
    "${REPO_ROOT}/scripts/kucoin_postgres_sync.py" \
    "${SCRIPTS_DIR}/kucoin_postgres_sync.py"
  sync_runtime_file \
    "${REPO_ROOT}/scripts/candle_collector.py" \
    "${SCRIPTS_DIR}/candle_collector.py"
  sync_runtime_file \
    "${REPO_ROOT}/scripts/ollama_finetune_batch.py" \
    "${SCRIPTS_DIR}/ollama_finetune_batch.py"
  sync_runtime_file \
    "${REPO_ROOT}/scripts/trading_daily_report.py" \
    "${SCRIPTS_DIR}/trading_daily_report.py"
  sync_runtime_file \
    "${REPO_ROOT}/btc_trading_agent/trading_conversation.py" \
    "${TARGET_DIR}/trading_conversation.py"
  sync_runtime_file \
    "${REPO_ROOT}/systemd/validate_btc_config.py" \
    "${SYSTEMD_HELPERS_DIR}/validate_btc_config.py"
  # Ferramentas Ollama referenciadas por units/drop-ins gerenciados
  # (ExecStart=/ExecStartPost= apontam para ${TOOLS_DIR}). Sincronizar ANTES de
  # instalar os drop-ins: um drop-in que chama um script ausente derruba o
  # ExecStartPost e deixa a GPU sem warmup.
  sudo install -d -o homelab -g homelab -m 0755 "${TOOLS_DIR}"
  local tool=""
  for tool in "${MANAGED_TOOLS[@]}"; do
    require_file "${REPO_ROOT}/tools/${tool}"
    sudo install -o homelab -g homelab -m 0755 \
      "${REPO_ROOT}/tools/${tool}" \
      "${TOOLS_DIR}/${tool}"
  done
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

code_reference_epoch() {
  # Maior mtime (epoch) entre os arquivos de runtime compartilhados recém-sincronizados.
  # Serve de marco: qualquer agent ativo que tenha entrado em execução ANTES disto está
  # rodando código velho.
  local newest=0 f m
  local runtime_files=(
    trading_agent.py training_db.py sell_target_mixin.py risk_guardian_mixin.py
    position_manager_mixin.py slot_exit_policy.py llm.py fast_model.py
    kucoin_api.py profile_rules.py secrets_helper.py prometheus_exporter.py
  )
  for f in "${runtime_files[@]}"; do
    m="$(stat -c %Y "${TARGET_DIR}/${f}" 2>/dev/null || echo 0)"
    (( m > newest )) && newest="${m}"
  done
  echo "${newest}"
}

verify_agents_running_current_code() {
  # HOOK de completude: garante que TODOS os crypto-agent ativos (descobertos no host,
  # não só os listados) foram reiniciados APÓS o sync do runtime. Um agent ativo que
  # ficou com código antigo = deploy incompleto → falha explícita.
  local ref_epoch discovered failed=0 svc load state enter enter_epoch
  ref_epoch="$(code_reference_epoch)"
  if [[ -z "${ref_epoch}" || "${ref_epoch}" == "0" ]]; then
    echo "⚠️  Não foi possível determinar o mtime do runtime em ${TARGET_DIR}; verificação de completude pulada" >&2
    return 0
  fi

  discovered="$(systemctl list-units --type=service --all --no-legend 'crypto-agent@*' 2>/dev/null \
    | awk '{print $1}' | grep -v '^crypto-agent@\.service$' || true)"

  echo "🔎 Verificando completude do deploy — todos os crypto-agent ativos no código novo…"
  for svc in ${discovered}; do
    load="$(systemctl show "${svc}" -p LoadState --value 2>/dev/null || echo not-found)"
    [[ "${load}" == "masked" || "${load}" == "not-found" ]] && continue
    state="$(systemctl show "${svc}" -p ActiveState --value 2>/dev/null || echo unknown)"
    if [[ "${state}" != "active" ]]; then
      echo "  ⚠️  ${svc}: ${state} (inativo — fora da verificação de código)"
      continue
    fi
    enter="$(systemctl show "${svc}" -p ActiveEnterTimestamp --value 2>/dev/null || echo '')"
    enter_epoch="$(date -d "${enter}" +%s 2>/dev/null || echo 0)"
    if (( enter_epoch < ref_epoch )); then
      echo "  ❌ ${svc}: código DESATUALIZADO (ativo desde '${enter}', anterior ao sync do runtime)" >&2
      failed=1
    else
      echo "  ✅ ${svc}: reiniciado após o sync"
    fi
  done

  if (( failed )); then
    echo "" >&2
    echo "❌ Deploy INCOMPLETO: há crypto-agent ativos rodando código antigo." >&2
    echo "   Causa provável: instância nova/perfil fora de AGENT_SERVICES neste script." >&2
    echo "   Ação: adicione-a a AGENT_SERVICES (ou 'systemctl restart' manual) e rode de novo." >&2
    exit 1
  fi
  echo "✅ Completude confirmada: todos os crypto-agent ativos no código recém-sincronizado."
}

# `source`ar o script expõe apenas as funções (usado por
# tests/test_systemd_dropin_parity.py para exercitar sync_systemd_dropins com um
# /etc/systemd/system falso). Execução direta segue normalmente.
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  return 0
fi

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
sync_multi_coin_configs
sync_btc_grafana_dashboard
sync_prometheus_config
sync_myClaude_trading_scripts
ensure_trading_venv
install_managed_units
sync_systemd_dropins

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
sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile "${TARGET_DIR}/training_db.py"
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

# Aplica drop-ins recém-instalados nas units que não são reiniciadas adiante
# (ollama.service / ollama-gpu1.service). Antes do coordenador e dos agents.
echo "♻️ Aplicando drop-ins alterados..."
restart_dropin_changed_units

# Habilita e inicia o coordenador de GPUs (deve iniciar antes dos agents)
sudo systemctl enable ollama-gpu-coordinator.service 2>/dev/null || true
sudo systemctl restart ollama-gpu-coordinator.service
sleep 2

# Atualiza common.conf para rotear TODAS as chamadas (HOST e FALLBACK_HOST)
# pelo coordenador (:11437) de propósito. O coordenador é quem decide qual
# GPU usar por modelo/saúde/carga e faz failover interno sozinho (ex.: NAS
# tem trading-analyst desde 2026-08-01 — se o GPU0 cai, ele roteia pra lá
# automaticamente). Um agente com FALLBACK_HOST apontando direto pra uma
# GPU (por fora do coordenador) tira a serialização anti-503-storm do
# incidente 2026-07-24 e quebra a visibilidade centralizada — não fazer
# isso. O coordenador em si nunca deve cair; se cair, conserte o que o
# derrubou (ver whatsapp_toolcall_chunked_train.sh), não dê um desvio pros
# agentes.
sudo sed -i \
  -e 's|^Environment=OLLAMA_PLAN_HOST=.*|Environment=OLLAMA_PLAN_HOST=http://192.168.15.2:11437|' \
  -e 's|^Environment=OLLAMA_TRADE_PARAMS_HOST=.*|Environment=OLLAMA_TRADE_PARAMS_HOST=http://192.168.15.2:11437|' \
  -e 's|^Environment=OLLAMA_TRADE_PARAMS_FALLBACK_HOST=.*|Environment=OLLAMA_TRADE_PARAMS_FALLBACK_HOST=http://192.168.15.2:11437|' \
  -e 's|^Environment=OLLAMA_TRADE_WINDOW_HOST=.*|Environment=OLLAMA_TRADE_WINDOW_HOST=http://192.168.15.2:11437|' \
  -e 's|^Environment=OLLAMA_TRADE_WINDOW_FALLBACK_HOST=.*|Environment=OLLAMA_TRADE_WINDOW_FALLBACK_HOST=http://192.168.15.2:11437|' \
  /etc/systemd/system/crypto-agent@.service.d/common.conf 2>/dev/null || true
echo "🔀 Routing: agents → coordenador :11437 (roteia GPU0/GPU1/NAS por saúde e modelo)"

# Habilita e reinicia RSS sentiment
sudo systemctl enable rss-sentiment-exporter.service 2>/dev/null || true
sudo systemctl try-restart rss-sentiment-exporter.service 2>/dev/null || true

sudo systemctl daemon-reload

# Restart escalonado: restart em massa sobrecarrega o Secrets Agent e gera
# falsos "Nenhuma credencial KuCoin" (ex.: ETH_USDT_conservative no deploy #225).
AGENT_RESTART_STAGGER_SEC="${AGENT_RESTART_STAGGER_SEC:-2}"
echo "♻️ Reiniciando agents com stagger ${AGENT_RESTART_STAGGER_SEC}s..."
idx=0
for svc in "${AGENT_SERVICES[@]}"; do
  idx=$((idx + 1))
  echo "  [${idx}/${#AGENT_SERVICES[@]}] restart ${svc}"
  sudo systemctl restart "${svc}" || {
    echo "⚠️  falha ao reiniciar ${svc} — seguindo" >&2
  }
  if [[ "${idx}" -lt "${#AGENT_SERVICES[@]}" ]]; then
    sleep "${AGENT_RESTART_STAGGER_SEC}"
  fi
done

if systemctl is-active --quiet "${LEGACY_EXPORTER_SERVICES[@]}"; then
  echo "ℹ️ Legacy BTC exporter detectado; desativando autocoinbot-exporter para evitar drift de métricas"
fi
sudo systemctl stop "${LEGACY_EXPORTER_SERVICES[@]}" 2>/dev/null || true
sudo systemctl disable "${LEGACY_EXPORTER_SERVICES[@]}" 2>/dev/null || true
sudo systemctl reset-failed "${LEGACY_EXPORTER_SERVICES[@]}" 2>/dev/null || true

EXPORTER_RESTART_STAGGER_SEC="${EXPORTER_RESTART_STAGGER_SEC:-1}"
echo "♻️ Reiniciando exporters com stagger ${EXPORTER_RESTART_STAGGER_SEC}s..."
eidx=0
for svc in "${EXPORTER_SERVICES[@]}"; do
  eidx=$((eidx + 1))
  echo "  [${eidx}/${#EXPORTER_SERVICES[@]}] restart ${svc}"
  sudo systemctl restart "${svc}" || {
    echo "⚠️  falha ao reiniciar ${svc} — seguindo" >&2
  }
  if [[ "${eidx}" -lt "${#EXPORTER_SERVICES[@]}" ]]; then
    sleep "${EXPORTER_RESTART_STAGGER_SEC}"
  fi
done
EXPORTER_STATUS_SERVICES=("${EXPORTER_SERVICES[@]}")

sleep 5

for svc in "${AGENT_SERVICES[@]}"; do
  echo "--- ${svc} ---"
  sudo systemctl --no-pager --full status "${svc}" | sed -n '1,12p' || true
done

for svc in "${EXPORTER_STATUS_SERVICES[@]}"; do
  echo "--- ${svc} ---"
  sudo systemctl --no-pager --full status "${svc}" | sed -n '1,12p' || true
done

restart_grafana_if_present
ensure_sol_trading_profiles
ensure_doge_trading_profiles

# HOOK de completude: aborta se algum agent ativo ficou com código antigo.
verify_agents_running_current_code

# HOOK de completude: aborta se algum drop-in versionado não chegou ao host.
verify_systemd_dropin_parity

echo "=== Deploy concluido ==="
