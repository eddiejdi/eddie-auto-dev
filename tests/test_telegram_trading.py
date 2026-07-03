"""Testes unitários do módulo de trading do Telegram."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import telegram_bot
from telegram_bot import TelegramBot

from btc_trading_agent import telegram_trading
from btc_trading_agent.telegram_trading import TelegramTradingClient


class FakeTelegramAPI:
    """API fake mínima para validar o dispatch do bot."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.actions: list[str] = []

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
        message_thread_id: int | None = None,
        parse_mode: str = "Markdown",
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.messages.append(text)
        return {"ok": True, "result": {"message_id": 1}}

    async def send_chat_action(
        self,
        chat_id: int,
        action: str = "typing",
        message_thread_id: int | None = None,
    ) -> dict[str, Any]:
        self.actions.append(action)
        return {"ok": True, "result": True}


class FakeTradingClient:
    """Cliente fake para inspecionar o roteamento do comando /cotacao."""

    def __init__(self) -> None:
        self.quote_queries: list[str] = []

    async def get_quote(self, query: str) -> str:
        self.quote_queries.append(query)
        return "cotacao fake"


def test_get_trading_help_menciona_cotacao() -> None:
    help_text = telegram_trading.get_trading_help()

    assert "/cotacao" in help_text
    assert "AKT-BRL" in help_text


def test_get_quote_formata_snapshot_da_kucoin(monkeypatch) -> None:
    client = TelegramTradingClient()
    fake_kucoin = SimpleNamespace(
        get_quote_snapshot=lambda query, default_quote="USDT", preferred_quotes=None: {
            "symbol": "AKT-USDT",
            "baseCurrency": "AKT",
            "quoteCurrency": "USDT",
            "matchedBy": "baseCurrency",
            "price": 0.8372,
            "bestBid": 0.8371,
            "bestAsk": 0.8373,
            "size": 120.5,
            "time": 1700000000123,
        },
        search_symbols=lambda query, limit=5: [],
        normalize_symbol=lambda query: str(query).strip().upper(),
    )
    monkeypatch.setattr(telegram_trading, "_load_kucoin_api_module", lambda: fake_kucoin)

    response = asyncio.run(client.get_quote("akt"))

    assert "AKT-USDT" in response
    assert "0.8372" in response
    assert "Bid/Ask" in response


def test_ask_question_detecta_consulta_de_cotacao() -> None:
    client = TelegramTradingClient()
    called: dict[str, str] = {}

    async def fake_get_quote(query: str) -> str:
        called["query"] = query
        return "ok"

    client.get_quote = fake_get_quote  # type: ignore[method-assign]

    response = asyncio.run(client.ask_question("qual a cotação de akt na kucoin?"))

    assert response == "ok"
    assert called["query"] == "AKT"


def test_handle_command_cotacao_usa_trading_client(monkeypatch) -> None:
    bot = TelegramBot.__new__(TelegramBot)
    fake_api = FakeTelegramAPI()
    fake_trading = FakeTradingClient()
    bot.api = fake_api

    monkeypatch.setattr(telegram_bot, "TRADING_AVAILABLE", True)
    monkeypatch.setattr(
        telegram_bot,
        "TRADING_COMMANDS",
        ["/btc", "/trades", "/performance", "/signal", "/trading", "/cotacao"],
    )
    monkeypatch.setattr(telegram_bot, "trading_client", fake_trading)

    message = {
        "chat": {"id": 10},
        "from": {"id": 20},
        "message_id": 30,
        "text": "/cotacao AKT",
    }

    asyncio.run(bot.handle_command(message))

    assert fake_api.actions == ["typing"]
    assert fake_trading.quote_queries == ["AKT"]
    assert fake_api.messages[-1] == "cotacao fake"
