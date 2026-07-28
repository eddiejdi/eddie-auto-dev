#!/usr/bin/env python3
"""Monitor de saldo liberado (disposed) do payout Storj.

A Storj retém pagamentos por ~2 períodos (meses) antes de liberá-los como
saldo gasto na carteira do nó. Este script detecta quando o total "disposed"
(liberado, cumulativo) aumenta e dispara um alerta via Telegram — não move
nenhum fundo, nem tem acesso a nenhuma chave privada.

Fluxo:
1. Lê held-history da API local do storagenode (totalDisposed por satélite).
2. Lê o saldo STORJ atual na carteira via block explorer público do zkSync-era.
3. Compara com o estado salvo da última execução; se o delta de disposed
   convertido em USD cruzar o threshold configurado, alerta e persiste.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from pathlib import Path
from urllib.error import URLError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("storj-payout-monitor")

STORJ_API_BASE = os.environ.get("STORJ_API_BASE", "http://127.0.0.1:14002/api").rstrip("/")
WALLET_ADDRESS = os.environ.get(
    "STORJ_WALLET_ADDRESS", "0x4787E8bA11d9D32f8A51336a1844e663105a7d24"
)
ZKSYNC_EXPLORER_BASE = os.environ.get(
    "ZKSYNC_EXPLORER_BASE", "https://block-explorer-api.mainnet.zksync.io"
)
COINGECKO_PRICE_URL = os.environ.get(
    "COINGECKO_PRICE_URL",
    "https://api.coingecko.com/api/v3/simple/price?ids=storj&vs_currencies=usd",
)

STATE_FILE = Path(
    os.environ.get("STORJ_PAYOUT_STATE_FILE", "/var/lib/storj-payout-monitor/state.json")
)
PROM_FILE = Path(
    os.environ.get(
        "PROM_FILE",
        "/var/lib/prometheus/node-exporter/storj_payout_monitor.prom",
    )
)

ALERT_THRESHOLD_USD = float(os.environ.get("STORJ_ALERT_THRESHOLD_USD", "20"))
HTTP_TIMEOUT = int(os.environ.get("STORJ_PAYOUT_HTTP_TIMEOUT", "15"))


def _http_json(url: str, *, headers: dict | None = None) -> dict:
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_disposed_total() -> float:
    """Soma totalDisposed (unidades: centavos de USD) de todos os satélites."""
    data = _http_json(f"{STORJ_API_BASE}/heldamount/held-history")
    if not isinstance(data, list):
        raise ValueError(f"held-history com formato inesperado: {type(data)}")
    total_cents = sum(float(sat.get("totalDisposed", 0) or 0) for sat in data)
    return total_cents / 100.0


def fetch_wallet_storj_balance(wallet: str = WALLET_ADDRESS) -> float:
    """Saldo STORJ na carteira (zkSync-era), em tokens (não USD)."""
    data = _http_json(f"{ZKSYNC_EXPLORER_BASE}/address/{wallet}")
    balances = data.get("balances", {})
    for entry in balances.values():
        token = entry.get("token", {})
        if token.get("symbol") == "STORJ":
            decimals = int(token.get("decimals", 8))
            raw = int(entry.get("balance", "0") or "0")
            return raw / (10**decimals)
    return 0.0


def fetch_storj_usd_price() -> float | None:
    try:
        data = _http_json(COINGECKO_PRICE_URL)
        return float(data.get("storj", {}).get("usd"))
    except (URLError, ValueError, TypeError, KeyError, OSError) as exc:
        log.warning("Falha ao buscar preço STORJ/USD: %s", exc)
        return None


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        tmp.replace(STATE_FILE)
    except OSError as exc:
        log.warning("Falha ao persistir estado: %s", exc)


def _fetch_from_secrets_agent(secret_name: str, field: str = "password") -> str | None:
    """HTTP direto ao secrets agent local — mesmo padrão do kucoin_api.py.

    Evita depender de `tools.secrets_agent_client` estar no PYTHONPATH do
    host (o script roda de /usr/local/bin, fora do checkout do repo).
    """
    api_key = os.getenv("SECRETS_AGENT_API_KEY", "")
    base_url = os.getenv("SECRETS_AGENT_URL", "http://127.0.0.1:8088")
    if not api_key:
        return None
    try:
        import requests

        r = requests.get(
            f"{base_url}/secrets/local/{secret_name}",
            params={"field": field},
            headers={"X-API-KEY": api_key},
            timeout=3,
        )
        if r.status_code == 200:
            return r.json().get("value")
    except Exception:  # noqa: BLE001
        pass
    return None


def _resolve_telegram_bot_token() -> str:
    for name, field in (
        ("shared/telegram_bot_token", "token"),
        ("authentik/shared/telegram_bot_token", "token"),
    ):
        value = _fetch_from_secrets_agent(name, field)
        if value:
            return value
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def _resolve_telegram_chat_id() -> str:
    for name, field in (
        ("shared/telegram_chat_id", "chat_id"),
        ("authentik/shared/telegram_chat_id", "chat_id"),
    ):
        value = _fetch_from_secrets_agent(name, field)
        if value:
            return value
    return os.getenv("TELEGRAM_CHAT_ID", "") or os.getenv("ADMIN_CHAT_ID", "")


def send_telegram_alert(message: str) -> None:
    """Best-effort — nunca lança exceção."""
    try:
        import requests

        bot_token = _resolve_telegram_bot_token()
        chat_id = _resolve_telegram_chat_id()
        if not bot_token or not chat_id:
            log.warning("Telegram alert pulado: token/chat_id ausente")
            return
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        if r.status_code != 200:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
                timeout=10,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("Telegram alert falhou: %s", exc)


def write_prom(metrics: dict[str, float | int]) -> None:
    help_text = {
        "storj_payout_disposed_total": ("gauge", "Total disposed (USD) somado de todos satélites"),
        "storj_payout_wallet_balance_storj": ("gauge", "Saldo STORJ atual na carteira on-chain"),
        "storj_payout_last_run_timestamp": ("gauge", "Unix time última execução"),
        "storj_payout_monitor_healthy": ("gauge", "1=OK 0=erro"),
        "storj_payout_alert_sent_total": ("counter", "Alertas de novo saldo liberado enviados"),
    }
    lines = []
    for name, value in metrics.items():
        mtype, mhelp = help_text.get(name, ("gauge", name))
        lines.append(f"# HELP {name} {mhelp}")
        lines.append(f"# TYPE {name} {mtype}")
        lines.append(f"{name} {value}")
    try:
        PROM_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PROM_FILE.with_suffix(".prom.tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(PROM_FILE)
    except OSError as exc:
        log.warning("Falha ao escrever métricas: %s", exc)


def main() -> int:
    state = load_state()
    alert_sent = int(state.get("alert_sent_total", 0))

    try:
        disposed_total = fetch_disposed_total()
    except (URLError, ValueError, OSError, KeyError) as exc:
        log.error("Falha ao ler held-history: %s", exc)
        write_prom(
            {
                "storj_payout_disposed_total": state.get("last_disposed_total", -1),
                "storj_payout_wallet_balance_storj": state.get("last_wallet_balance", -1),
                "storj_payout_last_run_timestamp": int(time.time()),
                "storj_payout_monitor_healthy": 0,
                "storj_payout_alert_sent_total": alert_sent,
            }
        )
        return 2

    try:
        wallet_balance = fetch_wallet_storj_balance()
    except (URLError, ValueError, OSError, KeyError) as exc:
        log.error("Falha ao ler saldo on-chain: %s", exc)
        wallet_balance = state.get("last_wallet_balance", 0.0)

    last_disposed_total = float(state.get("last_disposed_total", disposed_total))
    delta_disposed_usd = disposed_total - last_disposed_total

    log.info(
        "disposed_total=$%.2f (delta=$%.2f) wallet_balance=%.4f STORJ",
        disposed_total,
        delta_disposed_usd,
        wallet_balance,
    )

    if delta_disposed_usd >= ALERT_THRESHOLD_USD:
        price = fetch_storj_usd_price()
        price_note = f" (~{delta_disposed_usd / price:.2f} STORJ @ ${price:.4f})" if price else ""
        send_telegram_alert(
            "💰 *Storj Payout* — novo saldo liberado!\n"
            f"Delta: +${delta_disposed_usd:.2f}{price_note}\n"
            f"Total disposed acumulado: ${disposed_total:.2f}\n"
            f"Saldo atual na carteira: {wallet_balance:.4f} STORJ\n"
            f"Carteira: `{WALLET_ADDRESS}`"
        )
        alert_sent += 1
        log.info("Alerta enviado (delta $%.2f >= threshold $%.2f)", delta_disposed_usd, ALERT_THRESHOLD_USD)

    save_state(
        {
            "last_disposed_total": disposed_total,
            "last_wallet_balance": wallet_balance,
            "last_check_ts": int(time.time()),
            "alert_sent_total": alert_sent,
        }
    )

    write_prom(
        {
            "storj_payout_disposed_total": round(disposed_total, 2),
            "storj_payout_wallet_balance_storj": round(wallet_balance, 4),
            "storj_payout_last_run_timestamp": int(time.time()),
            "storj_payout_monitor_healthy": 1,
            "storj_payout_alert_sent_total": alert_sent,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
