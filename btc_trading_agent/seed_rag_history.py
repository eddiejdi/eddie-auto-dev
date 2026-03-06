#!/usr/bin/env python3
"""Popula o VectorStore do MarketRAG com dados históricos da KuCoin.

Busca candles de 1min via API KuCoin, calcula indicadores offline,
gera MarketSnapshots com outcomes retrospectivos e insere no VectorStore.

Uso:
    python -m btc_trading_agent.seed_rag_history --days 7
    python -m btc_trading_agent.seed_rag_history --days 30 --sample-rate 2
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

import numpy as np

# Imports locais
from btc_trading_agent.import_kucoin_data import KuCoinFetcher, OfflineIndicators
from btc_trading_agent.market_rag import (
    EMBEDDING_DIM,
    INDEX_FILE,
    MAX_SNAPSHOTS,
    MarketSnapshot,
    VectorStore,
)

logger = logging.getLogger(__name__)

# ±0.2% para classificar BULL/BEAR (mesmo threshold do market_rag.py)
OUTCOME_THRESHOLD = 0.002


def setup_logging(verbose: bool = False) -> None:
    """Configura logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def fetch_historical_candles(
    symbol: str,
    days: int,
    ktype: str = "1min",
) -> List[dict]:
    """Busca candles históricas via API KuCoin.

    Args:
        symbol: Par de trading (ex: BTC-USDT).
        days: Número de dias para buscar.
        ktype: Tipo de candle (1min, 5min, etc.).

    Returns:
        Lista de candles ordenadas cronologicamente.
    """
    fetcher = KuCoinFetcher()
    logger.info(f"📥 Buscando {days} dias de candles {ktype} para {symbol}...")
    candles = fetcher.fetch_all_candles(symbol, ktype, days=days)
    logger.info(f"✅ {len(candles)} candles obtidos")
    return candles


def compute_indicators(candles: List[dict]) -> dict:
    """Calcula indicadores técnicos offline a partir de candles.

    Args:
        candles: Lista de candles com OHLCV.

    Returns:
        Dicionário com arrays numpy de indicadores.
    """
    closes = np.array([c["close"] for c in candles], dtype=np.float64)
    opens = np.array([c["open"] for c in candles], dtype=np.float64)
    highs = np.array([c["high"] for c in candles], dtype=np.float64)
    lows = np.array([c["low"] for c in candles], dtype=np.float64)
    volumes = np.array([c["volume"] for c in candles], dtype=np.float64)
    timestamps = np.array([c["timestamp"] for c in candles], dtype=np.float64)

    indicators = OfflineIndicators()

    rsi = indicators.rsi(closes)
    momentum = indicators.momentum(closes)
    volatility = indicators.volatility(closes)
    trend = indicators.trend(closes)
    ema_20 = indicators.ema(closes, period=20)

    # SMAs manuais
    sma_10 = np.zeros_like(closes)
    sma_30 = np.zeros_like(closes)
    sma_60 = np.zeros_like(closes)

    for i in range(10, len(closes)):
        sma_10[i] = np.mean(closes[i - 10:i])
    for i in range(30, len(closes)):
        sma_30[i] = np.mean(closes[i - 30:i])
    for i in range(60, len(closes)):
        sma_60[i] = np.mean(closes[i - 60:i])

    return {
        "closes": closes,
        "opens": opens,
        "highs": highs,
        "lows": lows,
        "volumes": volumes,
        "timestamps": timestamps,
        "rsi": rsi,
        "momentum": momentum,
        "volatility": volatility,
        "trend": trend,
        "ema_20": ema_20,
        "sma_10": sma_10,
        "sma_30": sma_30,
        "sma_60": sma_60,
    }


def build_snapshots(
    candles: List[dict],
    indicators: dict,
    symbol: str,
    sample_rate: int = 1,
) -> List[MarketSnapshot]:
    """Gera MarketSnapshots a partir de candles + indicadores.

    Args:
        candles: Lista de candles OHLCV.
        indicators: Dicionário de arrays de indicadores.
        symbol: Par de trading.
        sample_rate: Amostra 1 a cada N candles (1=todos, 5=cada 5min).

    Returns:
        Lista de MarketSnapshots com outcomes preenchidos.
    """
    n = len(candles)
    warmup = 60  # Pular primeiros 60 candles (warm-up dos indicadores)
    snapshots: List[MarketSnapshot] = []

    closes = indicators["closes"]
    opens = indicators["opens"]
    highs = indicators["highs"]
    lows = indicators["lows"]
    volumes = indicators["volumes"]
    timestamps = indicators["timestamps"]

    logger.info(f"🔨 Gerando snapshots (sample_rate={sample_rate}, warmup={warmup})...")

    for i in range(warmup, n, sample_rate):
        # Outcome retrospectivo: preço 5min, 15min, 60min à frente
        price_change_5m: Optional[float] = None
        price_change_15m: Optional[float] = None
        price_change_60m: Optional[float] = None
        outcome: Optional[str] = None

        price = closes[i]
        if price <= 0:
            continue

        # 5 min à frente
        if i + 5 < n:
            price_change_5m = (closes[i + 5] / price) - 1
        # 15 min à frente
        if i + 15 < n:
            price_change_15m = (closes[i + 15] / price) - 1
        # 60 min à frente
        if i + 60 < n:
            price_change_60m = (closes[i + 60] / price) - 1

        # Classificar outcome baseado em 5m
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
            rsi=float(indicators["rsi"][i]),
            momentum=float(indicators["momentum"][i]),
            volatility=float(indicators["volatility"][i]),
            trend=float(indicators["trend"][i]),
            # Orderbook/flow indisponíveis em dados históricos
            orderbook_imbalance=0.0,
            spread=0.0,
            bid_volume=0.0,
            ask_volume=0.0,
            trade_flow=0.0,
            buy_volume=0.0,
            sell_volume=0.0,
            # Multi-timeframe
            sma_10=float(indicators["sma_10"][i]),
            sma_30=float(indicators["sma_30"][i]),
            sma_60=float(indicators["sma_60"][i]),
            ema_20=float(indicators["ema_20"][i]),
            # Outcomes retrospectivos
            price_change_5m=price_change_5m,
            price_change_15m=price_change_15m,
            price_change_60m=price_change_60m,
            outcome=outcome,
        )
        snapshots.append(snap)

    logger.info(f"✅ {len(snapshots)} snapshots gerados")

    # Estatísticas de outcomes
    bulls = sum(1 for s in snapshots if s.outcome == "BULL")
    bears = sum(1 for s in snapshots if s.outcome == "BEAR")
    flats = sum(1 for s in snapshots if s.outcome == "FLAT")
    nones = sum(1 for s in snapshots if s.outcome is None)
    logger.info(
        f"📊 Distribuição: BULL={bulls} ({bulls/max(len(snapshots),1):.1%}), "
        f"BEAR={bears} ({bears/max(len(snapshots),1):.1%}), "
        f"FLAT={flats} ({flats/max(len(snapshots),1):.1%}), "
        f"sem outcome={nones}"
    )

    return snapshots


def populate_store(
    snapshots: List[MarketSnapshot],
    merge: bool = True,
) -> VectorStore:
    """Insere snapshots no VectorStore.

    Args:
        snapshots: Lista de MarketSnapshots.
        merge: Se True, carrega store existente e adiciona (sem duplicar).

    Returns:
        VectorStore populado.
    """
    store = VectorStore(dim=EMBEDDING_DIM, max_size=MAX_SNAPSHOTS)

    existing_timestamps = set()

    if merge and INDEX_FILE.exists():
        loaded = store.load(INDEX_FILE)
        if loaded:
            logger.info(f"📂 Store existente: {store.size} vetores")
            for meta in store._metadata:
                existing_timestamps.add(meta.get("timestamp", 0))

    added = 0
    skipped = 0

    for snap in snapshots:
        # Evitar duplicatas por timestamp
        if snap.timestamp in existing_timestamps:
            skipped += 1
            continue

        embedding = snap.to_embedding()
        metadata = snap.to_dict()
        store.add(embedding, metadata)
        existing_timestamps.add(snap.timestamp)
        added += 1

    logger.info(
        f"✅ VectorStore: +{added} novos, {skipped} duplicatas ignoradas, "
        f"total={store.size}"
    )

    return store


def main() -> None:
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Popula VectorStore do MarketRAG com dados históricos da KuCoin"
    )
    parser.add_argument(
        "--symbol", default="BTC-USDT",
        help="Par de trading (default: BTC-USDT)",
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Dias de histórico para buscar (default: 7)",
    )
    parser.add_argument(
        "--sample-rate", type=int, default=1,
        help="Amostrar 1 candle a cada N (1=todos ~1440/dia, 5=~288/dia)",
    )
    parser.add_argument(
        "--no-merge", action="store_true",
        help="Não mesclar com store existente (recriar do zero)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Caminho do arquivo de index (default: data/market_rag/index.pkl)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Log detalhado",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    start = time.time()

    # 1. Buscar candles históricas
    candles = fetch_historical_candles(args.symbol, args.days)
    if len(candles) < 100:
        logger.error(f"❌ Poucos candles ({len(candles)}). Abortando.")
        sys.exit(1)

    # 2. Calcular indicadores
    indicators = compute_indicators(candles)

    # 3. Gerar snapshots
    snapshots = build_snapshots(
        candles, indicators, args.symbol, args.sample_rate
    )

    # 4. Popular VectorStore
    store = populate_store(snapshots, merge=not args.no_merge)

    # 5. Salvar
    output_path = Path(args.output) if args.output else INDEX_FILE
    output_path.parent.mkdir(parents=True, exist_ok=True)
    store._dirty = True  # Forçar save
    store.save(output_path)

    elapsed = time.time() - start
    logger.info(
        f"🎉 Concluído em {elapsed:.1f}s — "
        f"{store.size} vetores salvos em {output_path}"
    )


if __name__ == "__main__":
    main()
