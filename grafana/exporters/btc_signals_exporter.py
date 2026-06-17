#!/usr/bin/env python3
"""BTC Leading Signals Exporter v2 — sinais multi-fonte de derivativos, on-chain e opções.

Fontes gratuitas (sem API key):
  Derivativos:
    - Binance Futures: Long/Short ratio global, Top Trader L/S, Taker ratio, Funding
    - OKX: Long/Short ratio, Funding rate
    - Bybit: Open Interest, Funding rate, Mark price
  Opções:
    - Deribit: Put/Call OI ratio (lead 1-3 dias)
  Sentimento:
    - Alternative.me: Fear & Greed Index
    - CoinGecko: BTC Dominance
    - Coinbase: Premium vs mercado global (US institutional flow)
  On-chain:
    - Mempool.space: Fee rate, hashrate trend, mining pools
    - Stablecoins (DeFiLlama): poder de compra total no mercado

Pesos do composite (soma=1.0):
  Funding consensus (Binance+OKX+Bybit): 0.25  — custo real de posições long
  L/S global (Binance):                  0.20  — alavancagem de varejo
  Taker ratio (Binance):                 0.15  — momentum real agora
  Put/Call OI (Deribit):                 0.15  — expectativa de opções (1-3 dias)
  L/S top traders (Binance):             0.10  — o que profissionais fazem
  Fear & Greed:                          0.07  — sentimento macro
  Coinbase premium:                      0.05  — US institutional flow
  OI change:                             0.03  — leverage buildup
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [btc-signals] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("btc-signals")

# ── Config ────────────────────────────────────────────────────────────

FETCH_INTERVAL = int(os.environ.get("BTC_SIGNALS_INTERVAL", "60"))
SYMBOL         = os.environ.get("BTC_SIGNALS_SYMBOL", "BTC-USDT")
PROMETHEUS_PORT= int(os.environ.get("BTC_SIGNALS_PORT", "9123"))
DATABASE_URL   = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading",
)

WEIGHTS = {
    "funding_consensus": 0.25,
    "longshort":         0.20,
    "taker":             0.15,
    "put_call":          0.15,
    "top_trader_ls":     0.10,
    "fng":               0.07,
    "coinbase_premium":  0.05,
    "oi":                0.03,
}

# ── Helpers ───────────────────────────────────────────────────────────

def _fetch(url: str, timeout: int = 8) -> Optional[Any]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "btc-signals/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        log.debug("fetch %s: %s", url[:60], e)
        return None


def _clip(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))

# ── Coleta ────────────────────────────────────────────────────────────

def fetch_binance_global_ls() -> Optional[float]:
    """Long account ratio global Binance (0-1)."""
    d = _fetch("https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=5m&limit=1")
    return float(d[0]["longAccount"]) if d else None

def fetch_binance_top_ls() -> Optional[float]:
    """Top trader long account ratio (profissionais)."""
    d = _fetch("https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol=BTCUSDT&period=5m&limit=1")
    return float(d[0]["longAccount"]) if d else None

def fetch_binance_taker() -> Optional[float]:
    """Buy/Sell taker ratio Binance."""
    d = _fetch("https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=5m&limit=1")
    return float(d[0]["buySellRatio"]) if d else None

def fetch_binance_funding() -> Optional[float]:
    d = _fetch("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1")
    return float(d[0]["fundingRate"]) if d else None

def fetch_okx_ls() -> Optional[float]:
    """L/S ratio OKX (triangulação)."""
    d = _fetch("https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy=BTC&period=5m")
    if d and d.get("data"):
        ratio = float(d["data"][0][1])  # ex: 1.74
        return ratio / (1 + ratio)       # converter para account% (0-1)
    return None

def fetch_okx_funding() -> Optional[float]:
    d = _fetch("https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USD-SWAP")
    if d and d.get("data"):
        return float(d["data"][0]["fundingRate"])
    return None

def fetch_bybit_funding_oi() -> Tuple[Optional[float], Optional[float]]:
    """Funding rate e mark price Bybit."""
    d = _fetch("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT")
    if d and d.get("result", {}).get("list"):
        item = d["result"]["list"][0]
        funding = float(item.get("fundingRate", 0) or 0)
        mark    = float(item.get("markPrice", 0) or 0)
        return funding, mark
    return None, None

def fetch_bybit_oi_series() -> Tuple[Optional[float], Optional[float]]:
    """OI atual e OI de 1h atrás (para calcular mudança)."""
    d = _fetch("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=1h&limit=2")
    if d and d.get("result", {}).get("list"):
        lst = d["result"]["list"]
        return float(lst[0]["openInterest"]), float(lst[-1]["openInterest"])
    return None, None

def fetch_deribit_put_call() -> Optional[float]:
    """Put/Call OI ratio Deribit. <0.7=greed, >1.0=fear."""
    d = _fetch("https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option")
    if not d:
        return None
    put_oi  = sum(float(x.get("open_interest") or 0) for x in d["result"] if x["instrument_name"].endswith("-P"))
    call_oi = sum(float(x.get("open_interest") or 0) for x in d["result"] if x["instrument_name"].endswith("-C"))
    return put_oi / call_oi if call_oi > 0 else None

def fetch_fear_greed() -> Tuple[Optional[int], Optional[str]]:
    d = _fetch("https://api.alternative.me/fng/?limit=1&format=json")
    if d and d.get("data"):
        return int(d["data"][0]["value"]), d["data"][0]["value_classification"]
    return None, None

def fetch_coinbase_premium() -> Optional[float]:
    """Coinbase BTC/USD vs CoinGecko global — positivo = US comprando."""
    d_cb = _fetch("https://api.coinbase.com/v2/prices/BTC-USD/spot")
    d_cg = _fetch("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
    if d_cb and d_cg:
        cb = float(d_cb["data"]["amount"])
        cg = float(d_cg["bitcoin"]["usd"])
        if cg > 0:
            return (cb - cg) / cg
    return None

def fetch_mempool() -> Tuple[Optional[int], Optional[int]]:
    """Fee (sat/vB) e tamanho do mempool."""
    d = _fetch("https://mempool.space/api/v1/fees/recommended")
    d2 = _fetch("https://blockstream.info/api/mempool")
    fee   = int(d["fastestFee"]) if d else None
    vsize = int(d2["vsize"]) if d2 else None
    return fee, vsize

def fetch_btc_dominance() -> Optional[float]:
    d = _fetch("https://api.coingecko.com/api/v3/global")
    if d:
        return float(d["data"]["market_cap_percentage"].get("btc", 0))
    return None

def fetch_blockchain_info() -> Tuple[Optional[int], Optional[float]]:
    """Tx count e BTC enviado das últimas 24h (blockchain.info — sem API key).

    n_tx  : número de transações confirmadas no dia
    n_btc : volume de BTC movimentado (proxy de atividade on-chain)
    """
    d = _fetch("https://api.blockchain.info/stats")
    if not d:
        return None, None
    n_tx  = d.get("n_tx")
    n_btc = d.get("total_btc_sent")  # satoshis → BTC
    if n_btc is not None:
        n_btc = round(n_btc / 1e8, 2)
    return (int(n_tx) if n_tx else None), n_btc

def fetch_blockchair_onchain() -> Tuple[Optional[int], Optional[float]]:
    """Métricas on-chain via Blockchair — sem API key, sem cadastro.

    transactions_24h : txs confirmadas nas últimas 24h (atividade da rede)
    volume_24h_btc   : volume BTC movimentado on-chain (em BTC)

    Alto volume relativo à média histórica → rede ativa → pode indicar acumulação
    ou distribuição (confirmar com outros sinais).
    """
    d = _fetch("https://api.blockchair.com/bitcoin/stats", timeout=10)
    if not d:
        return None, None
    try:
        data = d.get("data", {})
        tx24  = data.get("transactions_24h")
        vol   = data.get("volume_24h")               # satoshis
        vol_btc = round(int(vol) / 1e8, 2) if vol else None
        return (int(tx24) if tx24 else None), vol_btc
    except (KeyError, TypeError, ValueError):
        return None, None


def compute_nvt(price: float, daily_btc_sent: Optional[float]) -> Optional[float]:
    """NVT ratio local — calculado sem API externa.

    NVT = Market Cap (USD) / Daily On-chain Volume (USD)
        = (price × 19_700_000) / (daily_btc_sent × price)
        = 19_700_000 / daily_btc_sent

    NVT < 20  → undervalued (bullish)
    NVT 20-65 → neutro
    NVT > 65  → overvalued (bearish)
    """
    if not daily_btc_sent or daily_btc_sent <= 0 or price <= 0:
        return None
    BTC_SUPPLY = 19_700_000
    return round(BTC_SUPPLY / daily_btc_sent, 2)

# ── Compute signals ───────────────────────────────────────────────────

def compute_funding_consensus(binance: Optional[float], okx: Optional[float], bybit: Optional[float]) -> Optional[float]:
    """Média do funding rate das 3 exchanges — positivo alto = longs sobre-pagando."""
    vals = [v for v in [binance, okx, bybit] if v is not None]
    if not vals:
        return None
    avg = sum(vals) / len(vals)
    # sinal: funding positivo alto = bearish (longs vão ser liquidados)
    return _clip(-avg * 3000)  # normaliza: 0.01% funding → -0.3 (bearish leve)

def compute_signals(
    global_ls: Optional[float],
    top_ls: Optional[float],
    taker: Optional[float],
    funding_consensus: Optional[float],
    oi_now: Optional[float],
    oi_prev: Optional[float],
    put_call: Optional[float],
    fng: Optional[int],
    cb_premium: Optional[float],
    fee: Optional[int],
    dominance: Optional[float],
) -> Dict[str, float]:
    sigs: Dict[str, float] = {}

    # L/S global: alto long (>0.62) = sobre-alavancado = bearish contrário
    if global_ls is not None:
        sigs["longshort"] = _clip((0.5 - global_ls) * 3)

    # Top trader L/S: profissionais hedgeando vs varejo
    if top_ls is not None:
        sigs["top_trader_ls"] = _clip((0.5 - top_ls) * 2.5)

    # Taker: momentum
    if taker is not None:
        sigs["taker"] = _clip((taker - 1.0) * 4)

    # Funding consensus: alto positivo = longs sobre-pagando = reversal bearish
    if funding_consensus is not None:
        sigs["funding_consensus"] = funding_consensus

    # OI change 1h
    if oi_now and oi_prev and oi_prev > 0:
        chg = (oi_now - oi_prev) / oi_prev
        sigs["oi"] = _clip(chg * 25)
    else:
        sigs["oi"] = 0.0

    # Put/Call: <0.7=greed=bearish contrário; >1.0=fear=bullish contrário
    if put_call is not None:
        # normalizar: 0.7 = neutro, abaixo = bearish, acima = bullish
        sigs["put_call"] = _clip((put_call - 0.75) * 2.5)

    # Fear & Greed: contrário
    if fng is not None:
        sigs["fng"] = _clip((50 - fng) / 60)

    # Coinbase premium: positivo = US comprando = bullish
    if cb_premium is not None:
        sigs["coinbase_premium"] = _clip(cb_premium * 200)

    return sigs


def compute_composite(sigs: Dict[str, float]) -> float:
    total_w = total_v = 0.0
    for k, w in WEIGHTS.items():
        if k in sigs:
            total_v += sigs[k] * w
            total_w += w
    return round(total_v / total_w, 4) if total_w else 0.0


def signal_label(c: float) -> str:
    if c >= 0.50: return "STRONG_BUY"
    if c >= 0.20: return "BUY"
    if c <= -0.50: return "STRONG_SELL"
    if c <= -0.20: return "SELL"
    return "NEUTRAL"

# ── DB + Prometheus ───────────────────────────────────────────────────

_prom: Dict[str, float] = {}


def persist(row: Dict[str, Any]) -> None:
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO btc.market_signals
              (symbol, long_ratio, taker_ratio, open_interest, oi_change_pct,
               funding_rate, fear_greed, fear_greed_cls, mempool_fee, hash_rate,
               sig_longshort, sig_taker, sig_oi, sig_funding, sig_fng, sig_mempool,
               composite, signal_label)
            VALUES
              (%(symbol)s, %(long_ratio)s, %(taker_ratio)s, %(open_interest)s, %(oi_change_pct)s,
               %(funding_rate)s, %(fear_greed)s, %(fear_greed_cls)s, %(mempool_fee)s, %(hash_rate)s,
               %(sig_longshort)s, %(sig_taker)s, %(sig_oi)s, %(sig_funding)s, %(sig_fng)s, %(sig_mempool)s,
               %(composite)s, %(signal_label)s)
            """,
            row,
        )
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        log.warning("DB persist: %s", e)


def serve_prometheus() -> None:
    import http.server, threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            lines = []
            for name, (help_txt, val) in sorted(_prom.items()):
                lines += [
                    f"# HELP {name} {help_txt}",
                    f"# TYPE {name} gauge",
                    f'{name}{{coin="BTC-USDT"}} {val}',
                ]
            body = ("\n".join(lines) + "\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def log_message(self, *a): pass

    threading.Thread(
        target=http.server.HTTPServer(("0.0.0.0", PROMETHEUS_PORT), H).serve_forever,
        daemon=True,
    ).start()
    log.info("Prometheus em ::%d/metrics", PROMETHEUS_PORT)


def _pset(name: str, help_txt: str, val: float) -> None:
    _prom[name] = (help_txt, val)

# ── Ciclo principal ───────────────────────────────────────────────────

_prev_oi: Optional[float] = None


def run_cycle() -> None:
    global _prev_oi
    log.info("Coletando sinais v2...")

    # --- Coleta paralela (sequencial mas rápido — todas <8s) ---
    global_ls   = fetch_binance_global_ls()
    top_ls      = fetch_binance_top_ls()
    taker       = fetch_binance_taker()
    bn_fund     = fetch_binance_funding()
    okx_ls      = fetch_okx_ls()
    okx_fund    = fetch_okx_funding()
    bybit_fund, bybit_mark = fetch_bybit_funding_oi()
    oi_now, oi_prev_api    = fetch_bybit_oi_series()
    put_call    = fetch_deribit_put_call()
    fng, fng_cls = fetch_fear_greed()
    cb_premium  = fetch_coinbase_premium()
    fee, vsize  = fetch_mempool()
    dominance   = fetch_btc_dominance()
    onchain_tx, onchain_btc     = fetch_blockchain_info()
    bc_tx24,    bc_vol_btc      = fetch_blockchair_onchain()
    # Preço atual para calcular NVT (usa o mark price do Bybit se disponível)
    _price_for_nvt = bybit_mark or 0.0
    nvt_ratio = compute_nvt(_price_for_nvt, onchain_btc or bc_vol_btc)

    # Usar série de OI local se API não retornar prev
    oi_prev_use = oi_prev_api if oi_prev_api else _prev_oi
    if oi_now:
        _prev_oi = oi_now

    # Funding consensus
    fund_consensus = compute_funding_consensus(bn_fund, okx_fund, bybit_fund)

    # Sinais normalizados
    sigs = compute_signals(
        global_ls, top_ls, taker, fund_consensus,
        oi_now, oi_prev_use, put_call, fng, cb_premium, fee, dominance,
    )
    composite = compute_composite(sigs)
    label     = signal_label(composite)

    oi_chg = None
    if oi_now and oi_prev_use and oi_prev_use > 0:
        oi_chg = round((oi_now - oi_prev_use) / oi_prev_use * 100, 4)

    avg_funding = None
    vals = [v for v in [bn_fund, okx_fund, bybit_fund] if v is not None]
    if vals:
        avg_funding = sum(vals) / len(vals)

    persist({
        "symbol":        SYMBOL,
        "long_ratio":    global_ls,
        "taker_ratio":   taker,
        "open_interest": oi_now,
        "oi_change_pct": oi_chg,
        "funding_rate":  avg_funding,
        "fear_greed":    fng,
        "fear_greed_cls": fng_cls,
        "mempool_fee":   fee,
        "hash_rate":     dominance,  # reutilizando coluna hash_rate para dominance
        "sig_longshort": sigs.get("longshort"),
        "sig_taker":     sigs.get("taker"),
        "sig_oi":        sigs.get("oi"),
        "sig_funding":   sigs.get("funding_consensus"),
        "sig_fng":       sigs.get("fng"),
        "sig_mempool":   sigs.get("coinbase_premium"),  # reutilizando coluna
        "composite":     composite,
        "signal_label":  label,
    })

    # Prometheus
    _pset("btc_signal_composite",     "Composite (-1=SELL +1=BUY)",     composite)
    _pset("btc_signal_longshort",     "L/S global contrarian",          sigs.get("longshort", 0))
    _pset("btc_signal_taker",         "Taker momentum",                  sigs.get("taker", 0))
    _pset("btc_signal_funding",       "Funding consensus contrarian",    sigs.get("funding_consensus", 0))
    _pset("btc_signal_put_call",      "Put/Call ratio contrarian",       sigs.get("put_call", 0))
    _pset("btc_signal_top_traders",   "Top trader L/S contrarian",       sigs.get("top_trader_ls", 0))
    _pset("btc_signal_fng",           "Fear & Greed contrarian",         sigs.get("fng", 0))
    _pset("btc_signal_cb_premium",    "Coinbase premium US flow",        sigs.get("coinbase_premium", 0))
    _pset("btc_longshort_raw",        "Long account ratio (0-1)",        global_ls or 0)
    _pset("btc_top_ls_raw",           "Top trader long ratio (0-1)",     top_ls or 0)
    _pset("btc_taker_raw",            "Taker buy/sell ratio",            taker or 0)
    _pset("btc_funding_raw",          "Average funding rate",            avg_funding or 0)
    _pset("btc_funding_binance_bps",  "Binance funding rate bps",        (bn_fund or 0) * 10000)
    _pset("btc_funding_okx_bps",      "OKX funding rate bps",            (okx_fund or 0) * 10000)
    _pset("btc_funding_bybit_bps",    "Bybit funding rate bps",          (bybit_fund or 0) * 10000)
    _pset("btc_put_call_raw",         "Put/Call OI ratio",               put_call or 0)
    _pset("btc_fear_greed_raw",       "Fear & Greed Index",              fng or 0)
    _pset("btc_coinbase_premium_pct", "Coinbase premium %",              (cb_premium or 0) * 100)
    _pset("btc_dominance_pct",        "BTC Dominance %",                 dominance or 0)
    _pset("btc_mempool_fee_raw",      "Mempool fee sat/vB",              fee or 0)
    _pset("btc_open_interest_raw",    "Bybit OI BTC",                    oi_now or 0)

    # On-chain blockchain.info (sem key)
    _pset("btc_onchain_tx_count",    "Tx confirmadas 24h (blockchain.info)", onchain_tx  or 0)
    _pset("btc_onchain_btc_sent",    "BTC enviado 24h (blockchain.info)",    onchain_btc or 0)

    # On-chain Blockchair (sem key, sem cadastro)
    _pset("btc_onchain_bc_tx24",     "Tx confirmadas 24h (Blockchair)",      bc_tx24     or 0)
    _pset("btc_onchain_bc_vol_btc",  "Volume BTC on-chain 24h (Blockchair)", bc_vol_btc  or 0)

    # NVT ratio local (calculado sem API externa)
    if nvt_ratio is not None:
        # NVT < 20 = undervalued (bullish); NVT > 65 = overvalued (bearish)
        # Signal normalizado: +1 = muito undervalued, -1 = muito overvalued
        nvt_signal = _clip((35.0 - nvt_ratio) / 35.0)
        _pset("btc_onchain_nvt_ratio",  "NVT ratio local (supply/daily_vol)", nvt_ratio)
        _pset("btc_onchain_nvt_signal", "NVT signal (+1=under -1=over)",      nvt_signal)

    # Triangulação de funding (convergência multi-exchange)
    fund_agree = all(
        v is not None and v > 0
        for v in [bn_fund, okx_fund, bybit_fund]
    )
    log.info(
        "Signal: %s (%.3f) | LS_global=%.2f LS_top=%.2f | taker=%.2f | "
        "funding=Bn%.4f%%+OKX%.4f%%+BY%.4f%%(agree=%s) | "
        "P/C=%.3f FnG=%s CB_prem=%s%% | dom=%.1f%%",
        label, composite,
        global_ls or 0, top_ls or 0, taker or 0,
        (bn_fund or 0)*100, (okx_fund or 0)*100, (bybit_fund or 0)*100, fund_agree,
        put_call or 0, fng,
        f"{(cb_premium or 0)*100:+.3f}" if cb_premium else "N/A",
        dominance or 0,
    )


def main() -> None:
    log.info("BTC Signals Exporter v2 (interval=%ds port=%d)", FETCH_INTERVAL, PROMETHEUS_PORT)
    serve_prometheus()

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT,  lambda *_: sys.exit(0))

    try:
        run_cycle()
    except Exception as e:
        log.error("Ciclo inicial: %s", e)

    while True:
        time.sleep(FETCH_INTERVAL)
        try:
            run_cycle()
        except Exception as e:
            log.error("Ciclo: %s", e)


if __name__ == "__main__":
    main()
