"""Profile rules for trading runtimes.

BTC-USDT is intentionally restricted to the dual-profile runtime:
- conservative
- aggressive
"""

from __future__ import annotations

from typing import Any

BTC_STRICT_SYMBOL = "BTC-USDT"
BTC_ALLOWED_PROFILES = {"conservative", "aggressive"}


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
