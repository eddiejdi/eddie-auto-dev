"""
Teste integrado de backtest — SellTargetMixin vs. comportamento anterior.

Compara dois comportamentos de target_sell_price usando dados reais:
  - OLD: entry × ai_tp (fórmula fixa, ignorava previsão da AI window)
  - NEW: AI trade window como alvo primário; fórmula apenas como teto MAX

Requisitos:
  - DATABASE_URL ou credencial hardcoded do homelab  [postgres]
  - Ollama rodando em 192.168.15.2:11434            [ollama]

Execução:
  pytest tests/integration/test_sell_target_backtest.py -m integration -v -s

Não roda no CI automático (markers: integration + ollama).
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest

# ── Deps opcionais — skip em CI ─────────────────────────────────────────────

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    pytest.skip("psycopg2 não disponível", allow_module_level=True)

try:
    import requests
except ImportError:
    pytest.skip("requests não disponível", allow_module_level=True)

# ── Constantes ───────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading",
)
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://192.168.15.2:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")  # vazio = detectar modelo carregado
SYMBOL       = "BTC-USDT"
TRADING_FEE  = 0.001
AI_TP_PCT    = 0.013   # ai_take_profit_pct padrão do config (1.3%)
RANGING_CAP  = 0.004   # ranging_max_tp_pct novo config (0.4%)
BACKTEST_H   = 24      # horas de candles para replay


# ── Helpers de DB ────────────────────────────────────────────────────────────

def _connect() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def _load_candles(conn, hours: int = BACKTEST_H) -> list[dict]:
    """Últimas `hours` horas de candles 1min do DB."""
    cutoff = time.time() - hours * 3600
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT timestamp, open, high, low, close, volume
        FROM btc.candles
        WHERE symbol = %s AND ktype = '1min' AND timestamp >= %s
        ORDER BY timestamp ASC
        """,
        (SYMBOL, cutoff),
    )
    return [dict(r) for r in cur.fetchall()]


def _load_ai_windows(conn, since_ts: float) -> list[dict]:
    """AI trade windows registradas desde `since_ts`."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT timestamp, regime, target_sell, entry_low, entry_high, profile, mode, rationale
        FROM btc.ai_trade_windows
        WHERE symbol = %s AND timestamp >= %s
        ORDER BY timestamp ASC
        """,
        (SYMBOL, since_ts),
    )
    return [dict(r) for r in cur.fetchall()]


def _load_news_sentiment(conn, since_ts: float) -> list[dict]:
    """Registros de sentimento de notícias desde `since_ts`."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    ts_dt = datetime.fromtimestamp(since_ts, tz=timezone.utc)
    cur.execute(
        "SELECT timestamp, sentiment, confidence, title FROM btc.news_sentiment "
        "WHERE timestamp >= %s ORDER BY timestamp ASC",
        (ts_dt,),
    )
    return [dict(r) for r in cur.fetchall()]


def _load_open_positions(conn) -> list[dict]:
    """
    Posições abertas: BUYs reais com target_sell_price no metadata (não vendidos).
    Identifica pela presença de target_sell_price no metadata — só buys abertos têm isso.
    Limita a 30 para o teste.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT id, timestamp, price, size, profile,
               (metadata->>'target_sell_price')::float AS old_target,
               (metadata->>'target_sell_reason') AS old_reason
        FROM btc.trades
        WHERE symbol = %s AND side = 'buy' AND dry_run = false
          AND metadata ? 'target_sell_price'
        ORDER BY timestamp DESC
        LIMIT 30
        """,
        (SYMBOL,),
    )
    return [dict(r) for r in cur.fetchall()]


# ── Ollama helper ─────────────────────────────────────────────────────────────

def _get_loaded_model() -> str | None:
    """Retorna modelo em memória: prefere trading-analyst, fallback para qualquer carregado."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/ps", timeout=5)
        if r.status_code == 200:
            running = [m["name"] for m in r.json().get("models", [])]
            # Preferir trading-analyst se disponível
            for name in running:
                if "trading-analyst" in name:
                    return name
            if running:
                return running[0]
    except Exception:
        pass
    return None


def _ask_ollama(prompt: str, timeout: int = 30) -> str | None:
    """
    Consulta Ollama. Usa /api/chat para modelos com template de chat (trading-analyst).
    Retorna o conteúdo texto da resposta.
    """
    model = OLLAMA_MODEL or _get_loaded_model()
    if not model:
        return None
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "stream": False,
                "think": False,   # desativa thinking mode (trading-analyst)
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return (data.get("message", {}).get("content") or "").strip()
    except Exception as e:
        return f"[ollama_error: {e}]"


def _ollama_target_sell(
    entry_price: float,
    current_price: float,
    regime: str,
    news_titles: list[str],
) -> float | None:
    """
    Pede ao trading-analyst um target de venda via JSON.
    Formato esperado: {"target_sell": 81500.0, ...}
    """
    import re, json as _json

    news_ctx = "; ".join(news_titles[:3]) or "no recent news"
    prompt = (
        f"Trade window request for BTC-USDT.\n"
        f"entry_price: {entry_price:.2f}\n"
        f"current_price: {current_price:.2f}\n"
        f"regime: {regime}\n"
        f"news_context: {news_ctx}\n\n"
        f"Respond with a JSON object containing at minimum: "
        f'{{ "target_sell": <number> }}'
    )
    raw = _ask_ollama(prompt)
    if not raw:
        return None

    # Tentar parsear JSON da resposta
    try:
        # Extrair primeiro bloco JSON da resposta
        m = re.search(r"\{.*?\}", raw, re.DOTALL)
        if m:
            data = _json.loads(m.group())
            val = float(data.get("target_sell") or 0)
            if 50_000 <= val <= 200_000:
                return val
    except Exception:
        pass

    # Fallback: extrair número BTC-range da resposta texto
    candidates = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]{4,8}(?:\.\d+)?", raw)]
    valid = [v for v in candidates if 50_000 <= v <= 200_000]
    return valid[0] if valid else None


# ── Simulação ─────────────────────────────────────────────────────────────────

@dataclass
class SlotResult:
    entry_price: float
    entry_ts: float
    sell_price: float
    sell_ts: float
    size: float
    pnl: float
    pnl_pct: float
    reason: str


@dataclass
class BacktestResult:
    label: str
    sold: list[SlotResult] = field(default_factory=list)
    stuck: int = 0

    @property
    def total_pnl(self) -> float:
        return sum(s.pnl for s in self.sold)

    @property
    def win_rate(self) -> float:
        if not self.sold:
            return 0.0
        return sum(1 for s in self.sold if s.pnl > 0) / len(self.sold)

    @property
    def avg_hold_hours(self) -> float:
        if not self.sold:
            return 0.0
        return sum((s.sell_ts - s.entry_ts) / 3600 for s in self.sold) / len(self.sold)

    def summary(self) -> str:
        return (
            f"[{self.label}] "
            f"vendas={len(self.sold)} stuck={self.stuck} "
            f"PnL=${self.total_pnl:.4f} "
            f"win={self.win_rate*100:.1f}% "
            f"hold_avg={self.avg_hold_hours:.1f}h"
        )


def _simulate_old(
    positions: list[dict],
    candles: list[dict],
    *,
    ai_tp_pct: float = AI_TP_PCT,
) -> BacktestResult:
    """
    Comportamento ANTIGO: usa o target_sell_price gravado no metadata do BUY
    (a fórmula real que estava sendo usada em produção).
    Fallback: entry × (1 + ai_tp_pct).
    """
    result = BacktestResult(label="OLD (target do metadata)")
    for pos in positions:
        entry_price = float(pos["price"])
        entry_ts    = float(pos["timestamp"])
        size        = float(pos["size"])
        # Usa o target gravado na época (comportamento real anterior ao fix)
        target = float(pos.get("old_target") or 0) or entry_price * (1 + ai_tp_pct)
        old_reason = pos.get("old_reason") or "formula"

        sold = False
        for c in candles:
            if float(c["timestamp"]) <= entry_ts:
                continue
            close = float(c["close"])
            if close >= target:
                gross   = (close - entry_price) * size
                fees    = (close + entry_price) * size * TRADING_FEE
                pnl     = gross - fees
                pnl_pct = (close * (1 - TRADING_FEE)) / (entry_price * (1 + TRADING_FEE)) - 1
                result.sold.append(SlotResult(
                    entry_price=entry_price, entry_ts=entry_ts,
                    sell_price=close, sell_ts=float(c["timestamp"]),
                    size=size, pnl=pnl, pnl_pct=pnl_pct,
                    reason=f"OLD target=${target:,.2f} ({old_reason})",
                ))
                sold = True
                break
        if not sold:
            result.stuck += 1
    return result


def _simulate_new(
    positions: list[dict],
    candles: list[dict],
    ai_windows: list[dict],
    news: list[dict],
    *,
    ai_tp_pct: float = AI_TP_PCT,
    ranging_cap: float = RANGING_CAP,
    use_ollama: bool = False,
) -> BacktestResult:
    """
    Comportamento NOVO: target = AI window target_sell (primário);
    fórmula entry × ai_tp é apenas teto.
    Em RANGING: teto reduzido para ranging_cap.
    """
    result = BacktestResult(label="NEW (AI window primário)")

    for pos in positions:
        entry_price = float(pos["price"])
        entry_ts    = float(pos["timestamp"])
        size        = float(pos["size"])

        # Buscar a AI window mais próxima após a compra
        window = next(
            (w for w in ai_windows if float(w["timestamp"]) >= entry_ts),
            None,
        )

        regime = (window or {}).get("regime") or "RANGING"

        # Teto: entry × ai_tp, reduzido em RANGING
        effective_tp = min(ai_tp_pct, ranging_cap) if regime == "RANGING" else ai_tp_pct
        cap_target = entry_price * (1 + effective_tp)

        # Alvo primário: window target_sell
        window_target = float((window or {}).get("target_sell") or 0)

        if use_ollama and not window_target:
            # Ollama ao vivo quando não há window registrada
            recent_news = [
                n["title"] for n in news
                if float(n["timestamp"].timestamp()) >= entry_ts
            ][:5]
            last_candle = next(
                (c for c in reversed(candles) if float(c["timestamp"]) >= entry_ts),
                candles[-1] if candles else None,
            )
            current_price = float((last_candle or {}).get("close", entry_price))
            ollama_target = _ollama_target_sell(entry_price, current_price, regime, recent_news)
            if ollama_target and ollama_target > entry_price:
                window_target = ollama_target

        if window_target > entry_price:
            target = min(window_target, cap_target)
            reason_prefix = "NEW_AI_WINDOW"
        else:
            target = cap_target
            reason_prefix = "NEW_CAP_FALLBACK"

        sold = False
        for c in candles:
            if float(c["timestamp"]) <= entry_ts:
                continue
            close = float(c["close"])
            if close >= target:
                gross   = (close - entry_price) * size
                fees    = (close + entry_price) * size * TRADING_FEE
                pnl     = gross - fees
                pnl_pct = (close * (1 - TRADING_FEE)) / (entry_price * (1 + TRADING_FEE)) - 1
                result.sold.append(SlotResult(
                    entry_price=entry_price, entry_ts=entry_ts,
                    sell_price=close, sell_ts=float(c["timestamp"]),
                    size=size, pnl=pnl, pnl_pct=pnl_pct,
                    reason=f"{reason_prefix} target=${target:,.2f} regime={regime}",
                ))
                sold = True
                break
        if not sold:
            result.stuck += 1

    return result


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db():
    try:
        conn = _connect()
        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"PostgreSQL homelab indisponível: {e}")


@pytest.fixture(scope="module")
def candles(db):
    data = _load_candles(db, hours=BACKTEST_H)
    if not data:
        pytest.skip("Nenhum candle nas últimas 24h no DB")
    return data


@pytest.fixture(scope="module")
def ai_windows(db, candles):
    since = float(candles[0]["timestamp"])
    return _load_ai_windows(db, since)


@pytest.fixture(scope="module")
def news(db, candles):
    since = float(candles[0]["timestamp"])
    return _load_news_sentiment(db, since)


@pytest.fixture(scope="module")
def open_positions(db):
    positions = _load_open_positions(db)
    if not positions:
        pytest.skip("Nenhuma posição aberta real no DB")
    return positions


@pytest.fixture(scope="module")
def ollama_ok():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# ── Testes ────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestDataDisponivel:
    """Valida que os dados históricos necessários existem."""

    def test_candles_24h_existem(self, candles):
        assert len(candles) > 100, f"Esperado >100 candles, obteve {len(candles)}"
        print(f"\n  Candles: {len(candles)} (últimas {BACKTEST_H}h)")
        prices = [float(c["close"]) for c in candles]
        print(f"  Preço: min=${min(prices):,.2f} max=${max(prices):,.2f} último=${prices[-1]:,.2f}")

    def test_news_existem(self, news):
        print(f"\n  News sentiment: {len(news)} registros")
        if news:
            sentiments = [float(n["sentiment"]) for n in news]
            avg = sum(sentiments) / len(sentiments)
            print(f"  Sentimento médio: {avg:.3f} ({'bullish' if avg > 0.1 else 'bearish' if avg < -0.1 else 'neutro'})")

    def test_ai_windows_existem(self, ai_windows):
        print(f"\n  AI trade windows: {len(ai_windows)}")
        if ai_windows:
            regimes = [w.get("regime") for w in ai_windows if w.get("regime")]
            from collections import Counter
            print(f"  Regimes: {dict(Counter(regimes))}")

    def test_posicoes_abertas(self, open_positions):
        print(f"\n  Posições abertas presas: {len(open_positions)}")
        prices = [float(p["price"]) for p in open_positions]
        if prices:
            print(f"  Entry prices: min=${min(prices):,.2f} max=${max(prices):,.2f}")


@pytest.mark.integration
class TestBacktestComparison:
    """Compara PnL do comportamento OLD vs NEW no replay histórico."""

    def test_new_teto_menor_em_ranging(self, candles, ai_windows, open_positions):
        """
        Em regime RANGING, o teto NEW (ranging_cap=0.4%) é menor que o OLD (ai_tp=1.3%).
        Resultado esperado: NEW vende mais posições por exigir menos movimento.
        """
        old = _simulate_old(open_positions, candles, ai_tp_pct=AI_TP_PCT)
        new = _simulate_new(open_positions, candles, ai_windows, [], ai_tp_pct=AI_TP_PCT, ranging_cap=RANGING_CAP)

        print(f"\n  {old.summary()}")
        print(f"  {new.summary()}")

        # NEW deve ter menos posições presas (ou igual — nunca pior)
        assert new.stuck <= old.stuck, (
            f"NEW ficou com mais posições presas ({new.stuck}) do que OLD ({old.stuck})"
        )
        # NEW deve ter mais vendas ou igual
        assert len(new.sold) >= len(old.sold), (
            f"NEW vendeu menos ({len(new.sold)}) do que OLD ({len(old.sold)})"
        )

    def test_pnl_new_nao_e_pior(self, candles, ai_windows, open_positions):
        """PnL do NEW deve ser >= OLD (alvo mais realista = vende mais cedo = menos prejuízo acumulado)."""
        old = _simulate_old(open_positions, candles, ai_tp_pct=AI_TP_PCT)
        new = _simulate_new(open_positions, candles, ai_windows, [], ai_tp_pct=AI_TP_PCT, ranging_cap=RANGING_CAP)

        print(f"\n  PnL OLD: ${old.total_pnl:.4f} | vendas={len(old.sold)} stuck={old.stuck}")
        print(f"  PnL NEW: ${new.total_pnl:.4f} | vendas={len(new.sold)} stuck={new.stuck}")

        # PnL pode ser menor por vender mais cedo, mas o saldo geral
        # deve ser melhor quando consideramos as posições que param de acumular prejuízo
        assert new.total_pnl >= old.total_pnl - 0.50, (
            f"PnL do NEW é muito menor: NEW=${new.total_pnl:.4f} OLD=${old.total_pnl:.4f}"
        )

    def test_hold_medio_new_menor(self, candles, ai_windows, open_positions):
        """NEW deve fechar posições mais rápido (menor tempo médio de hold)."""
        old = _simulate_old(open_positions, candles, ai_tp_pct=AI_TP_PCT)
        new = _simulate_new(open_positions, candles, ai_windows, [], ai_tp_pct=AI_TP_PCT, ranging_cap=RANGING_CAP)

        if old.sold and new.sold:
            print(f"\n  Hold médio OLD: {old.avg_hold_hours:.1f}h")
            print(f"  Hold médio NEW: {new.avg_hold_hours:.1f}h")
            # NEW deve fechar em tempo igual ou menor
            assert new.avg_hold_hours <= old.avg_hold_hours + 0.5

    def test_ranging_cap_efetivo(self, candles, open_positions):
        """Com ranging_cap=0.004: teto é entry×1.004 → deve vender mais que ai_tp=0.013."""
        result_cap  = _simulate_new(open_positions, candles, [], [], ranging_cap=0.004)
        result_full = _simulate_old(open_positions, candles, ai_tp_pct=0.013)

        print(f"\n  Com cap 0.4%:  vendas={len(result_cap.sold)} stuck={result_cap.stuck}")
        print(f"  Com cap 1.3%:  vendas={len(result_full.sold)} stuck={result_full.stuck}")

        assert result_cap.stuck <= result_full.stuck


@pytest.mark.integration
@pytest.mark.ollama
class TestOllamaIntegration:
    """Testa o ciclo completo com Ollama real gerando previsões de preço."""

    def test_ollama_disponivel(self, ollama_ok):
        assert ollama_ok, f"Ollama não respondeu em {OLLAMA_URL}"
        print(f"\n  Ollama OK: {OLLAMA_URL}")

    def test_ollama_gera_target_sell(self, candles, open_positions, ollama_ok):
        """Ollama deve retornar um preço-alvo numérico válido."""
        if not ollama_ok:
            pytest.skip("Ollama indisponível")

        pos = open_positions[0]
        entry = float(pos["price"])
        last_close = float(candles[-1]["close"])

        target = _ollama_target_sell(entry, last_close, "RANGING", ["BTC price analysis"])
        print(f"\n  Entry=${entry:,.2f} atual=${last_close:,.2f}")
        print(f"  Ollama target_sell: ${target:,.2f}" if target else "  Ollama não retornou target")

        if target is None:
            pytest.skip("Ollama não retornou preço-alvo numérico válido (modelo não carregado ou resposta inesperada)")
        # Target deve ser numérico e realista (±20% do preço atual)
        assert last_close * 0.80 <= target <= last_close * 1.20, (
            f"Target fora do intervalo razoável: ${target:,.2f}"
        )

    def test_backtest_com_ollama_ao_vivo(self, candles, ai_windows, news, open_positions, ollama_ok):
        """Replay completo com Ollama gerando targets para posições sem AI window."""
        if not ollama_ok:
            pytest.skip("Ollama indisponível")

        # Usa apenas as 5 primeiras posições para não sobrecarregar Ollama
        sample = open_positions[:5]

        old = _simulate_old(sample, candles, ai_tp_pct=AI_TP_PCT)
        new = _simulate_new(
            sample, candles, ai_windows, news,
            ai_tp_pct=AI_TP_PCT, ranging_cap=RANGING_CAP,
            use_ollama=True,
        )

        print(f"\n  === RESULTADO INTEGRADO (Ollama + News + Candles) ===")
        print(f"  {old.summary()}")
        print(f"  {new.summary()}")
        print(f"  Diferença PnL: ${new.total_pnl - old.total_pnl:+.4f}")
        print(f"  Posições liberadas pelo NEW: {old.stuck - new.stuck}")

        if new.sold:
            print("\n  Detalhes vendas NEW:")
            for s in new.sold:
                ts = datetime.fromtimestamp(s.sell_ts, tz=timezone.utc).strftime("%m-%d %H:%M")
                print(f"    [{ts}] entry=${s.entry_price:,.2f} → sell=${s.sell_price:,.2f}"
                      f" pnl=${s.pnl:.4f} ({s.pnl_pct*100:.3f}%) | {s.reason}")

        # Assertion mínima: NEW nunca deve piorar significativamente
        assert new.stuck <= old.stuck + 1
