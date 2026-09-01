#!/usr/bin/env bash
# Garante o checkout de homelab-btc-trading ao lado do auto-dev e o
# symlink btc_trading_agent → ../homelab-btc-trading/btc_trading_agent.
set -euo pipefail

AUTO_DEV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARENT="$(cd "${AUTO_DEV_ROOT}/.." && pwd)"
DEST="${BTC_TRADING_ROOT:-${PARENT}/homelab-btc-trading}"
REPO="${BTC_TRADING_REPO:-https://github.com/eddiejdi/homelab-btc-trading.git}"
LINK="${AUTO_DEV_ROOT}/btc_trading_agent"
REL_TARGET="../homelab-btc-trading/btc_trading_agent"

clone_or_update() {
  if [[ -d "${DEST}/.git" ]]; then
    if [[ "${ENSURE_BTC_PULL:-0}" == "1" ]]; then
      git -C "${DEST}" pull --ff-only origin main
    fi
    return 0
  fi
  echo "[ensure-btc] clonando ${REPO} → ${DEST}"
  if command -v gh >/dev/null 2>&1; then
    gh repo clone eddiejdi/homelab-btc-trading "${DEST}"
  else
    git clone "${REPO}" "${DEST}"
  fi
}

clone_or_update

if [[ ! -d "${DEST}/btc_trading_agent" ]]; then
  echo "❌ ${DEST}/btc_trading_agent não existe após o clone" >&2
  exit 1
fi

if [[ -e "${LINK}" && ! -L "${LINK}" ]]; then
  echo "❌ ${LINK} ainda é um diretório real. Remova a cópia in-tree primeiro." >&2
  exit 1
fi

ln -sfn "${REL_TARGET}" "${LINK}"
echo "[ensure-btc] ${LINK} → ${REL_TARGET} (repo ${DEST})"
