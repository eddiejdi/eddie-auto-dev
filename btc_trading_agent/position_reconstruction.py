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
        "dry_run": bool(trade.get("dry_run", False)),
    }


def _is_excluded_buy(trade: dict[str, Any], *, exclude_external_deposits: bool) -> bool:
    if trade.get("side") != "buy":
        return False
    if not exclude_external_deposits:
        return False
    source = str(trade.get("metadata", {}).get("source") or "")
    # Depósitos e fills de conversão intermoedas não contam como entries de swing
    return source in ("external_deposit", "conversion")


def reconstruct_open_buys(
    trades: list[dict[str, Any]],
    *,
    shared_profile_ambiguous: bool = False,
    exclude_external_deposits: bool = True,
) -> list[dict[str, Any]]:
    """Reconstrói BUYs abertos a partir de trades em ordem decrescente de tempo.

    Passe único, cronológico (trades vêm mais recente → mais antigo): créditos
    de SELL são acumulados conforme encontrados e só podem fechar um BUY que
    aparece DEPOIS no scan (ou seja, mais antigo de verdade — nunca um BUY
    mais novo que o próprio SELL, o que violaria causalidade).

    Um SELL com metadata de slot (`slot_exit_reason` + `slot_buy_trade_id`,
    ou preço como fallback) fecha exatamente a entrada que referencia. Um
    SELL sem esse metadata ("cego" — reconciliação manual/exchange/legado)
    soma seu `size` a um pool de volume cego; um BUY é considerado fechado
    quando esse pool cobre o tamanho do BUY dentro de uma tolerância de
    0,2% (cobre fees/rounding entre o size nominal da compra e o size real
    vendido). Isso substitui o antigo "qualquer SELL cego = flatten total
    do que vier antes" — que descartava entradas legitimamente abertas
    sempre que UM ÚNICO sell cego mais recente aparecia no ledger, mesmo
    que ele só tivesse fechado uma entrada específica (medido em produção:
    ~30 posições BTC e 4 posições DOGE ficaram invisíveis pro bot por causa
    disso, apesar de ainda abertas/vendíveis).

    Em conta compartilhada (`shared_profile_ambiguous=True`), o matching por
    preço fica desabilitado — preços podem colidir entre profiles que dividem
    a mesma subconta KuCoin — mas o matching por `slot_buy_trade_id` continua
    válido, pois o id referencia um trade já filtrado por profile na consulta
    ao banco.
    """
    normalized = [_normalize_trade(trade) for trade in trades]
    allow_price_matching = not shared_profile_ambiguous

    slot_sells_by_id: dict[int, int] = {}
    slot_sells_by_price: dict[float, int] = {}
    blind_sell_volume = 0.0
    open_buys: list[dict[str, Any]] = []

    for trade in normalized:
        side = trade.get("side")
        if side in SELL_SIDES:
            metadata = trade.get("metadata", {})
            matched_credit = False
            if metadata.get("slot_exit_reason"):
                buy_id = metadata.get("slot_buy_trade_id")
                slot_price = metadata.get("slot_entry_price")
                if buy_id:
                    key = int(buy_id)
                    slot_sells_by_id[key] = slot_sells_by_id.get(key, 0) + 1
                    matched_credit = True
                elif slot_price and allow_price_matching:
                    try:
                        key = round(float(slot_price), 2)
                        slot_sells_by_price[key] = slot_sells_by_price.get(key, 0) + 1
                        matched_credit = True
                    except (TypeError, ValueError):
                        pass
            if not matched_credit:
                blind_sell_volume += float(trade.get("size", 0) or 0)
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
        buy_size = float(trade.get("size", 0) or 0)
        consumed = False

        if trade_id:
            trade_id_int = int(trade_id)
            if slot_sells_by_id.get(trade_id_int, 0) > 0:
                slot_sells_by_id[trade_id_int] -= 1
                consumed = True
        if not consumed and allow_price_matching and slot_sells_by_price.get(price_key, 0) > 0:
            slot_sells_by_price[price_key] -= 1
            consumed = True
        if not consumed and buy_size > 0:
            tolerance = max(1e-8, buy_size * 0.002)
            if blind_sell_volume >= buy_size - tolerance:
                blind_sell_volume = max(0.0, blind_sell_volume - buy_size)
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
