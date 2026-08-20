"""Profile rules for trading runtimes.

BTC-USDT is intentionally restricted to the dual-profile runtime:
- conservative
- aggressive
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

BTC_STRICT_SYMBOL = "BTC-USDT"
BTC_ALLOWED_PROFILES = {"conservative", "aggressive", "shadow"}


def normalize_profile(profile: Any) -> str:
    """Return a normalized profile string with a stable fallback."""
    value = str(profile or "default").strip().lower()
    return value or "default"


def validate_profile_for_symbol(
    symbol: Any,
    profile: Any,
    *,
    config_name: str | None = None,
) -> str:
    """Validate the runtime profile for a symbol and return the normalized value."""
    normalized_symbol = str(symbol or "").strip().upper()
    normalized_profile = normalize_profile(profile)
    if normalized_symbol == BTC_STRICT_SYMBOL and normalized_profile not in BTC_ALLOWED_PROFILES:
        location = f" ({config_name})" if config_name else ""
        raise ValueError(
            f"BTC-USDT requires profile 'conservative' or 'aggressive'{location}; "
            f"found '{normalized_profile}'"
        )
    return normalized_profile


def config_subaccount_name(payload: Any) -> str:
    """Nome da subconta KuCoin no config, ou string vazia."""
    if not isinstance(payload, Mapping):
        return ""
    return str(payload.get("kucoin_subaccount_name") or "").strip()


def open_buy_net_sql_predicate(*, exclude_external_deposits: bool = False) -> str:
    """Predicado SQL de BUY ainda aberto (ignora status=closed e closed_reason)."""
    clause = (
        "side='buy' AND status <> 'closed' "
        "AND COALESCE(metadata->>'closed_reason','') = ''"
    )
    if exclude_external_deposits:
        clause += " AND COALESCE(metadata->>'source','') != 'external_deposit'"
    return clause


def live_config_shares_subaccount(
    *,
    current_symbol: str,
    current_profile: str,
    current_subaccount: str,
    current_config_name: str,
    candidate_name: str,
    candidate: Mapping[str, Any],
) -> bool:
    """True se o outro config live opera o mesmo par na mesma subconta.

    Sem nome de subconta nos dois lados não assume compartilhamento — configs
    no mesmo diretório (conservative vs shadow) não compartilham spot.
    """
    own = str(current_subaccount or "").strip()
    if not own:
        return False
    if candidate_name == current_config_name:
        return False
    if candidate.get("symbol", current_symbol) != current_symbol:
        return False
    if not bool(candidate.get("enabled", True)):
        return False
    if candidate.get("dry_run") is True:
        return False
    if "live_mode" in candidate and not bool(candidate.get("live_mode")):
        return False
    try:
        candidate_profile = validate_profile_for_symbol(
            current_symbol,
            candidate.get("profile", "default"),
            config_name=candidate_name,
        )
    except ValueError:
        return False
    if candidate_profile in {"default", current_profile}:
        return False
    other = config_subaccount_name(candidate)
    if not other:
        return False
    return own.casefold() == other.casefold()
