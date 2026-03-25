#!/usr/bin/env python3
"""
KuCoin API Module - Autenticação e Operações de Trading
Baseado no AutoCoinBot com otimizações para trading de alta frequência
"""

import os
import time
import hmac
import hashlib
import base64
import json
import requests
import logging
from typing import List, Dict, Any, Optional
from functools import wraps
from pathlib import Path
from dotenv import load_dotenv

# ====================== CONFIGURAÇÃO ======================
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Carregar .env (fallback — secrets agent tem prioridade)
ENV_PATH = Path(__file__).parent / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


# ====================== SECRETS AGENT INTEGRATION ======================
# Centralizado em secrets_helper.py — manter _fetch_from_secrets_agent para
# compatibilidade com training_db.py e outros que importam dele.
def _fetch_from_secrets_agent(secret_name: str, field: str = "password") -> Optional[str]:
    """Busca um segredo via secrets_helper centralizado.

    Mantido para compatibilidade — delega ao secrets_helper.get_secret().
    """
    try:
        from secrets_helper import get_secret
        return get_secret(secret_name, field)
    except ImportError:
        pass
    # Fallback HTTP direto (caso secrets_helper não disponível)
    api_key = os.getenv("SECRETS_AGENT_API_KEY", "")
    base_url = os.getenv("SECRETS_AGENT_URL", "http://127.0.0.1:8088")
    if not api_key:
        return None
    try:
        r = requests.get(
            f"{base_url}/secrets/local/{secret_name}",
            params={"field": field},
            headers={"X-API-KEY": api_key},
            timeout=3,
        )
        if r.status_code == 200:
            return r.json().get("value")
    except Exception:
        pass
    return None


# ====================== TELEGRAM ALERT ======================
def _send_telegram_alert(message: str) -> None:
    """Envia alerta via Telegram para o admin (best-effort, nunca lança exceção)."""
    try:
        bot_token = _fetch_from_secrets_agent("crypto/telegram_bot_token", "password")
        if not bot_token:
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("ADMIN_CHAT_ID", "948686300")
        if not bot_token:
            logger.warning("⚠️ Telegram alert skipped: no bot token available")
            return
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception as e:
        logger.warning(f"⚠️ Failed to send Telegram alert: {e}")


def _load_credentials():
    """Carrega credenciais KuCoin com prioridade: Secrets Agent > .env > env vars.

    Tenta obter do Secrets Agent primeiro; se falhar, usa variáveis de ambiente
    e envia alerta via Telegram.
    """
    key = secret = passphrase = None
    fallback_reason = "secrets-agent indisponível ou credenciais não encontradas"
    max_attempts = 4

    for attempt in range(1, max_attempts + 1):
        key = _fetch_from_secrets_agent("kucoin/homelab", "api_key")
        secret = _fetch_from_secrets_agent("kucoin/homelab", "api_secret")
        passphrase = _fetch_from_secrets_agent("kucoin/homelab", "passphrase")

        if key and secret and passphrase:
            break

        if not os.getenv("SECRETS_AGENT_API_KEY", ""):
            fallback_reason = "SECRETS_AGENT_API_KEY não configurada"
            break

        if attempt < max_attempts:
            logger.warning(
                "⚠️ Secrets Agent incompleto na tentativa %s/%s "
                "(api_key=%s, api_secret=%s, passphrase=%s); retry em 1s",
                attempt,
                max_attempts,
                bool(key),
                bool(secret),
                bool(passphrase),
            )
            time.sleep(1)

    if key and secret and passphrase:
        source = "secrets-agent"
    else:
        # Fallback — notificar via Telegram
        if not os.getenv("SECRETS_AGENT_API_KEY", ""):
            fallback_reason = "SECRETS_AGENT_API_KEY não configurada"
        logger.warning(f"⚠️ Secrets Agent fallback: {fallback_reason}. Usando .env")
        _send_telegram_alert(
            f"🚨 *BTC Trading Agent — Fallback de Credenciais*\n\n"
            f"O Secrets Agent não respondeu. Credenciais KuCoin carregadas do `.env`.\n"
            f"*Motivo:* {fallback_reason}\n"
            f"*Ação:* Verificar se `secrets-agent.service` está ativo no homelab."
        )
        key = None
        secret = None
        passphrase = None
        source = ".env"

    api_key = key or os.getenv("KUCOIN_API_KEY", "") or os.getenv("API_KEY", "")
    api_secret = secret or os.getenv("KUCOIN_API_SECRET", "") or os.getenv("API_SECRET", "")
    api_passphrase = passphrase or os.getenv("KUCOIN_API_PASSPHRASE", "") or os.getenv("API_PASSPHRASE", "")

    if api_key:
        logger.info(f"🔑 KuCoin credentials loaded from {source} (key: {api_key[:8]}...{api_key[-4:]})")
    else:
        logger.error("❌ Nenhuma credencial KuCoin encontrada (secrets-agent nem .env)")
        _send_telegram_alert(
            "🔴 *BTC Trading Agent — ERRO CRÍTICO*\n\n"
            "Nenhuma credencial KuCoin disponível!\n"
            "Nem o Secrets Agent nem o `.env` possuem as chaves.\n"
            "*O agente NÃO conseguirá operar.*"
        )

    return api_key, api_secret, api_passphrase


# ====================== CREDENCIAIS ======================
API_KEY, API_SECRET, API_PASSPHRASE = _load_credentials()
API_KEY_VERSION = os.getenv("API_KEY_VERSION", "1")
KUCOIN_BASE = os.getenv("KUCOIN_BASE", "https://api.kucoin.com").rstrip("/")

# ====================== RATE LIMITING ======================
_last_request_time = 0
_min_request_interval = 0.1  # 100ms entre requests

def rate_limit():
    """Rate limiting para evitar throttling"""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _min_request_interval:
        time.sleep(_min_request_interval - elapsed)
    _last_request_time = time.time()

# ====================== RETRY DECORATOR ======================
def retry_on_failure(max_retries: int = 3, delay: float = 0.5):
    """Decorator para retry automático"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
            raise last_error
        return wrapper
    return decorator

# ====================== AUTH HELPERS ======================
def _has_keys() -> bool:
    """Verifica se credenciais estão configuradas"""
    return bool(API_KEY and API_SECRET and API_PASSPHRASE)

def validate_credentials():
    """Valida credenciais da API"""
    if not _has_keys():
        raise RuntimeError(
            "❌ API credentials not configured. Set KUCOIN_API_KEY, "
            "KUCOIN_API_SECRET, and KUCOIN_API_PASSPHRASE"
        )

def _server_time() -> int:
    """Obtém timestamp do servidor KuCoin"""
    try:
        r = requests.get(f"{KUCOIN_BASE}/api/v1/timestamp", timeout=5)
        if r.status_code == 200:
            return r.json().get("data", int(time.time() * 1000))
    except:
        pass
    return int(time.time() * 1000)

def _build_headers(method: str, endpoint: str, body_str: str = "") -> Dict[str, str]:
    """Constrói headers autenticados para API"""
    validate_credentials()

    ts = str(_server_time())
    method_up = method.upper()
    to_sign = ts + method_up + endpoint + (body_str or "")

    signature = base64.b64encode(
        hmac.new(API_SECRET.encode(), to_sign.encode(), hashlib.sha256).digest()
    ).decode()

    if API_KEY_VERSION == "1":
        passphrase = API_PASSPHRASE
    else:
        passphrase = base64.b64encode(
            hmac.new(API_SECRET.encode(), API_PASSPHRASE.encode(), hashlib.sha256).digest()
        ).decode()

    return {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": ts,
        "KC-API-PASSPHRASE": passphrase,
        "KC-API-KEY-VERSION": API_KEY_VERSION,
        "Content-Type": "application/json"
    }

# ====================== PUBLIC ENDPOINTS ======================
@retry_on_failure(max_retries=2)
def get_price(symbol: str = "BTC-USDT") -> Optional[float]:
    """Obtém preço atual de um par"""
    url = f"{KUCOIN_BASE}/api/v1/market/orderbook/level1?symbol={symbol}"
    try:
        rate_limit()
        r = requests.get(url, timeout=3)
        r.raise_for_status()
        data = r.json().get("data", {})
        if data:
            bid = float(data.get("bestBid", 0))
            ask = float(data.get("bestAsk", 0))
            return (bid + ask) / 2 if bid and ask else None
    except Exception as e:
        logger.warning(f"⚠️ Error getting price: {e}")
    return None

def get_price_fast(symbol: str = "BTC-USDT", timeout: float = 1.5) -> Optional[float]:
    """Versão ultra-rápida sem retry"""
    url = f"{KUCOIN_BASE}/api/v1/market/orderbook/level1?symbol={symbol}"
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            data = r.json().get("data", {})
            if data:
                bid = float(data.get("bestBid", 0))
                ask = float(data.get("bestAsk", 0))
                return (bid + ask) / 2 if bid and ask else None
    except:
        pass
    return None

@retry_on_failure(max_retries=2)
def get_orderbook(symbol: str = "BTC-USDT", depth: int = 20) -> Dict[str, Any]:
    """Obtém order book"""
    url = f"{KUCOIN_BASE}/api/v1/market/orderbook/level2_{depth}?symbol={symbol}"
    try:
        rate_limit()
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json().get("data", {})
        return {
            "bids": [(float(p), float(s)) for p, s in data.get("bids", [])],
            "asks": [(float(p), float(s)) for p, s in data.get("asks", [])],
            "timestamp": time.time()
        }
    except Exception as e:
        logger.warning(f"⚠️ Error getting orderbook: {e}")
        return {"bids": [], "asks": [], "timestamp": time.time()}

@retry_on_failure(max_retries=2)
def get_candles(symbol: str = "BTC-USDT", ktype: str = "1min", 
                limit: int = 100) -> List[Dict[str, float]]:
    """Obtém candles históricos"""
    url = f"{KUCOIN_BASE}/api/v1/market/candles?type={ktype}&symbol={symbol}"
    try:
        rate_limit()
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        raw = r.json().get("data", [])

        candles = []
        for c in raw[:limit]:
            if len(c) >= 7:
                candles.append({
                    "timestamp": int(c[0]),
                    "open": float(c[1]),
                    "close": float(c[2]),
                    "high": float(c[3]),
                    "low": float(c[4]),
                    "volume": float(c[5]),
                    "turnover": float(c[6])
                })
        return candles[::-1]
    except Exception as e:
        logger.warning(f"⚠️ Error getting candles: {e}")
        return []

@retry_on_failure(max_retries=2)
def get_recent_trades(symbol: str = "BTC-USDT", limit: int = 50) -> List[Dict]:
    """Obtém trades recentes do mercado"""
    url = f"{KUCOIN_BASE}/api/v1/market/histories?symbol={symbol}"
    try:
        rate_limit()
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        trades = r.json().get("data", [])
        return trades[:limit]
    except Exception as e:
        logger.warning(f"⚠️ Error getting trades: {e}")
        return []

# ====================== PRIVATE ENDPOINTS ======================
@retry_on_failure(max_retries=3)
def get_balances(account_type: str = "trade") -> List[Dict[str, Any]]:
    """Obtém saldos da conta"""
    endpoint = "/api/v1/accounts"
    headers = _build_headers("GET", endpoint)
    rate_limit()

    r = requests.get(KUCOIN_BASE + endpoint, headers=headers, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"API error: {r.status_code}")

    accounts = r.json().get("data", [])
    return [
        {
            "currency": a.get("currency"),
            "balance": float(a.get("balance", 0)),
            "available": float(a.get("available", 0)),
            "holds": float(a.get("holds", 0))
        }
        for a in accounts if a.get("type") == account_type
    ]

def get_balance(currency: str = "USDT") -> float:
    """Obtém saldo específico"""
    balances = get_balances()
    for b in balances:
        if b["currency"] == currency:
            return b["available"]
    return 0.0


def inner_transfer(currency: str, amount: float,
                   from_account: str = "main",
                   to_account: str = "trade") -> Dict[str, Any]:
    """Transferência interna entre contas KuCoin (main ↔ trade).

    Args:
        currency: Moeda a transferir (ex: 'BTC', 'USDT').
        amount: Quantidade a transferir.
        from_account: Conta origem ('main' ou 'trade').
        to_account: Conta destino ('main' ou 'trade').

    Returns:
        Dict com 'success' e 'orderId' ou 'error'.
    """
    import uuid
    validate_credentials()

    endpoint = "/api/v2/accounts/inner-transfer"
    payload = {
        "clientOid": str(uuid.uuid4()),
        "currency": currency,
        "from": from_account,
        "to": to_account,
        "amount": str(round(amount, 8)),
    }
    body_str = json.dumps(payload, separators=(",", ":"))
    headers = _build_headers("POST", endpoint, body_str)

    logger.info(
        f"💸 Inner transfer: {amount:.8f} {currency} "
        f"{from_account} → {to_account}"
    )

    rate_limit()
    r = requests.post(
        KUCOIN_BASE + endpoint, headers=headers,
        data=body_str, timeout=10,
    )
    result = r.json()
    if result.get("code") != "200000":
        logger.error(f"❌ Inner transfer failed: {result}")
        return {"success": False, "error": result.get("msg", "Unknown")}

    order_id = result.get("data", {}).get("orderId", "")
    logger.info(f"✅ Inner transfer OK: {order_id}")
    return {"success": True, "orderId": order_id}


@retry_on_failure(max_retries=3)
def place_market_order(symbol: str, side: str, funds: float = None,
                       size: float = None) -> Dict[str, Any]:
    """Executa ordem de mercado"""
    validate_credentials()

    endpoint = "/api/v1/orders"
    client_oid = f"btc_agent_{int(time.time() * 1e6)}"

    payload = {
        "clientOid": client_oid,
        "side": side.lower(),
        "symbol": symbol,
        "type": "market",
    }

    if funds is not None:
        payload["funds"] = str(round(float(funds), 2))
    elif size is not None:
        payload["size"] = str(round(float(size), 8))
    else:
        raise ValueError("Must specify 'funds' or 'size'")

    body_str = json.dumps(payload, separators=(",", ":"))
    headers = _build_headers("POST", endpoint, body_str)

    logger.info(f"📤 {side.upper()} {symbol} - funds={funds}, size={size}")

    rate_limit()
    r = requests.post(KUCOIN_BASE + endpoint, headers=headers,
                      data=body_str, timeout=15)

    result = r.json()
    if result.get("code") != "200000":
        logger.error(f"❌ Order failed: {result}")
        return {"success": False, "error": result.get("msg", "Unknown"), "raw": result}

    order_id = result.get("data", {}).get("orderId")
    logger.info(f"✅ Order placed: {order_id}")

    return {"success": True, "orderId": order_id, "raw": result}

@retry_on_failure(max_retries=2)
def get_order_details(order_id: str) -> Optional[Dict[str, Any]]:
    """Obtém detalhes de uma ordem"""
    endpoint = f"/api/v1/orders/{order_id}"
    headers = _build_headers("GET", endpoint)
    rate_limit()

    r = requests.get(KUCOIN_BASE + endpoint, headers=headers, timeout=10)
    if r.status_code == 200 and r.json().get("code") == "200000":
        return r.json().get("data")
    return None

@retry_on_failure(max_retries=2)
def get_fills(symbol: str = None, limit: int = 50) -> List[Dict]:
    """Obtém execuções recentes"""
    endpoint = "/api/v1/fills"
    params = {"pageSize": limit}
    if symbol:
        params["symbol"] = symbol

    from urllib.parse import urlencode
    qs = urlencode(params)
    signed_endpoint = f"{endpoint}?{qs}"

    headers = _build_headers("GET", signed_endpoint)
    rate_limit()

    r = requests.get(KUCOIN_BASE + signed_endpoint, headers=headers, timeout=10)
    if r.status_code == 200 and r.json().get("code") == "200000":
        return r.json().get("data", {}).get("items", [])
    return []

# ====================== MARKET ANALYSIS ======================
def analyze_orderbook(symbol: str = "BTC-USDT") -> Dict[str, Any]:
    """Analisa desequilíbrio do order book"""
    ob = get_orderbook(symbol)

    bid_volume = sum(s for _, s in ob["bids"][:10])
    ask_volume = sum(s for _, s in ob["asks"][:10])
    total = bid_volume + ask_volume

    if total > 0:
        imbalance = (bid_volume - ask_volume) / total
    else:
        imbalance = 0

    return {
        "bid_volume": bid_volume,
        "ask_volume": ask_volume,
        "imbalance": imbalance,
        "spread": ob["asks"][0][0] - ob["bids"][0][0] if ob["bids"] and ob["asks"] else 0
    }

def analyze_trade_flow(symbol: str = "BTC-USDT") -> Dict[str, Any]:
    """Analisa fluxo de trades recentes"""
    trades = get_recent_trades(symbol, limit=100)

    buy_volume = 0
    sell_volume = 0

    for t in trades:
        side = t.get("side", "").lower()
        size = float(t.get("size", 0))
        if side == "buy":
            buy_volume += size
        else:
            sell_volume += size

    total = buy_volume + sell_volume
    if total > 0:
        flow_bias = (buy_volume - sell_volume) / total
    else:
        flow_bias = 0

    return {
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "flow_bias": flow_bias,
        "total_volume": total
    }

# ====================== TEST ======================
if __name__ == "__main__":
    print("=" * 50)
    print("🔑 KuCoin API Test")
    print("=" * 50)

    print(f"\nCredentials: {'✅ Configured' if _has_keys() else '❌ Missing'}")
    print(f"API Base: {KUCOIN_BASE}")

    price = get_price("BTC-USDT")
    print(f"\nBTC-USDT Price: ${price:,.2f}" if price else "❌ Price fetch failed")

    analysis = analyze_orderbook("BTC-USDT")
    print(f"Order Book Imbalance: {analysis['imbalance']:.3f}")
