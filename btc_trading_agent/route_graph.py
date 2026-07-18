"""Grafo de pares KuCoin e seleção de rota de menor custo efetivo."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from fee_spread_estimator import LegEstimate, estimate_leg

logger = logging.getLogger(__name__)

STABLE_EXOTIC = {"USD1", "USDC", "USDG", "DAI", "TUSD", "FDUSD", "USDE"}
DEFAULT_HUBS = ("USDT", "BTC", "ETH")
HARD_MAX_HOPS = 3


@dataclass
class RouteOptions:
    max_hops: int = 2
    hubs: Sequence[str] = DEFAULT_HUBS
    allow_exotic_hubs: bool = False
    prefer_direct_slack_bps: float = 5.0
    min_pair_vol_usd: float = 50_000.0
    max_spread_bps: float = 30.0
    max_route_cost_pct: float = 0.004
    slip_buffer_pct: float = 0.0005
    hop_penalty_pct: float = 0.0001  # small preference for fewer hops
    use_live_fees: bool = True


@dataclass
class RouteLeg:
    symbol: str
    side: str
    currency_in: str
    currency_out: str
    amount_in: float
    est_out: float
    cost_pct: float
    spread_bps: float
    fee_pct: float
    slip_bps: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RoutePlan:
    asset_in: str
    asset_out: str
    amount_in: float
    est_out: float
    total_cost_pct: float
    hops: int
    path_assets: List[str]
    legs: List[RouteLeg] = field(default_factory=list)
    via: str = ""  # direct | via:USDT | ...
    score: float = 0.0
    rejected: bool = False
    reject_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def _pair_orientation(
    base: str, quote: str, asset_from: str, asset_to: str
) -> Optional[Tuple[str, str, str, str]]:
    """Return (symbol, side, currency_in, currency_out) if edge connects from→to."""
    base_u, quote_u = base.upper(), quote.upper()
    a, b = asset_from.upper(), asset_to.upper()
    symbol = f"{base_u}-{quote_u}"
    if a == base_u and b == quote_u:
        # sell base → quote
        return symbol, "sell", base_u, quote_u
    if a == quote_u and b == base_u:
        # buy base with quote
        return symbol, "buy", quote_u, base_u
    return None


class RouteGraph:
    """Grafo não-direcionado de moedas ligado por símbolos negociáveis."""

    def __init__(
        self,
        symbols: Optional[List[Dict[str, Any]]] = None,
        *,
        vol_by_symbol: Optional[Dict[str, float]] = None,
        get_symbols_fn: Optional[Callable[[], List[Dict[str, Any]]]] = None,
    ):
        self.edges: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.adj: Dict[str, Set[str]] = {}
        self.vol_by_symbol = {k.upper(): float(v) for k, v in (vol_by_symbol or {}).items()}
        if symbols is None:
            if get_symbols_fn is None:
                from kucoin_api import get_symbols as get_symbols_fn  # type: ignore
            symbols = get_symbols_fn() or []
        self._build(symbols)

    def _build(self, symbols: List[Dict[str, Any]]) -> None:
        for item in symbols:
            if not item.get("enableTrading", True):
                continue
            base = str(item.get("baseCurrency") or "").upper()
            quote = str(item.get("quoteCurrency") or "").upper()
            symbol = str(item.get("symbol") or f"{base}-{quote}").upper()
            if not base or not quote or base == quote:
                continue
            meta = {
                "symbol": symbol,
                "base": base,
                "quote": quote,
                "baseMinSize": item.get("baseMinSize"),
                "quoteMinSize": item.get("quoteMinSize"),
                "minFunds": item.get("minFunds"),
                "vol_usd": self.vol_by_symbol.get(symbol),
            }
            self.edges[(base, quote)] = meta
            self.edges[(quote, base)] = meta
            self.adj.setdefault(base, set()).add(quote)
            self.adj.setdefault(quote, set()).add(base)

    def neighbors(self, asset: str) -> Set[str]:
        return set(self.adj.get(asset.upper(), set()))

    def edge_meta(self, a: str, b: str) -> Optional[Dict[str, Any]]:
        return self.edges.get((a.upper(), b.upper()))

    def edge_allowed(self, a: str, b: str, opts: RouteOptions) -> Tuple[bool, str]:
        meta = self.edge_meta(a, b)
        if not meta:
            return False, "no_edge"
        vol = meta.get("vol_usd")
        if vol is not None and opts.min_pair_vol_usd > 0 and float(vol) < opts.min_pair_vol_usd:
            return False, f"low_vol_usd={vol}"
        return True, ""


def _estimate_path(
    graph: RouteGraph,
    path: List[str],
    amount_in: float,
    opts: RouteOptions,
    *,
    estimate_leg_fn: Callable[..., LegEstimate] = estimate_leg,
) -> RoutePlan:
    asset_in = path[0]
    asset_out = path[-1]
    amount = float(amount_in)
    legs: List[RouteLeg] = []
    total_cost = 0.0

    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        meta = graph.edge_meta(a, b)
        if not meta:
            return RoutePlan(
                asset_in=asset_in,
                asset_out=asset_out,
                amount_in=amount_in,
                est_out=0.0,
                total_cost_pct=1.0,
                hops=len(path) - 1,
                path_assets=path,
                rejected=True,
                reject_reason=f"missing_edge_{a}_{b}",
            )
        orient = _pair_orientation(meta["base"], meta["quote"], a, b)
        if not orient:
            return RoutePlan(
                asset_in=asset_in,
                asset_out=asset_out,
                amount_in=amount_in,
                est_out=0.0,
                total_cost_pct=1.0,
                hops=len(path) - 1,
                path_assets=path,
                rejected=True,
                reject_reason=f"bad_orient_{a}_{b}",
            )
        symbol, side, cin, cout = orient
        ok, why = graph.edge_allowed(a, b, opts)
        # vol filter only when vol known; missing vol is allowed (public book still works)
        if not ok and why.startswith("low_vol"):
            return RoutePlan(
                asset_in=asset_in,
                asset_out=asset_out,
                amount_in=amount_in,
                est_out=0.0,
                total_cost_pct=1.0,
                hops=len(path) - 1,
                path_assets=path,
                rejected=True,
                reject_reason=why,
            )

        est = estimate_leg_fn(
            symbol,
            side,
            amount,
            currency_in=cin,
            currency_out=cout,
            slip_buffer_pct=opts.slip_buffer_pct,
            use_live_fees=opts.use_live_fees,
            get_symbol_meta_fn=lambda _s, m=meta: m,
        )
        if est.spread_bps > opts.max_spread_bps:
            return RoutePlan(
                asset_in=asset_in,
                asset_out=asset_out,
                amount_in=amount_in,
                est_out=0.0,
                total_cost_pct=1.0,
                hops=len(path) - 1,
                path_assets=path,
                rejected=True,
                reject_reason=f"spread_bps={est.spread_bps:.1f}>{opts.max_spread_bps}",
            )
        if not est.min_ok or est.est_out <= 0:
            return RoutePlan(
                asset_in=asset_in,
                asset_out=asset_out,
                amount_in=amount_in,
                est_out=0.0,
                total_cost_pct=1.0,
                hops=len(path) - 1,
                path_assets=path,
                rejected=True,
                reject_reason=est.reason or "leg_failed",
            )
        legs.append(
            RouteLeg(
                symbol=est.symbol,
                side=est.side,
                currency_in=est.currency_in,
                currency_out=est.currency_out,
                amount_in=est.amount_in,
                est_out=est.est_out,
                cost_pct=est.cost_pct,
                spread_bps=est.spread_bps,
                fee_pct=est.fee_pct,
                slip_bps=est.slip_bps,
            )
        )
        total_cost += est.cost_pct
        amount = est.est_out

    hops = len(path) - 1
    score = total_cost + opts.hop_penalty_pct * max(0, hops - 1)
    via = "direct" if hops == 1 else f"via:{'-'.join(path[1:-1])}"
    plan = RoutePlan(
        asset_in=asset_in,
        asset_out=asset_out,
        amount_in=amount_in,
        est_out=amount,
        total_cost_pct=total_cost,
        hops=hops,
        path_assets=path,
        legs=legs,
        via=via,
        score=score,
    )
    if total_cost > opts.max_route_cost_pct and opts.max_route_cost_pct > 0:
        # still return as candidate but mark soft reject for filtering later
        plan.reject_reason = f"cost_pct={total_cost:.4f}>max"
    return plan


def _candidate_paths(
    graph: RouteGraph,
    asset_in: str,
    asset_out: str,
    opts: RouteOptions,
) -> List[List[str]]:
    a = asset_in.upper()
    b = asset_out.upper()
    if a == b:
        return []

    paths: List[List[str]] = []
    # direct
    if b in graph.neighbors(a):
        paths.append([a, b])

    max_hops = max(1, min(int(opts.max_hops), HARD_MAX_HOPS))
    hubs = [h.upper() for h in opts.hubs]
    if not opts.allow_exotic_hubs:
        # also block exotic as intermediate even if listed
        pass

    if max_hops >= 2:
        for hub in hubs:
            if hub in (a, b):
                continue
            if not opts.allow_exotic_hubs and hub in STABLE_EXOTIC:
                continue
            if hub in graph.neighbors(a) and b in graph.neighbors(hub):
                paths.append([a, hub, b])

    if max_hops >= 3:
        # 3 hops via two hubs (rare): a-h1-h2-b
        for h1 in hubs:
            if h1 in (a, b):
                continue
            if not opts.allow_exotic_hubs and h1 in STABLE_EXOTIC:
                continue
            if h1 not in graph.neighbors(a):
                continue
            for h2 in hubs:
                if h2 in (a, b, h1):
                    continue
                if not opts.allow_exotic_hubs and h2 in STABLE_EXOTIC:
                    continue
                if h2 in graph.neighbors(h1) and b in graph.neighbors(h2):
                    paths.append([a, h1, h2, b])

    # de-dupe
    seen: Set[Tuple[str, ...]] = set()
    unique: List[List[str]] = []
    for p in paths:
        key = tuple(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def compare_routes(
    asset_in: str,
    asset_out: str,
    amount_in: float,
    *,
    opts: Optional[RouteOptions] = None,
    graph: Optional[RouteGraph] = None,
    estimate_leg_fn: Callable[..., LegEstimate] = estimate_leg,
) -> List[RoutePlan]:
    """Retorna candidatos ordenados por score (menor = melhor)."""
    opts = opts or RouteOptions()
    graph = graph or RouteGraph()
    plans: List[RoutePlan] = []
    for path in _candidate_paths(graph, asset_in, asset_out, opts):
        plan = _estimate_path(graph, path, amount_in, opts, estimate_leg_fn=estimate_leg_fn)
        if plan.rejected:
            continue
        if opts.max_route_cost_pct > 0 and plan.total_cost_pct > opts.max_route_cost_pct:
            continue
        plans.append(plan)
    plans.sort(key=lambda p: (p.score, p.hops, -p.est_out))
    return plans


def find_best_route(
    asset_in: str,
    asset_out: str,
    amount_in: float,
    *,
    opts: Optional[RouteOptions] = None,
    graph: Optional[RouteGraph] = None,
    estimate_leg_fn: Callable[..., LegEstimate] = estimate_leg,
) -> Optional[RoutePlan]:
    """Escolhe a rota de menor custo, com preferência leve a par direto."""
    opts = opts or RouteOptions()
    candidates = compare_routes(
        asset_in,
        asset_out,
        amount_in,
        opts=opts,
        graph=graph,
        estimate_leg_fn=estimate_leg_fn,
    )
    if not candidates:
        return None

    best = candidates[0]
    # prefer direct if within slack
    directs = [c for c in candidates if c.hops == 1]
    if directs:
        direct = directs[0]
        slack = opts.prefer_direct_slack_bps / 10000.0
        if direct.score <= best.score + slack:
            return direct
    return best


def savings_vs_usdt_bps(best: RoutePlan, candidates: Iterable[RoutePlan]) -> Optional[float]:
    """Economia em bps do best vs rota via USDT (se existir)."""
    via_usdt = None
    for c in candidates:
        if c.via == "via:USDT" or (c.hops == 2 and "USDT" in c.path_assets[1:-1]):
            via_usdt = c
            break
        if c.hops == 1 and set(c.path_assets) == {"USDT"}:
            continue
    if via_usdt is None:
        # also match path containing USDT as only mid
        for c in candidates:
            if len(c.path_assets) == 3 and c.path_assets[1] == "USDT":
                via_usdt = c
                break
    if via_usdt is None or via_usdt.est_out <= 0:
        return None
    if best.est_out <= 0:
        return None
    # positive = best gives more out than usdt route
    return (best.est_out / via_usdt.est_out - 1.0) * 10000.0
