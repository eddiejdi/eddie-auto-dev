"""Testes de roteamento do Trading Analyst no Diretor (orquestrador)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_delegate_to_trading_por_marcador_de_dominio() -> None:
    """O marcador explícito domain=trading tem prioridade sobre o texto."""
    from dev_agent.run_diretor_service import _should_delegate_to_trading

    assert _should_delegate_to_trading("qualquer coisa", {"domain": "trading"}) is True


def test_delegate_to_trading_por_palavra_chave() -> None:
    from dev_agent.run_diretor_service import _should_delegate_to_trading

    assert _should_delegate_to_trading("como está o BTC hoje?") is True
    assert _should_delegate_to_trading("qual o PnL das posições?") is True
    assert _should_delegate_to_trading("gerar imagem de um gato") is False
    assert _should_delegate_to_trading("revisar meu código python") is False


def test_run_trading_conversation_delega_ao_cerebro(monkeypatch) -> None:
    """_run_trading_conversation deve chamar answer_trading_question com metadata."""
    import btc_trading_agent.trading_conversation as tc
    from dev_agent.run_diretor_service import _run_trading_conversation

    captured = {}

    def fake_answer(question, *, symbols=None, profile="default", metadata=None):
        captured["question"] = question
        captured["symbols"] = symbols
        captured["profile"] = profile
        captured["metadata"] = metadata
        return "📈 resposta do analista"

    monkeypatch.setattr(tc, "answer_trading_question", fake_answer)

    out = _run_trading_conversation(
        "como está o eth?",
        {"domain": "trading", "profile": "scalp", "symbols": "ETH-USDT,BTC-USDT"},
    )

    assert out == "📈 resposta do analista"
    assert captured["question"] == "como está o eth?"
    assert captured["profile"] == "scalp"
    assert captured["symbols"] == ["ETH-USDT", "BTC-USDT"]
    assert captured["metadata"]["domain"] == "trading"


def test_run_trading_conversation_symbols_lista(monkeypatch) -> None:
    import btc_trading_agent.trading_conversation as tc
    from dev_agent.run_diretor_service import _run_trading_conversation

    captured = {}
    monkeypatch.setattr(
        tc, "answer_trading_question",
        lambda q, *, symbols=None, profile="default", metadata=None: captured.update(
            symbols=symbols
        ) or "ok",
    )

    _run_trading_conversation("btc?", {"symbols": ["BTC-USDT"]})
    assert captured["symbols"] == ["BTC-USDT"]
