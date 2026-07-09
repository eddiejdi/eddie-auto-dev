"""Testes do poder de conversação do Trading Analyst (orquestrado)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from btc_trading_agent import trading_conversation as tc


_SAMPLE_CONTEXT = {
    "profile": "default",
    "symbols": {
        "BTC-USDT": {
            "symbol": "BTC-USDT",
            "market": {"price": 65000.0, "rsi": 55, "trend": "up"},
            "performance": {"realized_24h": 12.34, "n_trades_24h": 3},
            "positions": [{"profile": "default", "n_entries": 2, "avg_entry": 60000.0}],
            "ai_window": {
                "regime": "range",
                "entry_low": 63000.0,
                "entry_high": 64000.0,
                "target_sell": 66000.0,
            },
            "ai_plan": {"plan_text": "Acumular em suporte forte.", "regime": "range"},
        }
    },
    "news": [
        {"sentiment": "bullish", "confidence": 0.8, "title": "ETF inflows record"},
    ],
    "learning": {
        "total_episodes": 100,
        "avg_reward": 0.05,
        "hold_count": 60,
        "buy_count": 25,
        "sell_count": 15,
    },
}


def test_format_context_digest_inclui_sinais_principais() -> None:
    digest = tc.format_context_digest(_SAMPLE_CONTEXT)
    assert "BTC-USDT" in digest
    assert "$65,000.00" in digest
    assert "PnL 24h $+12.3400" in digest
    assert "posição default" in digest
    assert "+8.33%" in digest  # (65000/60000 - 1) * 100
    assert "janela IA" in digest
    assert "plano IA" in digest
    assert "ETF inflows record" in digest
    assert "Q-learning" in digest


def test_format_context_digest_vazio() -> None:
    assert "Sem dados" in tc.format_context_digest({"symbols": {}})


def test_collect_trading_context_usa_btc_query(monkeypatch) -> None:
    calls = []

    def fake_query(sql, params=()):
        calls.append(sql.strip().split()[1])  # palavra após SELECT (aproximação)
        if "market_states" in sql:
            return [{"price": 100.0, "rsi": 50, "trend": "flat"}]
        if "news_sentiment" in sql:
            return [{"sentiment": "neutral", "confidence": 0.5, "title": "x"}]
        if "learning_rewards" in sql:
            return [{"total_episodes": 1, "avg_reward": 0.0}]
        return []

    monkeypatch.setattr(tc, "_btc_query", fake_query)
    ctx = tc.collect_trading_context(symbols=["BTC-USDT"], profile="default")

    assert "BTC-USDT" in ctx["symbols"]
    assert ctx["symbols"]["BTC-USDT"]["market"]["price"] == 100.0
    assert ctx["news"] and ctx["learning"]["total_episodes"] == 1


def test_answer_trading_question_formata_resposta(monkeypatch) -> None:
    monkeypatch.setattr(tc, "collect_trading_context", lambda **kw: _SAMPLE_CONTEXT)
    monkeypatch.setattr(
        tc, "generate_reply", lambda q, digest, model, host: "BTC estável em suporte."
    )

    out = tc.answer_trading_question("como está o btc?")
    assert out.startswith("📈 *Trading Analyst*")
    assert "BTC estável em suporte." in out


def test_answer_trading_question_pergunta_vazia() -> None:
    out = tc.answer_trading_question("   ")
    assert "Envie uma pergunta" in out


def test_answer_trading_question_fallback_quando_modelo_falha(monkeypatch) -> None:
    monkeypatch.setattr(tc, "collect_trading_context", lambda **kw: _SAMPLE_CONTEXT)
    monkeypatch.setattr(tc, "generate_reply", lambda q, digest, model, host: "")

    out = tc.answer_trading_question("e agora?")
    assert "indisponível" in out


def test_answer_trading_question_resiliente_a_falha_de_contexto(monkeypatch) -> None:
    def boom(**kw):
        raise RuntimeError("db down")

    captured = {}

    def fake_reply(q, digest, model, host):
        captured["digest"] = digest
        return "resposta"

    monkeypatch.setattr(tc, "collect_trading_context", boom)
    monkeypatch.setattr(tc, "generate_reply", fake_reply)

    out = tc.answer_trading_question("status?")
    assert "resposta" in out
    assert "Sem dados" in captured["digest"]
