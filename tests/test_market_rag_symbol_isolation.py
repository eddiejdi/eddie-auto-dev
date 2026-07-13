#!/usr/bin/env python3
"""Testes — isolamento por símbolo do VectorStore do Market RAG.

O index.pkl legado era compartilhado por todos os agentes (BTC/ETH/SOL/...),
contaminando o cálculo do AI buy target: o price_min da janela podia vir de
um snapshot de ETH (~$1.8k) enquanto o BTC operava a ~$62k, esmagando o alvo
para o clamp de -2% e bloqueando compras legítimas ("BUY blocked (AI target)").

Cobertura:
  - VectorStore.load(symbol=...) filtra vetores de outros símbolos
  - MarketRAG migra o índice legado compartilhado para o per-symbol
  - _calculate_ai_buy_target ignora preços de outros símbolos (defesa extra)
"""
import sys
import types
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

# Outros testes instalam um stub de market_rag em sys.modules (SimpleNamespace);
# aqui precisamos do módulo real — remover o stub antes de importar.
_existing = sys.modules.get("market_rag")
if _existing is not None and isinstance(_existing, types.SimpleNamespace):
    del sys.modules["market_rag"]

import market_rag
from market_rag import (
    EMBEDDING_DIM,
    MarketRAG,
    RegimeAdjuster,
    RegimeAdjustment,
    VectorStore,
)


def _meta(symbol: str, price: float, **extra) -> dict:
    base = {
        "symbol": symbol,
        "price": price,
        "volatility": 0.01,
        "momentum": 0.0,
        "timestamp": extra.pop("timestamp", 0.0),
    }
    base.update(extra)
    return base


def _mixed_store(n_btc: int = 30, n_eth: int = 20) -> VectorStore:
    """Store intercalado BTC (~62k) + ETH (~1.8k), como o index.pkl legado."""
    rng = np.random.default_rng(42)
    store = VectorStore(dim=EMBEDDING_DIM)
    for i in range(max(n_btc, n_eth)):
        if i < n_btc:
            store.add(rng.random(EMBEDDING_DIM, dtype=np.float32),
                      _meta("BTC-USDT", 62000.0 + (i % 10) * 50.0, timestamp=float(i)))
        if i < n_eth:
            store.add(rng.random(EMBEDDING_DIM, dtype=np.float32),
                      _meta("ETH-USDT", 1800.0 + (i % 10), timestamp=1000.0 + i))
    return store


# ── VectorStore.load(symbol=...) ─────────────────────────────────────────────

def test_load_filters_foreign_symbols(tmp_path):
    store = _mixed_store(n_btc=30, n_eth=20)
    idx = tmp_path / "index.pkl"
    store.save(idx)

    loaded = VectorStore(dim=EMBEDDING_DIM)
    assert loaded.load(idx, symbol="BTC-USDT") is True
    assert loaded.size == 30
    assert all(m["symbol"] == "BTC-USDT" for m in loaded._metadata)
    # Embeddings alinhados com metadata
    assert loaded._embeddings.shape[0] == len(loaded._metadata)
    # Filtro sujou o store → próximo save persiste o índice limpo
    assert loaded._dirty is True


def test_load_without_symbol_keeps_all(tmp_path):
    store = _mixed_store(n_btc=10, n_eth=10)
    idx = tmp_path / "index.pkl"
    store.save(idx)

    loaded = VectorStore(dim=EMBEDDING_DIM)
    assert loaded.load(idx) is True
    assert loaded.size == 20
    assert loaded._dirty is False


def test_load_filter_no_foreign_entries_is_noop(tmp_path):
    store = _mixed_store(n_btc=15, n_eth=0)
    idx = tmp_path / "index.pkl"
    store.save(idx)

    loaded = VectorStore(dim=EMBEDDING_DIM)
    assert loaded.load(idx, symbol="BTC-USDT") is True
    assert loaded.size == 15
    assert loaded._dirty is False


def test_load_filter_all_foreign_leaves_empty(tmp_path):
    store = _mixed_store(n_btc=0, n_eth=12)
    idx = tmp_path / "index.pkl"
    store.save(idx)

    loaded = VectorStore(dim=EMBEDDING_DIM)
    assert loaded.load(idx, symbol="BTC-USDT") is True
    assert loaded.size == 0
    assert loaded._embeddings.shape == (0, EMBEDDING_DIM)


def test_search_after_filter_returns_only_own_symbol(tmp_path):
    store = _mixed_store(n_btc=25, n_eth=25)
    idx = tmp_path / "index.pkl"
    store.save(idx)

    loaded = VectorStore(dim=EMBEDDING_DIM)
    loaded.load(idx, symbol="BTC-USDT")
    rng = np.random.default_rng(7)
    results = loaded.search(rng.random(EMBEDDING_DIM, dtype=np.float32), top_k=10)
    assert results
    assert all(meta["symbol"] == "BTC-USDT" for _, meta in results)


# ── Migração do índice legado no MarketRAG ───────────────────────────────────

def test_marketrag_migrates_legacy_shared_index(tmp_path, monkeypatch):
    monkeypatch.setattr(market_rag, "RAG_DIR", tmp_path)
    monkeypatch.setattr(market_rag, "INDEX_FILE", tmp_path / "index.pkl")

    legacy = _mixed_store(n_btc=18, n_eth=22)
    legacy.save(tmp_path / "index.pkl")

    rag = MarketRAG(symbol="BTC-USDT", profile="shadow")
    assert rag.index_file == tmp_path / "index_BTC-USDT.pkl"
    assert rag.store.size == 18
    assert all(m["symbol"] == "BTC-USDT" for m in rag.store._metadata)

    # Persistência no arquivo per-symbol não toca o legado
    rag.store.save(rag.index_file)
    assert (tmp_path / "index_BTC-USDT.pkl").exists()
    reloaded = VectorStore(dim=EMBEDDING_DIM)
    assert reloaded.load(rag.index_file, symbol="BTC-USDT") is True
    assert reloaded.size == 18


def test_marketrag_prefers_per_symbol_index(tmp_path, monkeypatch):
    monkeypatch.setattr(market_rag, "RAG_DIR", tmp_path)
    monkeypatch.setattr(market_rag, "INDEX_FILE", tmp_path / "index.pkl")

    # Legado contaminado + per-symbol já migrado com contagens distintas
    _mixed_store(n_btc=18, n_eth=22).save(tmp_path / "index.pkl")
    _mixed_store(n_btc=5, n_eth=0).save(tmp_path / "index_BTC-USDT.pkl")

    rag = MarketRAG(symbol="BTC-USDT", profile="shadow")
    assert rag.store.size == 5


# ── AI buy target ignora preços de outros símbolos ───────────────────────────

def _ranging_adjustment(symbol: str = "BTC-USDT") -> RegimeAdjustment:
    adj = RegimeAdjustment(timestamp=0.0, symbol=symbol)
    adj.suggested_regime = "RANGING"
    adj.regime_confidence = 0.6
    adj.ai_aggressiveness = 0.34
    return adj


def test_buy_target_ranging_ignores_foreign_prices():
    """Com store misto, o alvo deve sair do range do BTC, não do clamp de -2%.

    Antes do fix: price_min vinha do ETH (~$1.8k) → lower_third ~$17k →
    target esmagado para current*0.98 → BUY blocked com gap de ~2%.
    """
    adjuster = RegimeAdjuster("BTC-USDT")
    store = _mixed_store(n_btc=120, n_eth=120)
    current_price = 62400.0

    adj = _ranging_adjustment()
    adjuster._calculate_ai_buy_target(adj, current_price, store=store)

    # BTC no range 62000-62450 → alvo dentro do range, longe do piso de -2%
    assert adj.ai_buy_target_price >= current_price * 0.99
    assert adj.ai_buy_target_price <= current_price * 0.9995
    assert adj.ai_buy_target_reason.startswith("ranging")


def test_buy_target_ranging_pure_store_unchanged():
    """Sanidade: store puro BTC continua com o mesmo comportamento."""
    adjuster = RegimeAdjuster("BTC-USDT")
    store = _mixed_store(n_btc=120, n_eth=0)
    current_price = 62400.0

    adj = _ranging_adjustment()
    adjuster._calculate_ai_buy_target(adj, current_price, store=store)

    assert adj.ai_buy_target_price >= current_price * 0.99
    assert adj.ai_buy_target_reason.startswith("ranging")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
