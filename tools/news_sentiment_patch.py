#!/usr/bin/env python3
"""
Patch para integrar sinal de news sentiment no fast_model.py.
Adiciona o 5º fator ao ensemble: notícias cripto via RSS/Ollama.

Deve ser executado via SSH no homelab: python3 /tmp/news_sentiment_patch.py

Componentes:
  PATCH 18: Import psycopg2 + _news_sentiment_signal() method
  PATCH 19: Integrar na predict() como 5º fator do ensemble
"""

import sys
from pathlib import Path

FAST_MODEL_PATH = Path("/apps/crypto-trader/trading/btc_trading_agent/fast_model.py")


def read_file(path: Path) -> str:
    """Lê conteúdo do arquivo."""
    return path.read_text()


def write_file(path: Path, content: str) -> None:
    """Escreve conteúdo no arquivo com backup."""
    backup = path.with_suffix('.py.bak_news')
    if not backup.exists():
        import shutil
        shutil.copy2(path, backup)
    path.write_text(content)


def apply_news_sentiment_patch() -> int:
    """Aplica patches de news sentiment no fast_model.py."""
    code = read_file(FAST_MODEL_PATH)
    original = code
    patches: list[str] = []

    # ========== PATCH 18a: Adicionar imports necessários ==========
    old_imports = """import numpy as np
import time
import json
import pickle
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import deque"""

    new_imports = """import numpy as np
import time
import json
import pickle
import logging
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import deque

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False"""

    if old_imports in code:
        code = code.replace(old_imports, new_imports, 1)
        patches.append("P18a: Added psycopg2 + os imports")
    elif "HAS_PSYCOPG2" in code:
        patches.append("P18a: SKIP (already applied)")
    else:
        print("⚠️ P18a: Import block not found!")

    # ========== PATCH 18b: Adicionar _news_db_url e cache no __init__ ==========
    old_init_end = """        # Carregar modelo se existir
        model_path = MODEL_DIR / f"qmodel_{symbol.replace('-', '_')}.pkl"
        if model_path.exists():
            self.q_model.load(model_path)"""

    new_init_end = """        # News sentiment — 5º fator do ensemble (peso dinâmico 0-20%)
        self._news_db_url: str = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/postgres"
        )
        self._news_cache: Optional[Tuple[float, float, float]] = None  # (ts, score, weight)
        self._news_cache_ttl: float = 60.0  # Cache 60s (notícias mudam devagar)

        # Carregar modelo se existir
        model_path = MODEL_DIR / f"qmodel_{symbol.replace('-', '_')}.pkl"
        if model_path.exists():
            self.q_model.load(model_path)"""

    if old_init_end in code:
        code = code.replace(old_init_end, new_init_end, 1)
        patches.append("P18b: Added _news_db_url, cache vars to __init__")
    elif "_news_db_url" in code:
        patches.append("P18b: SKIP (already applied)")
    else:
        print("⚠️ P18b: __init__ end block not found!")

    # ========== PATCH 18c: Método _news_sentiment_signal() ==========
    # Inserir ANTES de def _check_flip_flop
    old_flip_flop = """    def _check_flip_flop(self, action: str) -> bool:"""

    new_method_plus_flip = """    def _news_sentiment_signal(self) -> Tuple[float, float, str]:
        \"\"\"Obtém sinal de sentimento de notícias cripto (5º fator do ensemble).

        Consulta btc.news_sentiment (janela 4h), calcula score ponderado por
        confiança e recência. Peso dinâmico de 0-20% baseado na confiança
        média e quantidade de artigos.

        Returns:
            Tuple[score, weight, reason]:
              - score: -1.0 (bearish) a +1.0 (bullish)
              - weight: 0.0 a 0.20 (peso sugerido no ensemble)
              - reason: descrição textual
        \"\"\"
        # Verificar cache (notícias são lentas, não precisa consultar a cada tick)
        now = time.time()
        if self._news_cache is not None:
            cache_ts, cached_score, cached_weight = self._news_cache
            if now - cache_ts < self._news_cache_ttl:
                direction = "bullish" if cached_score > 0.1 else "bearish" if cached_score < -0.1 else "neutral"
                return cached_score, cached_weight, f"news:{direction}(cached)"

        if not HAS_PSYCOPG2:
            return 0.0, 0.0, "news:unavailable"

        try:
            conn = psycopg2.connect(self._news_db_url, connect_timeout=3)
            conn.autocommit = True
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Buscar artigos das últimas 4 horas para BTC e GENERAL
            cur.execute(\"\"\"
                SELECT sentiment::float, confidence::float, category,
                       EXTRACT(EPOCH FROM (NOW() - timestamp))::float / 3600.0 AS hours_ago
                FROM btc.news_sentiment
                WHERE coin IN ('BTC', 'GENERAL')
                  AND timestamp > NOW() - INTERVAL '4 hours'
                  AND confidence >= 0.5
                ORDER BY timestamp DESC
                LIMIT 50
            \"\"\")
            rows = cur.fetchall()
            cur.close()
            conn.close()

            if not rows:
                self._news_cache = (now, 0.0, 0.0)
                return 0.0, 0.0, "news:no_recent"

            # Score ponderado por confiança e recência
            total_weight = 0.0
            weighted_sum = 0.0
            total_conf = 0.0

            for row in rows:
                hours = row["hours_ago"] if row["hours_ago"] else 0.0
                # Decaimento: artigos mais recentes pesam mais
                recency = max(0.1, 1.0 - hours / 4.0)
                conf = row["confidence"]
                w = conf * recency
                weighted_sum += row["sentiment"] * w
                total_weight += w
                total_conf += conf

            if total_weight < 0.01:
                self._news_cache = (now, 0.0, 0.0)
                return 0.0, 0.0, "news:low_weight"

            score = weighted_sum / total_weight  # -1 a +1
            avg_conf = total_conf / len(rows)
            n_articles = len(rows)

            # Peso dinâmico: 0-20% baseado em confiança e quantidade
            # Mais artigos + maior confiança = mais peso
            quantity_factor = min(n_articles / 10.0, 1.0)  # satura em 10 artigos
            confidence_factor = avg_conf  # 0.5-1.0
            weight = 0.20 * quantity_factor * confidence_factor
            weight = max(0.0, min(weight, 0.20))

            # Categorias com peso extra: 'regulation' e 'hack'
            categories = [r["category"] for r in rows if r.get("category")]
            if "hack" in categories or "regulation" in categories:
                weight = min(weight * 1.5, 0.20)

            direction = "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral"
            reason = f"news:{direction}({n_articles}art,w={weight:.0%})"

            # Atualizar cache
            self._news_cache = (now, score, weight)
            logger.info(
                f"📰 News sentiment: score={score:+.2f} weight={weight:.1%} "
                f"articles={n_articles} avg_conf={avg_conf:.2f}"
            )
            return score, weight, reason

        except Exception as e:
            logger.warning(f"📰 News sentiment error: {e}")
            # Em caso de erro, retornar neutro sem peso
            self._news_cache = (now, 0.0, 0.0)
            return 0.0, 0.0, "news:error"

    def _check_flip_flop(self, action: str) -> bool:"""

    if "_news_sentiment_signal" not in code and old_flip_flop in code:
        code = code.replace(old_flip_flop, new_method_plus_flip, 1)
        patches.append("P18c: Added _news_sentiment_signal() method")
    elif "_news_sentiment_signal" in code:
        patches.append("P18c: SKIP (already applied)")
    else:
        print("⚠️ P18c: _check_flip_flop not found!")

    # ========== PATCH 19a: Integrar no predict() — chamar _news_sentiment_signal ==========
    old_ensemble_calc = """        # Q-Learning decision
        q_action = self.q_model.choose_action(features, explore=explore)
        q_confidence = self.q_model.get_confidence(features)
        q_score = (q_action - 1)  # -1 (SELL), 0 (HOLD), 1 (BUY)
        
        # ===== ENSEMBLE COM PESOS DINÂMICOS POR REGIME (com override RAG) =====
        vol = state.volatility
        weights = self.weights.copy()"""

    new_ensemble_calc = """        # Q-Learning decision
        q_action = self.q_model.choose_action(features, explore=explore)
        q_confidence = self.q_model.get_confidence(features)
        q_score = (q_action - 1)  # -1 (SELL), 0 (HOLD), 1 (BUY)

        # News sentiment — 5º fator do ensemble
        news_score, news_weight, news_reason = self._news_sentiment_signal()
        
        # ===== ENSEMBLE COM PESOS DINÂMICOS POR REGIME (com override RAG) =====
        vol = state.volatility
        weights = self.weights.copy()"""

    if old_ensemble_calc in code:
        code = code.replace(old_ensemble_calc, new_ensemble_calc, 1)
        patches.append("P19a: Added news signal call in predict()")
    elif "news_score, news_weight, news_reason" in code:
        patches.append("P19a: SKIP (already applied)")
    else:
        print("⚠️ P19a: Ensemble calc block not found!")

    # ========== PATCH 19b: Modificar cálculo do final_score ==========
    old_final_score = """        final_score = (
            tech_score * weights["technical"] +
            ob_score * weights["orderbook"] +
            flow_score * weights["flow"] +
            q_score * weights["qlearning"]
        )"""

    new_final_score = """        # Ajustar pesos existentes para acomodar news_weight (proporcional)
        if news_weight > 0:
            scale = 1.0 - news_weight
            for k in weights:
                weights[k] *= scale
            weights["news"] = news_weight
        else:
            weights["news"] = 0.0

        final_score = (
            tech_score * weights["technical"] +
            ob_score * weights["orderbook"] +
            flow_score * weights["flow"] +
            q_score * weights["qlearning"] +
            news_score * weights["news"]
        )"""

    if old_final_score in code:
        code = code.replace(old_final_score, new_final_score, 1)
        patches.append("P19b: Added news to final_score with dynamic weight")
    elif 'news_score * weights["news"]' in code:
        patches.append("P19b: SKIP (already applied)")
    else:
        print("⚠️ P19b: final_score block not found!")

    # ========== PATCH 19c: Adicionar news_reason ao reason do Signal ==========
    old_reasons = """        # Montar razão
        reasons = []
        if regime.regime != "RANGING":
            reasons.append(f"[{regime.regime}]")
        if tech_reason != "neutral":
            reasons.append(tech_reason)
        if "pressure" in ob_reason:
            reasons.append(ob_reason)
        if "pressure" in flow_reason:
            reasons.append(flow_reason)"""

    new_reasons = """        # Montar razão
        reasons = []
        if regime.regime != "RANGING":
            reasons.append(f"[{regime.regime}]")
        if tech_reason != "neutral":
            reasons.append(tech_reason)
        if "pressure" in ob_reason:
            reasons.append(ob_reason)
        if "pressure" in flow_reason:
            reasons.append(flow_reason)
        if news_weight > 0 and abs(news_score) > 0.1:
            reasons.append(news_reason)"""

    if old_reasons in code:
        code = code.replace(old_reasons, new_reasons, 1)
        patches.append("P19c: Added news_reason to Signal.reason")
    elif "news_reason" in code and "reasons.append(news_reason)" in code:
        patches.append("P19c: SKIP (already applied)")
    else:
        print("⚠️ P19c: Reasons block not found!")

    # ========== PATCH 19d: Adicionar news_score aos features do Signal ==========
    old_features = """                "technical_score": tech_score,
                "orderbook_score": ob_score,
                "flow_score": flow_score,
                "q_score": q_score,"""

    new_features = """                "technical_score": tech_score,
                "orderbook_score": ob_score,
                "flow_score": flow_score,
                "q_score": q_score,
                "news_score": news_score,
                "news_weight": news_weight,"""

    if old_features in code:
        code = code.replace(old_features, new_features, 1)
        patches.append("P19d: Added news_score/news_weight to Signal.features")
    elif '"news_score": news_score' in code:
        patches.append("P19d: SKIP (already applied)")
    else:
        print("⚠️ P19d: Features block not found!")

    # ========== Aplicar ==========
    if code != original:
        write_file(FAST_MODEL_PATH, code)
        print(f"\n✅ fast_model.py: {len(patches)} patches applied:")
        for p in patches:
            print(f"  ✔ {p}")
    else:
        print("⚠️ fast_model.py: No changes made!")
        for p in patches:
            print(f"  ℹ {p}")

    return len(patches)


if __name__ == "__main__":
    print("=" * 60)
    print("📰 NEWS SENTIMENT PATCH: Trading Agent Integration")
    print("=" * 60)

    total = apply_news_sentiment_patch()

    print(f"\n{'=' * 60}")
    print(f"📊 Total: {total} patches processed")
    print("=" * 60)

    # Validation
    print("\n🔍 Syntax validation...")
    import subprocess
    result = subprocess.run(
        ["python3", "-c",
         f"import ast; ast.parse(open('{FAST_MODEL_PATH}').read()); print('  ✅ fast_model.py: OK')"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(f"  ❌ fast_model.py: SYNTAX ERROR")
        print(result.stderr)
        sys.exit(1)
