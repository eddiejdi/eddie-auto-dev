#!/usr/bin/env python3
"""Integração leve de trading para o bot do Telegram."""

from __future__ import annotations

import importlib
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

TRADING_COMMANDS = [
    "/btc",
    "/trades",
    "/performance",
    "/signal",
    "/trading",
    "/cotacao",
    "/relatorio",
]

DEFAULT_STATUS_SYMBOL = os.getenv("TRADING_STATUS_SYMBOL", "BTC-USDT").upper()
DEFAULT_QUOTE = os.getenv("TRADING_DEFAULT_QUOTE", "USDT").upper()
DEFAULT_PERFORMANCE_DAYS = int(os.getenv("TRADING_PERFORMANCE_DAYS", "7"))
LOCAL_TZ = ZoneInfo(os.getenv("TRADING_TIMEZONE", "America/Sao_Paulo"))
QUOTE_STOPWORDS = {
    "A", "AS", "COTACAO", "COTACAO?", "COTAÇÃO", "CONSULTAR", "DA", "DAS", "DE",
    "DO", "DOS", "KUCOIN", "ME", "MOEDA", "MOSTRA", "MOSTRE", "NA", "NO", "O",
    "OS", "PAR", "PARES", "PRECO", "PREÇO", "QUAL", "QUOTE", "VALOR", "VER",
}


def get_trading_help() -> str:
    """Ajuda resumida do agent trading no Telegram."""
    return (
        "📈 *Trading Agent*\n\n"
        "/btc - Status resumido do BTC\n"
        "/relatorio - Planejamento AI + P&L 24h (relatório completo)\n"
        "/trades [limite] - Últimos trades gravados\n"
        "/performance - Performance recente\n"
        "/signal - Último sinal registrado\n"
        "/cotacao [moeda|par] - Cotação na KuCoin\n"
        "/trading [pergunta] - Consulta livre\n\n"
        "*Exemplos de cotação:*\n"
        "• /cotacao AKT\n"
        "• /cotacao AKT-BRL\n"
        "• /cotacao BTC/USDT"
    )


def _escape_markdown(text: Any) -> str:
    raw = str(text or "")
    for token in ("\\", "_", "*", "`", "["):
        raw = raw.replace(token, f"\\{token}")
    return raw


def _format_timestamp_ms(timestamp_ms: int | float | None) -> str:
    try:
        ts_int = int(timestamp_ms or 0)
    except (TypeError, ValueError):
        return "n/d"
    if ts_int <= 0:
        return "n/d"
    return datetime.fromtimestamp(ts_int / 1000, tz=LOCAL_TZ).strftime("%d/%m/%Y %H:%M:%S %Z")


def _format_timestamp_seconds(timestamp_seconds: int | float | None) -> str:
    try:
        ts_value = float(timestamp_seconds or 0.0)
    except (TypeError, ValueError):
        return "n/d"
    if ts_value <= 0:
        return "n/d"
    return datetime.fromtimestamp(ts_value, tz=LOCAL_TZ).strftime("%d/%m %H:%M")


def _format_price(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/d"
    if numeric == 0:
        return "0"
    if abs(numeric) >= 1000:
        return f"{numeric:,.2f}"
    if abs(numeric) >= 1:
        return f"{numeric:,.4f}"
    return f"{numeric:,.6f}"


def _format_quantity(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/d"
    if numeric == 0:
        return "0"
    return f"{numeric:,.8f}".rstrip("0").rstrip(".")


def _load_kucoin_api_module():
    try:
        return importlib.import_module("btc_trading_agent.kucoin_api")
    except ImportError:
        return importlib.import_module("kucoin_api")


def _get_report_db_url() -> str:
    """Resolve DATABASE_URL sem importar training_db (evita cadeia secrets_helper)."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        from btc_trading_agent.secrets_helper import get_database_url as _gdu
        return _gdu()
    except Exception:
        pass
    try:
        from secrets_helper import get_database_url as _gdu  # type: ignore[no-redef]
        return _gdu()
    except Exception:
        pass
    # Fallback idêntico ao de training_db.py
    return "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading"


def _load_training_db_module():
    try:
        return importlib.import_module("btc_trading_agent.training_db")
    except ImportError:
        return importlib.import_module("training_db")


class TelegramTradingClient:
    """Cliente enxuto para consultas do agent trading via Telegram."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or Path(__file__).parent
        self.default_status_symbol = DEFAULT_STATUS_SYMBOL
        self.default_quote = DEFAULT_QUOTE
        self.default_performance_days = DEFAULT_PERFORMANCE_DAYS
        self._db = None
        self._db_error: Optional[str] = None

    def _get_db(self):
        if self._db is not None:
            return self._db
        if self._db_error:
            return None
        try:
            training_db = _load_training_db_module()
            self._db = training_db.TrainingDatabase()
            return self._db
        except Exception as exc:
            self._db_error = str(exc)
            return None

    def _extract_quote_query(self, text: str) -> str:
        raw = (text or "").strip()
        if not raw:
            return ""

        normalized = (
            unicodedata.normalize("NFKD", raw)
            .encode("ascii", "ignore")
            .decode("ascii")
        )

        pair_match = re.search(r"([A-Za-z0-9]{2,12})\s*[-/_]\s*([A-Za-z0-9]{2,12})", normalized)
        if pair_match:
            return f"{pair_match.group(1)}-{pair_match.group(2)}".upper()

        tokens = re.findall(r"[A-Za-z0-9]{2,12}", normalized.upper())
        for token in tokens:
            if token not in QUOTE_STOPWORDS:
                return token
        return ""

    async def get_quote(self, query: str) -> str:
        requested = (query or "").strip()
        if not requested:
            return (
                "❓ Use: /cotacao [moeda ou par]\n\n"
                "Exemplos:\n"
                "• /cotacao AKT\n"
                "• /cotacao AKT-BRL\n"
                "• /cotacao BTC/USDT"
            )

        kucoin_api = _load_kucoin_api_module()
        snapshot = kucoin_api.get_quote_snapshot(
            requested,
            default_quote=self.default_quote,
            preferred_quotes=["BRL", "USDT", "USDC"],
        )
        if not snapshot:
            suggestions = kucoin_api.search_symbols(requested, limit=5)
            if suggestions:
                hint = ", ".join(
                    f"`{item.get('symbol')}`"
                    for item in suggestions
                    if item.get("symbol")
                )
                return (
                    f"❌ Não encontrei a cotação de *{_escape_markdown(requested)}* na KuCoin.\n"
                    f"Talvez você queira: {hint}"
                )
            return (
                f"❌ Não encontrei a cotação de *{_escape_markdown(requested)}* na KuCoin.\n"
                "Tente um ticker como `AKT`, `BTC-USDT` ou `USDT-BRL`."
            )

        symbol = str(snapshot.get("symbol") or "")
        base = str(snapshot.get("baseCurrency") or "").upper()
        quote = str(snapshot.get("quoteCurrency") or "").upper()
        matched_by = str(snapshot.get("matchedBy") or "symbol")
        resolved_note = ""
        normalized_requested = kucoin_api.normalize_symbol(requested)
        if normalized_requested != symbol and matched_by == "baseCurrency":
            resolved_note = f"\nPar resolvido automaticamente: `{symbol}`"
        elif normalized_requested != symbol and matched_by == "quoteCurrency":
            resolved_note = f"\nPar encontrado pelo quote: `{symbol}`"

        return (
            f"💱 *KuCoin* `{symbol}`\n"
            f"Preço: `{_format_price(snapshot.get('price'))} {quote}`\n"
            f"Bid/Ask: `{_format_price(snapshot.get('bestBid'))}` / `{_format_price(snapshot.get('bestAsk'))}`\n"
            f"Último lote: `{_format_quantity(snapshot.get('size'))} {base or 'base'}`\n"
            f"Atualizado: `{_format_timestamp_ms(snapshot.get('time'))}`"
            f"{resolved_note}"
        )

    async def get_status(self) -> str:
        kucoin_api = _load_kucoin_api_module()
        symbol = self.default_status_symbol
        price = kucoin_api.get_price(symbol)
        db = self._get_db()
        performance = {}
        latest_trade: dict[str, Any] | None = None
        if db is not None:
            try:
                performance = db.calculate_performance(symbol, days=self.default_performance_days)
                recent_trades = db.get_recent_trades(symbol=symbol, limit=1, include_dry=True)
                latest_trade = recent_trades[0] if recent_trades else None
            except Exception as exc:
                if not self._db_error:
                    self._db_error = str(exc)

        lines = [
            f"📈 *Status Trading* `{symbol}`",
            f"Preço KuCoin: `{_format_price(price)} USDT`" if price is not None else "Preço KuCoin: `indisponível`",
        ]
        if performance:
            lines.extend(
                [
                    f"Trades {self.default_performance_days}d: `{int(performance.get('total_trades', 0) or 0)}`",
                    f"Win rate: `{float(performance.get('win_rate', 0.0) or 0.0):.1%}`",
                    f"PnL: `{float(performance.get('total_pnl', 0.0) or 0.0):.4f} USDT`",
                ]
            )
        else:
            lines.append("Métricas históricas: `indisponíveis`")

        if latest_trade:
            lines.append(
                "Último trade: "
                f"`{str(latest_trade.get('side') or '').upper()}` "
                f"@ `{_format_price(latest_trade.get('price'))}` "
                f"em `{_format_timestamp_seconds(latest_trade.get('timestamp'))}`"
            )
        elif self._db_error:
            lines.append(f"Banco de trades: `{_escape_markdown(self._db_error[:120])}`")

        return "\n".join(lines)

    async def get_trades(self, limit: int = 5) -> str:
        db = self._get_db()
        if db is None:
            detail = f" `{_escape_markdown(self._db_error[:120])}`" if self._db_error else ""
            return f"⚠️ Banco de trades indisponível.{detail}"

        rows = db.get_recent_trades(
            symbol=self.default_status_symbol,
            limit=max(1, min(int(limit or 5), 20)),
            include_dry=True,
        )
        if not rows:
            return f"📭 Nenhum trade recente encontrado para `{self.default_status_symbol}`."

        lines = [f"🧾 *Últimos trades* `{self.default_status_symbol}`"]
        for trade in rows:
            pnl = trade.get("pnl")
            pnl_text = ""
            if pnl is not None and str(pnl).strip():
                try:
                    pnl_text = f" | pnl `{float(pnl):.4f}`"
                except (TypeError, ValueError):
                    pnl_text = f" | pnl `{_escape_markdown(pnl)}`"
            lines.append(
                f"• `{_format_timestamp_seconds(trade.get('timestamp'))}` "
                f"`{str(trade.get('side') or '').upper()}` "
                f"`{_format_quantity(trade.get('size'))}` @ `{_format_price(trade.get('price'))}`"
                f"{pnl_text}"
            )
        return "\n".join(lines)

    async def get_performance(self) -> str:
        db = self._get_db()
        if db is None:
            detail = f" `{_escape_markdown(self._db_error[:120])}`" if self._db_error else ""
            return f"⚠️ Banco de performance indisponível.{detail}"

        stats = db.calculate_performance(self.default_status_symbol, days=self.default_performance_days)
        return (
            f"📊 *Performance* `{self.default_status_symbol}`\n"
            f"Janela: `{self.default_performance_days} dias`\n"
            f"Trades: `{int(stats.get('total_trades', 0) or 0)}`\n"
            f"Trades vencedores: `{int(stats.get('winning_trades', 0) or 0)}`\n"
            f"Win rate: `{float(stats.get('win_rate', 0.0) or 0.0):.1%}`\n"
            f"PnL total: `{float(stats.get('total_pnl', 0.0) or 0.0):.4f} USDT`\n"
            f"PnL médio: `{float(stats.get('avg_pnl', 0.0) or 0.0):.4f} USDT`"
        )

    async def get_signal(self) -> str:
        db = self._get_db()
        if db is None:
            detail = f" `{_escape_markdown(self._db_error[:120])}`" if self._db_error else ""
            return f"⚠️ Banco de sinais indisponível.{detail}"

        decisions = db.get_recent_decisions(symbol=self.default_status_symbol, limit=1)
        if not decisions:
            return f"📭 Nenhum sinal recente encontrado para `{self.default_status_symbol}`."

        signal = decisions[0]
        reason = _escape_markdown(str(signal.get("reason") or "Sem justificativa"))
        return (
            f"🧠 *Último sinal* `{self.default_status_symbol}`\n"
            f"Ação: `{str(signal.get('action') or '').upper()}`\n"
            f"Confiança: `{float(signal.get('confidence', 0.0) or 0.0):.1%}`\n"
            f"Preço: `{_format_price(signal.get('price'))}`\n"
            f"Executado: `{'sim' if signal.get('executed') else 'não'}`\n"
            f"Horário: `{_format_timestamp_seconds(signal.get('timestamp'))}`\n"
            f"Motivo: {reason}"
        )

    async def get_report(self) -> str:
        """Relatório completo: planejamento AI atual + P&L últimas 24h."""
        import psycopg2
        import psycopg2.extras

        DATABASE_URL = _get_report_db_url()

        price: Optional[float] = None
        try:
            kucoin_api = _load_kucoin_api_module()
            price = kucoin_api.get_price("BTC-USDT")
        except Exception:
            pass

        now_br = datetime.now(LOCAL_TZ).strftime("%d/%m %H:%M")
        header = (
            f"📈 *Trading Monitor* — BTC `${price:,.2f} USDT`\n🕐 `{now_br}`"
            if price is not None
            else f"📈 *Trading Monitor*\n🕐 `{now_br}`"
        )

        ai_lines: list[str] = ["", "🧠 *Planejamento AI atual*"]
        pnl_lines: list[str] = ["", "📊 *P&L últimas 24h*"]
        pos_lines: list[str] = ["", "📦 *Posições abertas*"]

        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Plano AI mais recente por perfil
            cur.execute("""
                SELECT DISTINCT ON (profile)
                    profile, regime, price AS plan_price, created_at
                FROM btc.ai_plans
                WHERE profile IN ('aggressive','conservative')
                  AND created_at >= NOW() - INTERVAL '2 hours'
                ORDER BY profile, created_at DESC
            """)
            plans = cur.fetchall()
            for p in plans:
                emoji = "⚡" if p["profile"] == "aggressive" else "🛡️"
                age_min = max(0, int(
                    (datetime.now(p["created_at"].tzinfo) - p["created_at"]).total_seconds() / 60
                ))
                ai_lines.append(
                    f"{emoji} *{p['profile'].capitalize()}*: "
                    f"`{p['regime']}` @ `${p['plan_price']:,.0f}` _{age_min}min atrás_"
                )
            if not plans:
                ai_lines.append("_Sem plano recente nos últimos 2h_")

            # P&L 24h por perfil
            cur.execute("""
                SELECT
                    profile,
                    COUNT(*) FILTER (WHERE side IN ('buy','buy_reconciled')) AS compras,
                    COUNT(*) FILTER (WHERE side IN ('sell','sell_reconciled')) AS vendas,
                    COALESCE(ROUND(SUM(pnl) FILTER (WHERE pnl IS NOT NULL AND pnl != 0)::numeric,4),0) AS pnl_usd,
                    COUNT(*) FILTER (WHERE side IN ('sell','sell_reconciled') AND pnl > 0) AS wins,
                    COUNT(*) FILTER (WHERE side IN ('sell','sell_reconciled') AND pnl <= 0) AS losses,
                    COALESCE(ROUND(AVG(pnl_pct) FILTER (
                        WHERE side IN ('sell','sell_reconciled') AND pnl_pct IS NOT NULL
                    )::numeric,2),0) AS avg_pct
                FROM btc.trades
                WHERE to_timestamp(timestamp) >= NOW() - INTERVAL '24 hours'
                  AND status = 'executed'
                  AND dry_run = false
                  AND profile IN ('aggressive','conservative')
                GROUP BY profile
                ORDER BY profile
            """)
            rows = cur.fetchall()
            total_pnl = 0.0
            for r in rows:
                emoji = "⚡" if r["profile"] == "aggressive" else "🛡️"
                pnl = float(r["pnl_usd"] or 0)
                total_pnl += pnl
                sign = "+" if pnl >= 0 else ""
                total_s = r["wins"] + r["losses"]
                wr = f"{r['wins']}/{total_s} ({r['wins']*100//total_s if total_s else 0}%)" if total_s else "—"
                pnl_lines.append(
                    f"{emoji} *{r['profile'].capitalize()}*: "
                    f"`{sign}{pnl:.4f} USD` | {r['vendas']} vendas | WR {wr} | avg `{r['avg_pct']:.2f}%`"
                )
            if not rows:
                pnl_lines.append("_Sem trades nas últimas 24h_")
            else:
                sign = "+" if total_pnl >= 0 else ""
                pnl_lines.append(f"💰 *Total*: `{sign}{total_pnl:.4f} USD`")

            # Posições abertas: net BTC por perfil nas últimas 48h
            cur.execute("""
                SELECT
                    profile,
                    COUNT(*) FILTER (WHERE side = 'buy') AS n_entries,
                    ROUND(SUM(CASE WHEN side='buy' THEN size ELSE -size END)::numeric,8) AS net_btc,
                    ROUND((
                        SUM(CASE WHEN side='buy' THEN size*price ELSE 0 END) /
                        NULLIF(SUM(CASE WHEN side='buy' THEN size ELSE 0 END),0)
                    )::numeric,2) AS avg_entry
                FROM btc.trades
                WHERE to_timestamp(timestamp) >= NOW() - INTERVAL '48 hours'
                  AND status = 'executed'
                  AND dry_run = false
                  AND side IN ('buy','sell')
                  AND profile IN ('aggressive','conservative')
                GROUP BY profile
                HAVING SUM(CASE WHEN side='buy' THEN size ELSE -size END) > 0.000001
                ORDER BY profile
            """)
            pos_rows = cur.fetchall()
            for pr in pos_rows:
                emoji = "⚡" if pr["profile"] == "aggressive" else "🛡️"
                net = float(pr["net_btc"] or 0)
                avg = float(pr["avg_entry"] or 0)
                unreal = (price - avg) * net if price and avg else None
                unreal_str = (
                    f" | PnL `{'+'if unreal>=0 else ''}{unreal:.2f} USD`"
                    if unreal is not None else ""
                )
                pct = ((price / avg) - 1) * 100 if price and avg else None
                pct_str = f" `({'+'if pct>=0 else ''}{pct:.2f}%)`" if pct is not None else ""
                pos_lines.append(
                    f"{emoji} *{pr['profile'].capitalize()}*: "
                    f"`{pr['n_entries']}` entradas | "
                    f"`{net:.6f} BTC` avg `${avg:,.2f}`{pct_str}{unreal_str}"
                )
            if not pos_rows:
                pos_lines.append("_Sem posições abertas (48h)_")

            cur.close()
            conn.close()

        except Exception as exc:
            err = _escape_markdown(str(exc)[:100])
            ai_lines.append(f"_Erro DB: {err}_")

        return "\n".join([header] + ai_lines + pnl_lines + pos_lines)

    async def ask_question(self, question: str) -> str:
        text = (question or "").strip()
        if not text:
            return get_trading_help()

        lowered = text.lower()
        quote_query = self._extract_quote_query(text)
        if quote_query and any(
            keyword in lowered for keyword in ("cotacao", "cotação", "preco", "preço", "quote", "valor")
        ):
            return await self.get_quote(quote_query)
        if quote_query and re.fullmatch(r"[A-Za-z0-9]{2,12}(?:[-/_ ][A-Za-z0-9]{2,12})?", text.strip()):
            return await self.get_quote(quote_query)
        if "trade" in lowered:
            return await self.get_trades(5)
        if "performance" in lowered or "pnl" in lowered:
            return await self.get_performance()
        if "signal" in lowered or "sinal" in lowered:
            return await self.get_signal()
        if "status" in lowered:
            return await self.get_status()
        return (
            "❓ Consulta de trading não reconhecida.\n\n"
            f"{get_trading_help()}"
        )
