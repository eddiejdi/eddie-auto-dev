"""Administra buffer de KCS para Pay Fees with KCS (owner: USDT_BRL).

Responsabilidades (somente master credentials):
  - Monitorar KCS **livre** no TRADE (Earn REDEEMING não paga fee)
  - Sweep MAIN→TRADE se KCS cair na funding/main
  - Opcional: financiar USDT com BRL (par USDT-BRL) se TRADE USDT insuficiente
  - Comprar KCS-USDT se o buffer livre < mínimo
  - Distribuir surplus para subcontas BTC/ETH

Sem side-effects se dry_run=True. Deps injetáveis para testes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_SUBS = (
    "BTCAgressive",
    "BTCConservative",
    "ETHAgressive",
    "ETHConservative",
)


@dataclass
class KcsSnapshot:
    trade_kcs: float = 0.0
    trade_usdt: float = 0.0
    trade_brl: float = 0.0
    main_kcs: float = 0.0
    redeeming_kcs: float = 0.0
    held_earn_kcs: float = 0.0
    earn_status: str = ""
    kcs_price: float = 0.0
    usdt_brl_price: float = 0.0
    sub_kcs: Dict[str, float] = field(default_factory=dict)
    sub_uids: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KcsAction:
    kind: str  # buy | fund_usdt_from_brl | transfer_main | transfer_sub | wait_redeem | noop
    detail: str
    amount: float = 0.0
    usdt: float = 0.0
    brl: float = 0.0
    sub_name: str = ""
    executed: bool = False
    dry_run: bool = True
    error: str = ""
    order_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KcsAdminResult:
    actions: List[KcsAction] = field(default_factory=list)
    snapshot: Optional[KcsSnapshot] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "actions": [a.to_dict() for a in self.actions],
        }


def _cfg_float(cfg: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def collect_snapshot(
    *,
    subs: List[str],
    get_balance_fn: Callable[[str], float],
    get_main_balance_fn: Optional[Callable[[str], float]] = None,
    get_price_fn: Callable[[str], Optional[float]],
    get_earn_hold_fn: Callable[[], Dict[str, Any]],
    list_sub_users_fn: Callable[[], List[Dict[str, Any]]],
    get_sub_kcs_fn: Callable[[str], float],
    pair: str = "KCS-USDT",
) -> KcsSnapshot:
    snap = KcsSnapshot()
    try:
        snap.trade_kcs = float(get_balance_fn("KCS") or 0.0)
    except Exception as exc:
        logger.debug("KCS balance error: %s", exc)
    try:
        snap.trade_usdt = float(get_balance_fn("USDT") or 0.0)
    except Exception as exc:
        logger.debug("USDT balance error: %s", exc)
    try:
        snap.trade_brl = float(get_balance_fn("BRL") or 0.0)
    except Exception as exc:
        logger.debug("BRL balance error: %s", exc)
    if get_main_balance_fn is not None:
        try:
            snap.main_kcs = float(get_main_balance_fn("KCS") or 0.0)
        except Exception as exc:
            logger.debug("MAIN KCS balance error: %s", exc)
    try:
        px = get_price_fn(pair)
        snap.kcs_price = float(px or 0.0)
    except Exception as exc:
        logger.debug("KCS price error: %s", exc)
    try:
        ub = get_price_fn("USDT-BRL")
        snap.usdt_brl_price = float(ub or 0.0)
    except Exception as exc:
        logger.debug("USDT-BRL price error: %s", exc)

    try:
        earn = get_earn_hold_fn() or {}
        items = earn.get("items") or []
        redeeming = 0.0
        held = 0.0
        status_bits: List[str] = []
        for it in items:
            if str(it.get("currency") or "").upper() != "KCS":
                continue
            st = str(it.get("status") or "")
            status_bits.append(st)
            try:
                held += float(it.get("holdAmount") or 0)
            except (TypeError, ValueError):
                pass
            try:
                redeeming += float(it.get("redeemingAmount") or 0)
            except (TypeError, ValueError):
                pass
        snap.held_earn_kcs = held
        snap.redeeming_kcs = redeeming
        snap.earn_status = ",".join(status_bits) if status_bits else "none"
    except Exception as exc:
        logger.debug("earn hold error: %s", exc)
        snap.earn_status = "error"

    try:
        for u in list_sub_users_fn() or []:
            name = str(u.get("subName") or "")
            # KuCoin sub-transfer expects subUserId = userId (hex string), not numeric uid
            uid = u.get("userId") or u.get("subUserId") or u.get("uid")
            if name and uid is not None:
                snap.sub_uids[name] = str(uid)
    except Exception as exc:
        logger.debug("list sub users error: %s", exc)

    for name in subs:
        try:
            snap.sub_kcs[name] = float(get_sub_kcs_fn(name) or 0.0)
        except Exception:
            snap.sub_kcs[name] = 0.0
    return snap


def plan_actions(cfg: Dict[str, Any], snap: KcsSnapshot) -> List[KcsAction]:
    """Planeja sweep / fund / buy / transfers sem executar.

    Importante: KCS em Earn REDEEMING **não** serve para Pay Fees.
    Só conta ``trade_kcs`` livre.
    """
    actions: List[KcsAction] = []
    min_trade = _cfg_float(cfg, "min_trade_kcs", 0.5)
    target_trade = _cfg_float(cfg, "target_trade_kcs", 1.5)
    max_buy_usdt = _cfg_float(cfg, "max_buy_usdt", 15.0)
    reserve_usdt = _cfg_float(cfg, "reserve_usdt", 1.0)
    min_buy_usdt = _cfg_float(cfg, "min_buy_usdt", 2.0)
    # Default FALSE: redeeming não cobre fee — ainda precisamos de KCS livre
    skip_if_redeeming = bool(cfg.get("skip_buy_if_redeeming", False))
    distribute = bool(cfg.get("distribute_to_subs", True))
    sub_min = _cfg_float(cfg, "sub_min_kcs", 0.2)
    sub_target = _cfg_float(cfg, "sub_target_kcs", 0.25)
    keep_master = _cfg_float(cfg, "keep_master_min_kcs", 0.4)
    fund_from_brl = bool(cfg.get("fund_usdt_from_brl", True))
    max_brl_spend = _cfg_float(cfg, "max_brl_for_kcs", 120.0)
    reserve_brl = _cfg_float(cfg, "reserve_brl", 50.0)
    min_brl_convert = _cfg_float(cfg, "min_brl_convert", 15.0)
    subs = [str(s) for s in (cfg.get("subs") or list(DEFAULT_SUBS))]

    # 1) Sweep MAIN → TRADE
    if snap.main_kcs >= 0.01:
        actions.append(
            KcsAction(
                kind="transfer_main",
                detail=f"sweep MAIN→TRADE {snap.main_kcs:.4f} KCS",
                amount=round(snap.main_kcs, 8),
            )
        )

    if snap.redeeming_kcs > 0:
        actions.append(
            KcsAction(
                kind="wait_redeem",
                detail=(
                    f"KCS redeeming={snap.redeeming_kcs:.4f} status={snap.earn_status} "
                    f"(não usa para fees até liberar no TRADE)"
                ),
                amount=snap.redeeming_kcs,
            )
        )

    # KCS livre após sweep planejado (ainda não executado) — conservador: só trade atual
    free_kcs_now = snap.trade_kcs
    need_buy = free_kcs_now < min_trade
    pending_redeem_covers = skip_if_redeeming and (
        free_kcs_now + snap.redeeming_kcs >= min_trade
    )

    if need_buy and not pending_redeem_covers:
        deficit_kcs = max(0.0, target_trade - free_kcs_now)
        # Também cobrir targets de subs se vamos distribuir
        if distribute:
            for name in subs:
                cur = float(snap.sub_kcs.get(name) or 0.0)
                if cur < sub_min:
                    deficit_kcs += max(0.0, sub_target - cur)
        px = snap.kcs_price if snap.kcs_price > 0 else 0.0
        if px <= 0:
            actions.append(
                KcsAction(kind="noop", detail="sem preço KCS-USDT — não compra")
            )
        else:
            desired_usdt = min(max_buy_usdt, deficit_kcs * px)
            usdt_free = max(0.0, snap.trade_usdt - reserve_usdt)
            spend = min(usdt_free, desired_usdt)

            if spend < min_buy_usdt and fund_from_brl and desired_usdt >= min_buy_usdt:
                # Precisa de mais USDT: converter BRL → USDT (buy USDT-BRL com funds=BRL)
                need_usdt = max(0.0, min_buy_usdt - usdt_free)
                need_usdt = max(need_usdt, min(desired_usdt, max_buy_usdt) - usdt_free)
                ub = snap.usdt_brl_price
                if ub > 0 and snap.trade_brl > reserve_brl:
                    brl_budget = min(max_brl_spend, max(0.0, snap.trade_brl - reserve_brl))
                    brl_needed = need_usdt * ub * 1.002  # small buffer
                    brl_spend = min(brl_budget, brl_needed)
                    if brl_spend >= min_brl_convert:
                        actions.append(
                            KcsAction(
                                kind="fund_usdt_from_brl",
                                detail=(
                                    f"USDT livre {usdt_free:.2f} < min_buy {min_buy_usdt:.2f}; "
                                    f"converter ~{brl_spend:.2f} BRL → USDT (USDT-BRL)"
                                ),
                                brl=round(brl_spend, 2),
                                usdt=round(brl_spend / ub, 4) if ub else 0.0,
                            )
                        )
                        # Assume funding succeeds for subsequent buy planning
                        spend = min(desired_usdt, usdt_free + brl_spend / ub)

            if spend >= min_buy_usdt:
                actions.append(
                    KcsAction(
                        kind="buy",
                        detail=(
                            f"buffer TRADE KCS livre={free_kcs_now:.4f} < min={min_trade:.4f}; "
                            f"comprar ~{spend / px:.4f} KCS com {spend:.2f} USDT"
                        ),
                        amount=spend / px,
                        usdt=round(spend, 2),
                    )
                )
            else:
                actions.append(
                    KcsAction(
                        kind="noop",
                        detail=(
                            f"precisa KCS livre mas USDT/BRL insuficiente "
                            f"(spend={spend:.2f} < min_buy={min_buy_usdt:.2f}, "
                            f"usdt={snap.trade_usdt:.2f}, brl={snap.trade_brl:.2f}, "
                            f"reserve_usdt={reserve_usdt:.2f})"
                        ),
                        usdt=spend,
                    )
                )
    elif need_buy and pending_redeem_covers:
        actions.append(
            KcsAction(
                kind="noop",
                detail=(
                    f"trade_kcs={free_kcs_now:.4f} baixo; skip_buy_if_redeeming=true e "
                    f"redeeming {snap.redeeming_kcs:.4f} cobre o mínimo — sem compra"
                ),
            )
        )

    # Distribuição: só KCS livre já no TRADE (após buy real o executor re-planeja)
    if distribute and free_kcs_now > keep_master:
        free = max(0.0, free_kcs_now - keep_master)
        for name in subs:
            cur = float(snap.sub_kcs.get(name) or 0.0)
            if cur >= sub_min:
                continue
            need = max(0.0, sub_target - cur)
            send = min(need, free)
            if send < 0.05:
                continue
            if name not in snap.sub_uids:
                actions.append(
                    KcsAction(
                        kind="noop",
                        detail=f"sub {name}: sem uid para transfer",
                        sub_name=name,
                    )
                )
                continue
            actions.append(
                KcsAction(
                    kind="transfer_sub",
                    detail=f"enviar {send:.4f} KCS master→{name} (sub tem {cur:.4f})",
                    amount=round(send, 8),
                    sub_name=name,
                )
            )
            free -= send
            if free < 0.05:
                break

    if not actions:
        actions.append(
            KcsAction(
                kind="noop",
                detail=(
                    f"OK trade_kcs={snap.trade_kcs:.4f} main={snap.main_kcs:.4f} "
                    f"redeeming={snap.redeeming_kcs:.4f} usdt={snap.trade_usdt:.2f} "
                    f"brl={snap.trade_brl:.2f}"
                ),
            )
        )
    return actions


def execute_actions(
    actions: List[KcsAction],
    snap: KcsSnapshot,
    *,
    dry_run: bool,
    pair: str = "KCS-USDT",
    place_order_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    sub_transfer_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    inner_transfer_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> List[KcsAction]:
    out: List[KcsAction] = []
    for act in actions:
        act.dry_run = dry_run
        if act.kind in ("noop", "wait_redeem"):
            out.append(act)
            continue
        if dry_run:
            act.executed = False
            act.detail = f"[dry_run] {act.detail}"
            out.append(act)
            continue

        if act.kind == "transfer_main":
            if inner_transfer_fn is None:
                act.error = "inner_transfer_fn missing"
                out.append(act)
                continue
            try:
                res = inner_transfer_fn(
                    "KCS", float(act.amount), from_account="main", to_account="trade"
                )
                if res.get("success") is False or res.get("error"):
                    act.error = str(res.get("error") or res)
                else:
                    act.executed = True
                    act.order_id = str(res.get("orderId") or "")
                    snap.trade_kcs += float(act.amount)
                    snap.main_kcs = max(0.0, snap.main_kcs - float(act.amount))
            except Exception as exc:
                act.error = str(exc)
            out.append(act)
            continue

        if act.kind == "fund_usdt_from_brl":
            if place_order_fn is None:
                act.error = "place_order_fn missing"
                out.append(act)
                continue
            try:
                # USDT-BRL: buy base=USDT with quote=BRL funds
                res = place_order_fn("USDT-BRL", "buy", funds=float(act.brl))
                if res.get("success") is False or res.get("error"):
                    act.error = str(res.get("error") or res)
                else:
                    act.executed = True
                    act.order_id = str(res.get("orderId") or res.get("order_id") or "")
                    sleep_fn(1.5)
                    # rough bookkeeping
                    if snap.usdt_brl_price > 0:
                        got = float(act.brl) / snap.usdt_brl_price
                        snap.trade_usdt += got * 0.998
                        snap.trade_brl = max(0.0, snap.trade_brl - float(act.brl))
            except Exception as exc:
                act.error = str(exc)
            out.append(act)
            continue

        if act.kind == "buy":
            if place_order_fn is None:
                act.error = "place_order_fn missing"
                out.append(act)
                continue
            try:
                res = place_order_fn(pair, "buy", funds=float(act.usdt))
                if res.get("success") is False or res.get("error"):
                    act.error = str(res.get("error") or res)
                else:
                    act.executed = True
                    act.order_id = str(res.get("orderId") or res.get("order_id") or "")
                    sleep_fn(1.5)
                    if snap.kcs_price > 0:
                        got = float(act.usdt) / snap.kcs_price * 0.998
                        snap.trade_kcs += got
                        snap.trade_usdt = max(0.0, snap.trade_usdt - float(act.usdt))
            except Exception as exc:
                act.error = str(exc)
            out.append(act)
            continue

        if act.kind == "transfer_sub":
            if sub_transfer_fn is None:
                act.error = "sub_transfer_fn missing"
                out.append(act)
                continue
            uid = snap.sub_uids.get(act.sub_name)
            if not uid:
                act.error = "missing sub uid"
                out.append(act)
                continue
            try:
                res = sub_transfer_fn(
                    "KCS",
                    float(act.amount),
                    uid,
                    direction="OUT",
                    account_type="TRADE",
                    sub_account_type="TRADE",
                )
                if res.get("success") is False or res.get("error"):
                    act.error = str(res.get("error") or res)
                else:
                    act.executed = True
                    act.order_id = str(res.get("orderId") or "")
                    snap.trade_kcs = max(0.0, snap.trade_kcs - float(act.amount))
                    snap.sub_kcs[act.sub_name] = float(snap.sub_kcs.get(act.sub_name) or 0) + float(
                        act.amount
                    )
            except Exception as exc:
                act.error = str(exc)
            out.append(act)
            continue

        out.append(act)
    return out


def _default_earn_hold() -> Dict[str, Any]:
    from kucoin_api import _signed_request  # type: ignore

    r = _signed_request(
        "GET",
        "/api/v1/earn/hold-assets",
        params={"currency": "KCS"},
        timeout=10,
    )
    data = (r.json() or {}).get("data") or {}
    if isinstance(data, dict):
        return data
    return {"items": []}


def _default_list_sub_users() -> List[Dict[str, Any]]:
    from kucoin_api import _signed_request  # type: ignore

    r = _signed_request("GET", "/api/v1/sub/user", timeout=15)
    data = (r.json() or {}).get("data") or []
    return data if isinstance(data, list) else []


def _main_balance(currency: str) -> float:
    from kucoin_api import get_balances  # type: ignore

    for b in get_balances("main") or []:
        if b.get("currency") == currency:
            try:
                return float(b.get("available") or 0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def run_kcs_fee_admin(
    cfg: Dict[str, Any],
    *,
    dry_run: bool = True,
) -> KcsAdminResult:
    """Ponto de entrada com deps padrão KuCoin.

    Executa em fases: plan → execute → se comprou KCS, re-planeja distribuição.
    """
    from kucoin_api import (  # type: ignore
        get_balance,
        get_price_fast,
        get_subaccount_balance,
        inner_transfer,
        place_market_order,
        sub_transfer,
    )

    pair = str(cfg.get("pair") or "KCS-USDT")
    subs = [str(s) for s in (cfg.get("subs") or list(DEFAULT_SUBS))]

    snap = collect_snapshot(
        subs=subs,
        get_balance_fn=get_balance,
        get_main_balance_fn=_main_balance,
        get_price_fn=get_price_fast,
        get_earn_hold_fn=_default_earn_hold,
        list_sub_users_fn=_default_list_sub_users,
        get_sub_kcs_fn=lambda name: get_subaccount_balance(name, "KCS", account_type="trade"),
        pair=pair,
    )
    planned = plan_actions(cfg, snap)
    executed = execute_actions(
        planned,
        snap,
        dry_run=dry_run,
        pair=pair,
        place_order_fn=place_market_order,
        sub_transfer_fn=sub_transfer,
        inner_transfer_fn=inner_transfer,
    )

    # Segunda passagem: se buy/fund/sweep rodou, redistribuir com saldo atualizado
    did_acquire = any(
        a.executed and a.kind in ("buy", "transfer_main", "fund_usdt_from_brl") for a in executed
    )
    if did_acquire and not dry_run:
        # refresh trade balances from exchange
        try:
            snap.trade_kcs = float(get_balance("KCS") or 0)
            snap.trade_usdt = float(get_balance("USDT") or 0)
            snap.main_kcs = float(_main_balance("KCS") or 0)
        except Exception as exc:
            logger.debug("post-buy refresh failed: %s", exc)
        # avoid re-buying: temporarily raise trade_kcs view via cfg clone
        cfg2 = dict(cfg)
        cfg2["skip_buy_if_redeeming"] = True  # noop for free path
        # force only distribute by setting min high... better re-plan with high min skip
        redistrib = [
            a
            for a in plan_actions(cfg2, snap)
            if a.kind == "transfer_sub"
        ]
        if redistrib:
            more = execute_actions(
                redistrib,
                snap,
                dry_run=False,
                pair=pair,
                place_order_fn=place_market_order,
                sub_transfer_fn=sub_transfer,
                inner_transfer_fn=inner_transfer,
            )
            executed.extend(more)

    msg_parts = [a.detail for a in executed]
    return KcsAdminResult(actions=executed, snapshot=snap, message="; ".join(msg_parts))
