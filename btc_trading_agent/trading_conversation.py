"""Poder de conversação do Trading Analyst — orquestrado pelo Diretor.

Este módulo é o ponto único onde o "cérebro" do agent trading responde em
linguagem natural. Ele NÃO é chamado diretamente pelo bot do Telegram: a
integração é feita **a partir do orquestrador** (Diretor / specialized-agents
API), que delega para `answer_trading_question()`.

O contexto de resposta é aterrado (grounding) nos dados ao vivo do schema
``btc.*`` — os mesmos sinais dos agentes relacionados ao trading:

* mercado + posições abertas + PnL 24h/7d (base do relatório diário);
* ``btc.news_sentiment`` (sentimento de notícias) e ``btc.learning_rewards``
  (estatísticas de Q-learning);
* ``btc.ai_plans`` (plano da IA) e ``btc.ai_trade_windows`` (janela operacional).

A geração usa o modelo ``trading-analyst`` (Ollama GPU0/11434), o mesmo do
relatório diário, via :class:`tools.ollama_mcp_bridge.OllamaMCPBridge`.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger("btc_trading_agent.conversation")

# Símbolos da frota multi-símbolo (BTC/ETH em subcontas; SOL/DOGE na TRADE master). Configurável.
SYMBOLS = [
    s.strip().upper()
    for s in os.getenv(
        "TRADING_CONVERSATION_SYMBOLS", "BTC-USDT,ETH-USDT,SOL-USDT,DOGE-USDT"
    ).split(",")
    if s.strip()
]

DEFAULT_PROFILE = os.getenv("TRADING_CONVERSATION_PROFILE", "default")

SYSTEM_PROMPT = (
    "Você é o Trading Analyst do sistema Eddie Auto-Dev, respondendo no grupo "
    "\"BTC Trade Agent\" do Telegram. Você acompanha a frota de agentes de "
    "trading (BTC e ETH em subcontas KuCoin; SOL e DOGE na conta TRADE master) e conversa "
    "em português do Brasil, "
    "de forma direta e técnica, como um analista quantitativo.\n\n"
    "Regras:\n"
    "- Use SOMENTE os dados ao vivo fornecidos no CONTEXTO. Nunca invente "
    "preços, PnL ou posições.\n"
    "- Se o dado necessário não estiver no contexto, diga que não há registro "
    "recente em vez de supor.\n"
    "- Seja conciso (no máximo ~8 linhas). Sem introduções genéricas.\n"
    "- Você é um analista, não um consultor financeiro: não prometa retornos "
    "nem dê ordem de compra/venda como recomendação garantida.\n"
    "- Não repita o contexto cru; interprete-o para responder a pergunta."
)


# ─────────────────────────  Acesso ao banco (read-only)  ──────────────────────

def _resolve_db_url() -> Optional[str]:
    """Resolve a connection string do trading DB sem hardcodar credenciais.

    Segue a mesma ordem do relatório diário e do MCP homelab.
    """
    url = os.getenv("TRADING_DATABASE_URL")
    if url:
        return url

    database_url = os.getenv("DATABASE_URL")
    if database_url and "btc_trading" in database_url:
        return database_url

    host = os.getenv("BTC_TRADING_DB_HOST", "192.168.15.2")
    port = os.getenv("BTC_TRADING_DB_PORT", "5433")
    user = os.getenv("BTC_TRADING_DB_USER", "postgres")
    password = os.getenv("BTC_TRADING_DB_PASSWORD", "")
    name = os.getenv("BTC_TRADING_DB_NAME", "btc_trading")
    auth = f"{user}:{password}@" if password else f"{user}@"
    return f"postgresql://{auth}{host}:{port}/{name}"


def _btc_query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Executa um SELECT read-only no schema ``btc.*`` e retorna as linhas."""
    url = _resolve_db_url()
    if not url:
        logger.warning("Trading DB não configurado; contexto de conversa vazio")
        return []
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(url)
        try:
            conn.set_session(readonly=True, autocommit=True)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params or None)
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception:
        logger.exception("Falha ao consultar trading DB")
        return []


# ─────────────────────────────  Coleta de contexto  ──────────────────────────

def _has_shared_profile_ambiguity(symbol: str) -> bool:
    """Detecta múltiplos profiles LIVE com posição líquida no mesmo símbolo."""
    rows = _btc_query(
        """
        SELECT profile
        FROM btc.trades
        WHERE symbol = %s AND dry_run = FALSE
        GROUP BY profile
        HAVING
            ABS(
                COALESCE(
                    SUM(
                        CASE
                            WHEN side = 'buy'
                                 AND COALESCE(metadata->>'source', '') != 'external_deposit'
                            THEN size
                            WHEN side IN ('sell', 'sell_reconciled')
                            THEN -size
                            ELSE 0
                        END
                    ),
                    0
                )
            ) > 0.000001
            AND profile NOT IN ('default', 'exchange_sync')
        """,
        (symbol,),
    )
    return len(rows) > 1


def _collect_open_positions(symbol: str) -> list[dict[str, Any]]:
    """Posições abertas por profile — mesma lógica do Grafana/exporter."""
    from btc_trading_agent.position_reconstruction import (
        reconstruct_open_buys,
        summarize_open_buys,
    )

    profiles = _btc_query(
        """
        SELECT DISTINCT profile
        FROM btc.trades
        WHERE symbol = %s AND dry_run = FALSE
          AND profile NOT IN ('default', 'exchange_sync')
        """,
        (symbol,),
    )
    shared_ambiguous = _has_shared_profile_ambiguity(symbol)
    positions: list[dict[str, Any]] = []
    for prow in profiles:
        profile_name = str(prow.get("profile") or "")
        if not profile_name:
            continue
        trades = _btc_query(
            """
            SELECT id, side, size, price, timestamp, metadata
            FROM btc.trades
            WHERE symbol = %s AND profile = %s AND dry_run = FALSE
            ORDER BY timestamp DESC
            LIMIT 200
            """,
            (symbol, profile_name),
        )
        open_buys = reconstruct_open_buys(
            trades,
            shared_profile_ambiguous=shared_ambiguous and profile_name != "default",
            exclude_external_deposits=True,
        )
        if not open_buys:
            continue
        total_size, avg_entry = summarize_open_buys(open_buys)
        if total_size <= 0:
            continue
        positions.append(
            {
                "profile": profile_name,
                "n_entries": len(open_buys),
                "total_size": total_size,
                "invested_usdt": total_size * avg_entry,
                "avg_entry": avg_entry,
            }
        )
    return positions


def _collect_symbol(symbol: str, profile: str) -> dict[str, Any]:
    """Snapshot compacto de um símbolo: preço, PnL 24h, posições abertas."""
    # market_states.timestamp é epoch (double precision) e a tabela não tem
    # created_at — expõe to_timestamp(timestamp) como created_at.
    market = _btc_query(
        """
        SELECT price, rsi, momentum, volatility, trend,
               to_timestamp(timestamp) AS created_at
        FROM btc.market_states
        WHERE symbol = %s
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (symbol,),
    )
    perf = _btc_query(
        """
        SELECT
            COUNT(*) AS n_trades_24h,
            COALESCE(SUM(pnl), 0) AS realized_24h
        FROM btc.trades
        WHERE symbol = %s AND dry_run = FALSE
          AND timestamp > extract(epoch FROM now()) - 86400
        """,
        (symbol,),
    )
    positions = _collect_open_positions(symbol)
    window = _btc_query(
        """
        SELECT regime, entry_low, entry_high, target_sell, min_confidence,
               to_timestamp(valid_until) AS valid_until
        FROM btc.ai_trade_windows
        WHERE symbol = %s AND profile = %s
          AND valid_until > extract(epoch FROM now())
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (symbol, profile),
    )
    plan = _btc_query(
        """
        SELECT plan_text, regime, created_at
        FROM btc.ai_plans
        WHERE symbol = %s AND profile = %s
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (symbol, profile),
    )
    return {
        "symbol": symbol,
        "market": market[0] if market else {},
        "performance": perf[0] if perf else {},
        "positions": positions,
        "ai_window": window[0] if window else {},
        "ai_plan": plan[0] if plan else {},
    }


def collect_trading_context(
    symbols: Optional[list[str]] = None, profile: str = DEFAULT_PROFILE
) -> dict[str, Any]:
    """Reúne o contexto ao vivo dos agentes de trading para o prompt."""
    symbols = symbols or SYMBOLS
    context: dict[str, Any] = {"symbols": {}, "profile": profile}

    for symbol in symbols:
        try:
            context["symbols"][symbol] = _collect_symbol(symbol, profile)
        except Exception:
            logger.exception("Falha ao coletar contexto de %s", symbol)
            context["symbols"][symbol] = {"symbol": symbol}

    # Sinais globais dos agentes relacionados (não por símbolo).
    # news_sentiment.timestamp é timestamptz (não epoch) — usa intervalo SQL.
    context["news"] = _btc_query(
        """
        SELECT source, title, sentiment, confidence, coin, created_at
        FROM btc.news_sentiment
        WHERE timestamp > NOW() - INTERVAL '24 hours'
          AND confidence >= 0.30
        ORDER BY timestamp DESC
        LIMIT 6
        """,
    )
    learning = _btc_query(
        """
        SELECT
            COUNT(*) AS total_episodes,
            COALESCE(AVG(reward), 0) AS avg_reward,
            SUM(CASE WHEN action = 0 THEN 1 ELSE 0 END) AS hold_count,
            SUM(CASE WHEN action = 1 THEN 1 ELSE 0 END) AS buy_count,
            SUM(CASE WHEN action = 2 THEN 1 ELSE 0 END) AS sell_count
        FROM btc.learning_rewards
        """,
    )
    context["learning"] = learning[0] if learning else {}
    return context


# ──────────────────────────────  Prompt / geração  ───────────────────────────

def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def format_context_digest(context: dict[str, Any]) -> str:
    """Monta um resumo textual compacto do contexto para o prompt."""
    parts: list[str] = []
    for symbol, s in context.get("symbols", {}).items():
        market = s.get("market") or {}
        perf = s.get("performance") or {}
        price = _f(market.get("price"))
        line = (
            f"{symbol}: preço ${price:,.2f}"
            f" | RSI {market.get('rsi', 'n/d')}"
            f" | tendência {market.get('trend', 'n/d')}"
            f" | PnL 24h ${_f(perf.get('realized_24h')):+.4f}"
            f" | {int(_f(perf.get('n_trades_24h')))} trades 24h"
        )
        parts.append(line)

        for p in s.get("positions") or []:
            avg = _f(p.get("avg_entry"))
            total_size = _f(p.get("total_size"))
            invested = _f(p.get("invested_usdt"))
            pct = round((price / avg - 1) * 100, 2) if avg > 0 and price > 0 else 0.0
            parts.append(
                f"  posição {p.get('profile')}: {int(_f(p.get('n_entries')))} entradas,"
                f" {total_size:.8f} {symbol.split('-')[0]},"
                f" custo ${invested:,.2f},"
                f" médio ponderado ${avg:,.2f} ({pct:+.2f}%)"
            )

        window = s.get("ai_window") or {}
        if window:
            parts.append(
                f"  janela IA [{window.get('regime', '?')}]: entrada "
                f"${_f(window.get('entry_low')):,.2f}–${_f(window.get('entry_high')):,.2f},"
                f" alvo venda ${_f(window.get('target_sell')):,.2f}"
            )
        plan = s.get("ai_plan") or {}
        if plan.get("plan_text"):
            parts.append(f"  plano IA: {str(plan['plan_text']).strip()[:280]}")

    news = context.get("news") or []
    if news:
        parts.append("\nNotícias recentes (sentimento):")
        for n in news[:5]:
            parts.append(
                f"  [{n.get('sentiment', '?')}/{_f(n.get('confidence')):.2f}]"
                f" {str(n.get('title', '')).strip()[:120]}"
            )

    learning = context.get("learning") or {}
    if learning.get("total_episodes"):
        parts.append(
            f"\nAprendizado (Q-learning): {int(_f(learning.get('total_episodes')))} episódios,"
            f" reward médio {_f(learning.get('avg_reward')):+.4f}"
            f" | hold={int(_f(learning.get('hold_count')))}"
            f" buy={int(_f(learning.get('buy_count')))}"
            f" sell={int(_f(learning.get('sell_count')))}"
        )

    if not parts:
        return "Sem dados de trading disponíveis no momento."
    return "\n".join(parts)


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()


def generate_reply(question: str, context_digest: str, model: str, host: str) -> str:
    """Gera a resposta textual via modelo trading-analyst (Ollama). '' em falha."""
    from tools.ollama_mcp_bridge import OllamaMCPBridge

    user_msg = (
        "CONTEXTO (dados ao vivo dos agentes de trading):\n"
        f"{context_digest}\n\n"
        f"PERGUNTA DO GRUPO:\n{question.strip()}\n\n"
        "Responda de forma direta usando apenas o contexto acima."
    )
    try:
        with OllamaMCPBridge(model=model, host=host, num_predict=1024) as bridge:
            answer = bridge.run_with_tools(
                system=SYSTEM_PROMPT,
                user_msg=user_msg,
                tools=[],
            )
    except Exception:
        logger.exception("Falha ao gerar resposta via Ollama")
        return ""
    return _strip_think(answer)


def answer_trading_question(
    question: str,
    *,
    symbols: Optional[list[str]] = None,
    profile: str = DEFAULT_PROFILE,
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """Ponto de entrada orquestrado: contexto ao vivo + trading-analyst.

    Chamado pelo Diretor (orquestrador) e pela specialized-agents API. Retorna
    sempre um texto pronto para enviar ao Telegram (nunca lança exceção).
    """
    question = (question or "").strip()
    if not question:
        return "❓ Envie uma pergunta sobre o trading (ex.: como está o BTC hoje?)."

    model = os.getenv("OLLAMA_TRADING_MODEL", "trading-analyst:latest")
    host = os.getenv("OLLAMA_GENERATE_HOST", "http://192.168.15.2:11434")

    try:
        context = collect_trading_context(symbols=symbols, profile=profile)
        digest = format_context_digest(context)
    except Exception:
        logger.exception("Falha ao coletar contexto de trading")
        digest = "Sem dados de trading disponíveis no momento."

    reply = generate_reply(question, digest, model=model, host=host)
    if not reply:
        return (
            "⚠️ Não consegui gerar a análise agora (modelo trading-analyst "
            "indisponível). Tente novamente em instantes."
        )
    return f"📈 *Trading Analyst*\n\n{reply}"
