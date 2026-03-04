"""
Token Economy Tracker
Rastreia economia de tokens entre Ollama LOCAL e APIs cloud.
Funciona de forma independente do bus — pode ser usado diretamente por qualquer agente
ou LLMClient, E também integrado ao bus para métricas centralizadas.

Uso direto (sem bus):
    from specialized_agents.token_economy import get_token_economy
    eco = get_token_economy()
    eco.record_ollama_call(prompt_tokens=150, completion_tokens=300, model="qwen2.5-coder:7b")
    print(eco.get_summary())

Via bus (automático no log_llm_call/log_llm_response):
    Já integrado — chamadas via bus atualizam o tracker automaticamente.
"""
import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

# Custo estimado por 1K tokens (USD) — referência março/2026
CLOUD_COSTS_PER_1K = {
    # OpenAI
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4.1": {"input": 0.002, "output": 0.008},
    "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
    "gpt-4.1-nano": {"input": 0.0001, "output": 0.0004},
    # Anthropic
    "claude-sonnet-4": {"input": 0.003, "output": 0.015},
    "claude-opus-4": {"input": 0.015, "output": 0.075},
    # Referência padrão (GPT-4.1 — modelo base gratuito mais usado)
    "default_cloud": {"input": 0.002, "output": 0.008},
}

# Custo de eletricidade Ollama por 1K tokens (estimado)
# RTX 2060 SUPER: ~125W durante inferência, ~31 tok/s → ~32s para 1K tokens
# Custo: 0.125kW * (32/3600)h * R$0.85/kWh = R$0.00094 ≈ $0.00016
# GTX 1050: ~60W, ~42 tok/s → ~24s para 1K tokens
# Custo: 0.060kW * (24/3600)h * R$0.85/kWh = R$0.00034 ≈ $0.00006
OLLAMA_COSTS_PER_1K = {
    "gpu0": 0.00016,  # RTX 2060 SUPER
    "gpu1": 0.00006,  # GTX 1050
    "default": 0.00016,
}

# Mapeamento de modelos Ollama para GPU
OLLAMA_MODEL_GPU = {
    "qwen2.5-coder:7b": "gpu0",
    "eddie-coder": "gpu0",
    "qwen2.5-coder:7b-cline": "gpu0",
    "qwen3:1.7b": "gpu1",
}


def _estimate_tokens(text: str) -> int:
    """Estima tokens a partir de texto (heurística: ~4 chars = 1 token)"""
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass
class LLMCallRecord:
    """Registro de uma chamada LLM"""
    timestamp: datetime
    source: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    provider: str  # "ollama_gpu0", "ollama_gpu1", "cloud"
    estimated_cloud_cost_usd: float  # quanto custaria na cloud
    actual_cost_usd: float  # custo real (eletricidade Ollama ou API cloud)
    savings_usd: float  # economia = cloud_cost - actual_cost


class TokenEconomyTracker:
    """
    Tracker singleton de economia de tokens.
    Funciona independente do bus — pode ser usado diretamente pelo LLMClient
    ou integrado ao bus de comunicação.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._records: List[LLMCallRecord] = []
        self._daily_stats: Dict[str, Dict[str, float]] = {}
        self._total_savings_usd: float = 0.0
        self._total_ollama_calls: int = 0
        self._total_cloud_calls: int = 0
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._start_time = datetime.now()

        # Persistência opcional
        self._data_dir = os.environ.get("DATA_DIR", "data")
        self._persist_path = Path(self._data_dir) / "token_economy.jsonl"

        self._initialized = True

    def record_ollama_call(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        model: str = "qwen2.5-coder:7b",
        source: str = "unknown",
        prompt_text: str = None,
        response_text: str = None,
        cloud_reference: str = "default_cloud",
    ) -> LLMCallRecord:
        """
        Registra uma chamada feita ao Ollama LOCAL e calcula economia vs cloud.

        Args:
            prompt_tokens: Tokens do prompt (ou estimados do texto)
            completion_tokens: Tokens da resposta (ou estimados do texto)
            model: Modelo Ollama usado
            source: Agente de origem
            prompt_text: Texto do prompt (para estimar tokens se não fornecidos)
            response_text: Texto da resposta (para estimar tokens se não fornecidos)
            cloud_reference: Modelo cloud para comparação de custo
        """
        # Estimar tokens se não fornecidos
        if prompt_tokens == 0 and prompt_text:
            prompt_tokens = _estimate_tokens(prompt_text)
        if completion_tokens == 0 and response_text:
            completion_tokens = _estimate_tokens(response_text)

        total_tokens = prompt_tokens + completion_tokens

        # Custo cloud estimado
        cloud_costs = CLOUD_COSTS_PER_1K.get(cloud_reference, CLOUD_COSTS_PER_1K["default_cloud"])
        cloud_cost = (prompt_tokens / 1000 * cloud_costs["input"]) + \
                     (completion_tokens / 1000 * cloud_costs["output"])

        # Custo real Ollama (eletricidade)
        gpu = OLLAMA_MODEL_GPU.get(model, "gpu0")
        ollama_cost_per_1k = OLLAMA_COSTS_PER_1K.get(gpu, OLLAMA_COSTS_PER_1K["default"])
        actual_cost = total_tokens / 1000 * ollama_cost_per_1k

        savings = cloud_cost - actual_cost

        record = LLMCallRecord(
            timestamp=datetime.now(),
            source=source,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            provider=f"ollama_{gpu}",
            estimated_cloud_cost_usd=cloud_cost,
            actual_cost_usd=actual_cost,
            savings_usd=savings,
        )

        self._records.append(record)
        self._total_savings_usd += savings
        self._total_ollama_calls += 1
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens

        # Estatísticas diárias
        day_key = record.timestamp.strftime("%Y-%m-%d")
        if day_key not in self._daily_stats:
            self._daily_stats[day_key] = {
                "ollama_calls": 0, "cloud_calls": 0,
                "savings_usd": 0.0, "cloud_cost_usd": 0.0,
                "actual_cost_usd": 0.0, "total_tokens": 0,
            }
        ds = self._daily_stats[day_key]
        ds["ollama_calls"] += 1
        ds["savings_usd"] += savings
        ds["cloud_cost_usd"] += cloud_cost
        ds["actual_cost_usd"] += actual_cost
        ds["total_tokens"] += total_tokens

        # Persistir de forma assíncrona
        self._persist_record(record)

        return record

    def record_cloud_call(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        model: str = "gpt-4.1",
        source: str = "unknown",
        prompt_text: str = None,
        response_text: str = None,
    ) -> LLMCallRecord:
        """Registra chamada que FOI para cloud (sem economia)"""
        if prompt_tokens == 0 and prompt_text:
            prompt_tokens = _estimate_tokens(prompt_text)
        if completion_tokens == 0 and response_text:
            completion_tokens = _estimate_tokens(response_text)

        total_tokens = prompt_tokens + completion_tokens
        cloud_costs = CLOUD_COSTS_PER_1K.get(model, CLOUD_COSTS_PER_1K["default_cloud"])
        cloud_cost = (prompt_tokens / 1000 * cloud_costs["input"]) + \
                     (completion_tokens / 1000 * cloud_costs["output"])

        record = LLMCallRecord(
            timestamp=datetime.now(),
            source=source,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            provider="cloud",
            estimated_cloud_cost_usd=cloud_cost,
            actual_cost_usd=cloud_cost,
            savings_usd=0.0,
        )

        self._records.append(record)
        self._total_cloud_calls += 1
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens

        day_key = record.timestamp.strftime("%Y-%m-%d")
        if day_key not in self._daily_stats:
            self._daily_stats[day_key] = {
                "ollama_calls": 0, "cloud_calls": 0,
                "savings_usd": 0.0, "cloud_cost_usd": 0.0,
                "actual_cost_usd": 0.0, "total_tokens": 0,
            }
        ds = self._daily_stats[day_key]
        ds["cloud_calls"] += 1
        ds["cloud_cost_usd"] += cloud_cost
        ds["actual_cost_usd"] += cloud_cost
        ds["total_tokens"] += total_tokens

        self._persist_record(record)
        return record

    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo geral da economia"""
        total_calls = self._total_ollama_calls + self._total_cloud_calls
        total_cloud_cost_avoided = sum(r.estimated_cloud_cost_usd for r in self._records if "ollama" in r.provider)
        total_actual_cost = sum(r.actual_cost_usd for r in self._records)
        pct_savings = (self._total_savings_usd / total_cloud_cost_avoided * 100) if total_cloud_cost_avoided > 0 else 0

        return {
            "total_calls": total_calls,
            "ollama_calls": self._total_ollama_calls,
            "cloud_calls": self._total_cloud_calls,
            "ollama_ratio": f"{self._total_ollama_calls / total_calls * 100:.1f}%" if total_calls > 0 else "0%",
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            "prompt_tokens": self._total_prompt_tokens,
            "completion_tokens": self._total_completion_tokens,
            "total_savings_usd": round(self._total_savings_usd, 6),
            "total_cloud_cost_avoided_usd": round(total_cloud_cost_avoided, 6),
            "total_actual_cost_usd": round(total_actual_cost, 6),
            "savings_percent": f"{pct_savings:.1f}%",
            "uptime_hours": round((datetime.now() - self._start_time).total_seconds() / 3600, 2),
            "daily_stats": self._daily_stats,
        }

    def get_today_summary(self) -> Dict[str, Any]:
        """Retorna resumo do dia atual"""
        today = datetime.now().strftime("%Y-%m-%d")
        ds = self._daily_stats.get(today, {
            "ollama_calls": 0, "cloud_calls": 0,
            "savings_usd": 0.0, "cloud_cost_usd": 0.0,
            "actual_cost_usd": 0.0, "total_tokens": 0,
        })
        return {
            "date": today,
            **ds,
            "savings_brl": round(ds["savings_usd"] * 6.0, 4),  # USD→BRL ~6.0
        }

    def _persist_record(self, record: LLMCallRecord):
        """Persiste registro em JSONL (append-only)"""
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts": record.timestamp.isoformat(),
                "src": record.source,
                "model": record.model,
                "p_tok": record.prompt_tokens,
                "c_tok": record.completion_tokens,
                "provider": record.provider,
                "cloud_cost": record.estimated_cloud_cost_usd,
                "actual_cost": record.actual_cost_usd,
                "savings": record.savings_usd,
            }
            with open(self._persist_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # Não falhar por causa de persistência

    def reset(self):
        """Reset para testes"""
        self._records.clear()
        self._daily_stats.clear()
        self._total_savings_usd = 0.0
        self._total_ollama_calls = 0
        self._total_cloud_calls = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._start_time = datetime.now()


# Singleton global
_tracker_instance = None


def get_token_economy() -> TokenEconomyTracker:
    """Obtém instância singleton do tracker de economia"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = TokenEconomyTracker()
    return _tracker_instance
