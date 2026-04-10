#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${REPO_ROOT}/patches"
TARGET_DIR="${TARGET_DIR:-/home/homelab/myClaude/btc_trading_agent}"
SHARED_ENV="${TARGET_DIR}/envfiles/shared-secrets.env"

CONSERVATIVE_SRC="${SOURCE_DIR}/config_BTC_USDT_conservative_optimized.json"
AGGRESSIVE_SRC="${SOURCE_DIR}/config_BTC_USDT_aggressive_optimized.json"
CONSERVATIVE_DST="${TARGET_DIR}/config_BTC_USDT_conservative.json"
AGGRESSIVE_DST="${TARGET_DIR}/config_BTC_USDT_aggressive.json"

SERVICES=(
  "crypto-agent@BTC_USDT_conservative.service"
  "crypto-agent@BTC_USDT_aggressive.service"
  "crypto-exporter@BTC_USDT_conservative.service"
  "crypto-exporter@BTC_USDT_aggressive.service"
)

require_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    echo "❌ Arquivo obrigatório ausente: ${path}" >&2
    exit 1
  fi
}

require_secret_key() {
  local env_file="$1"
  if [[ ! -f "${env_file}" ]]; then
    echo "❌ Arquivo de secrets não encontrado: ${env_file}" >&2
    exit 1
  fi

  if ! grep -Eq '^SECRETS_AGENT_API_KEY=.+' "${env_file}"; then
    echo "❌ SECRETS_AGENT_API_KEY ausente em ${env_file}" >&2
    exit 1
  fi
}

backup_if_present() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    cp "${path}" "${path}.bak.$(date +%Y%m%d_%H%M%S)"
  fi
}

echo "=== BTC trading profile deploy ==="
echo "Repo: ${REPO_ROOT}"
echo "Target: ${TARGET_DIR}"

require_file "${CONSERVATIVE_SRC}"
require_file "${AGGRESSIVE_SRC}"
require_secret_key "${SHARED_ENV}"

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

install -m 0644 "${CONSERVATIVE_SRC}" "${CONSERVATIVE_DST}"
install -m 0644 "${AGGRESSIVE_SRC}" "${AGGRESSIVE_DST}"

python3 -m py_compile "${TARGET_DIR}/trading_agent.py"
python3 -m py_compile "${TARGET_DIR}/kucoin_api.py"
python3 -m py_compile "${TARGET_DIR}/prometheus_exporter.py"

sudo systemctl daemon-reload
sudo systemctl restart "${SERVICES[@]}"
sleep 5

for svc in "${SERVICES[@]}"; do
  echo "--- ${svc} ---"
  sudo systemctl --no-pager --full status "${svc}" | sed -n '1,12p'
done

echo "=== Deploy concluido ==="
