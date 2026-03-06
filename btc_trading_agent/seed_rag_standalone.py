#!/usr/bin/env python3
"""Script standalone para popular VectorStore do MarketRAG com dados históricos da KuCoin.

Executa diretamente no homelab sem dependências externas além de numpy+requests.
Importa MarketSnapshot e VectorStore diretamente do market_rag.py local.

Uso:
    cd /home/homelab/myClaude
    python3 btc_trading_agent/seed_rag_standalone.py --days 7
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

# Adiciona o parent dir ao path para importar market_rag
sys.path.insert(0, str(Path(__file__).parent.parent))
from btc_trading_agent.market_rag import (
    EMBEDDING_DIM,
    INDEX_FILE,
    MarketSnapshot,
    VectorStore,
)

logger = logging.getLogger(__name__)

KUCOIN_BASE = "https://api.kucoin.com"
MAX_CANDLES = 1500
OUTCOME_THRESHOLD = 0.002  # ±0.2%


def setup_logging(verbose: bool = False) -> None:
    """Configura logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


# ==================== KuCoin API ====================
def fetch_candles(symbol: str, ktype: str, start_ts: int, end_ts: int) -> List[Dict]:
    """Busca candles de um período (max 1500)."""
    url = (
        f"{KUCOIN_BASE}/api/v1/market/candles"
        f"?type={ktype}&symbol={symbol}"
        f"&startAt={start_ts}&endAt={end_ts}"
    )
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "200000":
            logger.warning(f"API error: {data.get('msg', 'unknown')}")
            return []
        raw = data.get("data", [])
        candles = []
        for c in raw:
            if len(c) >= 7:
                candles.append({
                    "timestamp": int(c[0]),
                    "open": float(c[1]),
                    "close": float(c[2]),
                    "high": float(c[3]),
                    "low": float(c[4]),
                    "volume": float(c[5]),
                    "turnover": float(c[6]),
                })
        return candles
    except requests.exceptions.RequestException as e:
        logger.warning(f"Request error: {e}")
        return []


def fetch_all_candles(symbol: str, ktype: str, days: int) -> List[Dict]:
    """Busca todas as candles históricas com paginação e rate limiting."""
    interval_sec = 60  # 1min
    now = int(time.time())
    start = now - (days * 86400)
    window = MAX_CANDLES * interval_sec

    all_candles: List[Dict] = []
    current = start
    page = 0

    logger.info(f"📥 Buscando {days} dias de candles {ktype} para {symbol}...")

    while current < now:
        end = min(current + window, now)
        page += 1

        candles = fetch_candles(symbol, ktype, current, end)
        if candles:
            all_candles.extend(candles)

        if page % 5 == 0:
            pct = min(100, (current - start) / max(now - start, 1) * 100)
            logger.info(f"  📊 Página {page}: {len(all_candles)} candles ({pct:.0f}%)")

        current = end
        time.sleep(0.2)  # Rate limit

    # Deduplicar e ordenar
    seen = set()
    unique = []
    for c in all_candles:
        if c["timestamp"] not in seen:
            seen.add(c["timestamp"])
            unique.append(c)
    unique.sort(key=lambda x: x["timestamp"])

    logger.info(f"✅ {len(unique)} candles únicos obtidos")
    return unique


# ==================== Indicadores técnicos ====================
def compute_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """RSI vetorizado."""
    deltas = np.diff(closes, prepend=closes[0])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.zeros_like(closes)
    avg_loss = np.zeros_like(closes)

    # SMA inicial
    if len(closes) > period:
        avg_gain[period] = np.mean(gains[1:period + 1])
        avg_loss[period] = np.mean(losses[1:period + 1])

    # EMA suavizado
    for i in range(period + 1, len(closes)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period

    rs = np.where(avg_loss > 0, avg_gain / (avg_loss + 1e-10), 100.0)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def compute_momentum(closes: np.ndarray, period: int = 10) -> np.ndarray:
    """Momentum (ROC)."""
    mom = np.zeros_like(closes)
    for i in range(period, len(closes)):
        if closes[i - period] > 0:
            mom[i] = (closes[i] / closes[i - period]) - 1
    return mom


def compute_volatility(closes: np.ndarray, period: int = 20) -> np.ndarray:
    """Volatilidade (desvio padrão de retornos)."""
    returns = np.zeros_like(closes)
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            returns[i] = (closes[i] / closes[i - 1]) - 1

    vol = np.zeros_like(closes)
    for i in range(period, len(closes)):
        vol[i] = np.std(returns[i - period:i])
    return vol


def compute_trend(closes: np.ndarray, short: int = 10, long: int = 30) -> np.ndarray:
    """Trend (SMA curta / SMA longa - 1)."""
    trend = np.zeros_like(closes)
    for i in range(long, len(closes)):
        sma_short = np.mean(closes[i - short:i])
        sma_long = np.mean(closes[i - long:i])
        if sma_long > 0:
            trend[i] = (sma_short / sma_long) - 1
    return trend


def compute_ema(closes: np.ndarray, period: int = 20) -> np.ndarray:
    """EMA."""
    ema = np.zeros_like(closes)
    multiplier = 2.0 / (period + 1)
    ema[0] = closes[0]
    for i in range(1, len(closes)):
        ema[i] = (closes[i] - ema[i - 1]) * multiplier + ema[i - 1]
    return ema


def compute_sma(closes: np.ndarray, period: int) -> np.ndarray:
    """SMA."""
    sma = np.zeros_like(closes)
    for i in range(period, len(closes)):
        sma[i] = np.mean(closes[i - period:i])
    return sma


# ==================== Geração de snapshots ====================
def build_snapshots(
    candles: List[Dict],
    symbol: str,
    sample_rate: int = 1,
) -> List[MarketSnapshot]:
    """Gera MarketSnapshots com indicadores e outcomes retrospectivos."""
    n = len(candles)
    warmup = 60

    closes = np.array([c["close"] for c in candles], dtype=np.float64)
    opens = np.array([c["open"] for c in candles], dtype=np.float64)
    highs = np.array([c["high"] for c in candles], dtype=np.float64)
    lows = np.array([c["low"] for c in candles], dtype=np.float64)
    volumes = np.array([c["volume"] for c in candles], dtype=np.float64)
    timestamps = np.array([c["timestamp"] for c in candles], dtype=np.float64)

    logger.info("📊 Calculando indicadores técnicos...")
    rsi = compute_rsi(closes)
    momentum = compute_momentum(closes)
    volatility = compute_volatility(closes)
    trend = compute_trend(closes)
    ema_20 = compute_ema(closes, period=20)
    sma_10 = compute_sma(closes, 10)
    sma_30 = compute_sma(closes, 30)
    sma_60 = compute_sma(closes, 60)

    logger.info(f"🔨 Gerando snapshots (sample_rate={sample_rate}, warmup={warmup})...")
    snapshots: List[MarketSnapshot] = []

    for i in range(warmup, n, sample_rate):
        price = closes[i]
        if price <= 0:
            continue

        # Outcomes retrospectivos
        price_change_5m: Optional[float] = None
        price_change_15m: Optional[float] = None
        price_change_60m: Optional[float] = None
        outcome: Optional[str] = None

        if i + 5 < n:
            price_change_5m = (closes[i + 5] / price) - 1
        if i + 15 < n:
            price_change_15m = (closes[i + 15] / price) - 1
        if i + 60 < n:
            price_change_60m = (closes[i + 60] / price) - 1

        if price_change_5m is not None:
            if price_change_5m > OUTCOME_THRESHOLD:
                outcome = "BULL"
            elif price_change_5m < -OUTCOME_THRESHOLD:
                outcome = "BEAR"
            else:
                outcome = "FLAT"

        snap = MarketSnapshot(
            timestamp=float(timestamps[i]),
            symbol=symbol,
            price=price,
            open_1m=float(opens[i]),
            high_1m=float(highs[i]),
            low_1m=float(lows[i]),
            close_1m=float(closes[i]),
            volume_1m=float(volumes[i]),
            rsi=float(rsi[i]),
            momentum=float(momentum[i]),
            volatility=float(volatility[i]),
            trend=float(trend[i]),
            orderbook_imbalance=0.0,
            spread=0.0,
            bid_volume=0.0,
            ask_volume=0.0,
            trade_flow=0.0,
            buy_volume=0.0,
            sell_volume=0.0,
            sma_10=float(sma_10[i]),
            sma_30=float(sma_30[i]),
            sma_60=float(sma_60[i]),
            ema_20=float(ema_20[i]),
            price_change_5m=price_change_5m,
            price_change_15m=price_change_15m,
            price_change_60m=price_change_60m,
            outcome=outcome,
        )
        snapshots.append(snap)

    # Estatísticas
    bulls = sum(1 for s in snapshots if s.outcome == "BULL")
    bears = sum(1 for s in snapshots if s.outcome == "BEAR")
    flats = sum(1 for s in snapshots if s.outcome == "FLAT")
    nones = sum(1 for s in snapshots if s.outcome is None)
    logger.info(
        f"✅ {len(snapshots)} snapshots gerados: "
        f"BULL={bulls} ({bulls/max(len(snapshots),1):.1%}), "
        f"BEAR={bears} ({bears/max(len(snapshots),1):.1%}), "
        f"FLAT={flats} ({flats/max(len(snapshots),1):.1%}), "
        f"sem outcome={nones}"
    )

    return snapshots


def populate_store(snapshots: List[MarketSnapshot], merge: bool = True) -> VectorStore:
    """Insere snapshots no VectorStore."""
    store = VectorStore(dim=EMBEDDING_DIM)
    existing_ts = set()

    if merge and INDEX_FILE.exists():
        try:
            loaded = store.load(INDEX_FILE)
            if loaded:
                logger.info(f"📂 Store existente: {store.size} vetores")
                for meta in store._metadata:
                    existing_ts.add(meta.get("timestamp", 0))
        except Exception as e:
            logger.warning(f"⚠️ Falha ao carregar store existente: {e}")

    added = 0
    skipped = 0

    for snap in snapshots:
        if snap.timestamp in existing_ts:
            skipped += 1
            continue
        embedding = snap.to_embedding()
        metadata = snap.to_dict()
        store.add(embedding, metadata)
        existing_ts.add(snap.timestamp)
        added += 1

    logger.info(f"✅ VectorStore: +{added} novos, {skipped} duplicatas, total={store.size}")
    return store


def main() -> None:
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Popula VectorStore do MarketRAG com dados históricos"
    )
    parser.add_argument("--symbol", default="BTC-USDT")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--sample-rate", type=int, default=1)
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    setup_logging(args.verbose)

    start = time.time()

    # 1. Buscar candles
    candles = fetch_all_candles(args.symbol, "1min", args.days)
    if len(candles) < 100:
        logger.error(f"❌ Poucos candles ({len(candles)}). Abortando.")
        sys.exit(1)

    # 2. Gerar snapshots com indicadores e outcomes
    snapshots = build_snapshots(candles, args.symbol, args.sample_rate)

    # 3. Popular VectorStore
    store = populate_store(snapshots, merge=not args.no_merge)

    # 4. Salvar
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    store._dirty = True
    store.save(INDEX_FILE)

    elapsed = time.time() - start
    logger.info(f"🎉 Concluído em {elapsed:.1f}s — {store.size} vetores em {INDEX_FILE}")


if __name__ == "__main__":
    main()
