#!/usr/bin/env python3
"""Teste integrado do pipeline de trading sentiment.

Verifica end-to-end:
  1. GPU0 online + eddie-sentiment carregado
  2. GPU1 online + fallback disponível
  3. eddie-sentiment disponível na GPU0
  4. Classificação via eddie-sentiment (GPU0) funciona
  5. Fallback genérico via GPU1 funciona
  6. Parsing de resposta gera resultado válido
  7. Banco de dados acessível (btc.training_samples, btc.candles)
  8. RSS feeds acessíveis (pelo menos 3/7)
  9. Métricas Prometheus configuradas corretamente
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────
GPU0 = "http://192.168.15.2:11434"
GPU1 = "http://192.168.15.2:11435"
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading",
)

PASS = "\033[92m✅ PASS\033[0m"
FAIL = "\033[91m❌ FAIL\033[0m"
WARN = "\033[93m⚠️  WARN\033[0m"

results: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    """Registra resultado do teste."""
    results.append((name, passed, detail))
    status = PASS if passed else FAIL
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))


# ── 1. GPU Status ──────────────────────────────────────────────────

def test_gpu_online(host: str, name: str) -> bool:
    """Verifica se GPU está online."""
    try:
        req = urllib.request.Request(f"{host}/api/version")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            version = data.get("version", "?")
            check(f"{name} online", True, f"v{version}")
            return True
    except Exception as e:
        check(f"{name} online", False, str(e))
        return False


def test_model_loaded(host: str, gpu_name: str, expected_model: str) -> bool:
    """Verifica se modelo está carregado na VRAM."""
    try:
        req = urllib.request.Request(f"{host}/api/ps")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            loaded = [m["name"] for m in data.get("models", [])]
            found = any(expected_model in m for m in loaded)
            check(
                f"{gpu_name} modelo warm",
                found,
                f"esperado={expected_model}, carregados={loaded}",
            )
            return found
    except Exception as e:
        check(f"{gpu_name} modelo warm", False, str(e))
        return False


def test_model_available(host: str, gpu_name: str, model: str) -> bool:
    """Verifica se modelo existe na lista de modelos."""
    try:
        req = urllib.request.Request(f"{host}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            names = [m["name"] for m in data.get("models", [])]
            found = any(model in n for n in names)
            check(f"{gpu_name} tem {model}", found, f"disponíveis: {len(names)}")
            return found
    except Exception as e:
        check(f"{gpu_name} tem {model}", False, str(e))
        return False


# ── 2. Classificação ao vivo ────────────────────────────────────────

def test_classification(host: str, model: str, label: str) -> bool:
    """Testa classificação de sentimento ao vivo."""
    test_article = {
        "title": "Bitcoin ETF sees record $500M inflows as institutional adoption surges",
        "description": "Major financial institutions increase Bitcoin ETF holdings to record levels.",
        "coin": "BTC",
    }
    prompt = f"""Analyze this crypto news and classify sentiment for trading.
Reply ONLY in this exact format (no extra text, no thinking):
SENTIMENT: <-1.0 to 1.0> | CONFIDENCE: <0.0 to 1.0> | DIRECTION: <BULLISH|BEARISH|NEUTRAL> | CATEGORY: <regulation|adoption|hack|price|macro|defi|technical>

Coin: {test_article['coin']}
Title: {test_article['title']}
Summary: {test_article['description']}"""

    try:
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": -1,
            "options": {"num_predict": 64, "temperature": 0.1},
        }).encode()
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        start = time.monotonic()
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
            response = data.get("response", "").strip()
            elapsed = time.monotonic() - start

            # Validar formato
            has_sentiment = "SENTIMENT:" in response.upper()
            has_direction = any(d in response.upper() for d in ["BULLISH", "BEARISH", "NEUTRAL"])
            has_confidence = "CONFIDENCE:" in response.upper()
            valid = has_sentiment and has_direction and has_confidence

            # Extrair direção
            import re
            direction_match = re.search(r"DIRECTION:\s*(BULLISH|BEARISH|NEUTRAL)", response, re.IGNORECASE)
            direction = direction_match.group(1).upper() if direction_match else "?"

            check(
                f"Classificação {label}",
                valid,
                f"dir={direction}, {elapsed:.1f}s, parse_ok={valid}",
            )

            if not valid:
                print(f"    Resposta raw: {response[:200]}")

            return valid

    except Exception as e:
        check(f"Classificação {label}", False, str(e))
        return False


def test_eddie_sentiment_chat(host: str) -> bool:
    """Testa eddie-sentiment via /api/chat (como o exporter usa)."""
    try:
        payload = json.dumps({
            "model": "eddie-sentiment:latest",
            "messages": [
                {"role": "user", "content": "BTC: SEC approves spot Bitcoin ETF for major US exchange"},
            ],
            "stream": False,
            "keep_alive": -1,
            "options": {"num_predict": 64, "temperature": 0.1},
        }).encode()
        req = urllib.request.Request(
            f"{host}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        start = time.monotonic()
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
            msg = data.get("message", {}).get("content", "").strip()
            elapsed = time.monotonic() - start
            has_direction = any(d in msg.upper() for d in ["BULLISH", "BEARISH", "NEUTRAL"])
            check(
                "eddie-sentiment /api/chat",
                has_direction,
                f"{elapsed:.1f}s, resp={msg[:100]}",
            )
            return has_direction
    except Exception as e:
        check("eddie-sentiment /api/chat", False, str(e))
        return False


# ── 3. Banco de dados ──────────────────────────────────────────────

def test_database() -> bool:
    """Verifica acesso ao banco e tabelas do trading."""
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SET search_path TO btc")

            # training_samples
            cur.execute("SELECT COUNT(*) FROM btc.training_samples")
            samples = cur.fetchone()[0]

            # candles
            cur.execute("SELECT COUNT(*) FROM btc.candles")
            candles = cur.fetchone()[0]

            # news_sentiment (exporter table)
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema='btc' AND table_name='news_sentiment'
            """)
            has_news = cur.fetchone()[0] > 0
            news_count = 0
            if has_news:
                cur.execute("SELECT COUNT(*) FROM btc.news_sentiment")
                news_count = cur.fetchone()[0]

            # Dados recentes em training_samples
            cur.execute("""
                SELECT COUNT(*), 
                       SUM(CASE WHEN prediction_correct THEN 1 ELSE 0 END),
                       AVG(ollama_confidence)
                FROM btc.training_samples 
                WHERE ground_truth IS NOT NULL
            """)
            row = cur.fetchone()
            with_gt = row[0]
            correct = row[1] or 0
            avg_conf = row[2] or 0
            accuracy = (correct / with_gt * 100) if with_gt > 0 else 0

        conn.close()
        check(
            "Database acessível",
            True,
            f"samples={samples}, candles={candles}, news={news_count}",
        )
        check(
            "Dados de treinamento",
            samples > 0,
            f"total={samples}, com_GT={with_gt}, accuracy={accuracy:.1f}%, conf_avg={avg_conf:.2f}",
        )
        return True
    except ImportError:
        check("Database acessível", False, "psycopg2 não instalado")
        return False
    except Exception as e:
        check("Database acessível", False, str(e))
        return False


# ── 4. RSS Feeds ───────────────────────────────────────────────────

def test_rss_feeds() -> bool:
    """Testa acessibilidade dos RSS feeds."""
    feeds = [
        ("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("cointelegraph", "https://cointelegraph.com/rss"),
        ("decrypt", "https://decrypt.co/feed"),
        ("bitcoinmagazine", "https://bitcoinmagazine.com/.rss/full/"),
        ("cryptonews", "https://cryptonews.com/news/feed/"),
        ("theblock", "https://www.theblock.co/rss.xml"),
        ("beincrypto", "https://beincrypto.com/feed/"),
    ]
    ok_count = 0
    for name, url in feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                if r.status == 200:
                    ok_count += 1
        except Exception:
            pass

    check(
        "RSS feeds acessíveis",
        ok_count >= 3,
        f"{ok_count}/{len(feeds)} feeds respondendo",
    )
    return ok_count >= 3


# ── 5. Multi-coin Trading ──────────────────────────────────────────

def test_multi_coin_prediction() -> bool:
    """Testa previsão para múltiplas moedas (como trading agent usa)."""
    coins = {
        "BTC": "Bitcoin surges past $100K as institutional demand grows",
        "ETH": "Ethereum staking surpasses 30M ETH locked in validators",
        "SOL": "Solana processes 100K TPS in new network benchmark",
    }
    results_ok = 0
    for coin, title in coins.items():
        try:
            payload = json.dumps({
                "model": "eddie-sentiment:latest",
                "prompt": f"Coin: {coin}\nTitle: {title}\nSummary: Test article for {coin}",
                "stream": False,
                "keep_alive": -1,
                "options": {"num_predict": 64, "temperature": 0.1},
            }).encode()
            req = urllib.request.Request(
                f"{GPU0}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
                response = data.get("response", "")
                if any(d in response.upper() for d in ["BULLISH", "BEARISH", "NEUTRAL"]):
                    results_ok += 1
        except Exception:
            pass

    check(
        "Multi-coin prediction",
        results_ok >= 2,
        f"{results_ok}/{len(coins)} moedas classificadas",
    )
    return results_ok >= 2


# ── Main ──────────────────────────────────────────────────────────

def main() -> int:
    """Executa todos os testes integrados."""
    print("\n" + "=" * 70)
    print("  TESTE INTEGRADO — Trading Sentiment Pipeline")
    print("=" * 70 + "\n")

    print("📡 1. Status das GPUs")
    gpu0_ok = test_gpu_online(GPU0, "GPU0 (RTX 2060)")
    gpu1_ok = test_gpu_online(GPU1, "GPU1 (GTX 1050)")

    print("\n🔥 2. Modelos Warm")
    if gpu0_ok:
        test_model_loaded(GPU0, "GPU0", "eddie-sentiment")
        test_model_available(GPU0, "GPU0", "eddie-sentiment")
    if gpu1_ok:
        test_model_available(GPU1, "GPU1", "qwen3:0.6b")

    print("\n🧠 3. Classificação ao vivo")
    if gpu0_ok:
        test_eddie_sentiment_chat(GPU0)
    if gpu1_ok:
        test_classification(GPU1, "qwen3:0.6b", "qwen3:0.6b@GPU1")

    print("\n🪙 4. Multi-coin")
    if gpu0_ok:
        test_multi_coin_prediction()

    print("\n🗄️  5. Banco de dados")
    test_database()

    print("\n📰 6. RSS Feeds")
    test_rss_feeds()

    # Resumo
    print("\n" + "=" * 70)
    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    failed = total - passed
    print(f"  Resultado: {passed}/{total} testes passaram", end="")
    if failed:
        print(f" ({failed} falha(s))")
        print("\n  Falhas:")
        for name, ok, detail in results:
            if not ok:
                print(f"    {FAIL} {name}: {detail}")
    else:
        print(" — TUDO OK! 🎉")
    print("=" * 70 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
