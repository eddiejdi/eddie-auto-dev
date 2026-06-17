#!/usr/bin/env python3
"""Helpers para reconstruir posição aberta a partir do ledger de trades."""

from __future__ import annotations

import json
from typing import Any

SELL_SIDES = {"sell", "sell_reconciled"}


def _parse_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_trade(trade: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": trade.get("id"),
        "side": str(trade.get("side") or "").lower(),
        "price": float(trade.get("price", 0) or 0),
        "size": float(trade.get("size", 0) or 0),
        "timestamp": float(trade.get("timestamp", 0) or 0),
        "metadata": _parse_metadata(trade.get("metadata")),
    }


def _is_excluded_buy(trade: dict[str, Any], *, exclude_external_deposits: bool) -> bool:
    if trade.get("side") != "buy":
        return False
    if not exclude_external_deposits:
        return False
    return str(trade.get("metadata", {}).get("source") or "") == "external_deposit"


def _reconstruct_recent_buy_streak(
    trades: list[dict[str, Any]],
    *,
    exclude_external_deposits: bool,
) -> list[dict[str, Any]]:
    """Em conta compartilhada, usa apenas a sequência recente de BUYs ainda não revertida.

    Isso evita ressuscitar posições antigas de outro profile quando o saldo spot
    global é compartilhado e o ledger por profile já divergiu da KuCoin.
    """
    open_buys: list[dict[str, Any]] = []
    for trade in trades:
        side = trade.get("side")
        if side in SELL_SIDES:
            break
        if side == "buy" and not _is_excluded_buy(
            trade,
            exclude_external_deposits=exclude_external_deposits,
        ):
            open_buys.append(trade)
    return open_buys


def reconstruct_open_buys(
    trades: list[dict[str, Any]],
    *,
    shared_profile_ambiguous: bool = False,
    exclude_external_deposits: bool = True,
) -> list[dict[str, Any]]:
    """Reconstrói BUYs abertos a partir de trades em ordem decrescente de tempo."""
    normalized = [_normalize_trade(trade) for trade in trades]

    if shared_profile_ambiguous:
        return _reconstruct_recent_buy_streak(
            normalized,
            exclude_external_deposits=exclude_external_deposits,
        )

    slot_sells_by_id: dict[int, int] = {}
    slot_sells_by_price: dict[float, int] = {}
    slot_sells_blind = 0
    has_global_sell = False

    for trade in normalized:
        if trade.get("side") not in SELL_SIDES:
            continue
        metadata = trade.get("metadata", {})
        if metadata.get("slot_exit_reason"):
            buy_id = metadata.get("slot_buy_trade_id")
            slot_price = metadata.get("slot_entry_price")
            if buy_id:
                key = int(buy_id)
                slot_sells_by_id[key] = slot_sells_by_id.get(key, 0) + 1
            elif slot_price:
                try:
                    key = round(float(slot_price), 2)
                    slot_sells_by_price[key] = slot_sells_by_price.get(key, 0) + 1
                except (TypeError, ValueError):
                    slot_sells_blind += 1
            else:
                slot_sells_blind += 1
        else:
            has_global_sell = True
            break

    open_buys: list[dict[str, Any]] = []
    for trade in normalized:
        side = trade.get("side")
        if side in SELL_SIDES:
            if has_global_sell and not trade.get("metadata", {}).get("slot_exit_reason"):
                break
            continue
        if side != "buy":
            continue
        if _is_excluded_buy(
            trade,
            exclude_external_deposits=exclude_external_deposits,
        ):
            continue

        trade_id = trade.get("id")
        price_key = round(float(trade.get("price", 0) or 0), 2)
        consumed = False

        if trade_id:
            trade_id_int = int(trade_id)
            if slot_sells_by_id.get(trade_id_int, 0) > 0:
                slot_sells_by_id[trade_id_int] -= 1
                consumed = True
        if not consumed and slot_sells_by_price.get(price_key, 0) > 0:
            slot_sells_by_price[price_key] -= 1
            consumed = True
        if not consumed and slot_sells_blind > 0:
            slot_sells_blind -= 1
            consumed = True
        if not consumed:
            open_buys.append(trade)

    return open_buys


def summarize_open_buys(open_buys: list[dict[str, Any]]) -> tuple[float, float]:
    """Retorna (total_btc, avg_entry_price) para a lista de BUYs abertos."""
    total_btc = sum(float(trade.get("size", 0) or 0) for trade in open_buys)
    if total_btc <= 0:
        return 0.0, 0.0
    total_cost = sum(
        float(trade.get("size", 0) or 0) * float(trade.get("price", 0) or 0)
        for trade in open_buys
    )
    return total_btc, (total_cost / total_btc)
