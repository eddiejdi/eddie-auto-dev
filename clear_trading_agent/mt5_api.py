#!/usr/bin/env python3
"""
MT5 API Client — Client REST para o MT5 Bridge.

Equivalente ao kucoin_api.py do btc_trading_agent, mas comunica via
HTTP com o bridge_api.py rodando na VM Windows com MT5.

Funções: place_order, get_positions, get_account, get_price,
         get_candles, analyze_market, etc.
"""
from __future__ import annotations

import logging
import os
import time
from functools import wraps
from pathlib import Path
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

# ====================== CONFIGURAÇÃO ======================
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _load_bridge_config() -> tuple[str, str]:
    """Carrega URL e API key do bridge MT5."""
    try:
        from clear_trading_agent.secrets_helper import get_mt5_bridge_credentials
        return get_mt5_bridge_credentials()
    except ImportError:
        pass
    bridge_url = os.getenv("MT5_BRIDGE_URL", "http://192.168.15.100:8510")
    api_key = os.getenv("MT5_BRIDGE_API_KEY", "")
    return bridge_url, api_key


BRIDGE_URL, BRIDGE_API_KEY = _load_bridge_config()

# ====================== RATE LIMITING ======================
_last_request_time: float = 0
_min_request_interval: float = 0.1  # 100ms entre requests


def rate_limit() -> None:
    """Rate limiting para evitar sobrecarga no bridge."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _min_request_interval:
        time.sleep(_min_request_interval - elapsed)
    _last_request_time = time.time()


# ====================== RETRY DECORATOR ======================
def retry_on_failure(max_retries: int = 3, delay: float = 0.5):
    """Decorator para retry automático com backoff."""
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
            raise last_error  # type: ignore[misc]
        return wrapper
    return decorator


# ====================== HTTP HELPERS ======================
def _headers() -> dict[str, str]:
    """Headers com autenticação para o bridge."""
    return {
        "X-API-KEY": BRIDGE_API_KEY,
        "Content-Type": "application/json",
    }


def _get(endpoint: str, params: Optional[dict[str, Any]] = None, timeout: float = 10) -> Any:
    """GET request ao bridge."""
    rate_limit()
    url = f"{BRIDGE_URL}{endpoint}"
    r = requests.get(url, headers=_headers(), params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _post(endpoint: str, payload: dict[str, Any], timeout: float = 15) -> Any:
    """POST request ao bridge."""
    rate_limit()
    url = f"{BRIDGE_URL}{endpoint}"
    r = requests.post(url, headers=_headers(), json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ====================== HEALTH ======================
def is_bridge_healthy() -> bool:
    """Verifica se o bridge MT5 está respondendo e conectado."""
    try:
        data = _get("/health", timeout=5)
        return data.get("mt5_connected", False)
    except Exception as e:
        logger.warning("⚠️ MT5 bridge health check falhou: %s", e)
        return False


def get_clear_connection_status(check_bridge_health: bool = False) -> dict[str, Any]:
    """Retorna status sanitizado da integração Clear + MT5 Bridge.

    Args:
        check_bridge_health: Quando True, executa health check HTTP no bridge.
    """
    status: dict[str, Any] = {
        "bridge_url": BRIDGE_URL,
        "bridge_api_key_configured": bool(BRIDGE_API_KEY),
        "bridge_healthy": False,
        "broker_username_configured": False,
        "broker_password_configured": False,
    }

    if check_bridge_health:
        try:
            status["bridge_healthy"] = is_bridge_healthy()
        except Exception as e:
            logger.debug("Bridge health check falhou: %s", e)
            status["bridge_healthy"] = False

    try:
        from clear_trading_agent.secrets_helper import get_clear_integration_status
        creds_status = get_clear_integration_status()
        status["broker_username_configured"] = bool(creds_status.get("broker_username_configured"))
        status["broker_password_configured"] = bool(creds_status.get("broker_password_configured"))
    except Exception as exc:
        logger.debug("Falha ao obter status de credenciais Clear: %s", exc)

    return status


# ====================== MARKET DATA (PUBLIC) ======================
@retry_on_failure(max_retries=2)
def get_price(symbol: str = "PETR4") -> Optional[float]:
    """Obtém preço atual (mid-price bid/ask) de um ativo B3."""
    try:
        data = _get(f"/symbol/{symbol}/tick")
        bid = float(data.get("bid", 0))
        ask = float(data.get("ask", 0))
        if bid and ask:
            return (bid + ask) / 2
        last = float(data.get("last", 0))
        return last if last else None
    except Exception as e:
        logger.warning("⚠️ Erro ao obter preço de %s: %s", symbol, e)
    return None


def get_price_fast(symbol: str = "PETR4", timeout: float = 2.0) -> Optional[float]:
    """Versão rápida sem retry."""
    try:
        data = _get(f"/symbol/{symbol}/tick", timeout=timeout)
        bid = float(data.get("bid", 0))
        ask = float(data.get("ask", 0))
        if bid and ask:
            return (bid + ask) / 2
        return float(data.get("last", 0)) or None
    except Exception as e:
        logger.debug("get_price_fast %s: %s", symbol, e)
    return None


@retry_on_failure(max_retries=2)
def get_tick(symbol: str = "PETR4") -> dict[str, Any]:
    """Obtém tick completo de um ativo."""
    try:
        return _get(f"/symbol/{symbol}/tick")
    except Exception as e:
        logger.warning("⚠️ Erro ao obter tick de %s: %s", symbol, e)
        return {}


@retry_on_failure(max_retries=2)
def get_candles(
    symbol: str = "PETR4",
    timeframe: str = "M1",
    count: int = 100,
) -> list[dict[str, Any]]:
    """Obtém candles OHLCV históricos."""
    try:
        data = _get(
            f"/symbol/{symbol}/rates",
            params={"timeframe": timeframe, "count": count},
        )
        return [
            {
                "timestamp": int(c["timestamp"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": int(c.get("tick_volume", 0)),
                "real_volume": int(c.get("real_volume", 0)),
            }
            for c in data
        ]
    except Exception as e:
        logger.warning("⚠️ Erro ao obter candles de %s: %s", symbol, e)
        return []


# ====================== ACCOUNT & POSITIONS ======================
@retry_on_failure(max_retries=3)
def get_account_info() -> dict[str, Any]:
    """Obtém informações da conta Clear."""
    return _get("/account")


def get_balance() -> float:
    """Obtém saldo disponível (margin_free) em BRL."""
    try:
        acc = get_account_info()
        return float(acc.get("margin_free", 0))
    except Exception as e:
        logger.warning("⚠️ Erro ao obter saldo: %s", e)
        return 0.0


def get_equity() -> float:
    """Obtém patrimônio líquido (equity) em BRL."""
    try:
        acc = get_account_info()
        return float(acc.get("equity", 0))
    except Exception as e:
        logger.warning("⚠️ Erro ao obter equity: %s", e)
        return 0.0


@retry_on_failure(max_retries=2)
def get_positions(symbol: Optional[str] = None) -> list[dict[str, Any]]:
    """Obtém posições abertas."""
    params = {}
    if symbol:
        params["symbol"] = symbol
    return _get("/positions", params=params)


@retry_on_failure(max_retries=2)
def get_active_orders(symbol: Optional[str] = None) -> list[dict[str, Any]]:
    """Obtém ordens pendentes."""
    params = {}
    if symbol:
        params["symbol"] = symbol
    return _get("/orders", params=params)


# ====================== TRADING ======================
@retry_on_failure(max_retries=3)
def place_market_order(
    symbol: str,
    side: str,
    volume: float,
    deviation: int = 20,
    magic: int = 234000,
    comment: str = "clear_agent",
) -> dict[str, Any]:
    """Executa ordem de mercado (compra ou venda).

    Args:
        symbol: Código B3 (ex: PETR4, VALE3, WINFUT).
        side: 'buy' ou 'sell'.
        volume: Número de lotes/contratos.
        deviation: Slippage máximo em pontos.
        magic: Número mágico para identificar ordens do bot.
        comment: Comentário da ordem.

    Returns:
        Dict com success, order_id, price, volume, error.
    """
    payload = {
        "symbol": symbol,
        "side": side.lower(),
        "volume": volume,
        "order_type": "market",
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
    }

    logger.info(
        "📤 %s %s %.2f lotes (slippage=%d pts)",
        side.upper(), symbol, volume, deviation,
    )

    result = _post("/order", payload)

    if result.get("success"):
        logger.info(
            "✅ Ordem executada: id=%s price=%.4f vol=%.2f",
            result.get("order_id"), result.get("price", 0), result.get("volume", 0),
        )
    else:
        logger.warning("❌ Ordem rejeitada: %s", result.get("error"))

    return result


@retry_on_failure(max_retries=3)
def place_limit_order(
    symbol: str,
    side: str,
    volume: float,
    price: float,
    magic: int = 234000,
    comment: str = "clear_agent",
) -> dict[str, Any]:
    """Executa ordem limitada.

    Args:
        symbol: Código B3.
        side: 'buy' ou 'sell'.
        volume: Número de lotes/contratos.
        price: Preço limite.
        magic: Número mágico.
        comment: Comentário.

    Returns:
        Dict com success, order_id, error.
    """
    payload = {
        "symbol": symbol,
        "side": side.lower(),
        "volume": volume,
        "order_type": "limit",
        "price": price,
        "magic": magic,
        "comment": comment,
    }

    logger.info(
        "📤 LIMIT %s %s %.2f @ %.4f",
        side.upper(), symbol, volume, price,
    )

    result = _post("/order", payload)

    if result.get("success"):
        logger.info("✅ Ordem limitada: id=%s", result.get("order_id"))
    else:
        logger.warning("❌ Ordem limitada rejeitada: %s", result.get("error"))

    return result


# ====================== HISTORY ======================
@retry_on_failure(max_retries=2)
def get_history_deals(days: int = 7, symbol: Optional[str] = None) -> list[dict[str, Any]]:
    """Obtém histórico de deals (trades executados).

    Args:
        days: Quantos dias de histórico.
        symbol: Filtrar por símbolo (opcional).

    Returns:
        Lista de deals.
    """
    params: dict[str, Any] = {"days": days}
    if symbol:
        params["symbol"] = symbol
    return _get("/history/deals", params=params)


# ====================== MARKET ANALYSIS ======================
def analyze_spread(symbol: str = "PETR4") -> dict[str, Any]:
    """Analisa spread bid/ask de um ativo."""
    tick = get_tick(symbol)
    if not tick:
        return {"bid": 0, "ask": 0, "spread": 0, "spread_pct": 0}

    bid = float(tick.get("bid", 0))
    ask = float(tick.get("ask", 0))
    spread = ask - bid
    mid = (bid + ask) / 2 if (bid and ask) else 1
    spread_pct = (spread / mid) * 100

    return {
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "spread_pct": spread_pct,
    }


def analyze_trade_flow(symbol: str = "PETR4", candle_count: int = 50) -> dict[str, Any]:
    """Analisa fluxo de volume recente usando candles.

    Para B3, não temos trades tick-a-tick via bridge; usamos
    volume dos candles como proxy.
    """
    candles = get_candles(symbol, timeframe="M1", count=candle_count)
    if not candles:
        return {"buy_volume": 0, "sell_volume": 0, "flow_bias": 0, "total_volume": 0}

    buy_vol = 0.0
    sell_vol = 0.0
    for c in candles:
        vol = float(c.get("volume", 0))
        # Heurística: candle de alta = volume comprador, baixa = vendedor
        if c["close"] >= c["open"]:
            buy_vol += vol
        else:
            sell_vol += vol

    total = buy_vol + sell_vol
    flow_bias = (buy_vol - sell_vol) / total if total > 0 else 0

    return {
        "buy_volume": buy_vol,
        "sell_volume": sell_vol,
        "flow_bias": flow_bias,
        "total_volume": total,
    }


# ====================== TELEGRAM ALERT ======================
def _send_telegram_alert(message: str) -> None:
    """Envia alerta via Telegram (best-effort)."""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("ADMIN_CHAT_ID", "948686300")
        if not bot_token:
            return
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception as e:
        logger.warning("⚠️ Falha ao enviar alerta Telegram: %s", e)


# ====================== TEST ======================
if __name__ == "__main__":
    print("=" * 50)
    print("🔗 MT5 Bridge Client Test")
    print("=" * 50)
    print(f"Bridge URL: {BRIDGE_URL}")
    print(f"API Key: {'✅ Configurada' if BRIDGE_API_KEY else '❌ Ausente'}")

    healthy = is_bridge_healthy()
    print(f"Bridge Health: {'✅ OK' if healthy else '❌ Indisponível'}")

    if healthy:
        price = get_price("PETR4")
        print(f"PETR4 Preço: R${price:.2f}" if price else "❌ Sem cotação PETR4")

        acc = get_account_info()
        if acc:
            print(f"Conta: {acc.get('login')} | Saldo: R${acc.get('balance', 0):,.2f}")
