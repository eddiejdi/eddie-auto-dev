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
import logging
from urllib.parse import urlencode

import requests
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
def _resolve_telegram_bot_token() -> str:
    """Resolve o token do bot priorizando o cofre padrão do projeto."""
    for secret_name, field in (
        ("shared/telegram_bot_token", "token"),
        ("authentik/shared/telegram_bot_token", "token"),
        ("shared/telegram_bot_token", "password"),
        ("authentik/shared/telegram_bot_token", "password"),
        ("crypto/telegram_bot_token", "password"),
    ):
        value = _fetch_from_secrets_agent(secret_name, field)
        if value:
            return value
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def _resolve_telegram_chat_id() -> str:
    """Resolve o chat_id priorizando o cofre padrão do projeto."""
    for secret_name, field in (
        ("shared/trading_telegram_chat_id", "chat_id"),
        ("authentik/shared/trading_telegram_chat_id", "chat_id"),
        ("shared/trading_telegram_chat_id", "password"),
        ("authentik/shared/trading_telegram_chat_id", "password"),
    ):
        value = _fetch_from_secrets_agent(secret_name, field)
        if value:
            return value

    trading_chat_id = (os.getenv("TRADING_TELEGRAM_CHAT_ID", "") or "").strip()
    if trading_chat_id:
        return trading_chat_id

    for secret_name, field in (
        ("shared/telegram_chat_id", "chat_id"),
        ("authentik/shared/telegram_chat_id", "chat_id"),
        ("shared/telegram_chat_id", "password"),
        ("authentik/shared/telegram_chat_id", "password"),
    ):
        value = _fetch_from_secrets_agent(secret_name, field)
        if value:
            return value
    return os.getenv("TELEGRAM_CHAT_ID", "") or os.getenv("ADMIN_CHAT_ID", "948686300")


def _resolve_telegram_thread_id() -> str:
    """Resolve thread de destino para tópicos de fórum no Telegram (opcional)."""
    for secret_name, field in (
        ("shared/trading_telegram_thread_id", "thread_id"),
        ("authentik/shared/trading_telegram_thread_id", "thread_id"),
        ("shared/trading_telegram_thread_id", "password"),
        ("authentik/shared/trading_telegram_thread_id", "password"),
    ):
        value = _fetch_from_secrets_agent(secret_name, field)
        if value:
            return value

    return (os.getenv("TRADING_TELEGRAM_THREAD_ID", "") or "").strip()


def _get_extra_telegram_chat_ids() -> list:
    """Retorna lista de chat_ids extras para notificações de trading (TRADING_TELEGRAM_EXTRA_CHAT_IDS)."""
    raw = (os.getenv("TRADING_TELEGRAM_EXTRA_CHAT_IDS", "") or "").strip()
    return [c.strip() for c in raw.split(",") if c.strip()] if raw else []


def _send_telegram_alert(message: str) -> None:
    """Envia alerta via Telegram para o admin (best-effort, nunca lança exceção)."""
    try:
        bot_token = _resolve_telegram_bot_token()
        chat_id = _resolve_telegram_chat_id()
        thread_id = _resolve_telegram_thread_id()
        if not bot_token:
            logger.warning("⚠️ Telegram alert skipped: no bot token available")
            return
        if not chat_id:
            logger.warning("⚠️ Telegram alert skipped: no chat_id available")
            return
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        if thread_id:
            payload["message_thread_id"] = int(thread_id)
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload,
            timeout=10,
        )
        if r.status_code != 200:
            # Markdown inválido ou thread inexistente → retry texto puro
            logger.warning(
                "⚠️ Telegram alert HTTP %s: %s — retry sem parse_mode",
                r.status_code, r.text[:120],
            )
            payload.pop("parse_mode", None)
            payload.pop("message_thread_id", None)
            r = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json=payload,
                timeout=10,
            )
            if r.status_code != 200:
                logger.error("❌ Telegram alert falhou de vez: %s", r.text[:150])
        for _extra in _get_extra_telegram_chat_ids():
            try:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": _extra, "text": message, "parse_mode": "Markdown"},
                    timeout=5,
                )
            except Exception as _ex:
                logger.warning("⚠️ Telegram extra alert failed (%s): %s", _extra, _ex)
    except Exception as e:
        logger.warning(f"⚠️ Failed to send Telegram alert: {e}")


def _format_market_order_notification(
    *,
    symbol: str,
    side: str,
    funds: float | None = None,
    size: float | None = None,
    order_id: str | None = None,
    error: str | None = None,
    notify_extra: Dict[str, float] | None = None,
) -> str:
    """Monta mensagem Telegram para execução de ordem de mercado.

    notify_extra (opcional, para SELL): invested, proceeds, pnl, pnl_pct.
    """
    action = side.upper()
    icon = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "📤"
    status = "EXECUTADA" if not error else "FALHOU"
    lines = [
        f"{icon} *BTC Trading Agent — Ordem {status}*",
        "",
        f"• Ação: `{action}`",
        f"• Par: `{symbol}`",
    ]
    if funds is not None:
        lines.append(f"• Valor: `{float(funds):.2f} USDT`")
    if size is not None:
        lines.append(f"• Quantidade: `{float(size):.8f}`")
    extra = notify_extra or {}
    if extra.get("invested") is not None:
        lines.append(f"• Valor investido: `{float(extra['invested']):.2f} USDT`")
    if extra.get("proceeds") is not None:
        lines.append(f"• Valor da venda: `{float(extra['proceeds']):.2f} USDT`")
    if extra.get("pnl") is not None:
        pnl = float(extra["pnl"])
        pct = float(extra.get("pnl_pct") or 0.0)
        lines.append(f"• PnL líquido: `{pnl:+.4f} USDT ({pct:+.2f}%)`")
    if order_id:
        lines.append(f"• Order ID: `{order_id}`")
    if error:
        lines.append(f"• Erro: `{error[:180]}`")
    return "\n".join(lines)


def _agent_identity() -> dict[str, str]:
    """Identidade do processo (symbol/profile/unit) para alertas e logs."""
    config_name = (
        os.getenv("COIN_CONFIG_FILE")
        or os.getenv("BTC_CONFIG_FILE")
        or ""
    ).strip()
    unit = ""
    if config_name:
        stem = Path(config_name).name
        if stem.startswith("config_") and stem.endswith(".json"):
            unit = stem[len("config_") : -len(".json")]
        else:
            unit = Path(stem).stem

    symbol = (os.getenv("COIN_SYMBOL") or "").strip().upper()
    profile = (os.getenv("TRADING_PROFILE") or "").strip().lower()
    if unit and ("_" in unit):
        # ETH_USDT_conservative → symbol=ETH-USDT, profile=conservative
        parts = unit.rsplit("_", 1)
        if len(parts) == 2 and parts[1] in {"conservative", "aggressive", "shadow", "default"}:
            if not profile:
                profile = parts[1]
            if not symbol:
                symbol = parts[0].replace("_", "-")

    if not symbol and "-" in unit:
        symbol = unit
    label = unit or symbol or profile or "unknown"
    return {
        "unit": unit or label,
        "symbol": symbol or "?",
        "profile": profile or "?",
        "label": label,
        "systemd": f"crypto-agent@{unit}" if unit else "crypto-agent",
    }


def _load_credentials(
    *,
    max_attempts: int = 4,
    base_delay_sec: float = 0.75,
    sleep_fn=time.sleep,
):
    """Carrega credenciais KuCoin com prioridade: Agent Secrets > env vars.

    Em restart em massa o Secrets Agent pode falhar transitóriamente — retenta
    com backoff antes de alertar no Telegram. O título do alerta inclui o
    agent real (não "BTC" genérico).
    """
    identity = _agent_identity()
    agent_label = identity["label"]
    symbol = identity["symbol"]
    profile = identity["profile"]
    unit_name = identity["systemd"]

    api_key = api_secret = api_passphrase = ""
    source = "none"
    last_error: Exception | None = None

    for attempt in range(1, max(1, int(max_attempts)) + 1):
        try:
            from secrets_helper import clear_secret_cache, get_kucoin_credentials_with_source

            # Evita reusar cache parcial/vazio de tentativas anteriores sob race.
            if attempt > 1:
                clear_secret_cache()
            api_key, api_secret, api_passphrase, source = get_kucoin_credentials_with_source()
        except ImportError:
            api_key = os.getenv("KUCOIN_API_KEY", "") or os.getenv("API_KEY", "")
            api_secret = os.getenv("KUCOIN_API_SECRET", "") or os.getenv("API_SECRET", "")
            api_passphrase = os.getenv("KUCOIN_API_PASSPHRASE", "") or os.getenv("API_PASSPHRASE", "")
            source = "env"
        except Exception as exc:
            last_error = exc
            logger.warning(
                "⚠️ Credenciais KuCoin tentativa %s/%s falhou (%s/%s): %s",
                attempt,
                max_attempts,
                symbol,
                profile,
                exc,
            )
            api_key = api_secret = api_passphrase = ""
            source = f"error:{type(exc).__name__}"

        if api_key and api_secret and api_passphrase:
            if attempt > 1:
                logger.info(
                    "🔑 KuCoin credentials loaded from %s after %s attempt(s) "
                    "(%s / %s) (key: %s...%s)",
                    source,
                    attempt,
                    symbol,
                    profile,
                    api_key[:8],
                    api_key[-4:],
                )
            else:
                logger.info(
                    "🔑 KuCoin credentials loaded from %s (%s / %s) (key: %s...%s)",
                    source,
                    symbol,
                    profile,
                    api_key[:8],
                    api_key[-4:],
                )
            if not str(source).startswith("agent-secrets"):
                _send_telegram_alert(
                    f"🚨 *Trading Agent — Fallback de Credenciais*\n\n"
                    f"• Agent: `{agent_label}`\n"
                    f"• Par: `{symbol}`\n"
                    f"• Profile: `{profile}`\n"
                    f"• Unit: `{unit_name}`\n"
                    f"• Origem: `{source}`\n"
                    f"• Ação: verificar Secrets Agent / env no homelab."
                )
            return api_key, api_secret, api_passphrase

        if attempt < max_attempts:
            delay = float(base_delay_sec) * attempt
            logger.warning(
                "⚠️ Credenciais KuCoin incompletas tentativa %s/%s (%s / %s, source=%s) "
                "— retry em %.1fs",
                attempt,
                max_attempts,
                symbol,
                profile,
                source,
                delay,
            )
            sleep_fn(delay)

    logger.error(
        "❌ Nenhuma credencial KuCoin encontrada após %s tentativas "
        "(%s / %s, unit=%s, last_error=%s)",
        max_attempts,
        symbol,
        profile,
        unit_name,
        last_error,
    )
    _send_telegram_alert(
        "🔴 *Trading Agent — ERRO CRÍTICO*\n\n"
        "Nenhuma credencial KuCoin disponível após retries.\n"
        f"• Agent: `{agent_label}`\n"
        f"• Par: `{symbol}`\n"
        f"• Profile: `{profile}`\n"
        f"• Unit: `{unit_name}`\n"
        f"• Tentativas: `{max_attempts}`\n"
        "Nem o Agent Secrets nem as env vars devolveram as 3 chaves.\n"
        "*Este processo NÃO conseguirá operar em live.*"
    )
    return api_key, api_secret, api_passphrase


# ====================== CREDENCIAIS ======================
API_KEY, API_SECRET, API_PASSPHRASE = _load_credentials()
API_KEY_VERSION = os.getenv("API_KEY_VERSION", "1")
KUCOIN_BASE = os.getenv("KUCOIN_BASE", "https://api.kucoin.com").rstrip("/")
_SERVER_TIME_OFFSET_MS = 0
_SERVER_TIME_SYNC_TTL_SECONDS = 30.0
_SERVER_TIME_LAST_SYNC = 0.0
_SYMBOLS_CACHE_TTL_SECONDS = 300.0
_SYMBOLS_CACHE: Dict[str, Any] = {
    "expires_at": 0.0,
    "symbols": [],
}

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
    """Obtém timestamp bruto do servidor KuCoin em milissegundos."""
    try:
        r = requests.get(f"{KUCOIN_BASE}/api/v1/timestamp", timeout=5)
        if r.status_code == 200:
            return r.json().get("data", int(time.time() * 1000))
    except requests.RequestException as exc:
        logger.warning(f"⚠️ Failed to fetch KuCoin server time: {exc}")
    return int(time.time() * 1000)

def _sync_server_time_offset(force_refresh: bool = False) -> int:
    """Sincroniza o offset entre o relógio local e o relógio da KuCoin."""
    global _SERVER_TIME_OFFSET_MS, _SERVER_TIME_LAST_SYNC

    now = time.time()
    if not force_refresh and (now - _SERVER_TIME_LAST_SYNC) < _SERVER_TIME_SYNC_TTL_SECONDS:
        return _SERVER_TIME_OFFSET_MS

    local_before = int(time.time() * 1000)
    server_ts = _server_time()
    local_after = int(time.time() * 1000)
    local_mid = (local_before + local_after) // 2

    _SERVER_TIME_OFFSET_MS = server_ts - local_mid
    _SERVER_TIME_LAST_SYNC = now
    logger.info(
        "🕒 KuCoin time sync: server=%s local_mid=%s offset_ms=%s",
        server_ts,
        local_mid,
        _SERVER_TIME_OFFSET_MS,
    )
    return _SERVER_TIME_OFFSET_MS

def _current_kucoin_timestamp_ms(force_refresh: bool = False) -> int:
    """Retorna timestamp ajustado para assinatura com base no offset sincronizado."""
    offset_ms = _sync_server_time_offset(force_refresh=force_refresh)
    return int(time.time() * 1000) + offset_ms

def _build_headers(
    method: str,
    endpoint: str,
    body_str: str = "",
    timestamp_ms: Optional[int] = None,
) -> Dict[str, str]:
    """Constrói headers autenticados para API."""
    validate_credentials()

    ts = str(timestamp_ms if timestamp_ms is not None else _current_kucoin_timestamp_ms())
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

def _is_invalid_timestamp_response(result: Dict[str, Any]) -> bool:
    """Detecta rejeição de timestamp inválido retornada pela KuCoin."""
    code = str(result.get("code", ""))
    message = str(result.get("msg", "")).upper()
    return code == "400002" or "KC-API-TIMESTAMP" in message

def _signed_request(
    method: str,
    endpoint: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    body_str: str = "",
    timeout: float = 10,
    max_timestamp_retries: int = 2,
) -> requests.Response:
    """Executa request autenticada com retry específico para drift de timestamp."""
    validate_credentials()

    method_up = method.upper()
    query_string = urlencode(params) if params else ""
    signed_endpoint = f"{endpoint}?{query_string}" if query_string else endpoint
    url = f"{KUCOIN_BASE}{signed_endpoint}"

    for attempt in range(max_timestamp_retries + 1):
        timestamp_ms = _current_kucoin_timestamp_ms(force_refresh=(attempt > 0))
        headers = _build_headers(
            method_up,
            signed_endpoint,
            body_str,
            timestamp_ms=timestamp_ms,
        )

        rate_limit()
        response = requests.request(
            method_up,
            url,
            headers=headers,
            data=body_str or None,
            timeout=timeout,
        )

        try:
            result = response.json()
        except ValueError:
            return response

        if not _is_invalid_timestamp_response(result):
            return response

        if attempt >= max_timestamp_retries:
            logger.error("❌ KuCoin rejected timestamp after %s retries: %s", attempt + 1, result)
            return response

        logger.warning(
            "⚠️ KuCoin rejected timestamp on attempt %s/%s; forcing time resync",
            attempt + 1,
            max_timestamp_retries + 1,
        )
        _sync_server_time_offset(force_refresh=True)

    raise RuntimeError("Unexpected signed request flow termination")

# ====================== PUBLIC ENDPOINTS ======================
def normalize_symbol(symbol: str) -> str:
    """Normaliza pares para o formato BASE-QUOTE usado pela KuCoin."""
    raw = (symbol or "").strip().upper()
    if not raw:
        return ""

    for separator in ("/", "_", " "):
        raw = raw.replace(separator, "-")

    parts = [part for part in raw.split("-") if part]
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return parts[0] if parts else ""


@retry_on_failure(max_retries=2)
def get_symbols(refresh: bool = False, include_disabled: bool = False) -> List[Dict[str, Any]]:
    """Lista símbolos negociáveis da KuCoin com cache curto."""
    now = time.time()
    cached_symbols = _SYMBOLS_CACHE.get("symbols", [])
    if (
        not refresh
        and cached_symbols
        and float(_SYMBOLS_CACHE.get("expires_at", 0.0) or 0.0) > now
    ):
        if include_disabled:
            return list(cached_symbols)
        return [item for item in cached_symbols if bool(item.get("enableTrading", True))]

    url = f"{KUCOIN_BASE}/api/v2/symbols"
    try:
        rate_limit()
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        raw_items = r.json().get("data", [])
        parsed: List[Dict[str, Any]] = []
        for item in raw_items:
            symbol = normalize_symbol(str(item.get("symbol") or ""))
            if not symbol:
                continue

            parsed.append(
                {
                    **item,
                    "symbol": symbol,
                    "baseCurrency": str(item.get("baseCurrency") or "").upper(),
                    "quoteCurrency": str(item.get("quoteCurrency") or "").upper(),
                    "enableTrading": bool(item.get("enableTrading", False)),
                }
            )

        _SYMBOLS_CACHE["symbols"] = parsed
        _SYMBOLS_CACHE["expires_at"] = now + _SYMBOLS_CACHE_TTL_SECONDS
        if include_disabled:
            return list(parsed)
        return [item for item in parsed if bool(item.get("enableTrading", True))]
    except Exception as e:
        logger.warning(f"⚠️ Error getting symbols: {e}")
        if include_disabled:
            return list(cached_symbols)
        return [item for item in cached_symbols if bool(item.get("enableTrading", True))]


def resolve_symbol(
    query: str,
    default_quote: str = "USDT",
    preferred_quotes: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve consulta livre para um par listado na KuCoin."""
    normalized = normalize_symbol(query)
    if not normalized:
        return None

    symbols = get_symbols()
    if not symbols:
        return None

    by_symbol = {str(item.get("symbol") or ""): item for item in symbols}
    direct_match = by_symbol.get(normalized)
    if direct_match:
        return {**direct_match, "matchedBy": "symbol"}

    if "-" in normalized:
        return None

    base_asset = normalized
    quote_order: List[str] = []
    for quote in [default_quote, *(preferred_quotes or []), "USDT", "BRL", "USD", "USDC", "BTC", "ETH", "EUR"]:
        quote_up = str(quote or "").upper()
        if quote_up and quote_up not in quote_order:
            quote_order.append(quote_up)

    candidates = [
        item for item in symbols
        if str(item.get("baseCurrency") or "").upper() == base_asset
    ]
    if candidates:
        def _candidate_sort(item: Dict[str, Any]) -> tuple[int, str]:
            quote = str(item.get("quoteCurrency") or "").upper()
            try:
                rank = quote_order.index(quote)
            except ValueError:
                rank = len(quote_order)
            return rank, str(item.get("symbol") or "")

        best = sorted(candidates, key=_candidate_sort)[0]
        return {**best, "matchedBy": "baseCurrency"}

    inverse_candidates = [
        item for item in symbols
        if str(item.get("quoteCurrency") or "").upper() == base_asset
    ]
    if inverse_candidates:
        best = sorted(
            inverse_candidates,
            key=lambda item: str(item.get("symbol") or ""),
        )[0]
        return {**best, "matchedBy": "quoteCurrency"}

    return None


def search_symbols(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Busca pares próximos quando a consulta não resolve diretamente."""
    needle = normalize_symbol(query)
    if not needle:
        return []

    compact = needle.replace("-", "")
    matches: List[Dict[str, Any]] = []
    for item in get_symbols():
        symbol = str(item.get("symbol") or "")
        base = str(item.get("baseCurrency") or "")
        quote = str(item.get("quoteCurrency") or "")
        haystacks = (
            symbol,
            base,
            quote,
            symbol.replace("-", ""),
        )
        if any(compact in candidate for candidate in haystacks):
            matches.append(item)
        if len(matches) >= limit:
            break
    return matches


@retry_on_failure(max_retries=2)
def get_ticker(symbol: str) -> Dict[str, Any]:
    """Obtém snapshot level1 de um par."""
    normalized = normalize_symbol(symbol)
    if not normalized:
        return {}

    url = f"{KUCOIN_BASE}/api/v1/market/orderbook/level1?symbol={normalized}"
    try:
        rate_limit()
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data") or {}
        if not data:
            return {}

        def _to_float(value: Any) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        return {
            "symbol": normalized,
            "price": _to_float(data.get("price")),
            "bestBid": _to_float(data.get("bestBid")),
            "bestAsk": _to_float(data.get("bestAsk")),
            "size": _to_float(data.get("size")),
            "time": int(data.get("time") or 0),
            "sequence": str(data.get("sequence") or ""),
        }
    except Exception as e:
        logger.warning(f"⚠️ Error getting ticker: {e}")
        return {}


def get_quote_snapshot(
    query: str,
    default_quote: str = "USDT",
    preferred_quotes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Resolve uma moeda/par e retorna snapshot pronto para exibição."""
    match = resolve_symbol(
        query,
        default_quote=default_quote,
        preferred_quotes=preferred_quotes,
    )
    if not match:
        return {}

    ticker = get_ticker(str(match.get("symbol") or ""))
    if not ticker:
        return {}

    return {
        **match,
        **ticker,
        "requested": (query or "").strip(),
    }


@retry_on_failure(max_retries=2)
def get_price(symbol: str = "BTC-USDT") -> Optional[float]:
    """Obtém preço atual de um par"""
    try:
        ticker = get_ticker(symbol)
        if ticker:
            bid = float(ticker.get("bestBid") or 0.0)
            ask = float(ticker.get("bestAsk") or 0.0)
            if bid and ask:
                return (bid + ask) / 2
            price = float(ticker.get("price") or 0.0)
            return price or None
    except Exception as e:
        logger.warning(f"⚠️ Error getting price: {e}")
    return None

def get_price_fast(symbol: str = "BTC-USDT", timeout: float = 1.5) -> Optional[float]:
    """Versão ultra-rápida sem retry"""
    try:
        normalized = normalize_symbol(symbol)
        if not normalized:
            return None
        url = f"{KUCOIN_BASE}/api/v1/market/orderbook/level1?symbol={normalized}"
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
    r = _signed_request("GET", endpoint, timeout=10)
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

def get_sub_account_balances() -> List[Dict[str, Any]]:
    """Obtém saldos de todas as subcontas da conta master.

    Retorna lista plana com um item por (subconta, tipo, moeda):
    {sub_name, account_type, currency, balance, available, holds}.
    Lista vazia se não houver subcontas.
    """
    r = _signed_request("GET", "/api/v1/sub-accounts", timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"API error: {r.status_code}")

    data = r.json().get("data") or []
    # v1 retorna lista; formatos paginados usam {"items": [...]}
    subs = data.get("items", []) if isinstance(data, dict) else data
    out: List[Dict[str, Any]] = []
    for sub in subs:
        name = sub.get("subName") or sub.get("subUserId") or "sub"
        for bucket, acc_type in (
            ("mainAccounts", "main"),
            ("tradeAccounts", "trade"),
            ("marginAccounts", "margin"),
        ):
            for a in sub.get(bucket) or []:
                out.append({
                    "sub_name": name,
                    "account_type": acc_type,
                    "currency": a.get("currency"),
                    "balance": float(a.get("balance", 0)),
                    "available": float(a.get("available", 0)),
                    "holds": float(a.get("holds", 0)),
                })
    return out


def get_balance(currency: str = "USDT") -> float:
    """Obtém saldo específico da conta TRADE."""
    balances = get_balances(account_type="trade")
    for b in balances:
        if b["currency"] == currency:
            return b["available"]
    return 0.0


def get_total_balance(currency: str = "USDT") -> float:
    """Obtém saldo total (MAIN + TRADE).
    
    Usa para detecção de depósitos externos, pois alguns depósitos
    podem chegar em MAIN e não terem sido transferidos para TRADE ainda.
    """
    total = 0.0
    for account_type in ("main", "trade"):
        balances = get_balances(account_type=account_type)
        for b in balances:
            if b["currency"] == currency:
                total += b["available"]
    return total


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

    logger.info(
        f"💸 Inner transfer: {amount:.8f} {currency} "
        f"{from_account} → {to_account}"
    )

    r = _signed_request("POST", endpoint, body_str=body_str, timeout=10)
    result = r.json()
    if result.get("code") != "200000":
        logger.error(f"❌ Inner transfer failed: {result}")
        return {"success": False, "error": result.get("msg", "Unknown")}

    order_id = result.get("data", {}).get("orderId", "")
    logger.info(f"✅ Inner transfer OK: {order_id}")
    return {"success": True, "orderId": order_id}


def sub_transfer(currency: str, amount: float, sub_user_id: str,
                 direction: str = "OUT",
                 account_type: str = "TRADE",
                 sub_account_type: str = "TRADE") -> Dict[str, Any]:
    """Transferência master ↔ subconta KuCoin.

    Args:
        currency: Moeda a transferir (ex: 'USDT').
        amount: Quantidade.
        sub_user_id: UID da subconta (ex: '257506830').
        direction: 'OUT' (master→sub) ou 'IN' (sub→master).
        account_type: Conta do master ('MAIN' ou 'TRADE').
        sub_account_type: Conta da subconta ('MAIN' ou 'TRADE').

    Returns:
        Dict com 'success' e 'orderId' ou 'error'.
    """
    import uuid
    validate_credentials()

    endpoint = "/api/v2/accounts/sub-transfer"
    payload = {
        "clientOid": str(uuid.uuid4()),
        "currency": currency,
        "amount": str(round(amount, 8)),
        "direction": direction,
        "accountType": account_type,
        "subAccountType": sub_account_type,
        "subUserId": str(sub_user_id),
    }
    body_str = json.dumps(payload, separators=(",", ":"))

    logger.info(
        f"💸 Sub transfer: {amount:.8f} {currency} "
        f"master({account_type}) {direction} sub {sub_user_id}({sub_account_type})"
    )

    r = _signed_request("POST", endpoint, body_str=body_str, timeout=10)
    result = r.json()
    if result.get("code") != "200000":
        logger.error(f"❌ Sub transfer failed: {result}")
        return {"success": False, "error": result.get("msg", "Unknown")}

    order_id = (result.get("data") or {}).get("orderId", "")
    logger.info(f"✅ Sub transfer OK: {order_id}")
    return {"success": True, "orderId": order_id}


_symbol_increment_cache: Dict[str, Dict[str, str]] = {}


def get_symbol_increments(symbol: str) -> Dict[str, str]:
    """Retorna baseIncrement/quoteIncrement do símbolo (cache por processo).

    Fallback conservador (8 casas) se a API falhar — equivale ao
    comportamento antigo, válido para BTC-USDT.
    """
    if symbol not in _symbol_increment_cache:
        try:
            r = requests.get(
                f"{KUCOIN_BASE}/api/v2/symbols/{symbol}", timeout=8,
            )
            data = (r.json() or {}).get("data") or {}
            _symbol_increment_cache[symbol] = {
                "baseIncrement": data.get("baseIncrement") or "0.00000001",
                "quoteIncrement": data.get("quoteIncrement") or "0.01",
            }
        except Exception as e:
            logger.warning(f"⚠️ Falha ao obter increments de {symbol}: {e}")
            return {"baseIncrement": "0.00000001", "quoteIncrement": "0.01"}
    return _symbol_increment_cache[symbol]


def _floor_to_increment(value: float, increment: str) -> str:
    """Trunca value para múltiplo do increment, como string decimal exata.

    KuCoin rejeita ordens com mais casas que o increment do símbolo
    ('Order size increment invalid' — ex.: ETH-USDT usa 7 casas, não 8).
    """
    from decimal import Decimal, ROUND_DOWN
    inc = Decimal(increment)
    quantized = (Decimal(str(value)) / inc).to_integral_value(rounding=ROUND_DOWN) * inc
    return format(quantized.normalize(), "f")


@retry_on_failure(max_retries=3)
def place_market_order(symbol: str, side: str, funds: float = None,
                       size: float = None,
                       notify_extra: Dict[str, float] = None) -> Dict[str, Any]:
    """Executa ordem de mercado.

    notify_extra: contexto opcional para a notificação Telegram
    (invested, proceeds, pnl, pnl_pct) — usado nos SELLs.
    """
    validate_credentials()

    endpoint = "/api/v1/orders"
    client_oid = f"btc_agent_{int(time.time() * 1e6)}"

    payload = {
        "clientOid": client_oid,
        "side": side.lower(),
        "symbol": symbol,
        "type": "market",
    }

    increments = get_symbol_increments(symbol)
    if funds is not None:
        # Respeita quoteIncrement do par (BRL/BTC/ETH etc.); round(..., 2) quebrava quotes crypto.
        payload["funds"] = _floor_to_increment(float(funds), increments["quoteIncrement"])
    elif size is not None:
        payload["size"] = _floor_to_increment(float(size), increments["baseIncrement"])
    else:
        raise ValueError("Must specify 'funds' or 'size'")

    body_str = json.dumps(payload, separators=(",", ":"))

    logger.info(f"📤 {side.upper()} {symbol} - funds={funds}, size={size}")

    r = _signed_request("POST", endpoint, body_str=body_str, timeout=15)

    result = r.json()
    if result.get("code") != "200000":
        logger.error(f"❌ Order failed: {result}")
        error_msg = result.get("msg", "Unknown")
        _send_telegram_alert(
            _format_market_order_notification(
                symbol=symbol,
                side=side,
                funds=funds,
                size=size,
                error=error_msg,
                notify_extra=notify_extra,
            )
        )
        return {"success": False, "error": error_msg, "raw": result}

    order_id = result.get("data", {}).get("orderId")
    logger.info(f"✅ Order placed: {order_id}")
    _send_telegram_alert(
        _format_market_order_notification(
            symbol=symbol,
            side=side,
            funds=funds,
            size=size,
            order_id=order_id,
            notify_extra=notify_extra,
        )
    )

    return {"success": True, "orderId": order_id, "raw": result}


# ====================== WITHDRAWAL / DEPOSIT / FEES ======================
@retry_on_failure(max_retries=2)
def get_withdrawal_quotas(currency: str, chain: Optional[str] = None) -> Dict[str, Any]:
    """Obtém limites e taxas de saque para uma moeda/chain.

    Requer permissão: Withdrawal + IP Restriction habilitada.

    Args:
        currency: Moeda (ex: 'USDT', 'BTC').
        chain: Rede blockchain (ex: 'trc20', 'erc20', 'trx'). Opcional.

    Returns:
        Dict com limitAvailable, withdrawMinFee, withdrawMinSize, etc.
    """
    endpoint = "/api/v1/withdrawals/quotas"
    params: Dict[str, str] = {"currency": currency}
    if chain:
        params["chain"] = chain

    r = _signed_request("GET", endpoint, params=params, timeout=10)
    result = r.json()
    if result.get("code") != "200000":
        logger.error(f"❌ Withdrawal quotas failed: {result}")
        return {"success": False, "error": result.get("msg", "Unknown")}

    data = result.get("data", {})
    logger.info(
        f"📊 Withdrawal quotas {currency}"
        f"{f'/{chain}' if chain else ''}: "
        f"min={data.get('withdrawMinSize')}, "
        f"fee={data.get('withdrawMinFee')}, "
        f"available={data.get('limitAvailable')}"
    )
    return {"success": True, **data}


@retry_on_failure(max_retries=2)
def get_deposit_addresses(currency: str, chain: Optional[str] = None) -> Dict[str, Any]:
    """Obtém endereço(s) de depósito para uma moeda.

    Args:
        currency: Moeda (ex: 'USDT', 'BTC').
        chain: Rede blockchain opcional (ex: 'trc20', 'erc20').

    Returns:
        Dict com address, memo (se aplicável) e chain.
    """
    endpoint = "/api/v3/deposit-addresses"
    params: Dict[str, str] = {"currency": currency}
    if chain:
        params["chain"] = chain

    r = _signed_request("GET", endpoint, params=params, timeout=10)
    result = r.json()
    if result.get("code") != "200000":
        logger.error(f"❌ Deposit addresses failed: {result}")
        return {"success": False, "error": result.get("msg", "Unknown")}

    data = result.get("data", [])
    logger.info(f"📥 Deposit addresses for {currency}: {len(data)} found")
    return {"success": True, "addresses": data}


@retry_on_failure(max_retries=2)
def create_deposit_address(currency: str, chain: Optional[str] = None) -> Dict[str, Any]:
    """Cria um novo endereço de depósito.

    Args:
        currency: Moeda (ex: 'USDT', 'BTC').
        chain: Rede blockchain (ex: 'trc20', 'erc20').

    Returns:
        Dict com address, memo e chain.
    """
    endpoint = "/api/v1/deposit-addresses"
    payload: Dict[str, str] = {"currency": currency}
    if chain:
        payload["chain"] = chain

    body_str = json.dumps(payload, separators=(",", ":"))
    r = _signed_request("POST", endpoint, body_str=body_str, timeout=10)
    result = r.json()
    if result.get("code") != "200000":
        logger.error(f"❌ Create deposit address failed: {result}")
        return {"success": False, "error": result.get("msg", "Unknown")}

    data = result.get("data", {})
    logger.info(f"✅ Deposit address created: {currency}/{chain or 'default'}")
    return {"success": True, **data}


@retry_on_failure(max_retries=2)
def list_deposits(
    currency: Optional[str] = None,
    status: Optional[str] = None,
    start_at: Optional[int] = None,
    end_at: Optional[int] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Lista depósitos recentes.

    Args:
        currency: Filtrar por moeda.
        status: Filtrar por status (PROCESSING, SUCCESS, FAILURE).
        start_at: Timestamp ms início.
        end_at: Timestamp ms fim.
        limit: Máximo de registros.

    Returns:
        Lista de depósitos.
    """
    endpoint = "/api/v1/deposits"
    params: Dict[str, Any] = {"pageSize": limit}
    if currency:
        params["currency"] = currency
    if status:
        params["status"] = status
    if start_at:
        params["startAt"] = start_at
    if end_at:
        params["endAt"] = end_at

    r = _signed_request("GET", endpoint, params=params, timeout=10)
    result = r.json()
    if result.get("code") != "200000":
        logger.error(f"❌ List deposits failed: {result}")
        return []

    return result.get("data", {}).get("items", [])


def apply_withdrawal(
    currency: str,
    address: str,
    amount: float,
    chain: Optional[str] = None,
    memo: Optional[str] = None,
    is_inner: bool = False,
    remark: Optional[str] = None,
    fee_deduct_type: str = "INTERNAL",
) -> Dict[str, Any]:
    """Solicita saque de criptomoeda.

    ⚠️ REQUER: API Key com permissão 'Withdrawal' + IP Restriction habilitada.
    Para habilitar IP Restriction, cadastre o IPv6 fixo do homelab na KuCoin.

    Args:
        currency: Moeda a sacar (ex: 'USDT', 'BTC').
        address: Endereço de destino na blockchain.
        amount: Quantidade a sacar.
        chain: Rede blockchain (ex: 'trc20', 'erc20', 'trx'). Recomendado.
        memo: Memo/tag (necessário para XRP, EOS, etc.).
        is_inner: True para transferência interna KuCoin (sem fee on-chain).
        remark: Observação interna.
        fee_deduct_type: 'INTERNAL' (fee do saldo) ou 'EXTERNAL' (fee do amount).

    Returns:
        Dict com 'success', 'withdrawalId' ou 'error'.
    """
    validate_credentials()

    endpoint = "/api/v3/withdrawals"
    payload: Dict[str, Any] = {
        "currency": currency,
        "address": address,
        "amount": str(round(amount, 8)),
    }

    if chain:
        payload["chain"] = chain
    if memo:
        payload["memo"] = memo
    if is_inner:
        payload["isInner"] = True
    if remark:
        payload["remark"] = remark
    if fee_deduct_type:
        payload["feeDeductType"] = fee_deduct_type

    body_str = json.dumps(payload, separators=(",", ":"))

    logger.info(
        f"📤 Withdrawal request: {amount:.8f} {currency} → "
        f"{address[:12]}...{address[-6:]} "
        f"chain={chain or 'default'} inner={is_inner}"
    )

    # Alerta Telegram antes de executar (segurança)
    _send_telegram_alert(
        f"🔔 *Saque Solicitado*\n\n"
        f"• Moeda: `{currency}`\n"
        f"• Valor: `{amount:.8f}`\n"
        f"• Destino: `{address[:16]}...`\n"
        f"• Chain: `{chain or 'default'}`\n"
        f"• Interno: `{is_inner}`"
    )

    r = _signed_request("POST", endpoint, body_str=body_str, timeout=15)
    result = r.json()
    if result.get("code") != "200000":
        error_msg = result.get("msg", "Unknown")
        logger.error(f"❌ Withdrawal failed: {result}")
        _send_telegram_alert(
            f"🔴 *Saque FALHOU*\n"
            f"• Moeda: `{currency}` Valor: `{amount}`\n"
            f"• Erro: `{error_msg}`"
        )
        return {"success": False, "error": error_msg, "raw": result}

    withdrawal_id = result.get("data", {}).get("withdrawalId", "")
    logger.info(f"✅ Withdrawal submitted: {withdrawal_id}")
    _send_telegram_alert(
        f"✅ *Saque Enviado*\n"
        f"• ID: `{withdrawal_id}`\n"
        f"• Moeda: `{currency}` Valor: `{amount}`"
    )
    return {"success": True, "withdrawalId": withdrawal_id, "raw": result}


@retry_on_failure(max_retries=2)
def cancel_withdrawal(withdrawal_id: str) -> Dict[str, Any]:
    """Cancela um saque pendente.

    Args:
        withdrawal_id: ID do saque retornado por apply_withdrawal.

    Returns:
        Dict com 'success' ou 'error'.
    """
    endpoint = f"/api/v1/withdrawals/{withdrawal_id}"
    r = _signed_request("DELETE", endpoint, timeout=10)
    result = r.json()
    if result.get("code") != "200000":
        logger.error(f"❌ Cancel withdrawal failed: {result}")
        return {"success": False, "error": result.get("msg", "Unknown")}

    logger.info(f"✅ Withdrawal cancelled: {withdrawal_id}")
    return {"success": True}


@retry_on_failure(max_retries=2)
def list_withdrawals(
    currency: Optional[str] = None,
    status: Optional[str] = None,
    start_at: Optional[int] = None,
    end_at: Optional[int] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Lista saques recentes.

    Args:
        currency: Filtrar por moeda.
        status: PROCESSING, WALLET_PROCESSING, SUCCESS, FAILURE.
        start_at: Timestamp ms início.
        end_at: Timestamp ms fim.
        limit: Máximo de registros.

    Returns:
        Lista de saques.
    """
    endpoint = "/api/v1/withdrawals"
    params: Dict[str, Any] = {"pageSize": limit}
    if currency:
        params["currency"] = currency
    if status:
        params["status"] = status
    if start_at:
        params["startAt"] = start_at
    if end_at:
        params["endAt"] = end_at

    r = _signed_request("GET", endpoint, params=params, timeout=10)
    result = r.json()
    if result.get("code") != "200000":
        logger.error(f"❌ List withdrawals failed: {result}")
        return []

    return result.get("data", {}).get("items", [])


def get_transferable(currency: str, account_type: str = "MAIN") -> float:
    """Obtém saldo transferível de uma conta.

    Args:
        currency: Moeda (ex: 'USDT').
        account_type: MAIN, TRADE, MARGIN.

    Returns:
        Valor transferível disponível.
    """
    endpoint = "/api/v1/accounts/transferable"
    params = {"currency": currency, "type": account_type.upper()}

    r = _signed_request("GET", endpoint, params=params, timeout=10)
    result = r.json()
    if result.get("code") != "200000":
        logger.warning(f"⚠️ Get transferable failed: {result}")
        return 0.0

    return float(result.get("data", {}).get("transferable", 0))


def get_base_fee(currency_type: str = "1") -> Dict[str, Any]:
    """Obtém taxas base de trading.

    Args:
        currency_type: '0' para crypto-crypto, '1' para crypto-stablecoin.

    Returns:
        Dict com takerFeeRate e makerFeeRate.
    """
    endpoint = "/api/v1/base-fee"
    params = {"currencyType": currency_type}

    r = _signed_request("GET", endpoint, params=params, timeout=10)
    result = r.json()
    if result.get("code") != "200000":
        logger.warning(f"⚠️ Get base fee failed: {result}")
        return {"success": False}

    data = result.get("data", {})
    return {
        "success": True,
        "takerFeeRate": float(data.get("takerFeeRate", 0)),
        "makerFeeRate": float(data.get("makerFeeRate", 0)),
    }


def get_trade_fees(symbols: str) -> List[Dict[str, Any]]:
    """Obtém taxas de trading para pares específicos.

    Args:
        symbols: Pares separados por vírgula (ex: 'BTC-USDT,ETH-USDT').

    Returns:
        Lista com taxas por par.
    """
    endpoint = "/api/v1/trade-fees"
    params = {"symbols": symbols}

    r = _signed_request("GET", endpoint, params=params, timeout=10)
    result = r.json()
    if result.get("code") != "200000":
        logger.warning(f"⚠️ Get trade fees failed: {result}")
        return []

    return result.get("data", [])


@retry_on_failure(max_retries=2)
def get_order_details(order_id: str) -> Optional[Dict[str, Any]]:
    """Obtém detalhes de uma ordem"""
    endpoint = f"/api/v1/orders/{order_id}"
    r = _signed_request("GET", endpoint, timeout=10)
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

    r = _signed_request("GET", endpoint, params=params, timeout=10)
    if r.status_code == 200 and r.json().get("code") == "200000":
        return r.json().get("data", {}).get("items", [])
    return []


def get_fills_for_order(
    order_id: str,
    symbol: Optional[str] = None,
    *,
    max_retries: int = 4,
    retry_delay: float = 2.0,
) -> Dict[str, Any]:
    """Retorna resumo de fills de uma ordem específica.

    Faz polling com retry porque fills podem não aparecer imediatamente após
    a ordem ser aceita pela exchange. Retorna dict vazio se não encontrar.

    Campos retornados:
      fill_price    — preço médio ponderado pelo tamanho
      fill_size     — tamanho total preenchido (BTC)
      fill_funds    — valor total em USDT
      fill_fee      — taxa total cobrada (na feeCurrency)
      fee_currency  — moeda da taxa (USDT ou KCS)
      fee_rate      — taxa efetiva (ex: 0.001 = 0.1%)
      liquidity     — "taker" ou "maker"
      fills_count   — número de parciais preenchidas
    """
    params: Dict[str, Any] = {"orderId": order_id, "pageSize": 20}
    if symbol:
        params["symbol"] = symbol

    for attempt in range(max_retries):
        if attempt > 0:
            time.sleep(retry_delay)
        try:
            r = _signed_request("GET", "/api/v1/fills", params=params, timeout=10)
            if r.status_code != 200:
                continue
            payload = r.json()
            if payload.get("code") != "200000":
                continue
            items = (payload.get("data") or {}).get("items") or []
            if not items:
                continue

            total_size  = sum(float(it.get("size")  or 0) for it in items)
            total_funds = sum(float(it.get("funds") or 0) for it in items)
            total_fee   = sum(float(it.get("fee")   or 0) for it in items)
            fee_currency = items[0].get("feeCurrency", "USDT")
            fee_rate     = float(items[0].get("feeRate") or 0)
            liquidity    = items[0].get("liquidity", "taker")
            avg_price    = total_funds / total_size if total_size > 0 else 0.0

            return {
                "fill_price":   round(avg_price,   8),
                "fill_size":    round(total_size,  8),
                "fill_funds":   round(total_funds, 8),
                "fill_fee":     round(total_fee,   8),
                "fee_currency": fee_currency,
                "fee_rate":     fee_rate,
                "liquidity":    liquidity,
                "fills_count":  len(items),
            }
        except Exception as exc:
            logger.warning("⚠️ get_fills_for_order attempt %d/%d: %s", attempt + 1, max_retries, exc)

    return {}


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
